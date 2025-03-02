import asyncio

import websockets
import json
import threading
from datetime import datetime
import pytchat

# Функция для загрузки API ключей из файла
def load_api_keys(filename="api_keys.json"):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            keys = json.load(f)
        return keys
    except Exception as e:
        print(f"Ошибка при загрузке API ключей: {e}")
        return {}

# Загружаем ключи
api_keys = load_api_keys()
TWITCH_OAUTH_TOKEN = api_keys.get("twitch", "")
TWITCH_NICKNAME = api_keys.get("twitch_nickname", "your_twitch_username")

# -------------------------------
# Слушатель Twitch (через IRC WebSocket)
# -------------------------------
TWITCH_IRC_URL = "wss://irc-ws.chat.twitch.tv:443"

async def listen_twitch(channel):
    try:
        async with websockets.connect(TWITCH_IRC_URL) as ws:
            await ws.send(f"PASS {TWITCH_OAUTH_TOKEN}")
            await ws.send(f"NICK {TWITCH_NICKNAME}")
            await ws.send(f"JOIN #{channel}")
            print(f"✅ Подключено к Twitch чату канала: #{channel}")
            while True:
                message = await ws.recv()
                if message.startswith("PING"):
                    await ws.send("PONG :tmi.twitch.tv")
                    continue
                if "PRIVMSG" in message:
                    parts = message.split(":", 2)
                    if len(parts) > 2:
                        username = parts[1].split("!")[0]
                        # Убираем лишние символы переноса строки
                        chat_message = parts[2].rstrip("\n")
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        print(f"[{timestamp}][🟣 Twitch] {username}: {chat_message}")
    except Exception as e:
        print("Ошибка в Twitch listener:", e)

# -------------------------------
# Слушатель YouTube с использованием pytchat
# -------------------------------
async def listen_youtube(video_id):
    chat = pytchat.create(video_id=video_id)
    print(f"✅ Подключено к YouTube чату для видео: {video_id}")
    while chat.is_alive():
        for c in chat.get().sync_items():
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}][🔴 YouTube] {c.author.name}: {c.message}")
        await asyncio.sleep(1)

# -------------------------------
# Слушатель TikTok (обходной путь с использованием библиотеки TikTokLive)
# -------------------------------
def listen_tiktok(username):
    try:
        from TikTokLive import TikTokLiveClient
        from TikTokLive.events import CommentEvent

        client = TikTokLiveClient(unique_id=username)

        async def on_comment(event: CommentEvent):
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}][⚪ TikTok] {event.user.nickname}: {event.comment}")

        client.add_listener(CommentEvent, on_comment)

        print(f"✅ Подключено к TikTok чату пользователя: {username}")
        client.run()
    except ImportError:
        print("Библиотека TikTokLive не установлена. Установите её через pip install TikTokLive.")
    except Exception as e:
        print("Ошибка в TikTok listener:", e)

def run_tiktok_listener(username):
    thread = threading.Thread(target=listen_tiktok, args=(username,), daemon=True)
    thread.start()

# -------------------------------
# Основная функция программы
# -------------------------------
async def main():
    print("Введите данные для подключения к чатам трансляций.")
    twitch_channel = input("Twitch канал (имя канала, без #): ").strip()
    youtube_video_id = input("YouTube video id: ").strip()
    tiktok_username = input("TikTok username: ").strip()

    tasks = []
    if twitch_channel:
        tasks.append(listen_twitch(twitch_channel))
    if youtube_video_id:
        tasks.append(listen_youtube(youtube_video_id))
    if tiktok_username:
        (run_tiktok_listener(tiktok_username))
    if tasks:
        await asyncio.gather(*tasks)
    else:
        print("Не введено ни одного канала для прослушивания.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Программа остановлена пользователем.")
