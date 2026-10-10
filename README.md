# XiaoQ 智能助手 — 融合 MW 移动办公版

> 基于 Raspberry Pi 5 + Hailo-8L AI 处理器 + MobileWork Agent 的智能语音助手

## 更新日志

### 2026-10-10 方案1版（当前版本）
- **MW 模式显示 GIF 动图**: 进入移动办公后全屏循环播放 GIF 动画（480x480, 181帧），不再显示文字聊天界面
- **ASR/TTS 后台运行**: MW 模式下语音识别和 TTS 播报在后台工作，不显示文字
- **PIL 加载 GIF**: 使用 PIL 逐帧加载 GIF 转 pygame Surface
- **GIF 缩放**: 720x720 居中显示（适配 1280x720 屏幕）
- 摄像头/人脸跟踪不可用（picamera2 segfault 待解决）

### 2026-10-09 v4
- MW 模式统一配色（背景#F2F7FC、问题蓝色、回答黑色、思考灰色）
- 字体优化（wqy-zenhei 黑体 38px）
- 右下角 MW 图标替换
- 修复换行、TTS、SSL、回复显示

### 2026-10-08 v3
- 修复回复重复显示、长回复看不到文字、文字超出屏幕宽度
- 公司网络直接 DNS 访问 onerouter

### 2026-10-07 v2.5
- 修复 segfault（禁用 HailoFace/picamera2）
- 子线程用 curl 子进程避免线程冲突

### 2026-10-03 v2
- MW 思考过程实时显示、自动上传 PPT

### 2026-10-02 v1
- 初始版本

## 已知限制

1. **摄像头/人脸跟踪不可用** — picamera2 + GStreamer 线程冲突导致 segfault，待解决
2. MW 交互式 question 会导致 XiaoQ 卡住
3. MW 云端模型响应慢（每步 2-3 分钟）
4. PC 文件接收服务需手动启动

## 待解决问题：摄像头 segfault

**根本原因**: picamera2 线程（hailo_face_pipeline.py）与子线程/TTS 的 GStreamer 管线冲突
**影响**: 拍照、视觉问答、人脸跟踪、人脸授权均不可用
**待尝试方案**:
- 方案A: 完全移除 picamera2，用 OpenCV VideoCapture 替代
- 方案B: 只在需要时启动摄像头，用独立进程隔离
- 方案C: 修改 HailoFace 代码，不使用 GStreamer

## 部署

详见 [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)

## systemd 服务

| 服务 | 端口 | 说明 |
|------|------|------|
| xiaoq-face-auth-demo | 8766 (WS) | XiaoQ 主程序 |
| xiaoq-mobile-control | 8788 (HTTP) | 手机 App API |
| mw-gateway | 9800 (HTTP) | MW Agent Gateway |
| mobilework | 动态 | MW 桌面应用 |

## API 配置

| 服务 | URL | Key |
|------|-----|-----|
| LLM (onerouter) | https://onerouter.cmaiot.cn/v1 | tok_3Bgj8JoAIJEEHDMyh2eZzBUwxNpIQ4g5OBBQzciD |
| ASR/TTS (MiMo) | https://token-plan-cn.xiaomimimo.com/v1 | tp-cg4w819k5f30ewaet1usa9nq4grhzddidqsney3sstdnhhp0 |
| MW Gateway | http://127.0.0.1:9800 | 本地 |
