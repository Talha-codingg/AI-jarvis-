"""Text-to-speech: gTTS (English/Urdu/Punjabi) played with pygame, pyttsx3 offline fallback for English."""
import os
import re
import tempfile
import threading
import time

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import config

_URL = re.compile(r"https?://\S+")
_CODE = re.compile(r"```.*?```", re.DOTALL)


def clean_for_speech(text: str) -> str:
    text = _CODE.sub(" The code is shown on screen. ", text)
    text = _URL.sub("", text)
    text = re.sub(r"[*_`#>~|]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > config.MAX_SPOKEN_CHARS:
        cut = text[: config.MAX_SPOKEN_CHARS]
        end = max(cut.rfind(". "), cut.rfind("۔"), cut.rfind("? "))
        text = (cut[: end + 1] if end > 200 else cut) + " The rest is on screen."
    return text


class VoiceOutput:
    def __init__(self):
        self._stop = threading.Event()
        self._lock = threading.RLock()  # one voice at a time
        self._engine = None

    def speak(self, text: str, lang: str = "en") -> None:
        """Speak and block until finished or stop() is called."""
        text = clean_for_speech(text)
        if not text:
            return
        with self._lock:
            self._stop.clear()
            try:
                self._speak_gtts(text, lang)
            except Exception as e:
                if self._stop.is_set():
                    return
                print(f"[voice] online TTS failed ({e}); trying offline voice")
                if lang == "en":
                    self._speak_offline(text)
                else:
                    raise RuntimeError("Speech needs an internet connection for Urdu/Punjabi voices.") from e

    def _speak_gtts(self, text: str, lang: str) -> None:
        from gtts import gTTS
        import pygame

        tts_lang = {"en": "en", "ur": "ur", "pa": config.PUNJABI_TTS_LANG}.get(lang, "en")
        fd, path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
        try:
            gTTS(text=text, lang=tts_lang).save(path)
            if self._stop.is_set():
                return
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy() and not self._stop.is_set():
                time.sleep(0.05)
            pygame.mixer.music.stop()
            try:
                pygame.mixer.music.unload()
            except AttributeError:
                pass
        finally:
            try:
                os.remove(path)
            except OSError:
                pass

    def _speak_offline(self, text: str) -> None:
        import pyttsx3

        self._engine = pyttsx3.init()
        self._engine.say(text)
        self._engine.runAndWait()
        self._engine = None

    def stop(self) -> None:
        """Silence speech immediately (emergency stop)."""
        self._stop.set()
        try:
            import pygame
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
        except Exception:
            pass
        try:
            if self._engine:
                self._engine.stop()
        except Exception:
            pass
