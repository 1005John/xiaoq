# XiaoQ 智能助手 — 融合 MW 移动办公版

> 基于 Raspberry Pi 5 + Hailo-8L AI 处理器 + MobileWork Agent 的智能语音助手

## 功能概览

### 全屏表情模式（默认）
- **语音交互**: 按住说话 → ASR 转文字 → 意图识别 → 技能/LLM 回复 → TTS 播报
- **文字交互**: 手机文字输入 → 意图识别 → 技能/LLM 回复 → TTS 播报
- **表情系统**: 霓虹赛博风 / 元气活力风（F2 切换），支持眨眼、情绪切换、扫描线效果
- **人脸跟踪**: Hailo SCRFD 人脸检测 + ArcFace 识别 + 云台舵机跟随
- **技能系统**:
  - chat: LLM 对话（onerouter Auto / GLM-5.2）
  - todo: 待办事项（添加/查询/删除/提醒）
  - weather: 天气查询
  - news: 新闻查询
  - email: 邮件知识库（IMAP 抓取 + LLM 提炼 + FTS5 搜索）
  - module_test: 测试知识库（PostgreSQL + Text-to-SQL）
  - iot: ESP32 智能家居控制
  - vision: 摄像头视觉问答
  - monitor: 视觉监控（条件报警）
  - photo: 拍照

### MW 移动办公模式
- 进入方式: 说"进入移动办公"
- 退出方式: 说"退出移动办公"
- **聊天界面**: 表情缩小到右下角，左侧显示 Markdown 格式的聊天文字
- **MW Agent**: 所有消息走 MobileWork Gateway（port 9800），支持:
  - PPT 生成（cmit 模板）
  - 公文写作
  - 邮件撰写
  - 会议纪要
  - 海报设计
  - 思维导图
  - 网页设计
  - 代码生成
- **实时流式输出**: MW Agent 的中间输出实时显示
- **Markdown 渲染**: 表格、标题、列表、引用、分隔线、粗体

## 硬件清单

| 硬件 | 型号 | 说明 |
|------|------|------|
| 主板 | Raspberry Pi 5 (8GB) | |
| AI 加速 | Hailo-8L (13 TOPS) | PCIe M.2 |
| 屏幕 | 5寸 DSI 屏 (720x1280) | 旋转为 1280x720 横屏 |
| 摄像头 | OV5647 CSI | |
| 声卡 | ReSpeaker 2-Mic (seeed2micvoicec) | I2S |
| 舵机 | 2轴云台 | UART4 (GPIO 12/13) |
| 麦克风 | ReSpeaker 2-Mic 板载 | |
| 喇叭 | 外接扬声器 | |

## 全新部署指南

### 1. 烧录系统

```
系统: Raspberry Pi OS (64-bit) — Debian Trixie
工具: Raspberry Pi Imager
```

烧录时配置:
- 用户名: `pi`
- 密码: `123456`
- WiFi: 连接手机热点
- SSH: 开启

### 2. 基础配置

```bash
# SSH 连接
ssh pi@<IP>

# 禁用 WiFi 休眠
sudo iw dev wlan0 set power_save off
echo "iw dev wlan0 set power_save off" | sudo tee -a /etc/rc.local

# 安装基础工具
sudo apt update && sudo apt full-upgrade
sudo apt install -y socat git python3-pip
```

### 3. config.txt 配置

将 `config/config.txt` 复制到 `/boot/firmware/config.txt`:

```bash
sudo cp config.txt /boot/firmware/config.txt
```

关键配置:
- DSI0 屏幕: `dtoverlay=vc4-kms-dsi-waveshare-panel-v2,5_0_inch_a,dsi0`
- 声卡: `dtoverlay=respeaker-2mic-v2_0` + `dtoverlay=fix-respeaker-power`
- 摄像头: `dtoverlay=ov5647`
- 舵机: `dtoverlay=uart4-pi5,pin_tx=12,pin_rx=13`

> **注意**: respeaker overlay 文件需要从已有系统复制到 `/boot/firmware/overlays/`，Trixie 默认不包含。

```bash
# 复制 respeaker overlay（从其他系统获取）
sudo cp respeaker-2mic-v2_0.dtbo /boot/firmware/overlays/
sudo cp fix-respeaker-power.dtbo /boot/firmware/overlays/
```

