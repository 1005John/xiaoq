# XiaoQ 智能助手 — 融合 MW 移动办公版

> 基于 Raspberry Pi 5 + Hailo-8L AI 处理器 + MobileWork Agent 的智能语音助手

## 更新日志

### 2026-10-14 方案2版（当前版本）
- **MW 模式霓虹表情**: 进入移动办公后显示霓虹型表情（不再用 GIF 动图）
- **MW 配色**: 背景 #0047BB 蓝色，眼睛统一 #E8F8F5 浅青色（不分层）
- **MW 纯色眼睛**: _draw_neon_eye 在 MW 模式下直接画纯色椭圆，跳过所有渐变层
- **退出 MW 恢复**: 退出移动办公时显式恢复 PUPIL_COLOR/PUPIL_HIGHLIGHT/BG_COLOR
- **摄像头子进程方案**: camera_worker.py + camera_proxy.py 隔离 picamera2
- **人脸检测成功**: HailoFace 在子进程正常运行，输出 face_detected 事件
- **云台平滑跟踪**: 死区 8%（小幅度不移动），25% 平滑插值（避免振荡）
- **人脸授权恢复**: process_voice 里的 _face_authorized_for_dialogue() 已恢复
- **_pending 修复**: finally 块恢复 self._pending = False
- **_finish_face_authorization_failure 修复**: 末尾加 self._pending = False
- **card_show 禁用**: 不再弹卡片导致 TTS 被停止
- **ASR SSL 修复**: _asr_transcribe 加 ssl.CERT_NONE
- **idle timeout 不停止摄像头**: 修改跟踪逻辑，sleep 状态不停止子进程
- **_locked_track_id 清除**: select_active 时清除，避免切换人脸后仍跟踪旧目标
- **camera_worker XIAOQ_ROOT**: 子进程用正确路径访问 face_registry.json
- **人脸同步**: face_target_select/face_register/face_delete 同步到 camera_worker

### 2026-10-10 方案1版
- MW 模式 GIF 动图（已替换为霓虹表情）
- MW 配色 + 字体 + 右下角 MW 图标

### 2026-10-09 v4
- MW 配色、字体优化、换行修复、TTS/SSL 修复

### 2026-10-08 v3
- 修复回复重复显示、长回复看不到文字

### 2026-10-07 v2.5
- 修复 segfault（禁用 HailoFace/picamera2）

### 2026-10-02 v1
- 初始版本

## 已知限制

1. MW 交互式 question 会导致 XiaoQ 卡住
2. MW 云端模型响应慢
3. PC 文件接收服务需手动启动
4. JEV API 451 错误（不影响 LLM fallback）

## 摄像头子进程方案

picamera2 + GStreamer 在主进程（pygame + TTS 线程）里会导致 segfault。
解决方案：用独立子进程运行 HailoFace。

```
XiaoQ 主进程
  ↓ JSON 行协议（stdin/stdout）
camera_worker.py（子进程）
  ↓ picamera2 + GStreamer + Hailo
MW 云端模型
```

### 文件

| 文件 | 说明 |
|------|------|
| camera_worker.py | 子进程，运行 HailoFace，JSON 行协议通信 |
| camera_proxy.py | 主进程代理，管理子进程 + 云台跟踪 |
| hailo_face.py | HailoFace 封装（人脸检测+跟踪+ArcFace） |
| hailo_face_pipeline.py | GStreamer 管线 |
| face_identity.py | 人脸注册表（ArcFace embedding） |

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
