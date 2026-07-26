import aiosqlite
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

logger = logging.getLogger("BlinModBot")

# Initial comprehensive seed list of Russian profanity roots/stems and explicit words
DEFAULT_SEED_WORDS = [
    # Корень "хуй" и производные
    "хуй", "хуя", "хуе", "хуи", "хул", "поху", "охуе", "ниху", "наху", "доху", "отху", "заху", "переху",
    # Корень "пизд" и производные
    "пизд", "пизж", "распизд", "опизд", "допизд", "пиздец", "пизда", "пиздо",
    # Оскорбления на "пид"
    "пидор", "пидар", "пидра", "пидорас", "пидарас", "педигри",
    # Корень "еб" и производные
    "еба", "ебн", "ебу", "ебл", "ебт", "ебат", "ебать", "выеб", "заеб", "наеб", "доеб", "проеб", "приеб",
    "подъеб", "подъеб", "уеб", "съеб", "долбоеб", "долбоёб", "ебан", "ебанны", "ебану", "ебуч",
    # Блядь / бля
    "бля", "блят", "бляд", "блять", "бляха",
    # Сука / гнида / мудак / залупа / гондон
    "мудак", "мудил", "залуп", "гондон", "гандон", "шлюх", "проститут", "манда", "мандо",
    "хер", "херо", "похер", "охера", "нихера", "нахера",
    "дроч", "задрот"
]


async def init_db(db_path: str) -> bool:
    """Initialize database tables and seed words if empty. Returns True if success."""
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS words (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    word TEXT UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS violations (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    violation_count INTEGER DEFAULT 0,
                    last_violation_at TIMESTAMP,
                    banned_until TIMESTAMP
                );
            """)
            await db.commit()

            # Check if words table is empty and seed it
            async with db.execute("SELECT COUNT(*) FROM words") as cursor:
                count = (await cursor.fetchone())[0]

            if count == 0:
                logger.info("Seeding database with default profanity dictionary...")
                for word in DEFAULT_SEED_WORDS:
                    await db.execute(
                        "INSERT OR IGNORE INTO words (word) VALUES (?)",
                        (word.strip().lower(),)
                    )
                await db.commit()
                logger.info(f"Seeded {len(DEFAULT_SEED_WORDS)} default words into dictionary.")

        return True
    except Exception as e:
        logger.critical(f"Database initialization failed: {e}", exc_info=True)
        return False


async def get_words(db_path: str) -> List[str]:
    """Retrieve all profanity words from DB."""
    async with aiosqlite.connect(db_path) as db:
        async with db.execute("SELECT word FROM words ORDER BY word ASC") as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]


async def add_word(db_path: str, word: str) -> bool:
    """Add a new word/stem to profanity dictionary."""
    clean_word = word.strip().lower()
    if not clean_word:
        return False
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute("INSERT INTO words (word) VALUES (?)", (clean_word,))
            await db.commit()
            return True
    except aiosqlite.IntegrityError:
        return False  # Already exists


async def remove_word(db_path: str, word: str) -> bool:
    """Remove a word/stem from profanity dictionary."""
    clean_word = word.strip().lower()
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("DELETE FROM words WHERE word = ?", (clean_word,))
        await db.commit()
        return cursor.rowcount > 0


async def get_user_violation(db_path: str, user_id: int) -> Optional[Dict[str, Any]]:
    """Fetch user violation details."""
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT user_id, username, violation_count, last_violation_at, banned_until FROM violations WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None


async def record_violation(
    db_path: str,
    user_id: int,
    username: Optional[str],
    banned_until: Optional[datetime] = None
) -> int:
    """
    Record a violation for user.
    Increments count, updates last_violation_at and banned_until.
    Returns the new violation_count.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    banned_until_iso = banned_until.isoformat() if banned_until else None

    async with aiosqlite.connect(db_path) as db:
        # Check current count
        async with db.execute("SELECT violation_count FROM violations WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()

        if row:
            new_count = row[0] + 1
            await db.execute(
                """
                UPDATE violations
                SET username = ?,
                    violation_count = ?,
                    last_violation_at = ?,
                    banned_until = COALESCE(?, banned_until)
                WHERE user_id = ?
                """,
                (username, new_count, now_iso, banned_until_iso, user_id)
            )
        else:
            new_count = 1
            await db.execute(
                """
                INSERT INTO violations (user_id, username, violation_count, last_violation_at, banned_until)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, username, new_count, now_iso, banned_until_iso)
            )

        await db.commit()
        return new_count


async def set_banned_until(db_path: str, user_id: int, banned_until: datetime):
    """Set banned_until for user."""
    banned_until_iso = banned_until.isoformat()
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "UPDATE violations SET banned_until = ? WHERE user_id = ?",
            (banned_until_iso, user_id)
        )
        await db.commit()


async def unban_user_db(db_path: str, user_id: int) -> bool:
    """Clear banned_until state for user in DB."""
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "UPDATE violations SET banned_until = NULL WHERE user_id = ?",
            (user_id,)
        )
        await db.commit()
        return cursor.rowcount > 0


async def reset_user_violation(db_path: str, user_id: int):
    """Reset violation count to 0 for a user."""
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "UPDATE violations SET violation_count = 0 WHERE user_id = ?",
            (user_id,)
        )
        await db.commit()


async def get_expired_bans(db_path: str) -> List[Dict[str, Any]]:
    """Retrieve users whose ban duration has expired."""
    now_iso = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT user_id, username, banned_until FROM violations WHERE banned_until IS NOT NULL AND banned_until <= ?",
            (now_iso,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_inactive_violators(db_path: str, days: int = 30) -> List[Dict[str, Any]]:
    """Retrieve users with violation_count > 0 who haven't violated in `days` days."""
    now_dt = datetime.now(timezone.utc)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT user_id, username, last_violation_at, violation_count FROM violations WHERE violation_count > 0 AND last_violation_at IS NOT NULL"
        ) as cursor:
            rows = await cursor.fetchall()
            inactive = []
            for row in rows:
                row_dict = dict(row)
                last_viol = datetime.fromisoformat(row_dict["last_violation_at"])
                # Compare elapsed days
                if (now_dt - last_viol).days >= days:
                    inactive.append(row_dict)
            return inactive
