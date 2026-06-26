"""Speech-to-text via Groq Whisper-large-v3 with OpenAI Whisper fallback."""
from __future__ import annotations

import io
import requests


GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
OPENAI_URL = "https://api.openai.com/v1/audio/transcriptions"

TIMEOUT_S = 30


def transcribe(audio_wav: bytes, api_config: dict) -> str | None:
    if not audio_wav:
        return None

    provider = api_config.get("provider", "groq").lower()

    if provider == "groq":
        try:
            return _groq(audio_wav, api_config.get("groq_api_key", ""))
        except Exception as exc:
            print(f"Groq failed: {exc}")
            if api_config.get("openai_api_key"):
                print("Falling back to OpenAI Whisper.")
                return _openai(audio_wav, api_config["openai_api_key"])
            raise
    elif provider == "openai":
        return _openai(audio_wav, api_config.get("openai_api_key", ""))
    else:
        raise ValueError(f"Unknown STT provider: {provider!r}")


def _groq(wav: bytes, api_key: str) -> str:
    if not api_key:
        raise RuntimeError("groq_api_key is empty in config.toml")
    files = {"file": ("audio.wav", io.BytesIO(wav), "audio/wav")}
    data = {
        "model": "whisper-large-v3",
        "response_format": "json",
        # language omitted → Whisper auto-detects ru/en/etc.
    }
    r = requests.post(
        GROQ_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        files=files,
        data=data,
        timeout=TIMEOUT_S,
    )
    r.raise_for_status()
    return r.json().get("text", "").strip()


def _openai(wav: bytes, api_key: str) -> str:
    if not api_key:
        raise RuntimeError("openai_api_key is empty in config.toml")
    files = {"file": ("audio.wav", io.BytesIO(wav), "audio/wav")}
    data = {"model": "whisper-1", "response_format": "json"}
    r = requests.post(
        OPENAI_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        files=files,
        data=data,
        timeout=TIMEOUT_S,
    )
    r.raise_for_status()
    return r.json().get("text", "").strip()
