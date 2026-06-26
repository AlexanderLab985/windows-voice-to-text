"""Push-to-talk audio recorder with live FFT levels for the overlay."""
from __future__ import annotations

import io
import threading
import wave

import numpy as np
import sounddevice as sd


N_BARS = 16


class Recorder:
    """Records audio while active; computes 16-band FFT levels on each callback
    so the overlay can draw an equalizer in real time.
    """

    def __init__(self, sample_rate: int, channels: int, level_callback):
        self.sample_rate = sample_rate
        self.channels = channels
        self._level_callback = level_callback
        self._buffer: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None
        self._lock = threading.Lock()

    def start(self):
        with self._lock:
            self._buffer = []
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="float32",
            callback=self._audio_callback,
            blocksize=int(self.sample_rate * 0.04),  # 40 ms = 25 fps
        )
        self._stream.start()

    def stop(self) -> bytes:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        with self._lock:
            if not self._buffer:
                return b""
            audio = np.concatenate(self._buffer, axis=0)

        # Encode to int16 mono WAV (standard STT input)
        audio_int16 = np.clip(audio * 32767.0, -32768, 32767).astype(np.int16)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio_int16.tobytes())
        return buf.getvalue()

    def _audio_callback(self, indata, frames, time_info, status):
        # indata shape: (frames, channels)
        with self._lock:
            self._buffer.append(indata.copy())

        try:
            mono = indata[:, 0] if self.channels > 1 else indata.flatten()
            spectrum = np.abs(np.fft.rfft(mono))
            n = len(spectrum)
            if n < N_BARS + 1:
                return
            # log-spaced bin edges from bin 1..(n-1); skip DC
            edges = np.unique(np.logspace(0, np.log10(n - 1), N_BARS + 1).astype(int))
            if len(edges) < N_BARS + 1:
                edges = np.linspace(1, n - 1, N_BARS + 1, dtype=int)
            bars = []
            for i in range(N_BARS):
                seg = spectrum[edges[i]:edges[i + 1] + 1]
                bars.append(float(seg.mean()) if len(seg) else 0.0)
            peak = max(bars) if max(bars) > 0 else 1.0
            # Soft ceiling so quiet moments still show small bars
            norm = [min(1.0, b / (peak * 1.2)) for b in bars]
            self._level_callback(norm)
        except Exception:
            # Never let viz math break the audio stream
            pass
