"""Central configuration. Secrets come from environment variables / .env only."""
import os
import platform
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class ConfigError(RuntimeError):
    """Raised when required configuration (e.g. the API key) is missing."""


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    return default if value is None else value.strip().lower() in {"1", "true", "yes", "on"}


def _list(name: str, default: str):
    return [x.strip() for x in os.getenv(name, default).split(",") if x.strip()]


# --- Gemini -----------------------------------------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash").strip()
GEMINI_FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash-lite").strip()
ACTIVE_MODEL = GEMINI_MODEL  # switched to the fallback automatically on "model not found"

_client = None


def get_client():
    """Return a shared Gemini client (created lazily so the UI can start without a key)."""
    global _client
    if not GEMINI_API_KEY:
        raise ConfigError(
            "GEMINI_API_KEY is not set. Copy .env.example to .env and paste your key "
            "from https://aistudio.google.com/apikey, then restart JARVIS."
        )
    if _client is None:
        from google import genai

        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


# --- Personality / voice ----------------------------------------------------
USER_NAME = os.getenv("JARVIS_USER_NAME", "sir")
WAKE_WORDS = [w.lower() for w in _list("WAKE_WORDS", "hey jarvis,jarvis,ہے جارویس,ہیلو جارویس")]
STOP_PHRASES = [
    "stop listening", "go to sleep", "that's all", "that is all", "goodbye jarvis",
    "سننا بند کرو", "بس کرو", "خدا حافظ", "بس کر دیو",
]
CONVERSATION_TIMEOUT = int(os.getenv("CONVERSATION_TIMEOUT", "45"))  # seconds of silence -> standby
STT_FALLBACK_LANGS = _list("STT_FALLBACK_LANGS", "en-IN,ur-PK")
PUNJABI_TTS_LANG = os.getenv("PUNJABI_TTS_LANG", "ur")  # Shahmukhi text is voiced with the Urdu voice
MAX_SPOKEN_CHARS = 700

# --- Storage / safety -------------------------------------------------------
SAVE_HISTORY = _bool("SAVE_HISTORY", True)
CONFIRM_SCRIPTS = _bool("CONFIRM_SCRIPTS", True)
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "jarvis.db"

WORKSPACE = Path(os.getenv("JARVIS_WORKSPACE", Path.home() / "JarvisWorkspace")).expanduser().resolve()
SCRIPTS_DIR = WORKSPACE / "scripts"
SCREENSHOTS_DIR = WORKSPACE / "screenshots"
APPROVED_FOLDERS = [WORKSPACE] + [
    Path(p).expanduser().resolve() for p in os.getenv("JARVIS_APPROVED_FOLDERS", "").split(os.pathsep) if p.strip()
]

HOST = os.getenv("JARVIS_HOST", "127.0.0.1")
PORT = int(os.getenv("JARVIS_PORT", "8000"))


def ensure_dirs() -> None:
    for d in (DATA_DIR, WORKSPACE, SCRIPTS_DIR, SCREENSHOTS_DIR):
        d.mkdir(parents=True, exist_ok=True)


# --- Approved applications (edit to taste; only these can be launched) ------
_APPS = {
    "Windows": {
        "notepad": ["notepad"], "calculator": ["calc"], "paint": ["mspaint"],
        "file explorer": ["explorer"],
        "chrome": ["cmd", "/c", "start", "", "chrome"],
        "edge": ["cmd", "/c", "start", "", "msedge"],
        "vscode": ["cmd", "/c", "start", "", "code"],
    },
    "Darwin": {
        "calculator": ["open", "-a", "Calculator"], "notes": ["open", "-a", "Notes"],
        "safari": ["open", "-a", "Safari"], "chrome": ["open", "-a", "Google Chrome"],
        "finder": ["open", "-a", "Finder"], "vscode": ["open", "-a", "Visual Studio Code"],
        "music": ["open", "-a", "Music"],
    },
    "Linux": {
        "calculator": ["gnome-calculator"], "files": ["xdg-open", str(Path.home())],
        "text editor": ["gedit"], "chrome": ["google-chrome"], "firefox": ["firefox"],
        "vscode": ["code"],
    },
}
APPS = _APPS.get(platform.system(), {})

SITES = {
    "youtube": "https://www.youtube.com", "google": "https://www.google.com",
    "gmail": "https://mail.google.com", "github": "https://github.com",
    "wikipedia": "https://www.wikipedia.org", "stackoverflow": "https://stackoverflow.com",
    "kaggle": "https://www.kaggle.com", "colab": "https://colab.research.google.com",
}
