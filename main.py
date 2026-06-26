"""Voice-to-Text: push-to-talk → Groq Whisper → paste.

Entry point. Runs the Qt event loop on the main thread and wires up the
hotkey listener, audio recorder, STT client, paster and overlay window.
Hotkey is configured in config.toml under [hotkey].
"""
from __future__ import annotations

import sys
import threading
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # Python <3.11 fallback

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QObject, Signal

from hotkey import HotkeyListener
from recorder import Recorder
from stt import transcribe
from paster import paste_text
from overlay import OverlayWindow


class Controller(QObject):
    """Wires hotkey events to recorder/STT/paste and drives the overlay.

    All Qt widget updates travel through Qt signals so they run on the main
    thread regardless of which background thread fires the original event.
    """

    show_overlay = Signal()
    hide_overlay = Signal()
    level_update = Signal(list)
    set_processing = Signal(bool)

    def __init__(self, config: dict, overlay: OverlayWindow):
        super().__init__()
        self.config = config
        self.overlay = overlay

        self.recorder = Recorder(
            sample_rate=config["audio"]["sample_rate"],
            channels=config["audio"]["channels"],
            level_callback=self._on_level_chunk,
        )
        self.hotkey = HotkeyListener(
            on_press=self._on_hotkey_down,
            on_release=self._on_hotkey_up,
            key_names=config.get("hotkey", {}).get("keys", ["ctrl_r"]),
        )

        self.show_overlay.connect(overlay.show_recording)
        self.hide_overlay.connect(overlay.hide_recording)
        self.level_update.connect(overlay.update_levels)
        self.set_processing.connect(overlay.set_processing)

    def _on_hotkey_down(self):
        self.show_overlay.emit()
        self.recorder.start()

    def _on_hotkey_up(self):
        audio = self.recorder.stop()
        self.hide_overlay.emit()
        threading.Thread(target=self._process, args=(audio,), daemon=True).start()

    def _process(self, audio_bytes: bytes):
        self.set_processing.emit(True)
        try:
            text = transcribe(audio_bytes, self.config["api"])
            if text:
                paste_text(text)
                print(f"→ {text}")
            else:
                print("(empty transcription)")
        except Exception as exc:
            print(f"STT failed: {exc}", file=sys.stderr)
        finally:
            self.set_processing.emit(False)

    def _on_level_chunk(self, levels):
        self.level_update.emit(levels)


def load_config() -> dict:
    config_path = Path(__file__).parent / "config.toml"
    if not config_path.exists():
        raise SystemExit(
            f"config.toml not found at {config_path}. "
            "Copy config.example.toml to config.toml and fill in your API key."
        )
    with open(config_path, "rb") as f:
        return tomllib.load(f)


def main():
    config = load_config()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # overlay hides often — don't quit

    overlay = OverlayWindow(config.get("ui", {}))
    controller = Controller(config, overlay)
    controller.hotkey.start()

    hotkey_label = " + ".join(config.get("hotkey", {}).get("keys", ["ctrl_r"]))
    print(f"Voice-to-Text ready. Hold {hotkey_label} to dictate. Ctrl+C to quit.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
