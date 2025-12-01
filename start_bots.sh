#!/bin/bash
# Bot Manager Script
# Usage: ./manage_bots.sh [start|stop] [random]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SELF_BOT_DIR="$SCRIPT_DIR/self-bot"
NORMAL_BOT_DIR="$SCRIPT_DIR/normal-bot"
PID_FILE="$SCRIPT_DIR/.bot_pids"
LOCK_FILE="$SCRIPT_DIR/.bot_manager.lock"

# Function to acquire lock
acquire_lock() {
    if [ -f "$LOCK_FILE" ]; then
        local lock_pid=$(cat "$LOCK_FILE")
        # Check if the process that created the lock is still running
        if kill -0 "$lock_pid" 2>/dev/null; then
            echo "Error: Another instance of this script is already running (PID: $lock_pid)"
            echo "If you're sure no other instance is running, remove: $LOCK_FILE"
            exit 1
        else
            # Stale lock file, remove it
            echo "Removing stale lock file..."
            rm "$LOCK_FILE"
        fi
    fi
    
    # Create lock file with current PID
    echo $$ > "$LOCK_FILE"
}

# Function to release lock
release_lock() {
    rm -f "$LOCK_FILE"
}

# Trap to ensure lock is released on exit
trap release_lock EXIT INT TERM

# Function to generate random delay (0 to 3600 seconds = 1 hour)
random_delay() {
    if [ "$2" == "random" ]; then
        local delay=$((RANDOM % 3600))
        echo "Waiting for random delay: $delay seconds ($(($delay / 60)) minutes)"
        sleep $delay
    fi
}

# Function to start bots
start_bots() {
    echo "Starting bots..."
    random_delay "$@"
    
    # Start self-bot
    echo "Starting self-bot..."
    cd "$SELF_BOT_DIR"
    nohup ./venv/bin/python self_bot.py > /dev/null 2>&1 &
    SELF_BOT_PID=$!
    echo "Self-bot started with PID: $SELF_BOT_PID"
    
    # Start normal-bot
    echo "Starting normal-bot..."
    cd "$NORMAL_BOT_DIR"
    nohup ./venv/bin/python normal_bot.py > /dev/null 2>&1 &
    NORMAL_BOT_PID=$!
    echo "Normal-bot started with PID: $NORMAL_BOT_PID"
    
    # Save PIDs to file
    echo "$SELF_BOT_PID" > "$PID_FILE"
    echo "$NORMAL_BOT_PID" >> "$PID_FILE"
    
    echo "Both bots started successfully!"
}

# Function to stop bots
stop_bots() {
    echo "Stopping bots..."
    random_delay "$@"
    
    if [ ! -f "$PID_FILE" ]; then
        echo "No PID file found. Bots may not be running."
        # Try to find and kill processes by name
        pkill -f "self_bot.py"
        pkill -f "normal_bot.py"
        echo "Attempted to stop any running bot processes."
        return
    fi
    
    # Read PIDs and kill processes
    while IFS= read -r pid; do
        if kill -0 "$pid" 2>/dev/null; then
            echo "Stopping process $pid..."
            kill "$pid"
        else
            echo "Process $pid not found (already stopped)"
        fi
    done < "$PID_FILE"
    
    # Remove PID file
    rm "$PID_FILE"
    echo "Bots stopped successfully!"
}

# Function to check status
check_status() {
    if [ ! -f "$PID_FILE" ]; then
        echo "No bots running (no PID file found)"
        return
    fi
    
    echo "Checking bot status..."
    local running=0
    while IFS= read -r pid; do
        if kill -0 "$pid" 2>/dev/null; then
            echo "Process $pid is running"
            running=$((running + 1))
        else
            echo "Process $pid is not running"
        fi
    done < "$PID_FILE"
    
    if [ $running -eq 0 ]; then
        echo "No bots are running"
        rm "$PID_FILE"
    fi
}

# Acquire lock before proceeding
acquire_lock

# Main script logic
case "$1" in
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
    *)
        echo "Usage: $0 {start|stop|restart|status} [random]"
        echo ""
        echo "Commands:"
        echo "  start          Start both bots"
        echo "  stop           Stop both bots"
        echo "  restart        Restart both bots"
        echo "  status         Check if bots are running"
        echo ""
        echo "Options:"
        echo "  random         Add random delay (0-3600 seconds) before action"
        echo ""
        echo "Examples:"
        echo "  $0 start"
        echo "  $0 start random"
        echo "  $0 stop random"
        exit 1
        ;;
esac