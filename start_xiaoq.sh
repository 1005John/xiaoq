#!/usr/bin/env bash
# Single runtime for XiaoQ's face, mobile, vision, ESP32, and remote-laptop features.
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$ROOT_DIR/logs"
RUN_DATE="$(date +%Y%m%d)"

mkdir -p "$LOG_DIR"
cd "$ROOT_DIR"

export PYTHONUNBUFFERED=1
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"
export SDL_VIDEODRIVER="${SDL_VIDEODRIVER:-wayland}"
export XIAOQ_AUTO_FACE_TRACKING="${XIAOQ_AUTO_FACE_TRACKING:-1}"

mobile_pid=""
robot_pid=""

cleanup() {
    trap - EXIT INT TERM
    for child_pid in "$robot_pid" "$mobile_pid"; do
        if [[ -n "$child_pid" ]] && kill -0 "$child_pid" 2>/dev/null; then
            kill -TERM "$child_pid" 2>/dev/null || true
        fi
    done
    wait || true
}

trap cleanup EXIT INT TERM

/usr/bin/python3 "$ROOT_DIR/mobile_control.py" >>"$LOG_DIR/mobile_control_${RUN_DATE}.log" 2>&1 &
mobile_pid=$!

/usr/bin/python3 "$ROOT_DIR/robot_face_v11_fc245e4.py" >>"$LOG_DIR/v10_${RUN_DATE}.log" 2>&1 &
robot_pid=$!

wait -n "$mobile_pid" "$robot_pid"
