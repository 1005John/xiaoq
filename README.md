# XiaoQ 智能助手 — 融合 MW 移动办公版

> 基于 Raspberry Pi 5 + Hailo-8L AI 处理器 + MobileWork Agent 的智能语音助手

## 更新日志

### 2026-10-09 v4
- **MW 模式统一配色**: 背景#F2F7FC、问题#3A75E5蓝色、回答#000000黑色、思考灰色
- **字体优化**: 问题和回答用 wqy-zenhei 黑体 38px，思考用 28px
- **右下角 MW 图标**: 替换小Q表情为 MW 图标，面积翻倍
- **修复换行**: 解析阶段用 _font_mw_bold 计算宽度，与渲染字体一致
- **修复 TTS**: MW 模式下文字消息也 TTS 播报（强制 speak=True）
- **修复全屏 SSL**: urllib 加 ssl.CERT_NONE 跳过证书验证
- **修复全屏 chat**: 恢复 _finish_direct_chat 调用
- **修复回复显示**: done 分支添加 reply 到 _chat_lines

### 2026-10-08 v3
- 修复回复重复显示、长回复看不到文字、文字超出屏幕宽度
- 修复蓝色字体、卡片清屏、滚动不准
- 修复 _pending 拦截语音、done 分支覆盖
- 公司网络直接 DNS 访问 onerouter

### 2026-10-07 v2.5
- 修复 segfault（禁用 HailoFace/picamera2）
- 子线程用 curl 子进程避免线程冲突
- PYTHONDONTWRITEBYTECODE=1

### 2026-10-03 v2
- MW 思考过程实时显示、自动上传 PPT、自动滚动

### 2026-10-02 v1
- 初始版本

## 已知限制

1. 人脸跟踪不可用（picamera2 segfault）
2. MW 交互式 question 会导致 XiaoQ 卡住
3. MW 云端模型响应慢（每步 2-3 分钟）
4. PC 文件接收服务需手动启动

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
