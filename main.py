"""JARVIS entry point.  Run:  python main.py   (add --no-browser to skip opening the page)."""
import argparse
import difflib
import re
import socket
import threading
import time
import traceback
import webbrowser

import uvicorn

import config
import memory
from ai_brain import AIBrain, BrainError, detect_lang
from computer_control import clear_pending
from interface import Hub, create_app
from voice_output import VoiceOutput

try:
    import speech_recognition as sr
    from voice_input import MicrophoneError, VoiceInput
    VOICE_IN_ERROR = None
except ImportError as exc:  # UI and typed chat still work without audio libraries
    sr, VoiceInput, VOICE_IN_ERROR = None, None, str(exc)

    class MicrophoneError(RuntimeError):
        pass


def match_wake_word(text: str):
    """Return (found, remainder_after_wake_word). Tolerates mis-hearings like 'travis'."""
    t = text.lower().strip()
    for w in config.WAKE_WORDS:
        if w in t:
            return True, t.split(w, 1)[1].strip(" ,.!?")
    tokens = t.split()
    for i, tok in enumerate(tokens):
        tok = re.sub(r"[^a-z]", "", tok)
        if tok and difflib.SequenceMatcher(None, tok, "jarvis").ratio() >= 0.75:
            return True, " ".join(tokens[i + 1:])
    return False, ""


