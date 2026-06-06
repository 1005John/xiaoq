# 小Q — 系统设计

> 版本：v1.3 | 日期：2026-06-06

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
│  │ 麦克风 → WAV → ASR(MiMo) → 人名纠错×2                 │    │
│  │   → _call_hermes() → JSON指令解析 → 卡片 + TTS        │    │
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
│                  │  │ • MiMo-V2.5-Pro(LLM)  │
│ _call_hermes():  │  │ • MiMo-V2.5-ASR       │
│  1. API Server   │  │ • MiMo-V2.5-TTS(冰糖) │
│     :8086 (优先) │  │ • open-meteo.com(天气) │
│  2. CLI 回退     │  │ • RSS 源(新闻)         │
│                  │  │ • data_collector(缓存) │
│ Skills:          │  └──────────────────────┘
│ • pi-weather     │
│ • pi-news        │
│ • pi-todo(JSON)  │
│ • pi-moa         │
│ • pi-email       │
│ • pi-bug         │
└──────────────────┘
```

## 2. 语音流水线

```
麦克风 → WAV (16kHz mono)
  → ASR: MiMo-V2.5-ASR (token-plan-cn.xiaomimimo.com)
  → 人名纠错 ×2 (skills/name_corrector.py, 100人/734条)
  → _call_hermes(txt)
     ├── [优先] POST http://127.0.0.1:8086/v1/chat/completions
     │          model: mimo-v2.5-pro
     │          system prompt 含 JSON 格式指令
     │          → Hermes Gateway 常驻处理
     │
     └── [回退] hermes chat -q --provider deepseek
  → JSON 指令解析（后台，用户无感）
     ├── {"action":"add","text":"..."} → add.py
     ├── {"action":"query"}            → query.py
     ├── {"action":"done","index":N}   → done.py
     └── {"action":"delete","index":N} → delete.py
  → 卡片显示（JSON 行已剥离）+ TTS 播报
     • 完整回复显示为卡片
     • >40字时 qwen-turbo 摘要 TTS
     • TTS: MiMo-V2.5-TTS (冰糖, 24kHz PCM16, 流式)
```

## 3. 待办系统架构

```
用户语音 → ASR → Hermes(MiMo-Pro)
  → 回复末尾包含 JSON: {"action":"add","text":"用户原话"}
  → robot_face 解析 JSON → subprocess 执行 add.py/done.py/delete.py
  → 100% 可靠执行（不依赖 LLM）
  → 卡片 + TTS 显示结果（JSON 已剥离）
```

### 待办时间解析（add.py）
| 格式 | 示例 | 结果 |
|------|------|------|
| X分钟后 | 5分钟后提醒喝水 | now + 5min |
| 中文分钟后 | 一分钟后 | now + 1min |
| 晚上X点X分 | 晚上十一点十分 | 23:10 |
| 下午X点 | 下午三点 | 15:00 |
| 明天上午X点 | 明天上午9点 | 明天 09:00 |
| YYYY-MM-DD HH:MM | 2026-06-07 14:00 | 准时 |

### 提醒机制
- ReminderWatcher 每30s扫描 todos.json
- 到期待办 → ws_server.command_queue → voice_tts → TTS 播报
- voice_tts 同步调用（线程安全）
- 提醒后标记 notified=true

## 4. 缓存架构

```
┌─────────────────┐
│  data_collector  │  每 1800s 后台采集
├─────────────────┤
│ weather_cache    │  open-meteo.com → JSON
│ news_cache       │  RSS(36kr/sspai/ithome) → JSON
│ todos.json       │  本地 JSON（add.py 写入）
└─────────────────┘
         │
         ▼ Hermes skill query.py 读取
┌─────────────────┐
│  Hermes Agent    │
│  → pi-weather    │  读缓存 JSON
│  → pi-news       │  读缓存 JSON
│  → pi-todo       │  JSON 指令驱动
└─────────────────┘
```

## 5. 关键决策

| 决策 | 原因 |
|------|------|
| MiMo-V2.5-Pro 替代 DeepSeek | 全链路小米，Pro 版遵循指令格式 |
| JSON 指令 + 本地执行 | LLM 不直接执行 shell（不可靠），JSON 解析后 subprocess 执行（100%可靠） |
| 天气/新闻改为缓存读取 | 避免实时 API 调用，消除超时 |
| TTS 冰糖音色 | 中文自然女声 |
| T800 舵机时间 | T500 不响应，T1000 太慢 |
| voice_tts 同步调用 | PyAudio 线程不安全 |
| Gateway 仅保留 xiaomi | 避免 provider 路由错误 |
| SKILL.md 与 system prompt 统一 | 避免指令冲突 |
