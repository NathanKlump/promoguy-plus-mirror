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
# Support comma-separated channel IDs
TARGET_INPUT_CHANNEL_IDS = os.getenv("TARGET_INPUT_CHANNEL_IDS", "")
FLASK_ENDPOINT = os.getenv("FLASK_ENDPOINT", "http://localhost:5001/receive_message")

# Parse channel IDs from comma-separated string
def parse_channel_ids(channel_ids_str):
    """Parse comma-separated channel IDs into a set of integers."""
    if not channel_ids_str:
        return set()
    
    channel_ids = set()
    for id_str in channel_ids_str.split(','):
        id_str = id_str.strip()
        if id_str.isdigit():
            channel_ids.add(int(id_str))
    return channel_ids

def extract_embed_data(embed):
    """Extract all relevant data from a Discord embed."""
    embed_data = {}
    
    # Basic embed properties
    if embed.title:
        embed_data['title'] = embed.title
    if embed.description:
        embed_data['description'] = embed.description
    if embed.url:
        embed_data['url'] = embed.url
    if embed.color:
        embed_data['color'] = embed.color.value
    if embed.timestamp:
        embed_data['timestamp'] = embed.timestamp.isoformat()
    
    # Footer
    if embed.footer:
        embed_data['footer'] = {
            'text': embed.footer.text,
            'icon_url': embed.footer.icon_url if embed.footer.icon_url else None
        }
    
    # Image
    if embed.image:
        embed_data['image'] = {
            'url': embed.image.url,
            'width': embed.image.width,
            'height': embed.image.height
        }
    
    # Thumbnail
    if embed.thumbnail:
        embed_data['thumbnail'] = {
            'url': embed.thumbnail.url,
            'width': embed.thumbnail.width,
            'height': embed.thumbnail.height
        }
    
    # Author
    if embed.author:
        embed_data['author'] = {
            'name': embed.author.name,
            'url': embed.author.url if embed.author.url else None,
            'icon_url': embed.author.icon_url if embed.author.icon_url else None
        }
    
    # Fields
    if embed.fields:
        embed_data['fields'] = []
        for field in embed.fields:
            embed_data['fields'].append({
                'name': field.name,
                'value': field.value,
                'inline': field.inline
            })
    
    # Video (if present)
    if embed.video:
        embed_data['video'] = {
            'url': embed.video.url,
            'width': embed.video.width,
            'height': embed.video.height
        }
    
    # Provider (e.g., YouTube, Twitter)
    if embed.provider:
        embed_data['provider'] = {
            'name': embed.provider.name,
            'url': embed.provider.url if embed.provider.url else None
        }
    
    return embed_data

# -------------------------------------------------------------------
# Discord client definition
# -------------------------------------------------------------------
class MessageLogger(discord.Client):
    def __init__(self, target_channel_ids, webhook_url):
        # For discord.py-self - no intents parameter needed
        super().__init__()
        self.target_channel_ids = target_channel_ids
        self.webhook_url = webhook_url

    async def on_ready(self):
        print(f'Logged in as: {self.user}')
        print(f'User ID: {self.user.id}')
        print('-' * 50)
        
        # Display info for all target channels
        print(f'Monitoring {len(self.target_channel_ids)} channel(s):')
        for channel_id in self.target_channel_ids:
            channel = self.get_channel(channel_id)
            if channel:
                if hasattr(channel, 'guild'):
                    print(f'  • #{channel.name} (ID: {channel_id}) in {channel.guild.name}')
                else:
                    print(f'  • #{channel.name} (ID: {channel_id})')
            else:
                print(f'  • Channel ID: {channel_id} (not found - check ID and bot access)')
        
        print('-' * 50)
        print('Listening for messages...\n')

    async def on_message(self, message):
        # Only log messages from target channels
        if message.channel.id not in self.target_channel_ids:
            return

        # Get timestamp
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Prepare attachment data with more details
        attachments = []
        for att in message.attachments:
            attachments.append({
                'url': att.url,
                'filename': att.filename,
                'size': att.size,
                'content_type': att.content_type
            })

        # Extract embed data
        embeds = []
        for embed in message.embeds:
            embeds.append(extract_embed_data(embed))

        # Prepare message data
        message_data = {
            'timestamp': timestamp,
            'channel_id': message.channel.id,
            'channel_name': message.channel.name,
            'author': str(message.author),
            'content': message.content,
            'attachments': attachments,
            'embeds': embeds
        }

        # Log locally
        print(f'[{timestamp}] #{message.channel.name} (ID: {message.channel.id})')
        print(f'{message.author}: {message.content}')
        if message.attachments:
            for att in attachments:
                print(f'Attachment: {att["filename"]} ({att["content_type"]}) - {att["url"]}')
        if message.embeds:
            print(f'Embeds: {len(embeds)} embed(s)')
            for i, embed in enumerate(embeds, 1):
                print(f'  Embed {i}:')
                if 'title' in embed:
                    print(f'    Title: {embed["title"]}')
                if 'description' in embed:
                    desc_preview = embed["description"][:100] + '...' if len(embed["description"]) > 100 else embed["description"]
                    print(f'    Description: {desc_preview}')
                if 'image' in embed:
                    print(f'    Image: {embed["image"]["url"]}')
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
    
    # Parse channel IDs
    channel_ids = parse_channel_ids(TARGET_INPUT_CHANNEL_IDS)
    
    if not channel_ids:
        print('ERROR: No valid channel IDs found in TARGET_INPUT_CHANNEL_IDS')
        print('Please set TARGET_INPUT_CHANNEL_IDS in your .env file (comma-separated)')
        exit(1)
    
    client = MessageLogger(
        target_channel_ids=channel_ids,
        webhook_url=FLASK_ENDPOINT
    )
    client.run(DISCORD_TOKEN_SELF)