#!/usr/bin/env python3
import os, sys, time, threading
from pathlib import Path

_HAILO_ROOT = os.path.expanduser('~/hailo-apps')
if _HAILO_ROOT not in sys.path:
    sys.path.insert(0, _HAILO_ROOT)
_parent = str(Path(_HAILO_ROOT).parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst
Gst.init(None)

import numpy as np
import pygame
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
    SCRFD_2_5G_POSTPROCESS_FUNCTION, HAILO8L_ARCH,
)

W, H = 640, 480
FPS = 15

_frame_lock = threading.Lock()
_frame_data = [None]
_det_lock = threading.Lock()
_detections = []
_cb_count = [0]
_sink_count = [0]

def _appsink_cb(sink, _):
    sample = sink.emit('pull-sample')
    if sample is None:
        return Gst.FlowReturn.ERROR
    buf = sample.get_buffer()
    caps = sample.get_caps()
    w = caps.get_structure(0).get_value('width')
    h = caps.get_structure(0).get_value('height')
    ok, info = buf.map(Gst.MapFlags.READ)
    if not ok:
        return Gst.FlowReturn.ERROR
    try:
        arr = np.frombuffer(info.data, dtype=np.uint8).reshape((h, w, 3))
        with _frame_lock:
            _frame_data[0] = arr.copy()
        _sink_count[0] += 1
    finally:
        buf.unmap(info)
    return Gst.FlowReturn.OK

def _inference_cb(element, buf, udata):
    global _detections
    _cb_count[0] += 1
    if buf is None:
        return
    try:
        roi = hailo.get_roi_from_buffer(buf)
        dets = roi.get_objects_typed(hailo.HAILO_DETECTION)
    except:
        return
    results = []
    for d in dets:
        if d.get_label() != 'face':
            continue
        b = d.get_bbox()
        results.append((b.xmin(), b.ymin(), b.xmax(), b.ymax(), d.get_confidence()))
    with _det_lock:
        _detections = results

class FaceDemoApp(GStreamerApp):
    def __init__(self):
        parser = get_pipeline_parser()
        parser.add_argument('--mode', default='run')
        configure_multi_model_hef_path(parser)
        handle_list_models_flag(parser, FACE_RECOGNITION_PIPELINE)
        parser.set_defaults(input='rpi', arch=None, show_fps=False,
                          width=W, height=H, frame_rate=FPS)
        super().__init__(parser, app_callback_class())
        self.user_data.running = True
        if self.arch == HAILO8L_ARCH:
            self.det_func = SCRFD_2_5G_POSTPROCESS_FUNCTION
        self.post_so = get_resource_path(
            pipeline_name=None, resource_type=RESOURCES_SO_DIR_NAME,
            arch=self.arch, model=FACE_DETECTION_POSTPROCESS_SO_FILENAME)
        models = resolve_hef_paths(
            hef_paths=self.options_menu.hef_path,
            app_name=FACE_RECOGNITION_PIPELINE, arch=self.arch)
        self.hef_det = models[0].path
        self.app_callback = _inference_cb
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
        return (f'{src} ! tee name=t '
                f't. ! queue ! {wrap} ! {trk} ! {cb} ! queue ! fakesink sync=false '
                f't. ! queue leaky=downstream ! videoconvert ! '
                f'video/x-raw,format=RGB,width={W},height={H} ! '
                f'appsink name=face_sink emit-signals=true sync=false max-buffers=1 drop=true')

def main():
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption('Hailo Face Detection (OV5647)')
    clock = pygame.time.Clock()
    fps_timer = time.time()
    fps_count = 0
    display_fps = 0
    font = pygame.font.SysFont(None, 28)

    print('[启动] 初始化 Hailo 管线...', flush=True)
    app = FaceDemoApp()
    sink = app.pipeline.get_by_name('face_sink')
    sink.connect('new-sample', _appsink_cb, None)
    t = threading.Thread(target=app.run, daemon=True)
    t.start()
    time.sleep(4)

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_q):
                running = False

        with _frame_lock:
            frame = _frame_data[0]
        if frame is None:
            clock.tick(10)
            continue

        with _det_lock:
            dets = list(_detections)

        # 1. 先画帧
        surface = pygame.surfarray.make_surface(np.rot90(frame))
        screen.blit(surface, (0, 0))

        # 2. 再画检测框 (叠在帧上面)
        for (x1, y1, x2, y2, conf) in dets:
            # 水平镜像修正
            mx1, mx2 = 1.0 - x2, 1.0 - x1
            px1, py1 = int(mx1*W), int(y1*H)
            px2, py2 = int(mx2*W), int(y2*H)
            pygame.draw.rect(screen, (0,255,0), (px1,py1,px2-px1,py2-py1), 2)
            lbl = font.render(f'face {conf:.0%}', True, (255,255,0))
            screen.blit(lbl, (px1, max(0, py1-22)))

        # 3. HUD
        hud = font.render(f'FPS:{display_fps:.0f} Faces:{len(dets)} CB:{_cb_count[0]}', True, (0,255,255))
        screen.blit(hud, (10, 10))

        pygame.display.flip()
        fps_count += 1
        if time.time() - fps_timer >= 1.0:
            display_fps = fps_count / (time.time() - fps_timer)
            fps_count = 0
            fps_timer = time.time()
        clock.tick(FPS)

    app.loop.quit()
    pygame.quit()

if __name__ == '__main__':
    main()
