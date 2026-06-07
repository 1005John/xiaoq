# 变更日志

## [v1.3.1] - 2026-06-07

### 🔧 TTS 修复
- **去掉 PyAudio**：声卡重启后不支持 24000/44100Hz
- **改用 aplay + plughw**：保存 24000Hz WAV，aplay -D plughw:2,0 自动转码
- **按空格停止 TTS**：start_record 时 kill aplay 进程

### 📦 清理
- 删除本地人脸识别模型文件（YOLO/Haar/SSD/MediaPipe）
- 释放 ~200MB 磁盘空间
- 恢复干净 robot_face（去除 face_tracker/face_search/baidu_face 引用）

---

## [v1.3.0] - 2026-06-06

### 🧠 模型升级
- **LLM 升级**：MiMo-V2.5 → **MiMo-V2.5-Pro**（严格遵循指令格式）

### 🔧 待办系统
- **JSON 指令机制**：Hermes 回复末尾附带 JSON `{"action":"add","text":"..."}`，本地解析执行
- **SKILL.md 统一**：与 system prompt 一致，不再冲突
- **时间解析增强**：支持中文数字（晚上十一点十分、下午三点）
- 支持添加/完成/删除/查询/全部删除

### 🎤 交互优化
- **TTS 打断**：按空格设 `_tts_stop` 标志，32ms 块检查
- **voice_tts 同步调用**：解决线程不安全导致提醒无声
- **录音文件清理**：防止追加导致 12MB 大文件
- **麦克风设备**：改用声卡名防编号漂移

### 📦 基础设施
- **Hermes v0.15.1**：Gateway API Server（端口 8086）
- **模型**：MiMo-V2.5-Pro（LLM）+ MiMo-V2.5-ASR + MiMo-V2.5-TTS（冰糖）
- **Gateway**：仅保留 xiaomi provider

---

## [v1.2.0] - 2026-06-06

### 🧠 全链路 MiMo 化
- **LLM 切换**：deepseek-v4-flash → **MiMo-V2.5**（小米）
- **ASR 切换**：阿里云 paraformer → **MiMo-V2.5-ASR**
- **TTS 切换**：阿里云 qwen3-tts-flash → **MiMo-V2.5-TTS**（音色：冰糖）

### 🔧 待办系统重构
- **JSON 指令机制**：Hermes 回复中附带隐藏 JSON 指令，本地可靠执行
- 移除本地正则匹配，完全由 Hermes 判断意图
- 支持添加/完成/删除/查询操作
- System prompt 强制要求 JSON 格式

### 🎤 交互优化
- **TTS 打断**：按空格时停止 TTS 播放（32ms 块检查）
- **录音前清理**：防止音频文件追加导致 12MB 大文件
- **麦克风设备**：改用声卡名 `seeed2micvoicec`（防编号漂移）

### 📦 技能系统
- **新建 pi-news**：标准 Hermes SKILL.md，缓存读取
- **pi-weather 改为缓存**：不再实时调 API
- **pi-todo 重构**：JSON 指令驱动

### 🐛 修复
- 舵机时间 T800（T500 不响应）
- voice_tts 提醒同步调用（线程不安全导致无声）
- Gateway 路由修复（只保留 xiaomi provider）

---

## [v1.1.0] - 2026-06-06

### 🚀 性能优化
- **LLM 模型切换**：qwen3.6-plus → deepseek-v4-flash（响应 107s → 7s，14 倍加速）
- **Hermes 升级**：v0.11.0 → v0.15.1，支持 OpenAI 兼容 API Server
- **_call_hermes() 重构**：API Server 优先（端口 8086），CLI 子进程回退
- **API 密钥配置化**：从 `llm.json` / 环境变量读取，不再硬编码

### 📦 技能系统重构
- **天气改为缓存读取**：不再每次实时调 open-meteo API，读 `data/weather_cache.json`
- **新闻改为缓存读取**：不再让 Hermes 开浏览器搜索，读 `data/news_cache.json`
- **新建 pi-news 技能**：标准 Hermes SKILL.md 格式，`~/.hermes/skills/pi-news/`
- **pi-weather 改为缓存**：直接读 data_collector 后台采集的缓存
- **新闻/天气缓存源**：open-meteo.com（天气）、36kr/sspai/ithome 等 RSS（新闻）
- **data_collector**：每 1800 秒后台采集天气和新闻

### 🔧 硬件适配
- **舵机时间参数**：T500 → T800，修复小幅度运动不响应问题

### 📝 文档
- 补充 DESIGN.md / REQUIREMENTS.md / CHANGELOG.md

---

## [v1.0.0] - 2026-06-03

### 初始版本
- robot_face v11：霓虹赛博风格面部动画
- Hermes Agent 集成（hermes_wrapper.py）
- 语音流水线：ASR → 纠错 → Hermes → TTS
- MOA 聊天记录查询（pi-moa 技能）
- 邮件知识库查询（email-knowledge 技能）
- DeepSeek API 替代本地 LLM
- 回复文件传递机制（避免 stdout 污染）
- 卡片完整回复 + TTS 简短总结
