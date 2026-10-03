# 全新 SD 卡部署指南

## 前提条件
- PC 开启热点（IP: 192.168.137.1）
- PC 安装 ATrust VPN
- PC 配置 portproxy（见下文）
- SD 卡（≥32GB，推荐 64GB+）

## 步骤 1: 烧录系统
1. 下载 Raspberry Pi Imager
2. 选择 Raspberry Pi OS (64-bit) — 非 Legacy 版本（Trixie）
3. 烧录时配置:
   - 用户名: `pi`，密码: `123456`
   - WiFi: 连接 PC 热点
   - SSH: 开启

## 步骤 2: 首次启动配置
```bash
ssh pi@192.168.137.46

# 禁用 WiFi 休眠
sudo iw dev wlan0 set power_save off
echo "iw dev wlan0 set power_save off" | sudo tee -a /etc/rc.local

# 更新系统
sudo apt update && sudo apt full-upgrade
sudo apt install -y socat git python3-pip
```

## 步骤 3: config.txt 配置
```bash
# 复制 respeaker overlay（从本仓库 config/ 目录）
sudo cp config/respeaker-2mic-v2_0.dtbo /boot/firmware/overlays/
sudo cp config/fix-respeaker-power.dtbo /boot/firmware/overlays/

# 写入 config.txt
sudo cp config/config.txt /boot/firmware/config.txt

# 重启
sudo reboot
```

## 步骤 4: 验证硬件
```bash
arecord -l | grep seeed                    # 声卡
python3 -c "from picamera2 import Picamera2; print(Picamera2.global_camera_info())"  # 摄像头
ls /dev/ttyAMA4                            # 舵机
lspci | grep hailo                         # Hailo PCIe
```

## 步骤 5: 安装 Hailo
```bash
sudo apt install -y hailo-all
sudo reboot

# 验证
hailortcli scan
python3 -c "import hailo; print('OK')"
```

## 步骤 6: 安装 hailo-apps
```bash
cd ~
git clone --depth 1 https://github.com/hailo-ai/hailo-rpi5-examples.git hailo-apps
cd hailo-apps
pip3 install --break-system-packages setproctitle python-dotenv pyyaml psutil
```

## 步骤 7: 安装 MobileWork
```bash
# 上传 deb 包
scp mobilework-linux-arm64.deb pi@192.168.137.46:/tmp/

# 安装
sudo apt install -y /tmp/mobilework-linux-arm64.deb

# 首次启动 + 登录
DISPLAY=:0 /opt/MobileWork/mobilework --no-sandbox &
# 在屏幕上登录 MW 账号
```

## 步骤 8: 部署代码
```bash
# 创建目录
mkdir -p ~/xiaoq-face-auth-demo/{data,logs}

# 从本仓库复制所有文件
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

# MW Gateway
cp mw_gateway.py ~/mw_gateway.py
```

## 步骤 9: Hermes 配置
```bash
mkdir -p ~/.hermes/hermes-desktop-assistant

# .env 文件
cat > ~/.hermes/.env << 'EOF'
DEEPSEEK_API_KEY=tok_3Bgj8JoAIJEEHDMyh2eZzBUwxNpIQ4g5OBBQzciD
XIAOMI_MIMO_API_KEY=tp-cg4w819k5f30ewaet1usa9nq4grhzddidqsney3sstdnhhp0
EOF

# config.json
cat > ~/.hermes/hermes-desktop-assistant/config.json << 'EOF'
{"aliyun_api_key":"tp-cg4w819k5f30ewaet1usa9nq4grhzddidqsney3sstdnhhp0","xiaomi_mimo_api_key":"tp-cg4w819k5f30ewaet1usa9nq4grhzddidqsney3sstdnhhp0"}
EOF
```

## 步骤 10: Python 依赖
```bash
pip3 install --break-system-packages \
    websockets dashscope pyserial flask openai psycopg2 \
    setproctitle python-dotenv pyyaml psutil numpy pillow
```

## 步骤 11: 中文字体
```bash
sudo apt install -y fonts-wqy-zenhei
sudo fc-cache -fv
```

## 步骤 12: 网络转发
```bash
# hosts
echo "127.0.0.1 onerouter.cmaiot.cn" | sudo tee -a /etc/hosts

# IP 别名
echo 123456 | sudo ip addr add 172.16.251.159/32 dev lo

# socat
sudo nohup socat TCP-LISTEN:443,fork,reuseaddr TCP:192.168.137.1:18443 </dev/null >/tmp/socat443.log 2>&1 &
sudo nohup socat TCP-LISTEN:9070,bind=172.16.251.159,fork TCP:192.168.137.1:9070 </dev/null >/tmp/socat9070.log 2>&1 &
```

PC 端 portproxy（PowerShell 管理员）:
```powershell
netsh interface portproxy add v4tov4 listenport=18443 connectaddress=198.18.0.31 connectport=443
netsh interface portproxy add v4tov4 listenport=9070 connectaddress=172.16.251.159 connectport=9070
```

## 步骤 13: Hailo 模型
```bash
sudo mkdir -p /usr/local/hailo/resources/models/hailo8l
sudo chown -R pi:pi /usr/local/hailo
sudo ln -sf /usr/share/hailo-models/scrfd_2.5g_h8l.hef /usr/local/hailo/resources/models/hailo8l/scrfd_2.5g.hef
sudo ln -sf /usr/share/hailo-models/arcface_mobilefacenet.hef /usr/local/hailo/resources/models/hailo8l/
sudo ln -sf /usr/share/hailo-models/*.hef /usr/local/hailo/resources/models/hailo8l/
touch /usr/local/hailo/resources/.env
```

## 步骤 14: systemd 服务
```bash
sudo cp systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable xiaoq-face-auth-demo.service
sudo systemctl enable xiaoq-mobile-control.service
sudo systemctl enable mw-gateway.service
sudo systemctl enable mobilework.service
```

## 步骤 15: 首次启动顺序
```bash
# 1. 启动 MW
sudo systemctl start mobilework.service
sleep 30

# 2. 找 MW 端口
cat ~/.mobilework/electron/openwork-server-state.json
# 记录 workspacePorts 里的端口号

# 3. 更新 mw_gateway.py 里的 mw_port
sed -i "s/mw_port = [0-9]*/mw_port = <端口号>/" ~/mw_gateway.py

# 4. 启动 Gateway
sudo systemctl start mw-gateway.service

# 5. 启动 XiaoQ
sudo systemctl start xiaoq-face-auth-demo.service
sleep 30

# 6. 启动手机服务
sudo systemctl start xiaoq-mobile-control.service
```

## 验证
```bash
# 检查服务
systemctl is-active xiaoq-face-auth-demo.service    # active
systemctl is-active xiaoq-mobile-control.service    # active
systemctl is-active mw-gateway.service              # active
systemctl is-active mobilework.service              # active

# 测试
curl -s -m 15 -X POST -H "Content-Type: application/json" \
    -d '{"text":"你好","speak":true}' \
    http://127.0.0.1:8788/api/chat
# 应返回 {"ok":true,"reply":"你好！...","status":"completed"}
```
