# Windows Voice-to-Text

Lightweight push-to-talk dictation utility for Windows. Hold a hotkey, speak, release it, and the transcription is pasted into the currently focused app.

- **Default hotkey:** hold `Right Alt + Space`
- **Speech-to-text:** Groq Whisper (`whisper-large-v3`)
- **Optional fallback:** OpenAI Whisper (`whisper-1`)
- **Languages:** automatic detection, including Russian and English
- **UI:** small bottom-center recording indicator with a live equalizer

## Requirements

- Windows 10/11
- Python 3.10+
- A Groq API key: <https://console.groq.com/keys>

If Python is not installed, install it with:

```powershell
winget install Python.Python.3.12
```

## Installation

```powershell
git clone https://github.com/AlexanderLab985/windows-voice-to-text.git
cd windows-voice-to-text
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

## Configuration

Create your local config from the example:

```powershell
copy config.example.toml config.toml
notepad config.toml
```

In `config.toml`, paste your keys here:

```toml
[api]
provider = "groq"
groq_api_key = "paste-your-groq-api-key-here"
openai_api_key = ""
```

What to insert:

- `groq_api_key`: your Groq API key from <https://console.groq.com/keys>. This is required when `provider = "groq"`.
- `openai_api_key`: optional OpenAI API key from <https://platform.openai.com/api-keys>. Leave it empty unless you want OpenAI Whisper as a fallback.

Do not commit or share `config.toml`; it contains private API keys. The repository only includes `config.example.toml`.

## Run

```powershell
python main.py
```

Expected console message:

```text
Voice-to-Text ready. Hold alt_r + space to dictate. Ctrl+C to quit.
```

Usage:

1. Put the text cursor into any app: Notepad, browser, Word, Telegram, IDE, etc.
2. Hold `Right Alt + Space`.
3. Speak.
4. Release the hotkey.
5. The recognized text is pasted into the focused app.

Stop the app with `Ctrl+C` in the console.

## Hotkey

The default hotkey is configured in `config.toml`:

```toml
[hotkey]
keys = ["alt_r", "space"]
```

Supported key names include `ctrl_r`, `ctrl_l`, `alt_r`, `alt_l`, `alt_gr`, `shift_r`, `shift_l`, `space`, `f1`...`f12`, `pause`, and `scroll_lock`.

## Project structure

```text
main.py              Qt event loop and app controller
hotkey.py            global push-to-talk hotkey listener
recorder.py          microphone recording and live FFT levels
stt.py               Groq/OpenAI transcription client
paster.py            clipboard paste into the active window
overlay.py           frameless recording overlay
config.example.toml  public configuration template
requirements.txt     Python dependencies
```

## Known limitations

- Windows Defender or other security tools may warn about the global keyboard listener. This is expected for push-to-talk utilities.
- Paste uses clipboard + synthetic `Ctrl+V`; it may not work in some games, RDP sessions, or restricted terminal windows.
- Microphone, overlay, and global hotkey behavior are Windows-specific and should be tested on the target machine.

## Packaging to `.exe` optional

```powershell
pip install pyinstaller
pyinstaller --onefile --noconsole --name windows-voice-to-text main.py
```

The executable will be created in `dist\`.

## License

MIT
