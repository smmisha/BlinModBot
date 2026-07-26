import os
import sys
import logging
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID_RAW = os.getenv("ADMIN_ID", "").strip()
DB_PATH = os.getenv("DB_PATH", "bot_database.db").strip()

if not BOT_TOKEN:
    logging.critical("ERROR: BOT_TOKEN is missing in environment variables or .env file!")

try:
    ADMIN_ID = int(ADMIN_ID_RAW) if ADMIN_ID_RAW else 0
except ValueError:
    logging.critical("ERROR: ADMIN_ID must be a valid integer user ID!")
    ADMIN_ID = 0

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("BlinModBot")
