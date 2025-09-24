import os
from pyrogram import Client
from dotenv import load_dotenv

load_dotenv()

# Environment variables with validation
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
SPONSOR_CHANNEL = os.getenv("SPONSOR_CHANNEL")
DATABASE_CHANNEL = os.getenv("DATABASE_CHANNEL")
MAIN_CHANNEL = os.getenv("MAIN_CHANNEL")
ADMINS_STR = os.getenv("ADMINS", "")

# Validate required variables
if not all([API_ID, API_HASH, BOT_TOKEN]):
    raise ValueError("Missing required environment variables: API_ID, API_HASH, BOT_TOKEN")

# Convert types
try:
    API_ID = int(API_ID)
except ValueError:
    raise ValueError("API_ID must be a valid integer")

ADMINS = []
if ADMINS_STR:
    try:
        ADMINS = list(map(int, ADMINS_STR.split(",")))
    except ValueError:
        raise ValueError("ADMINS must be comma-separated integers")

# Clean channel usernames (remove @ if present)
if SPONSOR_CHANNEL:
    SPONSOR_CHANNEL = SPONSOR_CHANNEL.lstrip('@')
if DATABASE_CHANNEL:
    DATABASE_CHANNEL = DATABASE_CHANNEL.lstrip('@')
if MAIN_CHANNEL:
    MAIN_CHANNEL = MAIN_CHANNEL.lstrip('@')

# Single app client for the entire application
app = Client("tv_series_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
