import os
import discord
from flask import Flask, request, jsonify
import threading
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# -------------------------------------------------------------------
# Load environment variables
# -------------------------------------------------------------------
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN_NORMAL")  # token for normal bot
TARGET_OUTPUT_CHANNEL_ID = int(os.getenv("TARGET_OUTPUT_CHANNEL_ID", "0"))
FLASK_PORT = int(os.getenv("FLASK_PORT", "5001"))  # default to 5001 if not set

# -------------------------------------------------------------------
# Flask setup
# -------------------------------------------------------------------
app = Flask(__name__)

# -------------------------------------------------------------------
# Discord setup
# -------------------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
client = discord.Client(intents=intents)

@app.route('/receive_message', methods=['POST'])
def receive_message():
    """Endpoint to receive messages from the self bot"""
    try:
        data = request.json

        # Extract message details
        timestamp = data.get('timestamp', 'N/A')
        channel_name = data.get('channel_name', 'Unknown')
        author = data.get('author', 'Unknown')
        content = data.get('content', '')
        attachments = data.get('attachments', [])
        embed_count = data.get('embed_count', 0)

        # Format the message
        formatted_message = f"**[{timestamp}]** #{channel_name}\n"
        formatted_message += f"**{author}:** {content}"

        if attachments:
            formatted_message += f"\n📎 Attachments: {len(attachments)}"
        if embed_count > 0:
            formatted_message += f"\n📊 Embeds: {embed_count}"

        # Print to console
        print(f'\n[RECEIVED] {timestamp}')
        print(f'Channel: #{channel_name}')
        print(f'Author: {author}')
        print(f'Content: {content}')
        if attachments:
            print(f'Attachments: {", ".join(attachments)}')
        if embed_count > 0:
            print(f'Embeds: {embed_count}')
        print('-' * 50)

        # Send to Discord channel if configured
        if TARGET_OUTPUT_CHANNEL_ID:
            asyncio.run_coroutine_threadsafe(
                send_to_discord(formatted_message),
                client.loop
            )

        return jsonify({'status': 'success', 'message': 'Message received'}), 200

    except Exception as e:
        print(f'Error processing message: {e}')
        return jsonify({'status': 'error', 'message': str(e)}), 500


async def send_to_discord(message):
    """Send message to Discord channel"""
    if TARGET_OUTPUT_CHANNEL_ID:
        channel = client.get_channel(TARGET_OUTPUT_CHANNEL_ID)
        if channel:
            try:
                # Split message if too long (Discord has 2000 char limit)
                if len(message) > 2000:
                    chunks = [message[i:i + 2000] for i in range(0, len(message), 2000)]
                    for chunk in chunks:
                        await channel.send(chunk)
                else:
                    await channel.send(message)
            except Exception as e:
                print(f'Error sending to Discord: {e}')


@client.event
async def on_ready():
    print(f'Discord bot logged in as {client.user}')
    if TARGET_OUTPUT_CHANNEL_ID:
        channel = client.get_channel(TARGET_OUTPUT_CHANNEL_ID)
        if channel:
            print(f'Output channel: #{channel.name}')
        else:
            print(f'Warning: Output channel {TARGET_OUTPUT_CHANNEL_ID} not found')
    else:
        print('Warning: No output channel configured')
    print('-' * 50)


def run_flask():
    """Run Flask server"""
    app.run(host='0.0.0.0', port=FLASK_PORT, debug=False, use_reloader=False)


def run_discord():
    """Run Discord bot"""
    client.run(DISCORD_TOKEN)


if __name__ == '__main__':
    print('Starting Flask + Discord bot...')
    print(f'Flask server will run on http://0.0.0.0:{FLASK_PORT}')
    print('-' * 50)

    # Run Flask in a separate thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # Run Discord bot in main thread
    run_discord()
