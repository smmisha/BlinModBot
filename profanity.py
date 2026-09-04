import re
import unicodedata
from typing import List, Tuple, Optional, Set

# Explicit Unicode homoglyph mapping (Latin/digits/symbols -> Cyrillic Unicode codepoints)
HOMOGLYPHS = {
    '0': '\u043e',  # о
    '1': '\u0438',  # и
    '3': '\u0437',  # з
    '4': '\u0430',  # а
    '5': 's',
    '6': '\u0431',  # б
    '7': '\u0442',  # т
    '8': '\u0432',  # в
    '@': '\u0430',  # а
    '$': 's',
    '!': '\u0438',  # и
    'a': '\u0430',  # а
    'b': '\u0431',  # б
    'c': '\u0441',  # с
    'e': '\u0435',  # е
    'h': '\u043d',  # н
    'k': '\u043a',  # к
    'm': '\u043c',  # м
    'o': '\u043e',  # о
    'p': '\u0440',  # р
    't': '\u0442',  # т
    'u': '\u0443',  # у
    'x': '\u0445',  # х
    'y': '\u0443',  # у
}

# Clean words whitelist to prevent false positives when stems match harmless words
SAFE_WORDS_WHITELIST: Set[str] = {
    # Words with "бля" / "блят" / "бляд"
    "употреблять", "употребления", "употреблении", "употребление",
    "оскорблять", "оскорбление", "оскорблений", "оскорбления",
    "рублях", "рублям", "рубля",
    "потреблять", "потребление", "потребности",
    "углублять", "углубление", "расслаблять", "расслабление",
    "влюблять", "влюбленность", "размышлять", "размышления",
    "позволять", "отправлять", "отправление", "поздравлять", "поздравления",
    "проявлять", "проявление", "направлять", "направление",
    "оформлять", "оформление", "вставлять", "представлять", "представление",
    "заставлять", "доставлять", "доставка", "составлять", "составление",
    "ослаблять", "ослабление", "закупках", "возобновлять", "укреплять",
    "заменять", "замещать", "зачислять", "зачисление",
    # Words with "сук"
    "рисунок", "рисунка", "рисунки", "рисунках", "посуда", "посуду", "посуде",
    "сукно", "сукцессия", "рассудок", "рассудка", "рассуждения", "рассуждать",
    # Words with "хер"
    "парикмахер", "парикмахерская", "сверхестественный", "сверхвысокий",
    # Words with "еб"
    "колебание", "колебания", "колебаний", "колебаться", "потребность", "потребности",
    "хлеб", "хлеба", "хлебушек", "жребий", "жребия", "серебро", "стебель", "гребень",
    "тебе", "себе", "мебель"
}


def normalize_text(raw_text: str) -> str:
    """
    Normalizes text for profanity checking:
    1. Converts to lowercase and normalizes Unicode (NFC).
    2. Replaces numbers & homoglyphs with visual Cyrillic equivalents.
    3. Removes obfuscating punctuation inside words (*, ., -, _, etc.).
    4. Removes single spaces between individual letters (e.g. 'п и з д а' -> 'пизда').
    """
    if not raw_text:
        return ""

    text = unicodedata.normalize('NFC', raw_text.lower())

    # Step 1: Replace homoglyphs and leet-speak digits/symbols
    converted = [HOMOGLYPHS.get(char, char) for char in text]
    text = "".join(converted)

    # Step 2: Remove spaces between single letters ('п и з д а' -> 'пизда')
    text = re.sub(r'(?<=\b[а-яa-z])\s+(?=[а-яa-z]\b)', '', text, flags=re.IGNORECASE)

    # Step 3: Remove obfuscating punctuation inside words (like p.i.z.d.a or p*i*z*d*a or p-i-z-d-a)
    text = re.sub(r'(?<=[а-яa-z0-9])[.\*_\-~`\'"+=\\/#|]+(?=[а-яa-z0-9])', '', text, flags=re.IGNORECASE)

    return text


def contains_profanity(raw_text: str, profanity_list: List[str]) -> Tuple[bool, Optional[str]]:
    """
    Checks if raw_text contains profanity using the normalized profanity_list.
    Returns (True, matched_profanity_stem) if profanity is found, else (False, None).
    """
    if not raw_text or not profanity_list:
        return False, None

    normalized = normalize_text(raw_text)
    words = re.findall(r'[а-яa-z0-9]+', normalized)

    cleaned_words = [w for w in words if w not in SAFE_WORDS_WHITELIST]
    compact_text = "".join(cleaned_words)

    for stem in profanity_list:
        stem_norm = normalize_text(stem).strip()
        if not stem_norm:
            continue

        # Rule 1: Substring match within cleaned words
        for word in cleaned_words:
            if word in SAFE_WORDS_WHITELIST:
                continue

            if stem_norm in word:
                return True, stem_norm

        # Rule 2: Search in compact text (handles cases like 'б_л_я_т_ь' after normalization)
        if len(stem_norm) >= 4 and stem_norm in compact_text:
            return True, stem_norm

    return False, None


# In-memory profanity words cache
_words_cache: Optional[List[str]] = None


def get_cached_words() -> Optional[List[str]]:
    """Returns the in-memory cached list of profanity words, or None if not initialized."""
    return _words_cache


def set_cached_words(words: List[str]) -> None:
    """Sets the in-memory cached list of profanity words."""
    global _words_cache
    _words_cache = list(words)


def add_cached_word(word: str) -> None:
    """Adds a single word to the in-memory cache."""
    global _words_cache
    if _words_cache is not None and word not in _words_cache:
        _words_cache.append(word)


def remove_cached_word(word: str) -> None:
    """Removes a single word from the in-memory cache."""
    global _words_cache
    if _words_cache is not None and word in _words_cache:
        _words_cache.remove(word)


def invalidate_cache() -> None:
    """Clears the in-memory cache."""
    global _words_cache
    _words_cache = None
