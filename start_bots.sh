#!/bin/bash
# Bot Manager Script (minimal version, no logging)
# Usage: ./manage_bots.sh [start|stop|restart|status] [random]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SELF_BOT_DIR="$SCRIPT_DIR/self-bot"
NORMAL_BOT_DIR="$SCRIPT_DIR/normal-bot"
PID_FILE="$SCRIPT_DIR/.bot_pids"
LOCK_FILE="$SCRIPT_DIR/.bot_manager.lock"

mkdir -p "$SCRIPT_DIR" >/dev/null 2>&1

# --- Lock Handling ---
acquire_lock() {
    local max_wait=5 waited=0

    while [ $waited -lt $max_wait ]; do
        if mkdir "$LOCK_FILE" 2>/dev/null; then
            echo $$ > "$LOCK_FILE/pid"
            trap cleanup_lock EXIT INT TERM
            return 0
        fi

        # If locked by a dead PID, remove lock
        if [ -f "$LOCK_FILE/pid" ]; then
            local lock_pid=$(cat "$LOCK_FILE/pid")
            if ! kill -0 "$lock_pid" 2>/dev/null; then
                rm -rf "$LOCK_FILE"
                continue
            fi
        fi

        sleep 1
        waited=$((waited + 1))
    done

    echo "Another instance of this script is running."
    echo "If not, remove: $LOCK_FILE"
    exit 1
}

cleanup_lock() {
    rm -rf "$LOCK_FILE" 2>/dev/null || true
}

acquire_lock

# --- Helpers ---
random_delay() {
    if [ "${2:-}" == "random" ]; then
        local delay=$((RANDOM % 3600))
        sleep $delay
    fi
}

check_venv() {
    [ -f "$1/venv/bin/python" ]
}

start_single_bot() {
    local dir="$1" script="$2" name="$3"

    if ! check_venv "$dir"; then
        echo "Missing venv for $name"
        return 1
    fi

    cd "$dir"
    nohup ./venv/bin/python "$script" >/dev/null 2>&1 &
    local pid=$!

    sleep 1
    if kill -0 "$pid" 2>/dev/null; then
        echo "$pid" >> "$PID_FILE"
        return 0
    else
        return 1
    fi
}

are_bots_running() {
    [ -f "$PID_FILE" ] || return 1
    local running=0
    while read -r pid; do
        kill -0 "$pid" 2>/dev/null && running=$((running + 1))
    done < "$PID_FILE"
    [ $running -gt 0 ]
}

clean_stale_pids() {
    > "$PID_FILE"
}

# --- Commands ---
start_bots() {
    if [ -f "$PID_FILE" ] && are_bots_running; then
        echo "Bots already running"
        exit 1
    fi

    echo "PENDING" > "$PID_FILE"
    echo "PENDING" >> "$PID_FILE"

    random_delay "$@"

    : > "$PID_FILE"

    local ok=0
    start_single_bot "$SELF_BOT_DIR" "self_bot.py" "self-bot" && ok=$((ok + 1))
    start_single_bot "$NORMAL_BOT_DIR" "normal_bot.py" "normal-bot" && ok=$((ok + 1))

    if [ $ok -eq 0 ]; then
        rm "$PID_FILE"
        echo "Failed to start bots"
        exit 1
    fi

    echo "Started $ok bot(s)"
}

stop_bots() {
    random_delay "$@"

    if [ ! -f "$PID_FILE" ]; then
        pkill -f "self_bot.py" || true
        pkill -f "normal_bot.py" || true
        return
    fi

    while read -r pid; do
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
            sleep 1
            kill -9 "$pid" 2>/dev/null || true
        fi
    done < "$PID_FILE"

    rm -f "$PID_FILE"
    echo "Bots stopped"
}

check_status() {
    if [ ! -f "$PID_FILE" ]; then
        echo "No bots running"
        return
    fi

    local num=0
    while read -r pid; do
        num=$((num + 1))
        local name=$([ $num -eq 1 ] && echo "self-bot" || echo "normal-bot")

        if [ "$pid" = "PENDING" ]; then
            echo "$name: pending"
        elif kill -0 "$pid" 2>/dev/null; then
            echo "$name: running (PID $pid)"
        else
            echo "$name: not running"
        fi
    done < "$PID_FILE"
}

# --- Entry Point ---
case "${1:-}" in
    start)   start_bots "$@" ;;
    stop)    stop_bots "$@" ;;
    restart) stop_bots; sleep 1; start_bots "$@" ;;
    status)  check_status ;;
    *)
        echo "Usage: $0 {start|stop|restart|status} [random]"
        exit 1
        ;;
esac
