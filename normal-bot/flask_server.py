import asyncio
import re
from datetime import datetime

from flask import Flask, request, jsonify

import config
import discord_bot


app = Flask(__name__)


@app.route('/shutdown', methods=['POST', 'GET'])
def shutdown():
    discord_bot.shutdown_event.set()
    return jsonify({'status': 'shutting_down'}), 200


@app.route('/health', methods=['GET'])
def health():
    is_ready = discord_bot.ready_event.is_set()
    loop = getattr(discord_bot.client, 'loop', None)
    loop_ready = loop is not None and str(loop) != 'MISSING'
    
    if is_ready and loop_ready:
        return jsonify({'status': 'healthy', 'bot': 'ready'}), 200
    elif is_ready:
        return jsonify({'status': 'degraded', 'bot': 'ready but loop not init'}), 200
    else:
        return jsonify({'status': 'unhealthy', 'bot': 'not ready'}), 503


@app.route('/receive_message', methods=['POST'])
def receive_message():
    if not discord_bot.ready_event.is_set():
        print('[WARNING] Message received before bot ready, rejecting')
        return jsonify({'status': 'error', 'message': 'Bot not ready'}), 503
    
    loop = discord_bot.client.loop
    if loop is None or str(loop) == 'MISSING':
        print('[WARNING] Message received but loop not initialized, rejecting')
        return jsonify({'status': 'error', 'message': 'Bot event loop not initialized'}), 503
    
    try:
        data = request.json

        timestamp = data.get('timestamp', 'N/A')
        channel_name = data.get('channel_name', 'Unknown')
        author = data.get('author', 'Unknown')
        content = data.get('content', '')
        attachments = data.get('attachments', [])
        embeds = data.get('embeds', [])

        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            formatted_time = dt.strftime("%b: %d %I:%M%p").lower()
        except Exception:
            formatted_time = timestamp

        content_parsed = re.sub(r'<a?:(\w+):\d+>', r':\1:', content)

        formatted_message = f"`[{formatted_time}] #{channel_name}`\n{content_parsed}"

        print(f'\n[RECEIVED] {formatted_time}')
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

        if config.TARGET_OUTPUT_CHANNEL_IDS:
            asyncio.run_coroutine_threadsafe(
                discord_bot.send_to_discord_channels(formatted_message, attachments, embeds, content),
                loop
            )

        return jsonify({'status': 'success', 'message': 'Message received'}), 200

    except Exception as e:
        print(f'Error processing message: {e}')
        return jsonify({'status': 'error', 'message': str(e)}), 500


def run():
    import threading
    import time

    def flask_worker():
        while not discord_bot.shutdown_event.is_set():
            app.run(host='0.0.0.0', port=config.FLASK_PORT, debug=False, use_reloader=False, threaded=True)
            if not discord_bot.shutdown_event.is_set():
                time.sleep(0.5)

    flask_thread = threading.Thread(target=flask_worker)
    flask_thread.start()
    return flask_thread