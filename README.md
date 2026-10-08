# XiaoQ 智能助手 — 融合 MW 移动办公版

> 基于 Raspberry Pi 5 + Hailo-8L AI 处理器 + MobileWork Agent 的智能语音助手

## 更新日志

### 2026-10-08 v3
- **修复回复重复显示**: done 分支不再添加 reply 到 _chat_lines（progress 轮询时已添加）
- **修复长回复看不到文字**: progress 轮询时不覆盖 _chat_lines[-1]（直接 append 新条目）
- **修复文字超出屏幕宽度**: text 渲染分支加 _wrap_text_md 自动换行
- **修复蓝色字体**: 删除被 sed 误覆盖的 _C_TEXT = 蓝色定义行
- **修复卡片清屏**: MW 模式下不弹 card_show 卡片
- **修复滚动不准**: 从后往前计算每个 item 的实际行数（含换行）
- **修复 _pending 拦截语音**: MW 分支设 _pending = True，主线程消费时清除
- **修复 done 分支覆盖**: 移除 done 分支的 progress 获取（避免覆盖中间输出）
- **修复人脸授权拦截**: process_voice 里跳过 _face_authorized_for_dialogue 检查
- **公司网络支持**: 不需要 VPN/socat，直接 DNS 访问 onerouter
- **text 渲染加换行**: 长文字自动换行不超出屏幕
- **统一字体颜色**: 所有输出文字用 _C_TEXT（白色/黑色），不区分标题

### 2026-10-07 v2.5
- **修复 segfault**: 从 SD1 恢复原始代码 + 禁用 HailoFace/picamera2
- **子线程用 curl 子进程**: 避免 urllib 跟 picamera2 线程冲突
- **_pending_mw_reply 主线程消费**: TTS 在主线程调用
- **PYTHONDONTWRITEBYTECODE=1**: 禁止 .pyc 缓存
- **Gateway get_latest_reply 修复**: 跳过 compaction 摘要
- **Gateway 提交新 prompt 时清空 reply**

### 2026-10-03 v2
- MW 思考过程实时显示
- 自动上传 PPT 到 PC D:\XiaoQ_Share
- MW 无超时（while True）
- 自动滚动到最下方
- 行距 2 倍，字体 32px
- 元气型用户消息用腮红色
- segfault 修复: hailo_face_pipeline stop() try/except
- 人脸授权跳过
- PC 文件接收服务 (port 9998)

### 2026-10-02 v1
- 初始版本：全屏表情 + MW 移动办公双模式
- Hailo 人脸检测 + 云台跟踪
- ASR/TTS/LLM 管线
- 技能系统(todo/weather/news/email/module_test)
- MW Gateway (port 9800)
- 完整部署文档

## 已知限制（当前版本）

1. **人脸跟踪不可用** — HailoFace/picamera2 禁用（segfault），需要解决 GStreamer 管线冲突
2. **摄像头/视觉问答不可用** — picamera2 未启动
3. MW 回复里的 `#` 标题不区分颜色（统一用输出颜色）
4. MW 模式下思考过程不 TTS（只显示文字），最终回复才 TTS
5. MW 安全策略可能拦截 curl 命令（需在 MW 设置里关闭拦截）

## 全新部署指南

详见 [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)

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

## API 配置

| 服务 | URL | Key |
|------|-----|-----|
| LLM (onerouter) | https://onerouter.cmaiot.cn/v1 | tok_3Bgj8JoAIJEEHDMyh2eZzBUwxNpIQ4g5OBBQzciD |
| ASR/TTS (MiMo) | https://token-plan-cn.xiaomimimo.com/v1 | tp-cg4w819k5f30ewaet1usa9nq4grhzddidqsney3sstdnhhp0 |
| MW Gateway | http://127.0.0.1:9800 | 本地 |
