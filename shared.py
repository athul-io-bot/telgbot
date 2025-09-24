import os
from pyrogram import Client
from dotenv import load_dotenv

load_dotenv()

# Environment variables
API_ID = int(os.getenv("API_ID")) if os.getenv("API_ID") else 0
API_HASH = os.getenv("API_HASH") if os.getenv("API_HASH") else ""
BOT_TOKEN = os.getenv("BOT_TOKEN") if os.getenv("BOT_TOKEN") else ""
SPONSOR_CHANNEL = os.getenv("SPONSOR_CHANNEL") if os.getenv("SPONSOR_CHANNEL") else ""
DATABASE_CHANNEL = os.getenv("DATABASE_CHANNEL") if os.getenv("DATABASE_CHANNEL") else ""
MAIN_CHANNEL = os.getenv("MAIN_CHANNEL") if os.getenv("MAIN_CHANNEL") else ""
ADMINS = list(map(int, os.getenv("ADMINS").split(","))) if os.getenv("ADMINS") else []

# Single app client for the entire application
app = Client("tv_series_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
