# 功能设计文档

## 1. 整体架构

XiaoQ 是一个基于树莓派的智能语音助手，融合了全屏表情交互和 MW（MobileWork）移动办公两种模式。

### 1.1 系统组件

```
┌─────────────────────────────────────────────────┐
│                   手机 App                       │
│            (HarmonyOS Companion)                 │
└──────────┬──────────┬──────────┬────────────────┘
           │          │          │
     文字输入    语音输入    摄像头流
           │          │          │
           ▼          ▼          ▼
┌──────────────────────────────────────────────────┐
│         mobile_control.py (Flask, 8788)           │
│    PTT start/stop, chat, camera, photos          │
└──────────┬───────────────────────────────────────┘
           │ WebSocket (8766)
           ▼
┌──────────────────────────────────────────────────┐
│           XiaoQ 主程序 (robot_face_v11)           │
│                                                   │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────┐ │
│  │ process_text │  │ process_voice │  │ 渲染循环  │ │
│  │   (文字路由)  │  │  (语音ASR)   │  │(pygame)  │ │
│  └──────┬──────┘  └──────┬───────┘  └────┬─────┘ │
│         │                │               │       │
│  ┌──────▼──────────────────▼───────┐  ┌───▼───┐  │
│  │        模式切换检测              │  │全屏/MW │  │
│  │  "进入移动办公" → _chat_mode=True │  │渲染切换│  │
│  │  "退出移动办公" → _chat_mode=False│  │       │  │
│  └──────┬──────────────┬──────────┘  └───────┘  │
│         │              │                         │
│   ┌─────▼─────┐  ┌────▼──────┐                  │
│   │ 全屏模式   │  │  MW 模式  │                  │
│   │ L3+JEV    │  │ Gateway   │                  │
│   │ 技能路由   │  │ (9800)    │                  │
│   └────┬──────┘  └────┬──────┘                  │
└────────┼──────────────┼─────────────────────────┘
         │              │
    ┌────▼────┐    ┌────▼──────┐
    │onerouter│    │ MW Agent  │
    │ (Auto)  │    │ (GPT等)   │
    └─────────┘    └───────────┘
```

### 1.2 渲染模式

#### 全屏表情模式 (_chat_mode=False)
- 霓虹赛博风 / 元气活力风（F2 切换）
- 全屏表情 + 状态指示（左上角）
- 回复卡片弹出
- 人脸跟踪 + 云台跟随
- 环境特效（VFX）

#### MW 移动办公模式 (_chat_mode=True)
- 表情缩小到右下角（25% 缩放）
- 左侧聊天区域（Markdown 渲染）
- 配色方案:
  - 霓虹: 黑色背景，用户黄色(255,220,60)，回复白色(240,240,245)，思考灰色(120,120,140)
  - 元气: 肤色背景(240,208,192)，用户深棕(55,48,42)，回复黑色(40,35,30)
- 表格/标题/列表/引用/分隔线 Markdown 支持
- 光标闪烁

## 2. 意图路由

### 2.1 全屏模式路由
```
process_text(txt)
│
├── 模式切换检测（优先）
│   ├── "进入移动办公" → _chat_mode=True
│   └── "退出移动办公" → _chat_mode=False
│
├── _chat_mode == True → _route_mw_gateway()
│
└── _chat_mode == False（全屏模式）
    ├── match_intent(txt) → 窄意图匹配
    │   ├── module_test → Text-to-SQL 查询
    │   ├── PPT/公文/海报等 → MW 技能关键词
    │   └── 其他 → JEV 路由
    │
    └── JEV 路由 (TypeSafe System One)
        ├── chat → _llm_chat() → onerouter Auto
        ├── todo → TodoSkill
        ├── weather → WeatherSkill
        ├── news → NewsSkill
        ├── email → EmailKnowledgeSkill
        ├── vision → 摄像头问答
        ├── monitor → 视觉监控
        ├── iot → ESP32 控制
        └── skill → Hermes/MW 技能
```

### 2.2 MW 模式路由
```
_route_mw_gateway(txt)
│
├── POST / → Gateway 发送 prompt
├── GET /status → 轮询状态
├── GET /stream → 实时流式输出
└── GET /result → 获取最终回复
```

