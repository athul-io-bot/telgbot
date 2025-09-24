import os
from pyrogram import Client
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

load_dotenv()

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
SPONSOR_CHANNEL = os.getenv("SPONSOR_CHANNEL")
DATABASE_CHANNEL = os.getenv("DATABASE_CHANNEL")
MAIN_CHANNEL = os.getenv("MAIN_CHANNEL")
ADMINS_STR = os.getenv("ADMINS", "")

# Validate required variables and improve error message
missing_vars = [var for var in ["API_ID", "API_HASH", "BOT_TOKEN"] if not globals()[var]]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

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
if not ADMINS:
    logger.warning("ADMINS list is empty. No one can run admin commands.")

if SPONSOR_CHANNEL:
    SPONSOR_CHANNEL = SPONSOR_CHANNEL.lstrip('@')
if DATABASE_CHANNEL:
    DATABASE_CHANNEL = DATABASE_CHANNEL.lstrip('@')
if MAIN_CHANNEL:
    MAIN_CHANNEL = MAIN_CHANNEL.lstrip('@')

app = Client(
    "tvseriesbot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    plugins=dict(root="plugins")
)