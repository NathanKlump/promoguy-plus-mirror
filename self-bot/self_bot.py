import os
import discord
import requests
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# -------------------------------------------------------------------
# Load environment variables
# -------------------------------------------------------------------
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

DISCORD_TOKEN_SELF = os.getenv("DISCORD_TOKEN_SELF")
TARGET_INPUT_CHANNEL_ID = int(os.getenv("TARGET_INPUT_CHANNEL_ID", "0"))
FLASK_ENDPOINT = os.getenv("FLASK_ENDPOINT", "http://localhost:5001/receive_message")

# -------------------------------------------------------------------
# Discord client definition
# -------------------------------------------------------------------
class MessageLogger(discord.Client):
    def __init__(self, target_channel_id, webhook_url):
        intents = discord.Intents.default()
        intents.messages = True
        intents.message_content = True
        super().__init__(intents=intents)
        self.target_channel_id = target_channel_id
        self.webhook_url = webhook_url
    
    async def on_ready(self):
        print(f'Logged in as: {self.user}')
        print(f'User ID: {self.user.id}')
        print('-' * 50)
        
        # Try to find and display the target channel info
        channel = self.get_channel(self.target_channel_id)
        if channel:
            print(f'Monitoring channel: #{channel.name}')
            if hasattr(channel, 'guild'):
                print(f'Server: {channel.guild.name}')
        else:
            print(f'Monitoring channel ID: {self.target_channel_id}')
            print('(Channel not found - make sure the ID is correct)')
        
        print('-' * 50)
        print('Listening for messages...\n')
    
    async def on_message(self, message):
        # Only log messages from the target channel
        if message.channel.id != self.target_channel_id:
            return
        
        # Get timestamp
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Prepare message data
        message_data = {
            'timestamp': timestamp,
            'channel_name': message.channel.name,
            'author': str(message.author),
            'content': message.content,
            'attachments': [att.url for att in message.attachments],
            'embed_count': len(message.embeds)
        }
        
        # Log locally
        print(f'[{timestamp}] #{message.channel.name}')
        print(f'{message.author}: {message.content}')
        if message.attachments:
            print(f'Attachments: {", ".join(message_data["attachments"])}')
        if message.embeds:
            print(f'Embeds: {message_data["embed_count"]} embed(s)')
        print('-' * 50)
        
        # Forward to Flask endpoint
        try:
            response = requests.post(self.webhook_url, json=message_data, timeout=5)
            if response.status_code == 200:
                print(f'✓ Forwarded to Flask server')
            else:
                print(f'✗ Failed to forward: {response.status_code}')
        except requests.exceptions.RequestException as e:
            print(f'✗ Error forwarding message: {e}')
        
        print('-' * 50)


# -------------------------------------------------------------------
# Run the client
# -------------------------------------------------------------------
if __name__ == '__main__':
    print('Starting Discord message logger...')
    print('WARNING: Automating user accounts is against Discord ToS')
    print('Use at your own risk!\n')
    
    client = MessageLogger(
        target_channel_id=TARGET_INPUT_CHANNEL_ID,
        webhook_url=FLASK_ENDPOINT
    )
    client.run(DISCORD_TOKEN_SELF)
