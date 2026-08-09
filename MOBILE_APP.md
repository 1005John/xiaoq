# 小Q鸿蒙手机控制

鸿蒙端工程位于 `harmony/`，使用 ArkTS / ArkUI，包含四个页面：

- 对讲：文字消息会等待小Q返回文字并显示在手机上；对讲页可分别配置本机扬声器播报，以及是否附带一帧摄像头画面进行视觉问答。按住“按住说话”时，小Q使用自己的麦克风录音；松开后按与空格键相同的流程识别并回复。
- 会议：从手机选择录音上传，查看任务状态、历史纪要和 HTML 纪要结果。
- 遥控：查看局域网 MJPEG 视频，控制云台左右和上下，或恢复小Q自动模式。
- 设置：填写树莓派 IP 和设备令牌。

## 树莓派服务

`mobile_control.py` 是开机自启的 `xiaoq-mobile-control.service`，监听 `8788`。
它是手机唯一需要访问的服务；小Q内部 WebSocket 改为仅监听 `127.0.0.1:8766`，不再暴露给局域网。

服务令牌首次启动时保存在 `data/mobile_control_token`，权限为仅当前用户可读。将该文件内容填入 App 的设置页即可配对。令牌不可提交到仓库或通过公开渠道发送。

服务检查命令：

```bash
sudo systemctl status xiaoq-mobile-control
curl http://127.0.0.1:8788/health
```

## API

所有 `/api/*` 请求都需要请求头 `X-XiaoQ-Token`，视频流可使用 `?token=` 以兼容 Web 组件。

| 功能 | 接口 |
| --- | --- |
| 对讲文本 | `POST /api/chat`，JSON 可传 `speak: true/false`，同步返回 `reply` |
| 对讲视觉问答 | `POST /api/vision`，JSON 可传 `speak: true/false`，树莓派拍摄一帧 JPEG 后使用 `mimo-v2.5`，同步返回 `reply` |
| 对讲音频上传 | `POST /api/voice` |
| 会议上传 | `POST /api/meetings` |
| 会议列表 | `GET /api/meetings` |
| 会议任务状态 | `GET /api/meetings/jobs/{id}` |
| 云台控制 | `POST /api/gimbal` |
| 自动模式 | `POST /api/gimbal/release` |
| 视频页面 | `GET /api/camera` |

## 云台边界

手机控制的树莓派端与 App 端均限制为：Pan `75` 到 `105` 度，Tilt `138` 到 `162` 度。这正是已有表情云台映射的最大范围。手动控制会停止人脸追踪并在 30 秒无新命令后自动释放；也可在 App 点击“恢复自动”。

目前视频为第一期 MJPEG 实现。小Q在运行人脸追踪时，进入手机遥控会先释放追踪摄像头；第二期可以替换为共享采集管线和 WebRTC。

## 视觉问答

视觉开关只在手机对讲页生效。开启后每次发送文字都会请求树莓派当前画面，图片以 base64 方式发送到 `https://token-plan-cn.xiaomimimo.com/v1/chat/completions` 的 `mimo-v2.5` 模型；普通文字对讲仍使用小Q默认的 `mimo-v2.5-pro` 链路。视觉请求需要树莓派端已配置 `XIAOMI_MIMO_API_KEY`（兼容 Hermes 常用的 `XIAOMI_API_KEY`），或能从 Hermes 配置读取 MiMo 密钥。

视觉问答是单帧识别，不会持续上传视频。若摄像头被其他进程占用，手机会显示拍摄失败，需先释放摄像头或关闭占用摄像头的功能。
