#!/usr/bin/env python3
"""
Hailo-8L 人脸检测后台管线 v4
复用 hailo-apps 验证过的 INFERENCE_PIPELINE_WRAPPER (cropper+aggregator),
1280x720 采集, 低帧率+nice 控 CPU。
"""

import os, sys, queue, threading, time, logging
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

# 加载 hailo-apps
_HAILO_ROOT = os.path.expanduser("~/hailo-apps")
if _HAILO_ROOT not in sys.path:
    sys.path.insert(0, _HAILO_ROOT)
_parent = str(Path(_HAILO_ROOT).parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst
import hailo

from hailo_apps.python.core.common.core import (
    get_pipeline_parser, get_resource_path,
    handle_list_models_flag, configure_multi_model_hef_path, resolve_hef_paths,
)
from hailo_apps.python.core.gstreamer.gstreamer_app import GStreamerApp, app_callback_class
from hailo_apps.python.core.gstreamer.gstreamer_helper_pipelines import (
    INFERENCE_PIPELINE, INFERENCE_PIPELINE_WRAPPER,
    TRACKER_PIPELINE, USER_CALLBACK_PIPELINE,
)
from hailo_apps.python.core.common.defines import (
    RESOURCES_SO_DIR_NAME, FACE_RECOGNITION_PIPELINE,
    FACE_DETECTION_POSTPROCESS_SO_FILENAME,
    FACE_DETECTION_JSON_NAME, RESOURCES_JSON_DIR_NAME,
    SCRFD_10G_POSTPROCESS_FUNCTION, SCRFD_2_5G_POSTPROCESS_FUNCTION,
    HAILO8_ARCH, HAILO10H_ARCH, HAILO8L_ARCH,
)

log = logging.getLogger("hailo_face")

W, H = 1280, 720
FPS = 10  # 采集帧率 (低帧率+跳帧控 CPU, 不影响检测效果)


@dataclass
class FaceDetection:
    track_id: int
    bbox: tuple
    confidence: float
    label: str = "face"
    timestamp: float = field(default_factory=time.time)


class _CallbackData(app_callback_class):
    def __init__(self, q):
        super().__init__()
        self.q = q


class _HeadlessApp(GStreamerApp):
    """基于 hailo-apps GStreamerApp 的检测管线"""

    def __init__(self, cb_fn, user_data, parser=None):
        if parser is None:
            parser = get_pipeline_parser()
        parser.add_argument("--mode", default='run')
        configure_multi_model_hef_path(parser)
        handle_list_models_flag(parser, FACE_RECOGNITION_PIPELINE)
        parser.set_defaults(input="rpi", arch=None, show_fps=False,
                          width=W, height=H, frame_rate=FPS)
        super().__init__(parser, user_data)

        if self.arch in (HAILO8_ARCH, HAILO10H_ARCH):
            self.det_func = SCRFD_10G_POSTPROCESS_FUNCTION
        elif self.arch == HAILO8L_ARCH:
            self.det_func = SCRFD_2_5G_POSTPROCESS_FUNCTION

        self.post_so = get_resource_path(
            pipeline_name=None, resource_type=RESOURCES_SO_DIR_NAME,
            arch=self.arch, model=FACE_DETECTION_POSTPROCESS_SO_FILENAME)

        models = resolve_hef_paths(
            hef_paths=self.options_menu.hef_path,
            app_name=FACE_RECOGNITION_PIPELINE, arch=self.arch)
        self.hef_det = models[0].path

        self.app_callback = cb_fn
        self.create_pipeline()

    def get_pipeline_string(self):
        src = self.get_source_pipeline()
        det = INFERENCE_PIPELINE(
            hef_path=self.hef_det, post_process_so=self.post_so,
            post_function_name=self.det_func, batch_size=1,
            config_json=get_resource_path(
                pipeline_name=None, resource_type=RESOURCES_JSON_DIR_NAME,
                arch=self.arch, model=FACE_DETECTION_JSON_NAME))
        wrap = INFERENCE_PIPELINE_WRAPPER(det)
        trk = TRACKER_PIPELINE(class_id=-1, kalman_dist_thr=0.7, iou_thr=0.8,
                               init_iou_thr=0.9, keep_new_frames=2,
                               keep_tracked_frames=6, keep_lost_frames=8,
                               keep_past_metadata=True, name='face_trk')
        cb = USER_CALLBACK_PIPELINE()
        return f'{src} ! {wrap} ! {trk} ! {cb} ! queue ! fakesink sync=false'

    def run(self):
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.bus_call, self.loop)
        self._connect_callback()
        from hailo_apps.python.core.gstreamer.gstreamer_common import disable_qos
        disable_qos(self.pipeline)

        if self.source_type == "rpi":
            from hailo_apps.python.core.gstreamer.gstreamer_app import picamera_thread
            t = threading.Thread(target=picamera_thread,
                args=(self.pipeline, self.video_width, self.video_height,
                      self.video_format), daemon=True)
            self.threads.append(t)
            t.start()

        self.pipeline.set_state(Gst.State.PAUSED)
        self.pipeline.set_latency(self.pipeline_latency * Gst.MSECOND)
        self.pipeline.set_state(Gst.State.PLAYING)
        self.loop.run()

        try:
            self.user_data.running = False
            self.pipeline.set_state(Gst.State.NULL)
            for t in self.threads:
                t.join(timeout=2)
        except Exception:
            pass


def _callback(element, buf, udata: _CallbackData):
    if buf is None:
        return
    try:
        roi = hailo.get_roi_from_buffer(buf)
        dets = roi.get_objects_typed(hailo.HAILO_DETECTION)
    except Exception:
        return
    results = []
    for d in dets:
        if d.get_label() != "face":
            continue
        b = d.get_bbox()
        tid = 0
        trk = d.get_objects_typed(hailo.HAILO_UNIQUE_ID)
        if trk:
            tid = trk[0].get_id()
        results.append(FaceDetection(
            track_id=tid,
            bbox=(b.xmin(), b.ymin(), b.xmax(), b.ymax()),
            confidence=d.get_confidence()))
    if results:
        q = udata.q
        while not q.empty():
            try:
                q.get_nowait()
            except queue.Empty:
                break
        try:
            q.put_nowait(results)
        except queue.Full:
            pass


class HailoFacePipeline:
    def __init__(self, q: queue.Queue):
        self.q = q
        self._app = None
        self._thread = None
        self._running = False

    def start(self):
        if self._running:
            return
        udata = _CallbackData(self.q)
        parser = get_pipeline_parser()
        self._app = _HeadlessApp(_callback, udata, parser=parser)
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="hf")
        self._thread.start()

    def _run(self):
        os.nice(12)
        log.info("pipeline starting (1280x720, %dfps, nice 12)", FPS)
        self._app.run()

    def stop(self):
        self._running = False
        if self._app and self._app.loop:
            self._app.loop.quit()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
