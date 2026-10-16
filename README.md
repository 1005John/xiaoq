# XiaoQ 智能助手 — 融合 MW 移动办公版

> 基于 Raspberry Pi 5 + Hailo-8L AI 处理器 + MobileWork Agent 的智能语音助手

## 更新日志

### 2026-10-16 方案3版（当前版本）
- **Bluebot 表情系统**: 集成协作者的 Bluebot 表情（vendor/hardware_expression_system/）
- **MW 滚动文字**: 单行显示，思考灰色速度6，回复#E8F8F5速度6，回复出现后切换
- **TTS 子线程**: _finish_direct_chat 里 TTS 改成子线程，不阻塞主循环
- **画面不累计**: 用专用 _bb_surface 每帧清屏
- **退出 MW 修复**: 直接关闭 Bluebot + TTS 子线程
- **MW 状态映射**: 9个状态对接（WAITING_INPUT/PLANNING/EXPERT_ROUTING/TOOL_RUNNING/FILE_GENERATING/WAITING_CONFIRMATION/COMPLETED/FAILED/BLOCKED）
- **摄像头子进程**: camera_worker.py + camera_proxy.py 隔离 picamera2
- **人脸跟踪**: 死区8% + 25%平滑插值
- **人脸授权恢复**: process_voice 检查
- **_locked_track_id 清除**: 切换人脸时清除
- **ASR SSL 修复**: ssl.CERT_NONE
- **PPT 自动上传**: MW 完成后自动上传到 PC
- **onerouter 直连**: MW 模型切换到 onerouter，速度提升

### 2026-10-10 方案2版
- MW 霓虹表情（已替换为 Bluebot）

### 2026-10-09 v4
- MW 配色、字体、换行修复

### 2026-10-02 v1
- 初始版本

## 架构

```
XiaoQ 主进程
  ├─ Bluebot 表情（vendor/hardware_expression_system/）
  ├─ MW 滚动文字（思考+回复）
  ├─ TTS 子线程（不阻塞画面）
  ├─ camera_proxy.py → camera_worker.py（子进程）
  │    └─ HailoFace + picamera2 + GStreamer
  └─ MW Gateway (port 9800) → MW (port 35615)
```

## 文件说明

| 文件 | 说明 |
|------|------|
| robot_face_v11_fc245e4.py | 主程序 |
| camera_worker.py | 摄像头子进程（HailoFace） |
| camera_proxy.py | 主进程代理（子进程管理+云台跟踪） |
| bluebot_integration.py | Bluebot 表情开关 |
| vendor/hardware_expression_system/ | 独立表情系统（不可修改） |
| hailo_face.py | 人脸检测+跟踪+ArcFace |
| hailo_face_pipeline.py | GStreamer 管线 |
| face_identity.py | 人脸注册表 |
| mw_gateway.py | MW Gateway (port 9800) |

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

## 已知限制

1. MW 交互式 question 会导致 XiaoQ 卡住
2. MW cmit 模板可能需要重新配置
3. PC 文件接收服务需手动启动
4. 人脸跟踪子进程偶尔不稳定
