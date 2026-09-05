import os
import sys
import logging
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID_RAW = os.getenv("ADMIN_IDS", os.getenv("ADMIN_ID", "")).strip()
DB_PATH = os.getenv("DB_PATH", "bot_database.db").strip()

if not BOT_TOKEN:
    logging.critical("ERROR: BOT_TOKEN is missing in environment variables or .env file!")

ADMIN_IDS = set()
if ADMIN_ID_RAW:
    for item in ADMIN_ID_RAW.split(","):
        item = item.strip()
        if item.isdigit():
            ADMIN_IDS.add(int(item))

# Backward compatibility with single ADMIN_ID
ADMIN_ID = next(iter(ADMIN_IDS)) if ADMIN_IDS else 0

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
# Silence verbose HTTP requests from httpx that expose the bot token
logging.getLogger("httpx").setLevel(logging.WARNING)
# Silence routine background job execution logs
logging.getLogger("apscheduler").setLevel(logging.WARNING)

logger = logging.getLogger("BlinModBot")
