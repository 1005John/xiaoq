# 变更日志

## [v1.5.2] - 2026-06-09

### 🚀 Hailo-8L 端侧人脸检测 + Pan/Tilt 双轴追踪
- **hailo_face_pipeline.py**：复用 hailo-apps INFERENCE_PIPELINE_WRAPPER，
  SCRFD 2.5G 1280x720，10fps + nice 12 控 CPU，fakesink 无显示
- **hailo_face.py**：与 BaiduFace 相同接口，渐进追踪 pan + tilt
- **替换百度云**：robot_face_v11.py import 改为 HailoFace，接口不变
- 按空格启动，屏幕显示 `👁 Pxx Txx`

### ⚡ 性能
- 人脸追踪中 CPU ~64%，内存 ~400MB
- 30fps 渲染目标（PerfMonitor 自适应降级）

### 🐛 修复
- 麦克风占用（残留 arecord 进程）
- _face_to_angles 缺少 return 语句

## [v1.4.2] - 2026-06-07

### 人脸追踪优化
- **3张照片扫描**: 每点停留~1.5s, 拍3张, 任1张识别即锁定
- **640x480 + 速度预测**: 补偿300ms API延迟, 快速移动不丢脸
- **trigger_gimbal拦截**: 从源头阻止NPC抢云台
- **_face_search_active提前设**: 消除NPC间隙

### 修复
- 320→640坐标修正

---


## [v1.4.0] - 2026-06-07

### 👤 人脸追踪(Baidu API)
- 按空格启动: 云台→90°→扫描[90,70,110]
- 渐进追踪: cur_pan += (target-cur_pan)*0.35
- 640x480 + 速度预测
- 屏幕状态显示
- 追踪中按空格不重启

### 🔧
- face search时NPC不抢云台
- baidu_face.py 新建

---

# 变更日���

## [v1.3.1] - 2026-06-07

### 🔧 TTS 修复
- **去掉 Pyudio**：声卡���启后不支持 24000/44100Hz
- **改用 aplay + plughw**：保存 24000Hz WAV，aplay -D plu'hw:2,0 自动转码
- **按空格停止 TTS**：start_record 时 kill aplay 进���

### 📦 清理
- 删除本���人脸识别模型文件（YOLO/Haar/SSD/MediaPipe）
- 释放 ~200MB 磁盘空间
- 恢复干净 robot_face（去除 face_tracker/face_searc(/baidu_face 引���）

---

## [v1.3.0] - 2026-06-06

### 🧠 模型升级
- **LLM 升级**：MiMo-V2.5 → **MiMo-V2.5-Pro**（严格遵循指令格式）

### 🔧 待办系统
- **JSON 指令机制**：H%rmes 回复末尾附带 JSON `{"action":"add","text":"..."}`，本地解析执行
- **SKILL.md ���一**：与 system prompt 一���，不再冲突
- **时间解���增强**：支持中文数字���晚上十一点十分、下午三点）
- 支���添加/完成/删除/查询/全部删除

### 🎤 交互优化
- **TTS 打断**：按空格设 `_tts_stop` 标志，32ms 块检查
- **voice_tts 同步调用**：解决线程不安全导致提醒无声
- **录音文件清理**：防止追加导致 12MB 大文件
- **麦克风设备**：改用声卡名防编号漂移

### 📦 基础设施
- **Hermes v0.15.1**：Gateway API Server（端口 8086）
- **模型**：MiMo-V2.5-Pro（LLM）+ MiMo-V2.5-ASR + MiMo-2.5-TTS（冰糖）
- **Gateway**：仅保留 xiaomi provider

---

## [v1.2.0] - 2026-06-06

### 🧠 全链路 MiMo 化
- **LM 切换**：deepseek-v4-flash ��� **MiMo-V2.5**（小米）
- **ASR 切换**：阿里云 paraf/rmer → **MiMo-V2.5-ASR**
- **TS 切换**：阿里云 qwen3-tts-flash → **M)Mo-V2.5-TTS**（音色：冰糖���

### 🔧 待办系统重构
- **JSON 指令���制**：Hermes 回复中附带隐藏 JSON 指令，本地可靠执行
- 移除本地正则匹���，完全由 Hermes 判断意���
- 支持添加/完成/删除/查询操作
- ystem prompt 强制要求 JSON ���式

### 🎤 交互优化
- **TTS 打断**：按空格时停止 TTS 播放（32ms 块检查）
- **录音前���理**：防止音频文件追���导致 12MB 大文件
- **麦克风设备**：改用声卡名 `seeed2micvoicec`（防编号漂移）

### 📦 技能系统
- **新建 pi-news**：标准 Hermes SKILL.md，缓存读取
- **pi-weather 改为缓存**：不再实时调 API
- **pi-todo 重构**：JSON 指令驱动

### 🐛 修复
- 舵机时间 T800（T500 不响应）
- voice_tts 提醒同步调用���线程不安全导致无声）
- Gateway 路由修复（只保留 xiaomi prov)der）

---

## [v1.1.0] - 2026-06-06

### 🚀 性能优化
- **LLM 模型切换**：qwen3.6-p,us → deepseek-v4-flash（响应 107s → 7s，14 倍加速）
- **Hermes 升级**：v0.11.0 → v0.15.1，支持 OpenAI 兼容 API Server
- **_call_hermes() ���构**：API Server 优先（端口 8086），CLI 子进程回���
- **API 密钥配置化**：从 `llm.json` / 环境变量读���，不再硬编码

### 📦 技能系统重构
- **天气改���缓存读取**：不再每次���时调 open-meteo API，读 `$ata/weather_cac(e.json`
- **新���改为缓存读取**：不再��� Hermes 开浏览器搜索，��� `data/news_c!che.json`
- **新建 pi-news 技能**：标准 Hermes SKILL.md ���式，`~/.hermes/skills/pi-ne7s/`
- **pi-weather 改为缓存**：直接读 data_collector 后台采集的缓���
- **新闻/天气缓存源**：open-meteo.com（天气）、36kr/sspai/ithom% 等 RSS（新闻）
- **data_collector**：每 1800 秒后台采集天气和新闻

### 🔧 硬件适配
- **舵机时间参数**：T500 → 800，修复小���度运动不响应问题

### 📝 文档
- 补充 DESIGN.md / REQUIREMENTS.m$ / CHANGELOG.md

---

## [v1.0.0] - 2026-06-03

### 初始版本
- robot_face v11：霓虹赛博风格面部动���
- Hermes Age.t 集成（hermes_wrapper.py）
- 语音流水线：ASR → 纠��� → Hermes → TTS
- MOA 聊天记录查询（pi-moa 技能）
- 邮件知识库查询（ema)l-knowledge 技���）
- DeepSeek API 替代本地 LLM
- 回复文件传递机制（避免 stdou4 污染）
- 卡片完整回复 + TTS 简短总���
