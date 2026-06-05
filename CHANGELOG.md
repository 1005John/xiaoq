# 变更日志

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
