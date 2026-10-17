"""Microphone capture and speech recognition. Audio is kept in memory only; nothing is written to disk."""
import speech_recognition as sr

import config


class MicrophoneError(RuntimeError):
    pass


MIC_HELP = ("I can't use the microphone. Make sure one is connected, microphone access is allowed in your "
            "system privacy settings, and PyAudio is installed (see the README).")


class VoiceInput:
    def __init__(self):
        self.r = sr.Recognizer()
        self.r.dynamic_energy_threshold = True  # adapts to background noise
        self.r.energy_threshold = 300
        self.r.pause_threshold = 1.0
        self.r.non_speaking_duration = 0.6
        self._calibrated = False

    @staticmethod
    def available() -> bool:
        try:
            return len(sr.Microphone.list_microphone_names()) > 0
        except Exception:
            return False

    def capture(self, timeout: float, phrase_limit: float):
        """Record one phrase. Returns AudioData, or None if nobody spoke before the timeout."""
        try:
            with sr.Microphone() as source:
                if not self._calibrated:
                    self.r.adjust_for_ambient_noise(source, duration=0.8)
                    self._calibrated = True
                return self.r.listen(source, timeout=timeout, phrase_time_limit=phrase_limit)
        except sr.WaitTimeoutError:
            return None
        except (OSError, AttributeError) as e:  # no device, no permission, PyAudio missing
            raise MicrophoneError(MIC_HELP) from e

    def wake_listen(self):
        """Listen briefly for the wake word. Returns lowercase text, or None."""
        audio = self.capture(timeout=5, phrase_limit=5)
        if audio is None:
            return None
        try:
            return self.r.recognize_google(audio, language="en-IN").lower()
        except sr.UnknownValueError:
            return None  # noise or unclear speech: just keep listening

    def transcribe(self, audio, brain=None) -> str:
        """Gemini first (handles English/Urdu/Punjabi); Google free recognizer as a fallback."""
        if brain is not None:
            try:
                return brain.transcribe(audio.get_wav_data(convert_rate=16000, convert_width=2))
            except Exception as e:
                print(f"[voice] Gemini transcription failed, using fallback: {e}")
        for lang in config.STT_FALLBACK_LANGS:
            try:
                return self.r.recognize_google(audio, language=lang)
            except sr.UnknownValueError:
                continue
        return ""
