import os
import sys
import logging
from dotenv import load_dotenv

load_dotenv()

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True)

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

class TokenRedactingFormatter(logging.Formatter):
    """Custom formatter that censors the bot token from all log messages and tracebacks."""
    def __init__(self, fmt=None, datefmt=None, token=""):
        super().__init__(fmt, datefmt)
        self.token = token

    def format(self, record: logging.LogRecord) -> str:
        formatted = super().format(record)
        if self.token:
            formatted = formatted.replace(self.token, "[BOT_TOKEN_HIDDEN]")
        return formatted


# Configure root logging with token redaction
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.handlers.clear()

handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(
    TokenRedactingFormatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        token=BOT_TOKEN
    )
)
root_logger.addHandler(handler)

# Silence verbose HTTP requests that expose the bot token
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
# Silence routine background job execution logs
logging.getLogger("apscheduler").setLevel(logging.WARNING)

# Global unhandled exception hook to censor token even if Python crashes
def safe_excepthook(exc_type, exc_val, exc_tb):
    import traceback
    lines = traceback.format_exception(exc_type, exc_val, exc_tb)
    text = "".join(lines)
    if BOT_TOKEN:
        text = text.replace(BOT_TOKEN, "[BOT_TOKEN_HIDDEN]")
    sys.stderr.write(text)

sys.excepthook = safe_excepthook

logger = logging.getLogger("BlinModBot")
