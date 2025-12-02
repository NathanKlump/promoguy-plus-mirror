#!/bin/bash
# Bot Manager Script
# Usage: ./manage_bots.sh [start|stop|restart|status] [random]

set -euo pipefail  # Exit on error, undefined variables, and pipe failures

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SELF_BOT_DIR="$SCRIPT_DIR/self-bot"
NORMAL_BOT_DIR="$SCRIPT_DIR/normal-bot"
PID_FILE="$SCRIPT_DIR/.bot_pids"
LOG_DIR="$SCRIPT_DIR/logs"
LOCK_FILE="$SCRIPT_DIR/.bot_manager.lock"

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Function to acquire lock
acquire_lock() {
    local max_wait=5
    local waited=0
    
    # Try to acquire lock with timeout
    while [ $waited -lt $max_wait ]; do
        if mkdir "$LOCK_FILE" 2>/dev/null; then
            # Store our PID in the lock directory
            echo $ > "$LOCK_FILE/pid"
            trap cleanup_lock EXIT INT TERM
            return 0
        fi
        
        # Check if the lock holder is still running
        if [ -f "$LOCK_FILE/pid" ]; then
            local lock_pid=$(cat "$LOCK_FILE/pid")
            if ! kill -0 "$lock_pid" 2>/dev/null; then
                log_message "Removing stale lock from PID $lock_pid"
                rm -rf "$LOCK_FILE"
                continue
            fi
        fi
        
        sleep 1
        waited=$((waited + 1))
    done
    
    log_message "ERROR: Another instance of this script is already running"
    log_message "If you're sure no other instance is running, remove: $LOCK_FILE"
    exit 1
}

# Function to release lock
cleanup_lock() {
    rm -rf "$LOCK_FILE" 2>/dev/null || true
}

# Acquire lock at the start
acquire_lock

# Function to log messages
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_DIR/manager.log"
}

# Function to generate random delay (0 to 3600 seconds = 1 hour)
random_delay() {
    if [ "${2:-}" == "random" ]; then
        local delay=$((RANDOM % 3600))
        log_message "Waiting for random delay: $delay seconds ($(($delay / 60)) minutes)"
        sleep $delay
    fi
}

# Function to check if virtual environment exists
check_venv() {
    local bot_dir="$1"
    local bot_name="$2"
    
    if [ ! -f "$bot_dir/venv/bin/python" ]; then
        log_message "ERROR: Virtual environment not found for $bot_name at $bot_dir/venv"
        return 1
    fi
    return 0
}

# Function to start a single bot
start_single_bot() {
    local bot_dir="$1"
    local bot_script="$2"
    local bot_name="$3"
    local log_file="$LOG_DIR/${bot_name}.log"
    
    if ! check_venv "$bot_dir" "$bot_name"; then
        return 1
    fi
    
    log_message "Starting $bot_name..."
    cd "$bot_dir"
    
    # Start bot with output redirected to log file
    nohup ./venv/bin/python "$bot_script" >> "$log_file" 2>&1 &
    local pid=$!
    
    # Wait briefly and check if process is still running
    sleep 1
    if kill -0 "$pid" 2>/dev/null; then
        log_message "$bot_name started successfully with PID: $pid"
        echo "$pid" >> "$PID_FILE"
        return 0
    else
        log_message "ERROR: $bot_name failed to start. Check $log_file for details."
        return 1
    fi
}

# Function to start bots
start_bots() {
    log_message "=== Starting bots ==="
    
    # Check if bots are already running or being started
    if [ -f "$PID_FILE" ]; then
        log_message "WARNING: PID file exists. Checking if bots are already running..."
        if are_bots_running; then
            log_message "ERROR: Bots are already running or another instance is starting them."
            log_message "Use 'status' to check, 'stop' to stop them, or 'restart' instead."
            exit 1
        else
            clean_stale_pids
        fi
    fi
    
    # Create PID file with PENDING markers to prevent concurrent starts
    echo "PENDING" > "$PID_FILE"
    echo "PENDING" >> "$PID_FILE"
    log_message "Reserved bot slots (preventing concurrent starts)"
    
    # Apply random delay if requested
    random_delay "$@"
    
    # Now replace PENDING markers with actual PIDs
    : > "$PID_FILE"  # Clear the file
    
    local success=0
    
    # Start self-bot
    if start_single_bot "$SELF_BOT_DIR" "self_bot.py" "self-bot"; then
        success=$((success + 1))
    fi
    
    # Start normal-bot
    if start_single_bot "$NORMAL_BOT_DIR" "normal_bot.py" "normal-bot"; then
        success=$((success + 1))
    fi
    
    if [ $success -eq 2 ]; then
        log_message "All bots started successfully!"
    elif [ $success -eq 1 ]; then
        log_message "WARNING: Only 1 of 2 bots started successfully."
    else
        log_message "ERROR: Failed to start bots."
        rm "$PID_FILE"
        exit 1
    fi
}