重启后验证:
```bash
arecord -l | grep seeed          # 声卡
python3 -c "from picamera2 import Picamera2; print(Picamera2.global_camera_info())"  # 摄像头
ls /dev/ttyAMA4                   # 舵机串口
```

### 4. 安装 Hailo 驱动

```bash
sudo apt install -y hailo-all
sudo reboot

# 验证
hailortcli scan
python3 -c "import hailo; print('OK')"
```

### 5. 安装 hailo-apps

```bash
cd ~
git clone --depth 1 https://github.com/hailo-ai/hailo-rpi5-examples.git hailo-apps
cd hailo-apps
pip3 install --break-system-packages setproctitle python-dotenv pyyaml psutil
```

> 如果 Pi 无法访问 GitHub，可在 PC 上下载 zip 后上传。

### 6. 安装 MobileWork

```bash
# 上传 deb 包后安装
sudo apt install -y /tmp/mobilework-linux-arm64.deb

# 首次启动需要登录
DISPLAY=:0 /opt/MobileWork/mobilework --no-sandbox &
```

### 7. 部署 XiaoQ 代码

```bash
# 创建目录
mkdir -p ~/xiaoq-face-auth-demo/{data,logs}

# 复制代码
cp robot_face_v11_fc245e4.py ~/xiaoq-face-auth-demo/
cp start_xiaoq.sh ~/xiaoq-face-auth-demo/
cp mobile_control.py ~/xiaoq-face-auth-demo/
cp gimbal_driver.py ~/xiaoq-face-auth-demo/
cp hailo_face.py ~/xiaoq-face-auth-demo/
cp hailo_face_pipeline.py ~/xiaoq-face-auth-demo/
cp cute_face.py ~/xiaoq-face-auth-demo/
cp face_identity.py ~/xiaoq-face-auth-demo/
cp -r skills/ ~/xiaoq-face-auth-demo/
cp -r hermes_skills/ ~/xiaoq-face-auth-demo/

chmod +x ~/xiaoq-face-auth-demo/start_xiaoq.sh

# 部署 MW Gateway
cp mw_gateway.py ~/mw_gateway.py

# 部署 Hermes 配置
mkdir -p ~/.hermes/hermes-desktop-assistant
# 创建 .env 文件（参考 config/hermes_env.example）
```

### 8. 安装 Python 依赖

```bash
pip3 install --break-system-packages \
    websockets dashscope pyserial flask openai psycopg2 \
    setproctitle python-dotenv pyyaml psutil numpy pillow
```

### 9. 安装中文字体

```bash
sudo apt install -y fonts-wqy-zenhei
sudo fc-cache -fv
```

### 10. 网络转发配置

Pi 需要通过 PC 的 VPN 访问 onerouter 和 MW 云端:

```bash
# hosts — onerouter 走本地 socat 转发
echo "127.0.0.1 onerouter.cmaiot.cn" | sudo tee -a /etc/hosts

# IP 别名 — MW 云端转发
sudo ip addr add 172.16.251.159/32 dev lo

# socat 转发
sudo nohup socat TCP-LISTEN:443,fork,reuseaddr TCP:<PC_IP>:18443 </dev/null >/tmp/socat443.log 2>&1 &
sudo nohup socat TCP-LISTEN:9070,bind=172.16.251.159,fork TCP:<PC_IP>:9070 </dev/null >/tmp/socat9070.log 2>&1 &
```

PC 端配置 portproxy:
```powershell
netsh interface portproxy add v4tov4 listenport=18443 connectaddress=198.18.0.31 connectport=443
netsh interface portproxy add v4tov4 listenport=9070 connectaddress=172.16.251.159 connectport=9070
```

### 11. 配置 systemd 服务

```bash
# 安装服务文件
sudo cp systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload

# 启用自启动
sudo systemctl enable xiaoq-face-auth-demo.service
sudo systemctl enable xiaoq-mobile-control.service
sudo systemctl enable mw-gateway.service
sudo systemctl enable mobilework.service

# 启动
sudo systemctl start xiaoq-face-auth-demo.service
sleep 30
sudo systemctl start xiaoq-mobile-control.service
sudo systemctl start mobilework.service
sleep 30
# 找到 MW 端口后更新 Gateway
sudo systemctl start mw-gateway.service
```

