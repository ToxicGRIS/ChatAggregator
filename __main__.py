import asyncio
import json
import os
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext
import websockets
from datetime import datetime
from tkinter import messagebox
import tracemalloc
import pytchat
tracemalloc.start()

# Function to load API keys from file
def load_api_keys(filename="api_keys.json"):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            keys = json.load(f)
        return keys
    except Exception as e:
        print(f"Error loading API keys: {e}")
        return {}

# Load keys
api_keys = load_api_keys()
TWITCH_OAUTH_TOKEN = api_keys.get("twitch", "")
TWITCH_NICKNAME = api_keys.get("twitch_nickname", "your_twitch_username")

# Twitch IRC WebSocket URL
TWITCH_IRC_URL = "wss://irc-ws.chat.twitch.tv:443"

# Global variable to store the chat output window
chat_output = None
stop_event = threading.Event()

# -------------------------------
# Twitch Listener (via IRC WebSocket)
# -------------------------------
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
                        output_callback(f"[{timestamp}][🟣 Twitch] {username}: {chat_message}")
    except Exception as e:
        output_callback(f"Error in Twitch listener: {e}")

# -------------------------------
# YouTube Listener using pytchat
# -------------------------------
async def listen_youtube(video_id, output_callback):
    try:
        chat = pytchat.create(video_id=video_id, interruptable=False)
        output_callback(f"✅ Connected to YouTube chat for video: {video_id}")
        while chat.is_alive() and not stop_event.is_set():
            for c in chat.get().sync_items():
                timestamp = datetime.now().strftime("%H:%M:%S")
                output_callback(f"[{timestamp}][🔴 YouTube] {c.author.name}: {c.message}")
            await asyncio.sleep(1)
    except Exception as e:
        output_callback(f"Error in YouTube listener: {e}")

# -------------------------------
# TikTok Listener (using TikTokLive library)
# -------------------------------
def listen_tiktok(username, output_callback):
    try:
        from TikTokLive import TikTokLiveClient
        from TikTokLive.events import ConnectEvent, CommentEvent
        
        client = TikTokLiveClient(unique_id=username)

        async def on_comment(event: CommentEvent):
            if stop_event.is_set():
                await client.close()
                return
            timestamp = datetime.now().strftime("%H:%M:%S")
            output_callback(f"[{timestamp}][⚪ TikTok] {event.user.nickname}: {event.comment}")

        client.add_listener(CommentEvent, on_comment)

        output_callback(f"✅ Connected to TikTok chat for user: {username}")
        client.run()
    except Exception as e:
        output_callback(f"Error in TikTok listener: {e}")

def run_tiktok_listener(username, output_callback):
    thread = threading.Thread(target=listen_tiktok, args=(username, output_callback), daemon=True)
    thread.start()
    return thread

# Function to save channels configuration
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

# Function to load channels configuration
def load_config():
    try:
        if os.path.exists("chat_config.json"):
            with open("chat_config.json", "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading configuration: {e}")
    return []

# Apply dark mode style to ttk elements
def set_dark_theme(root):
    # Create a dark theme style
    style = ttk.Style()
    style.theme_use('clam')

    # Configure colors
    style.configure('TFrame', background='#2d2d2d')
    style.configure('TLabel', background='#2d2d2d', foreground='#ffffff')
    style.configure('TButton', background='#444444', foreground='#ffffff')
    style.configure('TEntry', fieldbackground='#3d3d3d', foreground='#ffffff')
    style.map('TButton',
              background=[('active', '#555555'), ('pressed', '#333333')],
              foreground=[('active', '#ffffff'), ('pressed', '#dddddd')])

    # Configure combobox
    style.configure('TCombobox',
                    fieldbackground='#3d3d3d',
                    background='#444444',
                    foreground='#ffffff',
                    arrowcolor='#ffffff')
    style.map('TCombobox',
              fieldbackground=[('readonly', '#3d3d3d')],
              selectbackground=[('readonly', '#555555')],
              selectforeground=[('readonly', '#ffffff')])

    # Configure scrollbar
    style.configure('Vertical.TScrollbar',
                    background='#444444',
                    arrowcolor='#ffffff',
                    troughcolor='#2d2d2d')

    # Set window background color
    root.configure(bg='#2d2d2d')

# Create the chat output window
def create_chat_window(root):
    global chat_output

    chat_window = tk.Toplevel(root)
    chat_window.title("Chat Messages")
    chat_window.geometry("800x600")
    chat_window.configure(bg='#2d2d2d')
    chat_window.protocol("WM_DELETE_WINDOW", lambda: on_chat_window_close(chat_window))

    # Make the window resizable
    chat_window.columnconfigure(0, weight=1)
    chat_window.rowconfigure(0, weight=1)

    # Create the scrolled text widget for output
    chat_output = scrolledtext.ScrolledText(chat_window, bg='#1e1e1e', fg='#ffffff', font=('Consolas', 10))
    chat_output.grid(row=0, column=0, sticky='nsew', padx=10, pady=10)

    # Customize the tag colors for different platforms
    chat_output.tag_config('twitch', foreground='#9146FF')
    chat_output.tag_config('youtube', foreground='#FF0000')
    chat_output.tag_config('tiktok', foreground='#00F2EA')
    chat_output.tag_config('info', foreground='#4CAF50')
    chat_output.tag_config('error', foreground='#F44336')

    # Button to clear chat
    clear_button = ttk.Button(chat_window, text="Clear Chat", command=lambda: chat_output.delete(1.0, tk.END))
    clear_button.grid(row=1, column=0, pady=10)

    return chat_window

