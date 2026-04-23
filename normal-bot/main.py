import sys
import time
import urllib.request

import config
import discord_bot
import flask_server


if __name__ == '__main__':
    print('Starting Flask + Discord bot...')
    print(f'Flask server will run on http://0.0.0.0:{config.FLASK_PORT}')
    print('-' * 50)

    flask_thread = flask_server.run()
    discord_bot.run()

    print("[!] Shutting down Flask server...")
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{config.FLASK_PORT}/shutdown", timeout=2)
    except Exception:
        pass
    time.sleep(1)

    print("[!] Exit complete.")
    sys.exit(1 if discord_bot.unexpected_disconnect else 0)