### 12. Hailo 模型配置

```bash
# 创建模型目录
sudo mkdir -p /usr/local/hailo/resources/models/hailo8l
sudo chown -R pi:pi /usr/local/hailo

# 链接模型文件
sudo ln -sf /usr/share/hailo-models/scrfd_2.5g_h8l.hef /usr/local/hailo/resources/models/hailo8l/scrfd_2.5g.hef
sudo ln -sf /usr/share/hailo-models/scrfd_2.5g_h8l.hef /usr/local/hailo/resources/models/hailo8l/scrfd_2.5g_h8l.hef
sudo ln -sf /usr/share/hailo-models/arcface_mobilefacenet.hef /usr/local/hailo/resources/models/hailo8l/
sudo ln -sf /usr/share/hailo-models/*.hef /usr/local/hailo/resources/models/hailo8l/

# 创建 .env 文件
touch /usr/local/hailo/resources/.env
```

## API 配置

| 服务 | URL | Key |
|------|-----|-----|
| LLM (onerouter) | https://onerouter.cmaiot.cn/v1 | tok_3Bgj8JoAIJEEHDMyh2eZzBUwxNpIQ4g5OBBQzciD |
| ASR/TTS (MiMo) | https://token-plan-cn.xiaomimimo.com/v1 | tp-cg4w819k5f30ewaet1usa9nq4grhzddidqsney3sstdnhhp0 |
| MW Gateway | http://127.0.0.1:9800 | 本地 |

## 架构设计

```
手机 App
    │
    ├── 文字输入 ──→ mobile_control (8788) ──→ WebSocket (8766) ──→ XiaoQ process_text()
    │                                                                   │
    ├── 语音输入 ──→ mobile_control (8788) ──→ WebSocket (8766) ──→ XiaoQ process_voice()
    │                                                                   │
    └── 摄像头流 ──→ mobile_control (8788) ──→ XiaoQ Hailo pipeline
                                                                        │
                    ┌───────────────────────────────────────────────────┘
                    │
                    ├── 全屏模式 (_chat_mode=False)
                    │   ├── 模式切换: "进入移动办公" → _chat_mode=True
                    │   ├── match_intent() → 技能路由 (todo/weather/news/email/...)
                    │   ├── JEV 路由 → chat → _llm_chat() → onerouter Auto
                    │   └── 渲染: 全屏表情 + 回复卡片 + TTS
                    │
                    └── MW 模式 (_chat_mode=True)
                        ├── 模式切换: "退出移动办公" → _chat_mode=False
                        ├── _route_mw_gateway() → MW Gateway (9800) → MW Agent
                        └── 渲染: 右下角小表情 + Markdown 聊天界面
```

## 已知限制

1. **picamera2 segfault**: picamera2 跟 Hailo GStreamer 管线同时使用会 segfault，已禁用 picamera2 检查
2. **视觉监控**: 人脸跟踪退出后摄像头关闭，视觉监控拿不到画面
3. **MW 端口变化**: MW 每次重启端口可能变化，需要更新 Gateway 配置
4. **网络依赖**: onerouter 和 MW 云端需要通过 PC VPN 转发

## 文件说明

| 文件 | 说明 |
|------|------|
| `robot_face_v11_fc245e4.py` | XiaoQ 主程序 |
| `start_xiaoq.sh` | 启动脚本（环境变量 + python3） |
| `mobile_control.py` | 手机 App LAN API (Flask, port 8788) |
| `mw_gateway.py` | MW Agent Gateway (port 9800) |
| `gimbal_driver.py` | 舵机云台驱动 (UART4) |
| `hailo_face.py` | Hailo 人脸检测 + 跟踪 |
| `hailo_face_pipeline.py` | Hailo GStreamer 管线 |
| `cute_face.py` | 元气活力风表情渲染器 |
| `face_identity.py` | 人脸注册/识别管理 |
| `skills/` | 技能模块（todo/weather/news/email 等） |
| `hermes_skills/` | 待办操作脚本（add/delete/done/query） |
| `systemd/` | systemd 服务配置文件 |
| `config/` | 配置文件模板 |
