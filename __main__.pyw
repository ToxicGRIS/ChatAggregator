import asyncio
import json
import os
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import websockets
from datetime import datetime
import tracemalloc
import pytchat

tracemalloc.start()

TWITCH_PREFIX = '[Twitch]'
YT_PREFIX = '[YouTube]'
TIKTOK_PREFIX = '[TikTok]'

def load_api_keys(filename="api_keys.json"):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            keys = json.load(f)
        return keys
    except Exception as e:
        print(f"Error loading API keys: {e}")
        return {}

api_keys = load_api_keys()
TWITCH_OAUTH_TOKEN = api_keys.get("twitch", "")
TWITCH_NICKNAME = api_keys.get("twitch_nickname", "your_twitch_username")

TWITCH_IRC_URL = "wss://irc-ws.chat.twitch.tv:443"

chat_output = None
stop_event = threading.Event()

async def listen_twitch(channel, output_callback):
    try:
        async with websockets.connect(TWITCH_IRC_URL) as ws:
            await ws.send(f"PASS {TWITCH_OAUTH_TOKEN}")
            await ws.send(f"NICK {TWITCH_NICKNAME}")
            await ws.send(f"JOIN #{channel}")
            output_callback(f"✅ Connected to Twitch chat for channel: #{channel}")
            while not stop_event.is_set():
                message = await ws.recv()
                if message.startswith("PING"):
                    await ws.send("PONG :tmi.twitch.tv")
                    continue
                if "PRIVMSG" in message:
                    parts = message.split(":", 2)
                    if len(parts) > 2:
                        username = parts[1].split("!")[0]
                        chat_message = parts[2].rstrip("\n")
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        output_callback(f"[{timestamp}]{TWITCH_PREFIX} {username}: {chat_message}")
    except Exception as e:
        output_callback(f"Error in Twitch listener: {e}")

async def listen_youtube(video_id, output_callback):
    try:
        chat = pytchat.create(video_id=video_id, interruptable=False)
        output_callback(f"✅ Connected to YouTube chat for video: {video_id}")
        while chat.is_alive() and not stop_event.is_set():
            for c in chat.get().sync_items():
                timestamp = datetime.now().strftime("%H:%M:%S")
                output_callback(f"[{timestamp}]{YT_PREFIX} {c.author.name}: {c.message}")
            await asyncio.sleep(1)
    except Exception as e:
        output_callback(f"Error in YouTube listener: {e}")

def listen_tiktok(username, output_callback):
    try:
        from TikTokLive import TikTokLiveClient
        from TikTokLive.events import CommentEvent

        client = TikTokLiveClient(unique_id=username)

        async def on_comment(event: CommentEvent):
            if stop_event.is_set():
                await client.close()
                return
            timestamp = datetime.now().strftime("%H:%M:%S")
            output_callback(f"[{timestamp}]{TIKTOK_PREFIX} {event.user.nickname}: {event.comment}")

        client.add_listener(CommentEvent, on_comment)
        output_callback(f"✅ Connected to TikTok chat for user: {username}")
        client.run()
    except Exception as e:
        output_callback(f"Error in TikTok listener: {e}")

def run_tiktok_listener(username, output_callback):
    thread = threading.Thread(target=listen_tiktok, args=(username, output_callback), daemon=True)
    thread.start()
    return thread

def save_config(channels):
    config = []
    for channel in channels:
        platform = channel["platform"].get()
        name = channel["name"].get()
        if platform and name:
            config.append({"platform": platform, "name": name})
    try:
        with open("chat_config.json", "w", encoding="utf-8") as f:
            json.dump(config, f)
    except Exception as e:
        print(f"Error saving configuration: {e}")

def load_config():
    try:
        if os.path.exists("chat_config.json"):
            with open("chat_config.json", "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading configuration: {e}")
    return []

