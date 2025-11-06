#!/bin/bash

# Go to self-bot folder
cd "$(dirname "$0")/self-bot" || exit 1
echo "Starting self-bot..."
source venv/bin/activate
pip install -r requirements.txt >/dev/null 2>&1
python self_bot.py &
SELF_BOT_PID=$!
deactivate

# Go to normal-bot folder
cd ../normal-bot || exit 1
echo "Starting normal-bot..."
source venv/bin/activate
pip install -r requirements.txt >/dev/null 2>&1
python normal_bot.py &
NORMAL_BOT_PID=$!
deactivate

cd ..

echo "Both bots started."
echo "Self-bot PID: $SELF_BOT_PID"
echo "Normal-bot PID: $NORMAL_BOT_PID"