# Function to stop bots
stop_bots() {
    log_message "=== Stopping bots ==="
    random_delay "$@"
    
    if [ ! -f "$PID_FILE" ]; then
        log_message "No PID file found. Attempting to find and stop bot processes..."
        pkill -f "self_bot.py" && log_message "Stopped self_bot.py processes" || true
        pkill -f "normal_bot.py" && log_message "Stopped normal_bot.py processes" || true
        return
    fi
    
    # Read PIDs and kill processes
    while IFS= read -r pid; do
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            log_message "Stopping process $pid..."
            kill "$pid"
            
            # Wait up to 5 seconds for graceful shutdown
            for i in {1..5}; do
                if ! kill -0 "$pid" 2>/dev/null; then
                    log_message "Process $pid stopped gracefully"
                    break
                fi
                sleep 1
            done
            
            # Force kill if still running
            if kill -0 "$pid" 2>/dev/null; then
                log_message "Force killing process $pid..."
                kill -9 "$pid" 2>/dev/null || true
            fi
        else
            log_message "Process $pid not found (already stopped)"
        fi
    done < "$PID_FILE"
    
    # Remove PID file
    rm "$PID_FILE"
    log_message "Bots stopped successfully!"
}

# Function to check status (silent version for internal use)
check_status_silent() {
    are_bots_running
}

# Function to check status (verbose version)
check_status() {
    log_message "=== Checking bot status ==="
    
    if [ ! -f "$PID_FILE" ]; then
        log_message "No bots running (no PID file found)"
        return
    fi
    
    local running=0
    local pending=0
    local line_num=0
    
    while IFS= read -r pid; do
        line_num=$((line_num + 1))
        local bot_name
        [ $line_num -eq 1 ] && bot_name="self-bot" || bot_name="normal-bot"
        
        if [ "$pid" = "PENDING" ]; then
            log_message "⏳ $bot_name is PENDING (another instance is starting bots)"
            pending=$((pending + 1))
        elif [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            log_message "✓ $bot_name (PID $pid) is running"
            running=$((running + 1))
        else
            log_message "✗ $bot_name (PID $pid) is NOT running"
        fi
    done < "$PID_FILE"
    
    if [ $running -eq 0 ] && [ $pending -eq 0 ]; then
        log_message "No bots are running. Cleaning up PID file..."
        rm "$PID_FILE"
    elif [ $pending -gt 0 ]; then
        log_message "$pending bot(s) are being started by another instance"
    else
        log_message "$running of 2 bots are running"
    fi
}

# Function to show logs
show_logs() {
    local bot="${2:-all}"
    local lines="${3:-50}"
    
    case "$bot" in
        self)
            tail -n "$lines" "$LOG_DIR/self-bot.log"
            ;;
        normal)
            tail -n "$lines" "$LOG_DIR/normal-bot.log"
            ;;
        manager)
            tail -n "$lines" "$LOG_DIR/manager.log"
            ;;
        all)
            echo "=== Manager Logs ==="
            tail -n "$lines" "$LOG_DIR/manager.log" 2>/dev/null || echo "No manager logs"
            echo -e "\n=== Self-Bot Logs ==="
            tail -n "$lines" "$LOG_DIR/self-bot.log" 2>/dev/null || echo "No self-bot logs"
            echo -e "\n=== Normal-Bot Logs ==="
            tail -n "$lines" "$LOG_DIR/normal-bot.log" 2>/dev/null || echo "No normal-bot logs"
            ;;
        *)
            echo "Unknown bot: $bot"
            echo "Use: self, normal, manager, or all"
            exit 1
            ;;
    esac
}

# Main script logic
case "${1:-}" in
    start)
        start_bots "$@"
        ;;
    stop)
        stop_bots "$@"
        ;;
    status)
        check_status
        ;;
    restart)
        stop_bots
        sleep 2
        start_bots "$@"
        ;;
    logs)
        show_logs "$@"
        ;;
    *)
        cat << EOF
Usage: $0 {start|stop|restart|status|logs} [options]

Commands:
  start          Start both bots
  stop           Stop both bots
  restart        Restart both bots
  status         Check if bots are running
  logs           View bot logs

Options:
  random         Add random delay (0-3600 seconds) before action

Logs Usage:
  $0 logs [bot] [lines]
    bot:   self, normal, manager, or all (default: all)
    lines: number of lines to show (default: 50)

Examples:
  $0 start
  $0 start random
  $0 stop random
  $0 restart
  $0 status
  $0 logs
  $0 logs self 100
  $0 logs all 200

Log files are stored in: $LOG_DIR
EOF
        exit 1
        ;;
esac