def on_chat_window_close(window):
    global stop_event
    stop_event.set()
    window.destroy()

# Function to add a message to the chat output window
def add_chat_message(message):
    if chat_output is None:
        return

    # Determine the tag based on the message content
    tag = 'info'
    if '[🟣 Twitch]' in message:
        tag = 'twitch'
    elif '[🔴 YouTube]' in message:
        tag = 'youtube'
    elif '[⚪ TikTok]' in message:
        tag = 'tiktok'
    elif 'Error' in message:
        tag = 'error'

    # Insert the message with the appropriate tag
    chat_output.insert(tk.END, message + '\n', tag)
    chat_output.see(tk.END)  # Scroll to the bottom

# Main GUI class
class ChatAggregatorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Chat Aggregator")
        self.root.geometry("600x400")

        # Apply dark theme
        set_dark_theme(self.root)

        # Make the window resizable
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        # Create a main frame
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.grid(row=0, column=0, sticky='nsew', padx=20, pady=20)
        self.main_frame.columnconfigure(0, weight=1)

        # Title label
        title_label = ttk.Label(self.main_frame, text="Chat Aggregator", font=('Arial', 16))
        title_label.grid(row=0, column=0, columnspan=3, pady=10, sticky='w')

        # Channels frame
        self.channels_frame = ttk.Frame(self.main_frame)
        self.channels_frame.grid(row=1, column=0, sticky='nsew', pady=10)
        self.channels_frame.columnconfigure(1, weight=1)

        # List to store channel entries
        self.channels = []

        # Add initial channel if config exists, otherwise add an empty one
        config = load_config()
        if config:
            for channel_config in config:
                self.add_channel_row(platform=channel_config.get("platform"), name=channel_config.get("name"))
        else:
            self.add_channel_row()

        # Add button for new channels
        self.add_button = ttk.Button(self.main_frame, text="Add Channel", command=self.add_channel_row)
        self.add_button.grid(row=2, column=0, pady=10, sticky='w')

        # Confirm button
        self.confirm_button = ttk.Button(self.main_frame, text="Connect", command=self.start_chat_monitoring)
        self.confirm_button.grid(row=3, column=0, pady=10, sticky='w')

        # Status label
        self.status_label = ttk.Label(self.main_frame, text="Ready to connect")
        self.status_label.grid(row=4, column=0, pady=5, sticky='w')

        # Save configuration on window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def add_channel_row(self, platform=None, name=None):
        # Create a new row index
        row_idx = len(self.channels)

        # Create a frame for this row
        row_frame = ttk.Frame(self.channels_frame)
        row_frame.grid(row=row_idx, column=0, sticky='ew', pady=5)
        row_frame.columnconfigure(2, weight=1)

        # Remove button
        remove_btn = ttk.Button(row_frame, text="-", width=3,
                                command=lambda idx=row_idx: self.remove_channel_row(idx))
        remove_btn.grid(row=0, column=0, padx=(0, 5))

        # Platform selection
        platform_var = tk.StringVar(value=platform if platform else "")
        platform_combo = ttk.Combobox(row_frame, textvariable=platform_var, values=["twitch", "youtube", "tiktok"], width=10)
        platform_combo.grid(row=0, column=1, padx=5)
        platform_combo.state(['readonly'])

        # Channel name entry
        name_var = tk.StringVar(value=name if name else "")
        name_entry = ttk.Entry(row_frame, textvariable=name_var)
        name_entry.grid(row=0, column=2, padx=5, sticky='ew')

        # Store the widgets and variables
        channel_data = {
            "frame": row_frame,
            "remove_btn": remove_btn,
            "platform": platform_var,
            "platform_combo": platform_combo,
            "name": name_var,
            "name_entry": name_entry,
            "index": row_idx
        }

        self.channels.append(channel_data)

        # Update all indices
        self.update_indices()

    def remove_channel_row(self, idx):
        if idx >= len(self.channels) or idx < 0:
            return

        # Remove from GUI
        self.channels[idx]["frame"].destroy()

        # Remove from our list
        self.channels.pop(idx)

        # Update all indices
        self.update_indices()

    def update_indices(self):
        for i, channel in enumerate(self.channels):
            channel["index"] = i
            # Update the command of the remove button
            channel["remove_btn"].configure(command=lambda idx=i: self.remove_channel_row(idx))

    def start_chat_monitoring(self):
        # Reset the stop event
        global stop_event
        stop_event.clear()

        # Save the current configuration
        save_config(self.channels)

        # Check if we have any channels configured
        valid_channels = []
        for channel in self.channels:
            platform = channel["platform"].get()
            name = channel["name"].get()
            if platform and name:
                valid_channels.append((platform, name))

        if not valid_channels:
            messagebox.showwarning("Warning", "Please add at least one channel to monitor.")
            return

        # Create the chat window
        chat_window = create_chat_window(self.root)

        # Start tasks for each platform
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

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
            # Set the event loop for this thread
            asyncio.set_event_loop(loop)

            # Create a gathering task
            future = asyncio.gather(*tasks)

            # Run the loop until the future is complete
            loop.run_until_complete(future)
        except Exception as e:
            add_chat_message(f"Error in chat monitoring: {e}")
        finally:
            try:
                # Clean up any pending tasks
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()

                # Run the event loop until all tasks are cancelled
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))

                loop.close()
            except Exception:
                pass

    def on_close(self):
        # Save configuration
        save_config(self.channels)

        # Stop all tasks
        global stop_event
        stop_event.set()

        # Close the window
        self.root.destroy()

# Main entry point
if __name__ == "__main__":
    root = tk.Tk()
    app = ChatAggregatorGUI(root)
    root.mainloop()