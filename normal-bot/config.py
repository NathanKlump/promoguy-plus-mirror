import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN_NORMAL")

TARGET_OUTPUT_CHANNEL_IDS_STR = os.getenv("TARGET_OUTPUT_CHANNEL_IDS", "")
TARGET_OUTPUT_CHANNEL_IDS = [
    int(cid.strip())
    for cid in TARGET_OUTPUT_CHANNEL_IDS_STR.split(",")
    if cid.strip().isdigit()
]

FLASK_PORT = int(os.getenv("FLASK_PORT", "5001"))

LINK_FORWARD_CHANNEL_ID = os.getenv("LINK_FORWARD_CHANNEL_ID", "")
LINK_FORWARD_CHANNEL_ID = int(LINK_FORWARD_CHANNEL_ID) if LINK_FORWARD_CHANNEL_ID.isdigit() else None