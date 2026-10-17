# JARVIS: voice-controlled AI assistant (powered by Google Gemini)

Speak in English, Urdu or Punjabi. JARVIS listens, thinks with Gemini, answers aloud, and can do approved tasks on your computer. No Anthropic/Claude packages are used anywhere.

## Architecture

| File | Job |
|---|---|
| `main.py` | Entry point; wake word, conversation loop, reminders, emergency stop |
| `voice_input.py` | Microphone capture, noise adaptation, speech recognition |
| `voice_output.py` | Text-to-speech (gTTS online, pyttsx3 offline fallback for English) |
| `ai_brain.py` | Gemini chat with memory, tool calling, multilingual transcription |
| `web_search.py` | Live web answers via Gemini's Google Search grounding |
| `computer_control.py` | Approved actions only (apps, sites, files, notes, reminders, volume...) |
| `memory.py` | SQLite: history, notes, reminders, settings |
| `interface.py` + `static/index.html` | FastAPI + WebSocket dashboard (original artwork) |
| `config.py` | Settings, approved folders/apps; reads `.env` |

Flow: mic, then wake word ("Hey Jarvis", Google free recognizer), then your phrase is sent to Gemini for transcription (auto-detects language) and answered, then spoken. After the first reply you can keep talking without the wake word; after 45 s of silence (or "stop listening") it returns to standby.

## Setup

1. **Python 3.10+**.
2. **Get a Gemini API key** (free tier available): https://aistudio.google.com/apikey
3. Install:
   ```bash
   cd jarvis
   python -m venv .venv
   # Windows: .venv\Scripts\activate     macOS/Linux: source .venv/bin/activate
   pip install -r requirements.txt
   ```
   PyAudio needs system help on some platforms:
   - macOS: `brew install portaudio` then `pip install pyaudio`
   - Linux: `sudo apt install portaudio19-dev python3-dev xclip playerctl` then `pip install pyaudio`
   - Windows: `pip install pyaudio` normally works on recent Python.
4. Configure the key:
   ```bash
   cp .env.example .env      # Windows: copy .env.example .env
   ```
   Open `.env` and set `GEMINI_API_KEY=...`. The key stays on the server side; the browser never sees it. Never commit `.env`.
5. Run: `python main.py`, then the dashboard opens at http://127.0.0.1:8000. Allow microphone access when your OS/browser asks.

## Using it

- Press the **microphone button** to start talking immediately, or say **"Hey Jarvis"** while voice is on.
- Typing in the box works too, so you can test the brain before the audio setup.
- Say **"stop listening"** (or "go to sleep") for standby. **Emergency stop** (or the Esc key) closes the mic, silences speech, cancels pending confirmations and discards any reply in progress.
- Examples: "What's the time?", "Open YouTube", "Search the web for today's PKR to USD rate", "Create a note: buy milk", "Remind me at 6 pm to call Ali", "Turn the volume down", "Read my selected text", "Explain SQL joins simply", "Python mein list comprehension samjhao".

Computer tasks work in the **workspace** (`~/JarvisWorkspace`): put runnable scripts in `scripts/`; screenshots are saved to `screenshots/`. Add more approved folders via `JARVIS_APPROVED_FOLDERS`, and more apps by editing `APPS` in `config.py`.

## Security and privacy

- Least privilege: no arbitrary shell. Only whitelisted apps, files inside approved folders, `.py` files in `scripts/` (30 s timeout).
- Deleting files (to the recycle bin) and running scripts need a spoken/typed **yes in a later message**; the code enforces this, not just the prompt. JARVIS cannot send messages or make purchases.
- Screenshots and "read selected text" happen only when you ask. Reading selected text briefly uses the clipboard and restores it.
- The mic is open only when the dashboard shows **Mic is open** (red indicator). Audio is never saved. Voice snippets are processed in memory and sent to Google (wake word: Google speech recognizer; commands: Gemini). If that is unacceptable, don't use voice.
- Conversation history is stored locally in `data/jarvis.db`. Set `SAVE_HISTORY=false` to disable.
- The interface binds to `127.0.0.1` and rejects WebSocket connections from other websites.

## Testing

```bash
pytest -q                 # offline tests of safety rules and memory
python main.py            # then type "What is 17 times 23?" in the box (tests Gemini)
```
Check in order: typed chat, then speaker output, then microphone, then wake word.

## Common problems

| Symptom | Fix |
|---|---|
| "GEMINI_API_KEY is not set" | Create `.env` from `.env.example` and restart |
| "Gemini rejected my API key" | Re-copy the key from AI Studio; no quotes or spaces |
| Error 404 / model not found | Set `GEMINI_MODEL` to a current name from https://ai.google.dev/gemini-api/docs/models |
| "I've reached the usage limit" (429) | Wait a minute, or enable billing on the key's project |
| "Could not find PyAudio" | See PyAudio notes above |
| No microphone / permission error | Enable mic access for your terminal/Python (macOS: Privacy & Security, Microphone; Windows: Settings, Privacy, Microphone) |
| Wake word never triggers | Speak clearly, or just press the mic button; edit `WAKE_WORDS` |
| No sound / Urdu or Punjabi not spoken | gTTS needs internet; check speakers. Punjabi is written in Shahmukhi and voiced with the Urdu voice (`PUNJABI_TTS_LANG`) |
| Volume/media keys do nothing | Windows works best; macOS has volume only; Linux needs `pactl`/`playerctl` |
| Port already in use | Set `JARVIS_PORT` in `.env` |

## Ideas for later

Offline wake word (Porcupine/openWakeWord), streaming replies, a real audio-level visualizer from the mic stream, an app allow-list editor in the UI.
