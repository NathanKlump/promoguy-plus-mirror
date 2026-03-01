# Discord Message Relay

A two-bot system for mirroring messages between Discord channels.

## Overview

- **Self-bot**: Monitors specified Discord channels and forwards messages to a Flask endpoint
- **Normal-bot**: Receives messages via Flask and reposts them to configured output channels

## Setup

1. Copy `.env.example` to `.env` and configure:

   ```
   DISCORD_TOKEN_SELF=          # Token for self-bot (discord.py-self)
   DISCORD_TOKEN_NORMAL=        # Token for normal bot
   TARGET_INPUT_CHANNEL_IDS=    # Channel IDs to monitor (comma-separated)
   TARGET_OUTPUT_CHANNEL_IDS=  # Channel IDs to relay to (comma-separated)
   LINK_FORWARD_CHANNEL_ID=    # Channel to forward links from output channels (optional)
   FLASK_ENDPOINT=http://localhost:5001/receive_message
   FLASK_PORT=5001
   ```

2. Install dependencies:
   ```bash
   cd normal-bot && pip install -r requirements.txt
   cd ../self-bot && pip install -r requirements.txt
   ```

3. Run both bots:
   ```bash
   ./start_bots.sh
   ```

## Architecture

```
[Source Channel] → [Self-bot] → [Flask API] → [Normal-bot] → [Output Channels]
                                                              ↓
                                                    [Link Forward Channel]
```

The self-bot uses `discord.py-self` to read messages from channels. The normal-bot uses regular `discord.py` to post messages.

## Link Forwarding

When `LINK_FORWARD_CHANNEL_ID` is set, any URLs posted to the output channels will be automatically forwarded to the specified channel. This is useful for tracking links in a dedicated channel.
