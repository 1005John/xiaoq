# XiaoQ 智能助手 — 融合 MW 移动办公版

> 基于 Raspberry Pi 5 + Hailo-8L AI 处理器 + MobileWork Agent 的智能语音助手

## 更新日志

### 2026-10-03 v2
- **MW 思考过程实时显示**: 修复 reasoning/text 为空时不记录 rowid，确保后续轮询重新获取有内容的 parts
- **自动上传 PPT 到 PC**: MW 完成任务后自动检测 .pptx 文件并 curl 上传到 `D:\XiaoQ_Share`
- **MW 无超时**: `while True` 无限等待直到 MW 完成
- **自动滚动**: 文字占满屏幕后自动滚到最下方，最后一条用户消息始终可见
- **行距 2 倍**: 字体 32px，行高 64px
- **配色优化**: 元气型用户消息用腮红色(193,77,51)，回复用黑色(40,35,30)
- **_pending 排队**: MW 模式下消息排队，避免并发冲突
- **segfault 修复**: hailo_face_pipeline.py 的 stop() 加 try/except + join timeout=2
- **人脸授权跳过**: 禁用自动人脸跟踪(XIAOQ_AUTO_FACE_TRACKING=0)，跳过 face_authorized 检查
- **Gateway reply 修复**: 从 DB 获取最终 text part 作为回复，不依赖 SSE 事件
- **PC 文件接收服务**: xiaoq_share_server.py 运行在 PC port 9998
- **系统提示词**: MW prompt 自动追加文件上传指令

### 2026-10-02 v1
- 初始版本：全屏表情 + MW 移动办公双模式
- Hailo 人脸检测 + 云台跟踪
- ASR/TTS/LLM 管线
- 技能系统(todo/weather/news/email/module_test)
- MW Gateway (port 9800)
- 完整部署文档

## 功能概览

### 全屏表情模式（默认）
- 语音交互: ASR → 意图识别 → 技能/LLM → TTS
- 文字交互: 手机输入 → 意图识别 → 技能/LLM → TTS
- 表情系统: 霓虹赛博风 / 元气活力风（F2 切换）

### MW 移动办公模式
- 进入: "进入移动办公" / 退出: "退出移动办公"
- 聊天界面: 表情右下角 + Markdown 文字
- 实时显示: 思考过程(灰色) + 步骤 + 回复(白色)
- 自动上传: PPT/文件生成后自动传到 PC `D:\XiaoQ_Share`
- 无超时: 等待 MW 完成才返回

## 全新部署指南

详见 [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)

## 架构设计

详见 [docs/DESIGN.md](docs/DESIGN.md)

## PC 端文件接收服务

```bash
python xiaoq_share_server.py
# 运行在 http://0.0.0.0:9998
# 文件保存到 D:\XiaoQ_Share
```

## systemd 服务

| 服务 | 端口 | 说明 |
|------|------|------|
| xiaoq-face-auth-demo | 8766 (WS) | XiaoQ 主程序 |
| xiaoq-mobile-control | 8788 (HTTP) | 手机 App API |
| mw-gateway | 9800 (HTTP) | MW Agent Gateway |
| mobilework | 动态 | MW 桌面应用 |

## 已知限制

1. picamera2 与 Hailo GStreamer 管线冲突 → segfault（已用 try/except + timeout 规避）
2. MW 安全策略可能拦截 curl 命令（需在 MW 设置里关闭拦截）
3. MW 端口每次重启可能变化（Gateway 从配置文件自动读取）
4. 网络依赖 PC VPN 转发（hosts + socat + portproxy）
5. 人脸跟踪已禁用（XIAOQ_AUTO_FACE_TRACKING=0），避免 segfault