def set_dark_theme(root):
    style = ttk.Style()
    style.theme_use('clam')
    style.configure('TFrame', background='#2d2d2d')
    style.configure('TLabel', background='#2d2d2d', foreground='#ffffff')
    style.configure('TButton', background='#444444', foreground='#ffffff')
    style.configure('TEntry', fieldbackground='#3d3d3d', foreground='#ffffff')
    style.map('TButton',
              background=[('active', '#555555'), ('pressed', '#333333')],
              foreground=[('active', '#ffffff'), ('pressed', '#dddddd')])
    style.configure('TCombobox',
                    fieldbackground='#3d3d3d',
                    background='#444444',
                    foreground='#ffffff',
                    arrowcolor='#ffffff')
    style.map('TCombobox',
              fieldbackground=[('readonly', '#3d3d3d')],
              selectbackground=[('readonly', '#555555')],
              selectforeground=[('readonly', '#ffffff')])
    style.configure('Vertical.TScrollbar',
                    background='#444444',
                    arrowcolor='#ffffff',
                    troughcolor='#2d2d2d')
    root.configure(bg='#2d2d2d')

def create_chat_window(root):
    global chat_output
    chat_window = tk.Toplevel(root)
    chat_window.title("Chat Messages")
    chat_window.geometry("800x600")
    chat_window.configure(bg='#2d2d2d')
    chat_window.protocol("WM_DELETE_WINDOW", lambda: on_chat_window_close(chat_window))
    chat_window.columnconfigure(0, weight=1)
    chat_window.rowconfigure(0, weight=1)
    chat_output = scrolledtext.ScrolledText(chat_window, bg='#1e1e1e', fg='#ffffff', font=('Consolas', 12))
    chat_output.grid(row=0, column=0, sticky='nsew', padx=10, pady=10)
    chat_output.tag_config('twitch', foreground='#a970ff')
    chat_output.tag_config('youtube', foreground='#ef0434')
    chat_output.tag_config('tiktok', foreground='#ffa236')
    chat_output.tag_config('info', foreground='#4CAF50')
    chat_output.tag_config('error', foreground='#F44336')
    clear_button = ttk.Button(chat_window, text="Clear Chat", command=lambda: chat_output.delete(1.0, tk.END))
    clear_button.grid(row=1, column=0, pady=10)
    return chat_window

def on_chat_window_close(window):
    global stop_event, chat_output
    stop_event.set()
    try:
        window.destroy()
    except tk.TclError:
        pass
    chat_output = None

def add_chat_message(message):
    global chat_output
    if chat_output is None:
        return

    def insert_message():
        if chat_output is None:
            return
        tag = 'info'
        if TWITCH_PREFIX in message:
            tag = 'twitch'
        elif YT_PREFIX in message:
            tag = 'youtube'
        elif TIKTOK_PREFIX in message:
            tag = 'tiktok'
        elif 'Error' in message:
            tag = 'error'
        try:
            chat_output.insert(tk.END, message + '\n', tag)
            chat_output.see(tk.END)
        except tk.TclError:
            pass

    try:
        chat_output.after(0, insert_message)
    except tk.TclError:
        pass

class ChatAggregatorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Chat Aggregator")
        self.root.geometry("600x400")
        set_dark_theme(self.root)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        self.main_frame = ttk.Frame(self.root)
        self.main_frame.grid(row=0, column=0, sticky='nsew', padx=20, pady=20)
        self.main_frame.columnconfigure(0, weight=1)

        title_label = ttk.Label(self.main_frame, text="Chat Aggregator", font=('Arial', 16))
        title_label.grid(row=0, column=0, columnspan=3, pady=10, sticky='w')

        self.channels_frame = ttk.Frame(self.main_frame)
        self.channels_frame.grid(row=1, column=0, sticky='nsew', pady=10)
        self.channels_frame.columnconfigure(1, weight=1)

        self.channels = []
        config = load_config()
        if config:
            for channel_config in config:
                self.add_channel_row(platform=channel_config.get("platform"), name=channel_config.get("name"))
        else:
            self.add_channel_row()

        self.add_button = ttk.Button(self.main_frame, text="Add Channel", command=self.add_channel_row)
        self.add_button.grid(row=2, column=0, pady=10, sticky='w')

        self.confirm_button = ttk.Button(self.main_frame, text="Connect", command=self.start_chat_monitoring)
        self.confirm_button.grid(row=3, column=0, pady=10, sticky='w')

        self.status_label = ttk.Label(self.main_frame, text="Ready to connect")
        self.status_label.grid(row=4, column=0, pady=5, sticky='w')

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def add_channel_row(self, platform=None, name=None):
        row_idx = len(self.channels)
        row_frame = ttk.Frame(self.channels_frame)
        row_frame.grid(row=row_idx, column=0, sticky='ew', pady=5)
        row_frame.columnconfigure(2, weight=1)

        remove_btn = ttk.Button(row_frame, text="-", width=3,
                                command=lambda idx=row_idx: self.remove_channel_row(idx))
        remove_btn.grid(row=0, column=0, padx=(0, 5))

        platform_var = tk.StringVar(value=platform if platform else "")
        platform_combo = ttk.Combobox(row_frame, textvariable=platform_var,
                                      values=["twitch", "youtube", "tiktok"], width=10, state="readonly")
        platform_combo.grid(row=0, column=1, padx=5)

        name_var = tk.StringVar(value=name if name else "")
        name_entry = ttk.Entry(row_frame, textvariable=name_var)
        name_entry.grid(row=0, column=2, padx=5, sticky='ew')

        channel_data = {
            "frame": row_frame,
            "remove_btn": remove_btn,
            "platform": platform_var,
            "platform_combo": platform_combo,
            "name": name_var,
            "name_entry": name_entry
        }

        self.channels.append(channel_data)
        self.update_indices()

    def remove_channel_row(self, idx):
        if idx < 0 or idx >= len(self.channels):
            return
        self.channels[idx]["frame"].destroy()
        self.channels.pop(idx)
        self.update_indices()

    def update_indices(self):
        for i, channel in enumerate(self.channels):
            channel["frame"].grid_configure(row=i)
            channel["remove_btn"].configure(command=lambda idx=i: self.remove_channel_row(idx))

    def start_chat_monitoring(self):
        global stop_event
        stop_event.clear()
        save_config(self.channels)

        valid_channels = []
        for channel in self.channels:
            platform = channel["platform"].get()
            name = channel["name"].get()
            if platform and name:
                valid_channels.append((platform, name))

        if not valid_channels:
            messagebox.showwarning("Warning", "Please add at least one channel to monitor.")
            return

        create_chat_window(self.root)

        loop = asyncio.new_event_loop()

        tasks = []
        tiktok_threads = []

        for platform, name in valid_channels:
            if platform == "twitch":
                tasks.append(listen_twitch(name, add_chat_message))
            elif platform == "youtube":
                tasks.append(listen_youtube(name, add_chat_message))
            elif platform == "tiktok":
                thread = run_tiktok_listener(name, add_chat_message)
                tiktok_threads.append(thread)

        if tasks:
            self.status_label.config(text="Connected! Monitoring chats...")
            threading.Thread(target=self.run_asyncio_tasks, args=(loop, tasks), daemon=True).start()

    def run_asyncio_tasks(self, loop, tasks):
        try:
            asyncio.set_event_loop(loop)
            future = asyncio.gather(*tasks)
            loop.run_until_complete(future)
        except Exception as e:
            add_chat_message(f"Error in chat monitoring: {e}")
        finally:
            try:
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                loop.close()
            except Exception:
                pass

    def on_close(self):
        save_config(self.channels)
        global stop_event
        stop_event.set()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = ChatAggregatorGUI(root)
    root.mainloop()