class Assistant:
    def __init__(self, emit):
        self.emit = emit
        memory.init()
        self.brain, self.brain_error = None, None
        try:
            self.brain = AIBrain(history=memory.preload_history() if config.SAVE_HISTORY else [])
        except config.ConfigError as e:
            self.brain_error = str(e)
            print(f"[config] {e}")
        self.vin = VoiceInput() if VoiceInput else None
        self.vout = VoiceOutput()
        self.enabled = threading.Event()   # voice loop on/off (the microphone button)
        self.shutdown = threading.Event()
        self.awake = False                 # inside a conversation (no wake word needed)
        self.stopped = False               # emergency stop engaged
        self.state = "off"
        self.epoch = 0                     # bumped by emergency stop to discard in-flight replies
        self.last_active = 0.0
        self.handle_lock = threading.Lock()
        self.status_cache = {"ai": bool(self.brain), "net": True, "mic": False}

    # ---- events to the UI --------------------------------------------------
    def set_state(self, state: str) -> None:
        self.state = state
        self.emit({"type": "state", "state": state})

    def rest_state(self) -> str:
        if self.stopped:
            return "stopped"
        if not self.enabled.is_set():
            return "off"
        return "listening" if self.awake else "standby"

    def transcript(self, role: str, text: str) -> None:
        self.emit({"type": "transcript", "role": role, "text": text})
        if role in ("user", "jarvis"):
            memory.save_message(role, text)

    def status(self) -> dict:
        return {"type": "status", **self.status_cache, "voice_ready": self.vin is not None}

    def snapshot(self):
        events = [{"type": "state", "state": self.state}, self.status(), {"type": "history_start"}]
        if config.SAVE_HISTORY:
            events += [{"type": "transcript", "role": m["role"], "text": m["text"]} for m in memory.recent_messages(12)]
        if self.brain_error:
            events.append({"type": "transcript", "role": "system", "text": self.brain_error})
        if VOICE_IN_ERROR:
            events.append({"type": "transcript", "role": "system",
                           "text": f"Voice input unavailable ({VOICE_IN_ERROR}). Typed chat still works."})
        return events

    # ---- controls ----------------------------------------------------------
    def toggle_mic(self) -> None:
        if self.enabled.is_set():
            self.enabled.clear()
            self.awake = False
            self.vout.stop()
            self.set_state("off")
            return
        if self.vin is None:
            self.transcript("system", "Voice input is unavailable. Install the audio packages from requirements.txt.")
            return
        self.stopped = False
        self.awake = True  # button press starts a conversation immediately
        self.last_active = time.time()
        self.enabled.set()
        self.set_state("listening")

    def emergency_stop(self) -> None:
        self.epoch += 1
        self.stopped = True
        self.enabled.clear()
        self.awake = False
        self.vout.stop()
        clear_pending()
        self.set_state("stopped")
        self.transcript("system", "Emergency stop: microphone closed, speech silenced, pending actions cancelled.")

    # ---- conversation ------------------------------------------------------
    def _say(self, text: str, lang: str) -> None:
        self.set_state("speaking")
        try:
            self.vout.speak(text, lang)
        except Exception as e:
            self.transcript("system", f"Voice output failed: {e}")
        self.set_state(self.rest_state())

    def handle_text(self, text: str) -> None:
        with self.handle_lock:
            text = text.strip()
            if not text:
                return
            epoch = self.epoch
            self.last_active = time.time()
            self.transcript("user", text)
            if any(p in text.lower() for p in config.STOP_PHRASES):
                self.awake = False
                self.transcript("jarvis", "Standing by. Say “Hey Jarvis” when you need me.")
                self._say("Standing by. Say hey Jarvis when you need me.", "en")
                return
            if not self.brain:
                self.transcript("system", self.brain_error or "The AI brain is not available.")
                self.set_state(self.rest_state())
                return
            self.set_state("thinking")
            try:
                reply, lang = self.brain.ask(text)
            except BrainError as e:
                reply, lang = str(e), "en"
            if epoch != self.epoch:
                return  # emergency stop happened while thinking
            self.transcript("jarvis", reply)
            self._say(reply, lang)
            self.last_active = time.time()

    # ---- background loops --------------------------------------------------
    def voice_loop(self) -> None:
        last_net_warn = 0.0
        while not self.shutdown.is_set():
            if not self.enabled.is_set() or self.vin is None:
                time.sleep(0.2)
                continue
            try:
                if not self.awake:
                    self.set_state("standby")
                    heard = self.vin.wake_listen()
                    if not heard or not self.enabled.is_set():
                        continue
                    found, rest = match_wake_word(heard)
                    if not found:
                        continue
                    self.awake, self.last_active = True, time.time()
                    if rest:
                        self.handle_text(rest)
                    else:
                        self._say("At your service.", "en")
                    continue

                self.set_state("listening")
                audio = self.vin.capture(timeout=6, phrase_limit=25)
                if not self.enabled.is_set():
                    continue
                if audio is None:
                    if time.time() - self.last_active > config.CONVERSATION_TIMEOUT:
                        self.awake = False
                        self.transcript("system", "No speech for a while. Back to standby; say “Hey Jarvis” to continue.")
                    continue
                self.set_state("thinking")
                text = self.vin.transcribe(audio, self.brain)
                if not self.enabled.is_set():
                    continue
                if not text:
                    continue  # background noise / unclear speech: keep listening quietly
                self.handle_text(text)
            except MicrophoneError as e:
                self.enabled.clear()
                self.awake = False
                self.status_cache["mic"] = False
                self.transcript("system", str(e))
                self.set_state("off")
            except Exception as e:
                if sr and isinstance(e, sr.RequestError):
                    if time.time() - last_net_warn > 30:
                        self.transcript("system", "The speech service is unreachable. Check your internet connection.")
                        last_net_warn = time.time()
                    time.sleep(3)
                else:
                    traceback.print_exc()
                    time.sleep(1)

    def reminder_loop(self) -> None:
        while not self.shutdown.is_set():
            try:
                for r in memory.due_reminders():
                    text = f"Reminder: {r['text']}"
                    self.transcript("system", text)
                    with self.handle_lock:
                        self._say(text, detect_lang(r["text"]))
            except Exception:
                traceback.print_exc()
            time.sleep(15)

    def status_loop(self) -> None:
        while not self.shutdown.is_set():
            try:
                socket.create_connection(("generativelanguage.googleapis.com", 443), timeout=3).close()
                net = True
            except OSError:
                net = False
            mic = bool(self.vin and self.vin.available())
            self.status_cache.update(net=net, mic=mic, ai=bool(self.brain))
            self.emit(self.status())
            time.sleep(10)


def main() -> None:
    parser = argparse.ArgumentParser(description="JARVIS voice assistant")
    parser.add_argument("--no-browser", action="store_true", help="do not open the interface automatically")
    args = parser.parse_args()

    hub = Hub()
    assistant = Assistant(hub.emit)
    hub.assistant = assistant
    for target in (assistant.voice_loop, assistant.reminder_loop, assistant.status_loop):
        threading.Thread(target=target, daemon=True).start()

    url = f"http://{config.HOST}:{config.PORT}"
    print(f"JARVIS interface: {url}   (Ctrl+C to quit)")
    if not args.no_browser:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    try:
        uvicorn.run(create_app(hub), host=config.HOST, port=config.PORT, log_level="warning")
    finally:
        assistant.shutdown.set()


if __name__ == "__main__":
    main()
