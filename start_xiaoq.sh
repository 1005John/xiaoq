#!/usr/bin/env bash
set -eo pipefail
ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$ROOT_DIR/logs"
RUN_DATE="$(date +%Y%m%d)"
mkdir -p "$LOG_DIR"
cd "$ROOT_DIR"
export PYTHONPATH="${ROOT_DIR}:${HOME}/hailo-apps"
export PYTHONUNBUFFERED=1
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export WAYLAND_DISPLAY="wayland-0"
export SDL_VIDEODRIVER="wayland"
export XIAOQ_AUTO_FACE_TRACKING=1
export XIAOQ_ROOT="$ROOT_DIR"
export XIAOQ_FACE_AUTH_REQUIRED=0
export AIOT_API_KEY="tok_3Bgj8JoAIJEEHDMyh2eZzBUwxNpIQ4g5OBBQzciD"
export AIOT_BASE_URL="https://onerouter.cmaiot.cn/v1"
export AIOT_LLM_MODEL="Auto"
export AIOT_ASR_MODEL="TS/SenseVoiceSmall"
export TYPESAFE_API_KEY="apikey_2179cde0d02c344b43caa28d175161cbe9ae_e82cb551a98da7b100e8f90976038d08ba6053b6f02e2df56631d764dcbdea71"
export KB_DB_HOST="192.168.137.1"
export KB_DB_USER="kb_reader"
export KB_DB_PASS="ModuleKbV02_20260714"
export KB_DB_NAME="module_test_kb_v02"
export DISPLAY=:0
python3 "$ROOT_DIR/robot_face_v11_fc245e4.py" >>"$LOG_DIR/v10_${RUN_DATE}.log" 2>&1
