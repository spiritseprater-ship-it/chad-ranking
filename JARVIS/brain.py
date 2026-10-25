"""
brain.py - JARVIS command understanding.

Responsibilities
----------------
* Turn one piece of recognized speech into a *canonical command* plus slots.
* Understand English, Hindi, Hinglish and common Indian English pronunciations
  without relying on exact string equality.
* Never execute anything: ``brain`` is pure language understanding.  Execution
  lives in ``actions.py``.

Text pipeline
-------------
1. lower-casing, accent folding, Devanagari digits -> ascii digits
2. Devanagari (Hindi) words -> English keywords
3. Hinglish / Hindi words -> English keywords
4. Devanagari number words -> digits
5. assistant name + filler removal, trailing polite imperative removal
6. scored matching against the command specification table

Every :class:`CommandSpec` carries ``patterns`` (regexes searched on the
normalized text), ``keywords`` (fallback group), ``slot_patterns`` (how to pull
slots out) and ``slot_noise`` (words to drop from a slot).

Nothing here imports PySide6 / pyautogui / speech libraries, so the module is
fully unit-testable on Linux without a microphone.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

__all__ = [
    "ParsedCommand",
    "CommandSpec",
    "Brain",
    "parse_number",
    "normalize_text",
    "KNOWN_COMMANDS",
    "strip_noise",
]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _sub_all(text: str, mapping: Dict[str, str]) -> str:
    """Replace whole-word keys of ``mapping`` with their values.

    Keys are applied longest-first so ``"khalo"`` is not eaten by ``"kha"``.
    """
    if not mapping:
        return text
    keys = sorted(mapping, key=len, reverse=True)
    # ASCII boundaries rather than \b: Devanagari vowel signs are combining
    # marks (\W in Python) and would break a \b based look-ahead.
    pattern = re.compile(
        r"(?<![A-Za-z0-9])(" + "|".join(re.escape(k) for k in keys) + r")(?![A-Za-z0-9])",
        re.IGNORECASE,
    )
    return pattern.sub(lambda m: mapping[m.group(1).lower()], text)


def strip_noise(text: str, words: Sequence[str]) -> str:
    """Remove ``words`` (case-insensitive, whole-word) from ``text``.

    Repetition is allowed so ``"search on chrome"`` -> ``""`` even when the
    same word appears more than once.
    """
    if not text or not words:
        return (text or "").strip()
    pattern = re.compile(
        r"\s*(?:\b(?:" + "|".join(re.escape(w) for w in words) + r")\b\s*)+",
        re.IGNORECASE,
    )
    out = pattern.sub(" ", text)
    return re.sub(r"\s+", " ", out).strip(" .,!?;:")


# Filler words that add nothing to a command and hurt coverage scoring.
_FILLERS: Tuple[str, ...] = (
    r"\bplease\b", r"\bplzz?\b", r"\bhey\b", r"\bhi\b", r"\bhello\b",
    r"\bcan\s+you\b", r"\bcould\s+you\b", r"\bwould\s+you\b", r"\bwill\s+you\b",
    r"\bcan\s+we\b", r"\blets?\b", r"\blet'?s\b", r"\bjust\b",
    r"\bi\s+want\s+to\b", r"\bi\s+need\s+to\b", r"\bi'?d\s+like\b",
    r"\bkind(?:ly)?\b", r"\bbro\b", r"\bbhai\b", r"\bsir\b", r"\bmadam\b",
    r"\bok(?:ay)?\b", r"\barey\b", r"\bhaan\b", r"\bnahi\b",
    r"\bthe\b", r"\bmy\b", r"\band\b", r"\bto\b", r"\bme\b",
)

# Trailing polite imperative: "karo", "keejiye", "kar", "do" (last word only).
_TRAILING_IMPERATIVE = re.compile(
    r"\s+(?:karo|keejiye|kejiye|kiye|kar|do)\s*$", re.IGNORECASE
)

# Hinglish / Hindi words -> English keywords.  Keep the dictionary tidy: one
# spelling per key, most specific first.
_HINGLISH: Dict[str, str] = {
    # "open" family
    "khulate": "open", "khula": "open", "khali": "open", "khul": "open",
    "kholo": "open", "khulo": "open", "khola": "open", "kholate": "open",
    # "close" family
    "bandh": "close", "bandhdo": "close", "bandh": "close", "band": "close",
    # "show" family
    "dikhlao": "show", "dikhao": "show", "dikha": "show", "dikhana": "show",
    "dikhao": "show", "dakhao": "show", "dakha": "show", "dekhao": "show",
    "dekha": "show",
    # "do / make" family
    "karo": "do", "kar": "do", "keejiye": "do", "kejiye": "do", "kijiye": "do",
    "karke": "do", "kiya": "did",
    # "search"
    "khojiye": "search", "khoj": "search", "talak": "search",
    # direction words
    "uthao": "up", "uthan": "up", "uthay": "up", "uthe": "up", "upar": "up",
    "uncha": "up",
    "nico": "down", "nicha": "down", "nichay": "down", "neeche": "down",
    "niche": "down",
    "aage": "forward", "age": "forward", "agla": "forward",
    "piche": "back", "peeche": "back", "ghum": "back", "ghume": "back",
    "ghumao": "back", "wapas": "back",
    # misc verbs / prepositions
    "chalo": "start", "chal": "start", "chaliye": "start",
    "batado": "tell", "batao": "tell", "bata": "tell",
    "suno": "listen", "lena": "take", "lelo": "take", "le": "take",
    "khinch": "capture", "khincho": "capture",
    "dekho": "look", "dekh": "look",
    "kya hai": "is", "kya": "what", "hai": "is",
    "par": "on", "per": "on", "pe": "on", "mein": "in", "main": "in",
    "ko": "to", "ke": "of", "ki": "of", "ka": "of",
    # nouns
    "aawaj": "volume", "awaj": "volume", "swar": "volume",
    "file": "file", "files": "file", "folder": "folder", "folders": "folder",
    "explorer": "explorer", "time": "time", "waqt": "time", "date": "date",
    "tarik": "date", "tarikh": "date", "tarif": "date",
    "tareek": "date", "taarikh": "date",
    "screenshot": "screenshot", "google": "google", "chrome": "chrome",
    "browser": "browser", "windows": "windows", "settings": "settings",
    "calculator": "calculator", "calc": "calculator", "notepad": "notepad",
}

# Hindi number words -> value.  Ambiguous spellings are deliberately omitted
# (e.g. "sath" can mean 7 or 60 depending on dialect) to avoid wrong volumes.
_HINDI_NUMBERS: Dict[str, int] = {
    "shunya": 0, "shoonya": 0, "sunkhe": 0,
    "ek": 1, "aek": 1, "yek": 1,
    "do": 2, "dau": 2, "dve": 2,
    "teen": 3, "tiha": 3,
    "char": 4, "chaar": 4, "chara": 4,
    "paanch": 5, "panch": 5, "pancha": 5,
    "chhe": 6, "che": 6, "chha": 6,
    "saat": 7, "saath": 7,
    "aath": 8, "ath": 8, "aathe": 8,
    "nau": 9, "naun": 9,
    "das": 10, "dah": 10, "dasha": 10,
    "gyara": 11, "gyarah": 11, "gyarha": 11,
    "barah": 12, "bara": 12, "baras": 12,
    "tera": 13, "tehra": 13, "tira": 13,
    "choda": 14, "chaudah": 14,
    "pandra": 15, "pandrah": 15,
    "solah": 16, "sola": 16,
    "satrah": 17, "satra": 17, "satara": 17,
    "athrah": 18, "athara": 18, "atharah": 18,
    "unnees": 19, "unees": 19,
    "bis": 20, "bees": 20,
    "tees": 30, "tis": 30,
    "chalis": 40, "chalees": 40,
    "pachas": 50, "pacchaas": 50, "pachha": 50,
    "sathish": 60, "sath": 60,
    "sattar": 70, "sathas": 70,
    "assi": 80, "assee": 80,
    "nabbe": 90, "nubhe": 90,
    "sau": 100,
}

# Devanagari (Hindi) words -> English keywords.  Best effort: recognizers often
# return Devanagari when the language hint is hi-IN.
_DEVANAGARI: Dict[str, str] = {
    "खोल दो": "open do", "खोल लीजिए": "open", "खोल लीजिये": "open",
    "खोल दिया": "open", "खोल दिया गया": "open", "खोलओ": "open",
    "खोलo": "open", "खोलेगा": "open", "खोलेगा": "open", "खोलता": "open",
    "खोलिये": "open", "खोलें": "open", "खुला": "open", "खुलें": "open",
    "खोलो": "open", "खुलो": "open",
    "बंद करो": "close do", "बंद कर": "close do", "बंद": "close",
    "दखो": "show", "दखाओ": "show", "दखलाओ": "show", "दखाएगा": "show",
    "दखा": "show", "दखीए": "show",
    "करो": "do", "कर": "do", "करिए": "do", "करिये": "do",
    "खोजो": "search", "खोजिए": "search", "खोज": "search",
    "ऊपर": "up", "ऊंचे": "up", "ऊपर जाओ": "up",
    "नीचे": "down", "नीचा": "down", "नीचे जाओ": "down",
    "आगे": "forward", "पीछे": "back", "वापस": "back", "घूम": "back",
    "आवाज़": "volume", "आवाज": "volume", "स्वर": "volume",
    "एक्सप्लोरर": "explorer", " एक्सพลोरर": "explorer",
    "फाइल": "file", "फ़ाइल": "file", "फाइल्स": "file", "फ़ाइल्स": "file",
    "फोल्डर": "folder", "फ़ोल्डर": "folder",
    "फोल्डर्स": "folder", "फ़ोल्डर्स": "folder",
    "गुगल": "google",
    "क्रोम": "chrome", "ब्राउज़र": "browser", "ब्रॉजर": "browser",
    "सेटिंग्स": "settings", "सेटिंग": "settings",
    "रुको": "stop", "रुक": "stop", "समय": "time", "समय": "time",
    "टाइम": "time", "वाक़्त": "time", "बताओ": "tell", "बता": "tell",
    "वाक़्त": "time", "तारीख़": "date", "तारीख": "date", "तरीक": "date",
}

_DEVANAGARI_DIGITS: Dict[str, str] = {
    "०": "0", "१": "1", "२": "2", "३": "3", "४": "4", "५": "5",
    "६": "6", "७": "7", "८": "8", "९": "9",
}

_HINDI_NUMBERS_DEVANAGARI: Dict[str, int] = {
    "एक": 1, "एका": 1, "دو": 2, "तीन": 3, "चार": 4, "पाँच": 5, "पांच": 5,
    "छह": 6, "सात": 7, "आठ": 8, "नौ": 9, "दस": 10,
    "बीस": 20, "तीस": 30, "चालीस": 40, "पचास": 50, "साठ": 60,
    "सत्तर": 70, "अस्सी": 80, "नब्बे": 90, "सौ": 100,
}

_ENGLISH_NUMBERS: Dict[str, int] = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100,
}

_PERCENT_WORDS = ("percent", "pct", "per cent", "payis", "paise")


# ---------------------------------------------------------------------------
# number parsing
# ---------------------------------------------------------------------------

def parse_number(text: str) -> Optional[int]:
    """Extract an integer from ``text``.

    Supports decimal digits (``"50"``, ``"50%"``), English number words and
    Hindi number words.  Returns ``None`` when no number is present.
    """
    if not text:
        return None
    work = text.lower()

    digit_match = re.search(r"(\d{1,3})", work)
    if digit_match:
        return int(digit_match.group(1))

    for ch, digit in _DEVANAGARI_DIGITS.items():
        if ch in work:
            m = re.search(r"(\d{1,3})", work.replace(ch, digit))
            if m:
                return int(m.group(1))

    for word, value in _HINDI_NUMBERS_DEVANAGARI.items():
        if word in work:
            return value

    found: List[int] = []
    for word, value in _ENGLISH_NUMBERS.items():
        if re.search(rf"\b{re.escape(word)}\b", work):
            found.append(value)
    for word, value in _HINDI_NUMBERS.items():
        if re.search(rf"\b{re.escape(word)}\b", work):
            found.append(value)
    if found:
        total = sum(found)
        if 0 < total <= 1000:
            return total
    return None


def has_percent(text: str) -> bool:
    low = (text or "").lower()
    return any(w in low for w in _PERCENT_WORDS) or "%" in low


# ---------------------------------------------------------------------------
# normalization
# ---------------------------------------------------------------------------

_PUNCT_RE = re.compile(r"[^\w\s%°.]", re.UNICODE)
_WS_RE = re.compile(r"\s+")


def normalize_text(text: str) -> Tuple[str, Dict[str, str]]:
    """Normalize recognized speech.

    Returns ``(normalized, meta)`` where ``meta`` keeps information lost during
    normalization (the raw text and the pre-trailing-strip form, which is needed
    to recover number words such as ``"do"`` = 2).
    """
    meta = {"raw": text or "", "pre_strip": "", "had_jarvis": False}
    if not text:
        return "", meta

    work = (text or "").lower()
    meta["had_jarvis"] = "jarvis" in work
    work = work.replace("\u2019", "'").replace("\u2018", "'")

    for dev, asc in _DEVANAGARI_DIGITS.items():
        work = work.replace(dev, asc)

    # Devanagari words -> English keywords while the conjunct (virama) is
    # still intact, so words like \u0924\u0947\u092e match their keys.
    work = _sub_all(work, _DEVANAGARI)
    for word, value in _HINDI_NUMBERS_DEVANAGARI.items():
        # only standalone words: "\u0908\u0915" must not match inside
        # "\u0908\u0915\u092a\u0932\u094b\u0930\u0930"
        work = re.sub(
            rf"(?<![\u0900-\u097f]){re.escape(word)}(?![\u0900-\u097f])",
            str(value),
            work,
        )
    work = _sub_all(work, _HINGLISH)
    # drop Devanagari text that could not be translated: vowel signs are
    # combining marks and would otherwise survive the punctuation cleanup
    work = re.sub(r"[\u0900-\u097f]+", " ", work)

    work = re.sub(r"\bjarvis\b", " ", work)
    for filler in _FILLERS:
        work = re.sub(filler, " ", work)
    work = _WS_RE.sub(" ", work).strip()
    meta["pre_strip"] = work

    work = _TRAILING_IMPERATIVE.sub("", work)
    work = _PUNCT_RE.sub(" ", work)
    work = _WS_RE.sub(" ", work).strip()
    return work, meta


# ---------------------------------------------------------------------------
# command specifications
# ---------------------------------------------------------------------------

@dataclass
class CommandSpec:
    """One canonical command and the language that maps onto it."""

    id: str
    name: str
    patterns: Tuple[str, ...] = ()
    keywords: Tuple[str, ...] = ()
    min_keyword_hits: int = 2
    slot_patterns: Dict[str, str] = field(default_factory=dict)
    slot_noise: Dict[str, Tuple[str, ...]] = field(default_factory=dict)
    priority: int = 50
    examples: Tuple[str, ...] = ()


# --- lifecycle (highest priority) ------------------------------------------

LIFECYCLE_SPECS: Tuple[CommandSpec, ...] = (
    CommandSpec(
        id="exit_jarvis",
        name="Exit JARVIS",
        patterns=(
            r"\b(?:exit|quit|shutdown|turn\s+off|stop)\b.*\b(?:jarvis|assistant)\b",
            r"\bgoodbye\b", r"\bbye\b", r"\bkhatam\b", r"\bkhatm\b",
            r"\bexit\b", r"\bquit\b", r"\bshutdown\b",
        ),
        keywords=("exit", "quit", "goodbye", "shutdown", "khatam"),
        priority=5,
        examples=("Exit Jarvis", "Jarvis, bye", "Shutdown Jarvis", "Khatam karo"),
    ),
    CommandSpec(
        id="stop_listening",
        name="Stop listening",
        patterns=(
            r"\bstop\s+listening\b",
            r"\bstop\s+(?:the\s+)?(?:mic|microphone|listening|recognition)\b",
            r"\b(?:close|mute|shut)\s+(?:the\s+)?(?:mic|microphone|listening)\b",
            r"\bmute\s+the\s+mic\b", r"\bgo\s+quiet\b", r"\bshush\b",
            r"\bkhamoshi\b", r"\bshant\b", r"\bstop\s+now\b",
            r"\b(?:stop|close)\s+do\s*$",
            r"\bstop\s*$", r"\bclose\s*$",
        ),
        keywords=("stop", "listening", "mute", "close"),
        priority=8,
        examples=("Stop listening", "Jarvis, band karo", "Mute the mic"),
    ),
    CommandSpec(
        id="go_standby",
        name="Return to standby",
        patterns=(
            r"\bgo\s+to\s+standby\b", r"\bstandby\b", r"\bback\s+to\s+standby\b",
            r"\bsleep\b", r"\bdeactivate\b", r"\bready\s+mode\b",
            r"\bstandby\s+mode\b", r"\bgo\s+off\b",
        ),
        keywords=("standby", "sleep", "deactivate"),
        priority=9,
        examples=("Go to standby", "Back to standby", "Jarvis, sleep"),
    ),
)

# --- web / browser ---------------------------------------------------------

WEB_SPECS: Tuple[CommandSpec, ...] = (
    CommandSpec(
        id="search_file",
        name="Search for a file",
        patterns=(
            r"\bsearch\s+(?:for\s+)?(?:the\s+)?file\s+(.+)$",
            r"\bsearch\s+(.+?)\s+file\b",
            r"\bfind\s+(?:the\s+)?file\s+(.+)$",
            r"\bfind\s+(.+?)\s+file\b",
            r"\bfile\s+search\s+(.+)$",
            r"\bfile\s+ko\s+search\s+karo\s+(.+)$",
            r"\b(?:search|find)\s+for\s+(.+)\s+files\b",
            r"\b(.+?)\s+file\s+search\b",
        ),
        slot_patterns={"query": r"(.+)$"},
        slot_noise={"query": ("file", "files", "search", "find", "for", "the", "please")},
        priority=11,
        examples=("Search for resume", "File search project report", "Find the file budget"),
    ),
    CommandSpec(
        id="google_search",
        name="Google search",
        patterns=(
            # browser/search in any order: "chrome par python search karo"
            r"(?=.*\bsearch\b)(?=.*\b(?:google|chrome|browser)\b).+",
            r"\bgoogle\s+search\s+(?:for\s+)?(.+)$",
            r"\bsearch\s+(?:for\s+)?(?:the\s+)?(.+)$",
            r"\bfind\s+(?:for\s+)?(?:the\s+)?(.+)$",
        ),
        slot_patterns={"query": r"(.+)$"},
        slot_noise={
            "query": ("google", "chrome", "browser", "search", "find", "on",
                      "in", "par", "the", "please", "for", "online"),
        },
        priority=12,
        examples=("Chrome par Python search karo", "Search for weather", "Google search cricket"),
    ),
    CommandSpec(
        id="open_chrome",
        name="Open Chrome",
        patterns=(
            r"\b(?:google\s+chrome|chrome|chromium)\b[^.]*\b(?:open|launch|start|show)\b",
            r"\b(?:open|launch|start)\b[^.]*\b(?:google\s+chrome|chrome|chromium)\b",
            r"\bopen\s+the\s+browser\b", r"\bopen\s+browser\b",
            r"\bbrowser\s+open\b", r"\bbrowser\s+kholo\b",
            r"\blaunch\s+the\s+browser\b",
        ),
        keywords=("chrome", "browser", "open"),
        priority=14,
        examples=("Chrome kholo", "Open Chrome", "Browser kholo"),
    ),
    CommandSpec(
        id="browser_back",
        name="Browser back",
        patterns=(
            r"\bbrowser\s+back\b", r"\bgo\s+back\b", r"\bchrome\s+back\b",
            r"\bback\s+button\b", r"\bback\b",
        ),
        keywords=("back", "browser"),
        priority=20,
        examples=("Go back", "Browser back", "Peeche jao"),
    ),
    CommandSpec(
        id="browser_forward",
        name="Browser forward",
        patterns=(
            r"\bbrowser\s+forward\b", r"\bgo\s+forward\b", r"\bforward\b",
            r"\bnext\s+page\b",
        ),
        keywords=("forward", "next", "browser"),
        priority=21,
        examples=("Go forward", "Browser forward", "Next page"),
    ),
)

# --- files / applications --------------------------------------------------

FILE_SPECS: Tuple[CommandSpec, ...] = (
    CommandSpec(
        id="open_file_explorer",
        name="Open File Explorer",
        patterns=(
            r"\bfile\s*explorer\b",
            r"\bexplorer\b[^.]*\b(?:open|launch|start|show|display)\b",
            r"\b(?:open|launch|start|show|display)\b[^.]*\bexplorer\b",
            r"\bfiles?\b[^.]*\b(?:open|launch|start|show|display)\b",
            r"\bfolders\b[^.]*\b(?:open|launch|start|show|display)\b",
            r"\bmy\s+computer\b", r"\bthis\s+pc\b", r"\bmy\s+pc\b",
        ),
        keywords=("explorer", "file", "folder", "show", "open"),
        priority=30,
        examples=("File Explorer kholo", "Explorer kholo", "Jarvis, files dikhao"),
    ),
    CommandSpec(
        id="open_folder",
        name="Open a folder",
        patterns=(
            r"\bopen\s+(?:the\s+)?folder\s+(.+)$",
            r"\bopen\s+(?:the\s+)?(.+?)\s+folder\b",
            r"\b(.+?)\s+folder\s+(?:open|khul|show)\b",
            r"\bfolder\s+(?:ko\s+)?khol\s+(?:do\s+)?(.+)$",
        ),
        slot_patterns={"folder": r"(.+)$"},
        slot_noise={"folder": ("folder", "the", "please", "open", "show")},
        priority=31,
        examples=("Open folder Downloads", "Downloads folder kholo"),
    ),
    CommandSpec(
        id="open_file",
        name="Open a file",
        patterns=(
            r"\bopen\s+(?:the\s+)?file\s+(.+)$",
            r"\bopen\s+(?:the\s+)?(.+?)\s+file\b",
            r"\b(.+?)\s+file\s+open\b",
            r"\bopen\s+(?:the\s+)?(.+)$",
        ),
        slot_patterns={"file": r"(.+)$"},
        slot_noise={"file": ("file", "files", "the", "please", "open")},
        priority=37,
        examples=("Open file report.pdf", "Open report.pdf"),
    ),
    CommandSpec(
        id="open_app",
        name="Open an application",
        patterns=(
            r"\bopen\s+(?:the\s+)?app(?:lication)?\s+(.+)$",
            r"\bopen\s+(?:the\s+)?(.+?)\s+app(?:lication)?\b",
            r"\blaunch\s+(?:the\s+)?(.+)$",
            r"\brun\s+(?:the\s+)?(.+)$",
        ),
        slot_patterns={"app": r"(.+)$"},
        slot_noise={"app": ("app", "application", "the", "please", "open", "launch", "run")},
        priority=36,
        examples=("Open app Spotify", "Launch Visual Studio Code"),
    ),
    CommandSpec(
        id="close_app",
        name="Close an application",
        patterns=(
            r"\bclose\s+app\s+(.+)$",
            r"\bclose\s+(?:the\s+)?app(?:lication)?\s+(?:called\s+)?(.+)$",
            r"\bclose\s+(?:the\s+)?(.+?)\s+app(?:lication)?\b",
            r"\bclose\s+(?:the\s+)?(.+?)\s+window\b",
            r"\bquit\s+(?:the\s+)?(.+)$",
        ),
        slot_patterns={"app": r"(.+)$"},
        slot_noise={"app": ("app", "application", "the", "please", "close", "quit", "window")},
        priority=39,
        examples=("Close app Chrome", "Quit Notepad"),
    ),
)

# --- system ----------------------------------------------------------------

SYSTEM_SPECS: Tuple[CommandSpec, ...] = (
    CommandSpec(
        id="open_settings",
        name="Open Windows Settings",
        patterns=(
            r"\bwindows\s+settings\b", r"\bsettings\b[^.]*\bopen\b",
            r"\bopen\s+settings\b", r"\bsettings\s+kholo\b",
            r"\bsettings\s+ko\s+open\b",
        ),
        keywords=("settings", "open"),
        priority=31,
        examples=("Open settings", "Settings kholo", "Windows settings kholo"),
    ),
    CommandSpec(
        id="open_calculator",
        name="Open Calculator",
        patterns=(
            r"\bcalculator\b[^.]*\b(?:open|launch|start)\b",
            r"\bopen\s+calculator\b", r"\bcalc\s+kholo\b", r"\bcalculator\b",
        ),
        keywords=("calculator", "open"),
        priority=32,
        examples=("Open calculator", "Calculator kholo", "Calc kholo"),
    ),
    CommandSpec(
        id="open_notepad",
        name="Open Notepad",
        patterns=(
            r"\bnotepad\b[^.]*\b(?:open|launch|start)\b",
            r"\bopen\s+notepad\b", r"\bnotepad\s+kholo\b", r"\bnotepad\b",
        ),
        keywords=("notepad", "open"),
        priority=33,
        examples=("Open notepad", "Notepad kholo"),
    ),
    CommandSpec(
        id="screenshot",
        name="Take a screenshot",
        patterns=(
            r"\bscreenshot\b", r"\bscreen\s+shot\b", r"\bscreen\s+capture\b",
            r"\bcapture\s+(?:the\s+)?screen\b", r"\bscreenshot\s+le\s+karo\b",
            r"\bscreenshot\s+khincho\b", r"\bscreenshot\s+lena\b",
            r"\bscreenshot\s+lete\s+karo\b",
        ),
        keywords=("screenshot", "screen", "capture"),
        priority=43,
        examples=("Take a screenshot", "Screenshot le lo", "Screenshot khincho"),
    ),
    CommandSpec(
        id="current_time",
        name="Report the time",
        patterns=(
            r"\bwhat\s+time\b", r"\bcurrent\s+time\b", r"\btime\s+now\b",
            r"\bwaqt\b", r"\btime\s+(?:batao|batado|tell|bata|please)\b",
            r"\bwhat\s+is\s+the\s+time\b", r"\btime\s+hai\b",
            r"\btime\s+ka\s+bath\b", r"\btime\s+ka\s+bataya\b",
            r"\btime\s+kya\s*$", r"\btime\s+is\s*$",
            r"\btime\s+kya\s+hai\b", r"\btime\s*$",
        ),
        keywords=("time", "waqt"),
        priority=44,
        examples=("What time is it", "Time batao", "Waqt kya hai"),
    ),
    CommandSpec(
        id="current_date",
        name="Report the date",
        patterns=(
            r"\bwhat\s+(?:is\s+)?the\s+date\b", r"\bcurrent\s+date\b",
            r"\bdate\s+(?:please|batao|batado|tell)\b", r"\btarik\b",
            r"\btareek\b", r"\bwhat\s+is\s+today\b", r"\bdate\s+hai\b",
            r"\btoday'?s\s+date\b", r"\btoday\s+(?:of|ka|ki)?\s*date\b",
            r"\bdate\s+kya\s*$", r"\bdate\s+is\s*$",
            r"\bdate\s+kya\s+hai\b", r"\bdate\s*$",
        ),
        keywords=("date", "tarik"),
        priority=45,
        examples=("What is the date", "Date batao", "Tarikh kya hai"),
    ),
)

# --- input / audio ---------------------------------------------------------

INPUT_SPECS: Tuple[CommandSpec, ...] = (
    CommandSpec(
        id="scroll_up",
        name="Scroll up",
        patterns=(
            r"\bscroll\s+up\b", r"\bscroll\s+upwards\b", r"\bpage\s+up\b",
            r"\bscroll\s+upar\b", r"\bup\s+scroll\b", r"\bscroll\s+up\s+karo\b",
        ),
        keywords=("scroll", "up"),
        priority=50,
        examples=("Scroll up", "Page up", "Scroll upar karo"),
    ),
    CommandSpec(
        id="scroll_down",
        name="Scroll down",
        patterns=(
            r"\bscroll\s+down\b", r"\bscroll\s+downwards\b", r"\bpage\s+down\b",
            r"\bscroll\s+niche\b", r"\bdown\s+scroll\b",
            r"\bscroll\s+down\s+karo\b", r"\bscroll\s+nico\b",
        ),
        keywords=("scroll", "down"),
        priority=51,
        examples=("Scroll down", "Page down", "Scroll niche karo"),
    ),
    CommandSpec(
        id="scroll_unknown",
        name="Scroll (direction unknown)",
        patterns=(r"\bscroll\b", r"\bscrolling\b"),
        keywords=("scroll",),
        min_keyword_hits=1,
        priority=52,
        examples=("Scroll", "Kuch scroll karo"),
    ),
    CommandSpec(
        id="volume_up",
        name="Volume up",
        patterns=(
            r"\bvolume\s+(?:up|increa\w*|raise)\b",
            r"\bturn\s+(?:the\s+)?volume\s+up\b", r"\bvolume\s+badata\b",
            r"\bvolume\s+uthao\b", r"\bauwaj\s+badata\b",
        ),
        keywords=("volume", "up"),
        priority=53,
        examples=("Volume up", "Aawaj badao", "Volume badhao"),
    ),
    CommandSpec(
        id="volume_down",
        name="Volume down",
        patterns=(
            r"\bvolume\s+(?:down|decrea\w*|lower|kam)\b",
            r"\bturn\s+(?:the\s+)?volume\s+down\b", r"\bvolume\s+kama\b",
            r"\bvolume\s+ghata\b", r"\bauwaj\s+kama\b",
        ),
        keywords=("volume", "down"),
        priority=54,
        examples=("Volume down", "Aawaj kam karo"),
    ),
    CommandSpec(
        id="set_volume",
        name="Set volume",
        patterns=(
            r"\b(?:set|change|make|turn)\s+(?:the\s+)?volume\s+(?:to\s+)?(.+)$",
            r"\bvolume\s+(?:ko\s+)?(?:set|change|karo)\s+(.+)$",
            r"\b(?:set|change|turn)\s+(?:the\s+)?(?:volume|aawaj)\s+(.+)$",
            r"\bvolume\s*$", r"\bauwaj\s*$",
            r"\bvolume\s+(.+)$", r"\bauwaj\s+(.+)$",
        ),
        slot_patterns={"level": r"(.+)$"},
        slot_noise={"level": ("set", "change", "to", "the", "volume", "aawaj", "karo", "please")},
        priority=55,
        examples=("Set volume to 50", "Volume 80", "Aawaj pachas karo"),
    ),
    CommandSpec(
        id="mute",
        name="Mute system",
        patterns=(r"\bmute\b", r"\bmuted\b", r"\bsilent\b"),
        keywords=("mute", "silent"),
        priority=56,
        examples=("Mute", "System ko silent karo"),
    ),
    CommandSpec(
        id="unmute",
        name="Unmute system",
        patterns=(r"\bunmute\b", r"\bun\s?mute\b"),
        keywords=("unmute",),
        priority=57,
        examples=("Unmute", "Unmute the system"),
    ),
)

KNOWN_COMMANDS: Tuple[CommandSpec, ...] = (
    LIFECYCLE_SPECS + WEB_SPECS + FILE_SPECS + SYSTEM_SPECS + INPUT_SPECS
)

_SPEC_BY_ID: Dict[str, CommandSpec] = {s.id: s for s in KNOWN_COMMANDS}


# ---------------------------------------------------------------------------
# result
# ---------------------------------------------------------------------------

@dataclass
class ParsedCommand:
    """The outcome of understanding one utterance."""

    command: str
    raw: str
    normalized: str
    confidence: float
    slots: Dict[str, str] = field(default_factory=dict)
    known: bool = True
    reason: str = ""

    @property
    def label(self) -> str:
        spec = _SPEC_BY_ID.get(self.command)
        return spec.name if spec else self.command

    @property
    def is_ambiguous(self) -> bool:
        return self.command == "scroll_unknown"


# ---------------------------------------------------------------------------
# Brain
# ---------------------------------------------------------------------------

class Brain:
    """Match natural language onto canonical commands."""

    #: minimum score for a match to be accepted
    ACCEPT_SCORE = 0.52

    def __init__(self, extra_commands: Optional[Sequence[CommandSpec]] = None) -> None:
        specs: List[CommandSpec] = list(KNOWN_COMMANDS)
        if extra_commands:
            specs.extend(extra_commands)
        specs.sort(key=lambda s: (s.priority, s.id))
        self.specs = specs
        self._by_id = {s.id: s for s in specs}

    @property
    def commands(self) -> List[CommandSpec]:
        return list(self.specs)

    def command_label(self, command_id: str) -> str:
        spec = self._by_id.get(command_id)
        return spec.name if spec else command_id

    def parse(self, text: str) -> Optional[ParsedCommand]:
        """Understand one utterance.

        Returns ``None`` when nothing confident was recognized so the caller
        can ask for a repeat instead of guessing.
        """
        norm, meta = normalize_text(text)
        if not norm.strip():
            return None

        best: Optional[Tuple[float, CommandSpec]] = None
        for spec in self.specs:
            score = self._score(spec, norm)
            if score and (best is None or score > best[0] + 1e-9):
                best = (score, spec)

        if best is None or best[0] < self.ACCEPT_SCORE:
            return None

        score, spec = best
        slots = self._extract_slots(spec, norm, meta["pre_strip"])
        return ParsedCommand(
            command=spec.id,
            raw=meta["raw"],
            normalized=norm,
            confidence=round(score, 3),
            slots=slots,
        )

    # -- internals ----------------------------------------------------------

    @staticmethod
    def _score(spec: CommandSpec, norm: str) -> float:
        best = 0.0
        for pattern in spec.patterns:
            try:
                match = re.search(pattern, norm)
            except re.error:  # pragma: no cover - defensive
                continue
            if not match:
                continue
            covered = len(match.group(0)) / max(len(norm), 1)
            score = 0.62 + 0.38 * covered
            if re.fullmatch(pattern, norm):
                score = min(1.0, score + 0.1)
            best = max(best, score)
        if best:
            return best

        if not spec.keywords or spec.min_keyword_hits <= 1:
            return 0.0
        hits = sum(
            1 for kw in spec.keywords if re.search(rf"\b{re.escape(kw)}\b", norm)
        )
        if hits >= spec.min_keyword_hits:
            return 0.5 + 0.1 * (hits - spec.min_keyword_hits)
        return 0.0

    @staticmethod
    def _extract_slots(
        spec: CommandSpec, norm: str, alt: str = ""
    ) -> Dict[str, str]:
        slots: Dict[str, str] = {}
        for slot, pattern in spec.slot_patterns.items():
            noise = spec.slot_noise.get(slot, ())
            value = ""
            for source in (norm, alt):
                if not source:
                    continue
                try:
                    match = re.search(pattern, source)
                except re.error:  # pragma: no cover - defensive
                    continue
                if not match:
                    continue
                groups = match.groups()
                candidate = match.group(1) if groups else match.group(0)
                cleaned = (candidate or "").strip()
                cleaned = re.sub(
                    r"^(?:the|a|an)\s+", "", cleaned, flags=re.IGNORECASE
                ).strip(" .,!?;:")
                if noise:
                    cleaned = strip_noise(cleaned, noise)
                if cleaned and len(cleaned) > 1:
                    value = cleaned
                    break
            if value:
                slots[slot] = value
        return slots
