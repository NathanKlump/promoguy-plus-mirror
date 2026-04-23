import asyncio
import re
import threading
from datetime import datetime
from io import BytesIO

import discord  # type: ignore[import]
import aiohttp # type: ignore[import]

import config


intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
client = discord.Client(intents=intents)

shutdown_event = threading.Event()
unexpected_disconnect = False


def contains_link(content, embeds):
    url_pattern = re.compile(r'https?://\S+', re.IGNORECASE)

    if content and url_pattern.search(content):
        return True

    if embeds:
        for embed in embeds:
            if isinstance(embed, dict):
                if embed.get('url'):
                    return True
                description = embed.get('description', '')
                if description and url_pattern.search(description):
                    return True

    return False


def create_discord_embed(embed_data):
    embed = discord.Embed()

    if 'title' in embed_data:
        embed.title = embed_data['title']
    if 'description' in embed_data:
        embed.description = embed_data['description']
    if 'url' in embed_data:
        embed.url = embed_data['url']
    if 'color' in embed_data:
        embed.color = discord.Color(embed_data['color'])
    if 'timestamp' in embed_data:
        embed.timestamp = datetime.fromisoformat(embed_data['timestamp'].replace('Z', '+00:00'))

    if 'footer' in embed_data:
        footer = embed_data['footer']
        embed.set_footer(
            text=footer.get('text', ''),
            icon_url=footer.get('icon_url')
        )

    if 'image' in embed_data:
        embed.set_image(url=embed_data['image']['url'])

    if 'thumbnail' in embed_data:
        embed.set_thumbnail(url=embed_data['thumbnail']['url'])

    if 'author' in embed_data:
        author = embed_data['author']
        embed.set_author(
            name=author.get('name', ''),
            url=author.get('url'),
            icon_url=author.get('icon_url')
        )

    if 'fields' in embed_data:
        for field in embed_data['fields']:
            embed.add_field(
                name=field.get('name', '\u200b'),
                value=field.get('value', '\u200b'),
                inline=field.get('inline', False)
            )

    return embed


async def download_attachment(session, attachment):
    try:
        if isinstance(attachment, dict):
            url = attachment.get('url')
            filename = attachment.get('filename', 'attachment')
        else:
            url = attachment
            filename = url.split('/')[-1].split('?')[0]

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


async def send_to_discord_channel(channel, message, files, embeds):
    sent_messages = []
    try:
        msg_to_send = message
        if len(message) > 2000:
            msg_to_send = message[:1997] + "..."

        if files or embeds:
            embeds_to_send = embeds[:10]
            remaining_embeds = embeds[10:]

            if len(files) <= 10:
                sent_msg = await channel.send(
                    content=msg_to_send if msg_to_send.strip() else None,
                    files=files,
                    embeds=embeds_to_send
                )
                if sent_msg:
                    sent_messages.append(sent_msg)
            else:
                sent_msg = await channel.send(
                    content=msg_to_send if msg_to_send.strip() else None,
                    files=files[:10],
                    embeds=embeds_to_send
                )
                if sent_msg:
                    sent_messages.append(sent_msg)
                for i in range(10, len(files), 10):
                    batch = files[i:i+10]
                    sent_msg = await channel.send(files=batch)
                    if sent_msg:
                        sent_messages.append(sent_msg)

            if remaining_embeds:
                for i in range(0, len(remaining_embeds), 10):
                    batch = remaining_embeds[i:i+10]
                    sent_msg = await channel.send(embeds=batch)
                    if sent_msg:
                        sent_messages.append(sent_msg)
        else:
            sent_msg = await channel.send(msg_to_send)
            if sent_msg:
                sent_messages.append(sent_msg)

    except Exception as e:
        print(f'Error sending to Discord channel {channel.id}: {e}')

    return sent_messages


async def send_to_discord_channels(message, attachments=None, embeds=None, original_content=None):
    if not config.TARGET_OUTPUT_CHANNEL_IDS:
        return

    files_data = []
    if attachments:
        async with aiohttp.ClientSession() as session:
            for attachment in attachments:
                file = await download_attachment(session, attachment)
                if file:
                    files_data.append(file)

    discord_embeds = []
    if embeds:
        for embed_data in embeds:
            try:
                discord_embed = create_discord_embed(embed_data)
                discord_embeds.append(discord_embed)
            except Exception as e:
                print(f'Error creating embed: {e}')

    forward_channel = None
    if config.LINK_FORWARD_CHANNEL_ID:
        forward_channel = client.get_channel(config.LINK_FORWARD_CHANNEL_ID)
        if not forward_channel:
            print(f'Link forward channel {config.LINK_FORWARD_CHANNEL_ID} not found')

    should_forward = forward_channel and contains_link(original_content or '', embeds)

    all_sent_messages = []
    for channel_id in config.TARGET_OUTPUT_CHANNEL_IDS:
        channel = client.get_channel(channel_id)
        if not channel:
            print(f'Channel {channel_id} not found')
            continue

        channel_files = []
        if files_data:
            for file in files_data:
                file.fp.seek(0)
                channel_files.append(discord.File(file.fp, filename=file.filename))

        sent_messages = await send_to_discord_channel(channel, message, channel_files, discord_embeds)
        all_sent_messages.extend(sent_messages)

        if should_forward and sent_messages:
            for sent_msg in sent_messages:
                try:
                    await sent_msg.forward(forward_channel)
                    if forward_channel:
                        print(f'[LINK FORWARD] Message forwarded to #{forward_channel.name}')
                except Exception as e:
                    print(f'Error forwarding message: {e}')


def graceful_shutdown(exit_code=1):
    global unexpected_disconnect
    unexpected_disconnect = True
    print(f"\n[!] Discord bot disconnected! Shutting down... (exit code: {exit_code})")
    shutdown_event.set()


@client.event
async def on_ready():
    global unexpected_disconnect
    unexpected_disconnect = False
    print(f'Discord bot logged in as {client.user}')
    if config.TARGET_OUTPUT_CHANNEL_IDS:
        print(f'Output channels ({len(config.TARGET_OUTPUT_CHANNEL_IDS)}):')
        for channel_id in config.TARGET_OUTPUT_CHANNEL_IDS:
            channel = client.get_channel(channel_id)
            if channel:
                print(f'  - #{channel.name} (ID: {channel_id})')
            else:
                print(f'  - Channel ID {channel_id} (not found)')
    else:
        print('Warning: No output channels configured')
    if config.LINK_FORWARD_CHANNEL_ID:
        channel = client.get_channel(config.LINK_FORWARD_CHANNEL_ID)
        if channel:
            print(f'Link forward channel: #{channel.name} (ID: {config.LINK_FORWARD_CHANNEL_ID})')
        else:
            print(f'Link forward channel: ID {config.LINK_FORWARD_CHANNEL_ID} (not found)')
    print('-' * 50)


@client.event
async def on_disconnect():
    print("[!] Discord bot disconnected!")
    graceful_shutdown(exit_code=1)


def run():
    client.run(config.DISCORD_TOKEN)