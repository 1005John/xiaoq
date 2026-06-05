# 小Q — 系统设计

> 版本：v1.1 | 日期：2026-06-06

## 1. 架构概览

```
┌──────────────────────────────────────────────────────────────┐
│                      robot_face_v11.py                        │
│                                                               │
│  ┌─────────┐  ┌──────────┐  ┌──────────────────┐            │
│  │ pygame  │  │ State    │  │ NPCStateMachine  │            │
│  │ 渲染    │  │ Machine  │  │ (行为/人格)       │            │
│  └─────────┘  └──────────┘  └──────────────────┘            │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐    │
│  │ 语音流水线（process_voice）                            │    │
│  │ 麦克风 → WAV → ASR(阿里云) → 人名纠错×2               │    │
│  │   → _call_hermes() → 卡片显示 + TTS 播放              │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                               │
│  ┌─────────┐  ┌──────────┐  ┌────────────────┐              │
│  │ Gimbal  │  │ VFX      │  │ Ambient        │              │
│  │ 云台控制 │  │ 粒子特效  │  │ 环境动画        │              │
│  └─────────┘  └──────────┘  └────────────────┘              │
└──────────────────────────────────────────────────────────────┘
         │                    │
         ▼                    ▼
┌──────────────────┐  ┌──────────────────────┐
│ Hermes v0.15.1   │  │ 外部服务               │
│                  │  │ • DeepSeek v4-flash   │
│ _call_hermes():  │  │ • 阿里云 ASR/TTS      │
│  1. API Server   │  │ • open-meteo.com(天气) │
│     :8086 (优先) │  │ • RSS 源(新闻)         │
│  2. CLI 子进程   │  │ • data_collector(缓存) │
│     (回退)       │  └──────────────────────┘
│                  │
│ Hermes Skills:   │
│ • pi-weather ──┐ │
│ • pi-news      │ │
│ • pi-todo      │ │  数据流：后台采集 → JSON 缓存
│ • pi-moa       │ │         → skill query.py → Hermes → 回复
│ • pi-email     │ │
│ • pi-bug ──────┘ │
└──────────────────┘
```

## 2. 语音流水线（v1.1）

```
麦克风录音 → WAV 文件（16kHz mono）
  → 阿里云 ASR (paraformer-realtime-v2)
  → 人名纠错 ×2 (skills/name_corrector.py, 100人/734条)
  → _call_hermes(txt)
     ├── [优先] POST http://127.0.0.1:8086/v1/chat/completions
     │          Authorization: Bearer local-secret-2026
     │          model: deepseek-v4-flash
     │          → Hermes Gateway 常驻处理（无冷启动）
     │
     └── [回退] hermes chat -q --provider deepseek
                → CLI 子进程（有冷启动 ~5s）
  → Hermes 匹配 skill → 运行 query.py → 读缓存 JSON
     ├── weather: data/weather_cache.json
     ├── news:    data/news_cache.json
     ├── todo:    skills 内部 JSON
     ├── moa:     ~/moa_chats/export/ SQLite
     ├── email:   ~/email-knowledge/data/ SQLite
     └── 其他:    LLM 直接回复
  → 卡片显示（完整回复，WebSocket 推送）
  → TTS 摘要（>40 字时 qwen-turbo 压缩至 20 字内）
  → qwen3-tts-flash 流式合成 → PyAudio 播放
```

## 3. 数据缓存架构

```
┌─────────────────┐
│  data_collector  │  每 1800s 后台采集
│  (后台线程)       │
├─────────────────┤
│ 天气缓存          │  open-meteo.com API
│ weather_cache    │  → JSON: {temp, humidity, wind, forecast[5]}
│ .json            │
├─────────────────┤
│ 新闻缓存          │  RSS: 36kr, sspai, ithome 等
│ news_cache       │  → JSON: [{title, summary}, ...]
│ .json            │
└─────────────────┘
         │
         ▼ 读取（Hermes skill query.py）
┌─────────────────┐
│  Hermes Agent    │
│  → pi-weather    │  python3 ~/.hermes/skills/pi-weather/query.py
│  → pi-news       │  python3 ~/.hermes/skills/pi-news/query.py
└─────────────────┘
```

## 4. 表情与舵机映射

| 表情 | 水平(pan) | 垂直(tilt) | 说明 |
|------|:---:|:---:|------|
| idle | 90° | 150° | 默认正中 |
| look_left | 100° | 150° | 左看 |
| look_right | 80° | 150° | 右看 |
| look_up | 90° | 138° | 上看 |
| curious | 105° | 146° | 好奇歪头 |
| thinking | 75° | 150° | 思考 |
| sleepy | 90° | 162° | 低头闭眼 |
| surprised | 90° | 138° | 抬头惊讶 |
| happy/smile | 90° | 150° | 正面微笑 |

- 通信协议：`#<ID>P<位置>T<时间>!`，串口 `/dev/ttyAMA4` 115200 baud
- 位置范围：500~2500（对应 0~180°）
- 时间参数：T800（800ms），blocking=False

## 5. 关键决策

| 决策 | 原因 |
|------|------|
| Hermes 子进程 + API Server 双模式 | 无冷启动优先，CLI 作为回退 |
| deepseek-v4-flash 替代 qwen3.6-plus | 响应 107s→7s，14 倍加速 |
| 天气/新闻改为缓存读 | 避免每次实时 API 调用，响应稳定快速 |
| data_collector 后台采集 | 解耦数据获取和用户请求 |
| TTS 用 qwen3-tts-flash 而非本地 | 自然度高，无需 GPU |
| 卡片完整 + TTS 简短摘要 | 屏幕看详情，语音听要点 |
| T800 舵机时间 | T500 不响应，T1000 太慢，T800 平衡 |
| 人名纠错 ×2 | 双重纠错覆盖嵌套/重叠场景 |
