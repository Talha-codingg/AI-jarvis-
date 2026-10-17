"""Microphone test. Put this file in the jarvis folder and run:  python mic_test.py"""
import array

import speech_recognition as sr

print("Microphones found:")
for i, name in enumerate(sr.Microphone.list_microphone_names()):
    print(f"  {i}: {name}")

r = sr.Recognizer()
with sr.Microphone() as src:
    r.adjust_for_ambient_noise(src, duration=1)
    print("\nBackground noise level:", round(r.energy_threshold))
    print(">>> SPEAK NOW (say: 'hello testing one two three') <<<")
    try:
        audio = r.listen(src, timeout=8, phrase_time_limit=5)
    except sr.WaitTimeoutError:
        raise SystemExit("Heard nothing for 8 seconds: the microphone is silent or muted.")

samples = array.array("h", audio.get_raw_data(convert_rate=16000, convert_width=2))
peak = max((abs(x) for x in samples), default=0)
print(f"\nPeak volume: {peak}  (max 32767; below ~1000 means too quiet)")

for lang in ("en-IN", "hi-IN", "ur-PK"):
    try:
        print(f"{lang} -> {r.recognize_google(audio, language=lang)}")
    except sr.UnknownValueError:
        print(f"{lang} -> could not understand")
    except sr.RequestError as e:
        print("Google speech service not reachable (internet?):", e)
        break