## 3. 技能系统

### 3.1 本地技能 (skills/)
| 技能 | 文件 | 功能 |
|------|------|------|
| todo | skills/todo.py + hermes_skills/ | 待办 CRUD + 定时提醒 |
| weather | skills/weather.py | 天气查询（缓存） |
| news | skills/news.py | 新闻查询（RSS） |
| email_knowledge | skills/email_knowledge.py | 邮件知识库搜索 |
| ingest | skills/ingest.py | 邮件抓取+LLM提炼 |
| data_collector | skills/data_collector.py | 天气/新闻定时采集 |
| esp32_led | skills/esp32_led.py | ESP32 智能家居 |
| vision_monitor | skills/vision_monitor.py | 视觉条件监控 |
| xiaomi_iot | skills/xiaomi_iot.py | 小米 IoT |
| relax | skills/relax.py | 木鱼放松 |
| bgm | skills/bgm.py | 背景音乐 |

### 3.2 MW 技能 (通过 Gateway)
| 技能 | 触发关键词 |
|------|-----------|
| PPT 生成 | ppt/PPT |
| 公文写作 | 公文/写文档 |
| 邮件撰写 | 写邮件 |
| 会议纪要 | 会议纪要 |
| 海报设计 | 海报 |
| 思维导图 | 脑图/思维导图 |
| 网页设计 | 网页 |
| 代码生成 | 写代码/编程 |

## 4. 语音管线

### 4.1 ASR (语音转文字)
1. 手机 PTT start → XiaoQ 开始录音（arecord）
2. 手机 PTT stop → 停止录音
3. `_asr_transcribe(wav)` → onerouter SenseVoiceSmall
4. 失败 fallback → MiMo ASR (mimo-v2.5-asr)
5. 人名纠错 (`correct()`)

### 4.2 TTS (文字转语音)
- API: MiMo (token-plan-cn.xiaomimimo.com)
- 模型: mimo-v2.5-tts
- 格式: PCM16, 24kHz, 单声道
- 播放: aplay -D plughw:CARD=seeed2micvoicec,DEV=0

## 5. 人脸检测 + 云台跟踪

### 5.1 Hailo 管线
- 模型: SCRFD 2.5g (人脸检测) + ArcFace MobileFaceNet (人脸识别)
- GStreamer 管线: 1280x720 采集 → Hailo 推理 → 人脸坐标
- 帧率: ~30fps

### 5.2 云台控制
- 舵机: 2轴 (水平/垂直)
- 通信: UART4 (/dev/ttyAMA4, 115200 baud)
- 协议: `#<ID>P<位置>T<时间>!`
- 范围: 水平 50-130, 垂直 138-162

## 6. 配色方案

### 6.1 霓虹赛博风 (neon)
| 元素 | 颜色 |
|------|------|
| 背景 | (8,8,16) 深黑 |
| 用户文字 | (255,220,60) 黄色 |
| Agent 回复 | (240,240,245) 白色 |
| 思考 | (120,120,140) 灰色 |
| 标题 H1/H2/H3 | 蓝色系 |
| 表格表头 | (60,80,120) |
| 表格行 | (25,25,40) |

### 6.2 元气活力风 (cute)
| 元素 | 颜色 |
|------|------|
| 背景 | (240,208,192) 肤色 |
| 用户文字 | (55,48,42) 深棕(眉毛色) |
| Agent 回复 | (40,35,30) 黑色 |
| 思考 | (130,110,100) 灰棕 |
| 标题 | 玫红色系 |
| 表格表头 | (200,170,155) |

## 7. systemd 服务

| 服务 | 端口 | 说明 |
|------|------|------|
| xiaoq-face-auth-demo | 8766 (WS) | XiaoQ 主程序 |
| xiaoq-mobile-control | 8788 (HTTP) | 手机 App API |
| mw-gateway | 9800 (HTTP) | MW Agent Gateway |
| mobilework | 动态 | MW 桌面应用 |

## 8. 已知限制

1. picamera2 与 Hailo GStreamer 管线冲突 → segfault（已禁用 picamera2）
2. 视觉监控在人脸跟踪退出后无法获取画面
3. MW 端口每次重启可能变化
4. 网络依赖 PC VPN 转发
