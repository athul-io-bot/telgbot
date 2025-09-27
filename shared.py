import os
from pyrogram import Client
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

load_dotenv()

# Environment variables (with safe casting & validation)
API_ID = os.getenv("API_ID")
if API_ID is not None and API_ID != "":
    try:
        API_ID = int(API_ID)
    except ValueError:
        logger.error("API_ID must be an integer. Got: %r", API_ID)
        raise

API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

SPONSOR_CHANNEL = os.getenv("SPONSOR_CHANNEL")
DATABASE_CHANNEL = os.getenv("DATABASE_CHANNEL")
MAIN_CHANNEL = os.getenv("MAIN_CHANNEL")

# ADMINS: comma separated user ids
ADMINS_STR = os.getenv("ADMINS", "")
ADMINS = []
if ADMINS_STR:
    try:
        ADMINS = [int(x.strip()) for x in ADMINS_STR.split(",") if x.strip()]
    except Exception as e:
        logger.error("ADMINS must be comma-separated integers. Error: %s", e)
        raise

# normalize channel identifiers (strip leading @ or convert to int when possible)
def _normalize_channel(val):
    if not val:
        return None
    val = val.strip()
    if val.startswith("@"):
        val = val.lstrip("@")
    try:
        return int(val)
    except Exception:
        return val  # keep as username string without @

if SPONSOR_CHANNEL:
    SPONSOR_CHANNEL = _normalize_channel(SPONSOR_CHANNEL)
if DATABASE_CHANNEL:
    DATABASE_CHANNEL = _normalize_channel(DATABASE_CHANNEL)
if MAIN_CHANNEL:
    MAIN_CHANNEL = _normalize_channel(MAIN_CHANNEL)

# Create app instance (pyrogram expects api_id to be int or None)
app = Client("tv_series_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
