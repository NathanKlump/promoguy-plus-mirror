import os
import discord
from flask import Flask, request, jsonify
import threading
import asyncio
import aiohttp
from io import BytesIO
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

def create_discord_embed(embed_data):
    """Convert embed data dict to Discord Embed object"""
    embed = discord.Embed()
    
    # Basic properties
    if 'title' in embed_data:
        embed.title = embed_data['title']
    if 'description' in embed_data:
        embed.description = embed_data['description']
    if 'url' in embed_data:
        embed.url = embed_data['url']
    if 'color' in embed_data:
        embed.color = discord.Color(embed_data['color'])
    if 'timestamp' in embed_data:
        # Parse ISO format timestamp
        from datetime import datetime
        embed.timestamp = datetime.fromisoformat(embed_data['timestamp'].replace('Z', '+00:00'))
    
    # Footer
    if 'footer' in embed_data:
        footer = embed_data['footer']
        embed.set_footer(
            text=footer.get('text', ''),
            icon_url=footer.get('icon_url')
        )
    
    # Image
    if 'image' in embed_data:
        embed.set_image(url=embed_data['image']['url'])
    
    # Thumbnail
    if 'thumbnail' in embed_data:
        embed.set_thumbnail(url=embed_data['thumbnail']['url'])
    
    # Author
    if 'author' in embed_data:
        author = embed_data['author']
        embed.set_author(
            name=author.get('name', ''),
            url=author.get('url'),
            icon_url=author.get('icon_url')
        )
    
    # Fields
    if 'fields' in embed_data:
        for field in embed_data['fields']:
            embed.add_field(
                name=field.get('name', '\u200b'),
                value=field.get('value', '\u200b'),
                inline=field.get('inline', False)
            )
    
    return embed

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
        embeds = data.get('embeds', [])

        # Format the message
        formatted_message = f"**[{timestamp}]** #{channel_name}\n"
        formatted_message += f"**{author}:** {content}"

        # Print to console
        print(f'\n[RECEIVED] {timestamp}')
        print(f'Channel: #{channel_name}')
        print(f'Author: {author}')
        print(f'Content: {content}')
        if attachments:
            print(f'Attachments: {len(attachments)} file(s)')
            for att in attachments:
                if isinstance(att, dict):
                    print(f'  - {att.get("filename", "unknown")} ({att.get("content_type", "unknown")})')
                else:
                    print(f'  - {att}')
        if embeds:
            print(f'Embeds: {len(embeds)} embed(s)')
            for i, embed in enumerate(embeds, 1):
                print(f'  Embed {i}:')
                if 'title' in embed:
                    print(f'    Title: {embed["title"]}')
        print('-' * 50)

        # Send to Discord channel if configured
        if TARGET_OUTPUT_CHANNEL_ID:
            asyncio.run_coroutine_threadsafe(
                send_to_discord(formatted_message, attachments, embeds),
                client.loop
            )

        return jsonify({'status': 'success', 'message': 'Message received'}), 200

    except Exception as e:
        print(f'Error processing message: {e}')
        return jsonify({'status': 'error', 'message': str(e)}), 500


async def download_attachment(session, attachment):
    """Download an attachment and return it as a Discord File object"""
    try:
        # Handle both dict format (new) and string format (old)
        if isinstance(attachment, dict):
            url = attachment.get('url')
            filename = attachment.get('filename', 'attachment')
        else:
            url = attachment
            filename = url.split('/')[-1].split('?')[0]  # Extract filename from URL
        
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.read()
                return discord.File(BytesIO(data), filename=filename)
            else:
                print(f'Failed to download attachment: {response.status}')
                return None
    except Exception as e:
        print(f'Error downloading attachment: {e}')
        return None


async def send_to_discord(message, attachments=None, embeds=None):
    """Send message to Discord channel with attachments and embeds"""
    if not TARGET_OUTPUT_CHANNEL_ID:
        return
        
    channel = client.get_channel(TARGET_OUTPUT_CHANNEL_ID)
    if not channel:
        print(f'Channel {TARGET_OUTPUT_CHANNEL_ID} not found')
        return
    
    try:
        # Split message if too long (Discord has 2000 char limit)
        if len(message) > 2000:
            message = message[:1997] + "..."
        
        # Download attachments if any
        files = []
        if attachments:
            async with aiohttp.ClientSession() as session:
                for attachment in attachments:
                    file = await download_attachment(session, attachment)
                    if file:
                        files.append(file)
        
        # Create Discord embed objects
        discord_embeds = []
        if embeds:
            for embed_data in embeds:
                try:
                    discord_embed = create_discord_embed(embed_data)
                    discord_embeds.append(discord_embed)
                except Exception as e:
                    print(f'Error creating embed: {e}')
        
        # Discord limits: 10 embeds per message, 10 files per message
        # Send message with embeds and attachments
        if files or discord_embeds:
            # Limit embeds to 10 per message (Discord limit)
            embeds_to_send = discord_embeds[:10]
            remaining_embeds = discord_embeds[10:]
            
            # Limit files to 10 per message (Discord limit)
            if len(files) <= 10:
                await channel.send(
                    content=message if message.strip() else None,
                    files=files,
                    embeds=embeds_to_send
                )
            else:
                # Send first batch with message and embeds
                await channel.send(
                    content=message if message.strip() else None,
                    files=files[:10],
                    embeds=embeds_to_send
                )
                # Send remaining files in batches
                for i in range(10, len(files), 10):
                    batch = files[i:i+10]
                    await channel.send(files=batch)
            
            # Send remaining embeds if any
            if remaining_embeds:
                for i in range(0, len(remaining_embeds), 10):
                    batch = remaining_embeds[i:i+10]
                    await channel.send(embeds=batch)
        else:
            # Just send the text message
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