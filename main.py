"""Voice-to-Text: push-to-talk → Groq Whisper → paste.

Entry point. Runs the Qt event loop on the main thread and wires up the
hotkey listener, audio recorder, STT client, paster and overlay window.
Hotkey is configured in config.toml under [hotkey].
"""
from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # Python <3.11 fallback


def _app_dir() -> Path:
    """Folder next to the running file (.py) or executable (.exe).

    PyInstaller's --onefile sets ``sys.frozen`` and ``sys.executable`` points
    to the .exe; ``__file__`` would point to the temp extraction folder.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


def _redirect_output_when_no_console() -> None:
    """In --noconsole builds stdout/stderr can be None — every print() crashes.
    Pipe them to a log file next to the .exe so issues are debuggable."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    log_path = _app_dir() / "voice-to-text.log"
    f = open(log_path, "a", encoding="utf-8", buffering=1)
    sys.stdout = f
    sys.stderr = f


_redirect_output_when_no_console()

from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtGui import QIcon, QPixmap, QPainter, QBrush, QColor, QPen, QAction

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
        self.is_recording = False
        self.debounce_timer = None
        self.lock = threading.Lock()

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

        self._setup_tray(config.get("ui", {}).get("accent_color", "#5DADE2"))

    def _setup_tray(self, accent_color_hex: str):
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # Background circle
        painter.setBrush(QBrush(QColor(accent_color_hex)))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(4, 4, 56, 56)

        # Draw microphone (white)
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        # Mic body
        painter.drawRoundedRect(25, 16, 14, 22, 7, 7)

        # Pen for curves/lines
        pen = QPen(QColor(255, 255, 255), 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        # Cradle
        painter.drawArc(18, 22, 28, 20, -180 * 16, 180 * 16)
        # Stand
        painter.drawLine(32, 42, 32, 48)
        painter.drawLine(24, 48, 40, 48)

        painter.end()

        icon = QIcon(pixmap)

        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(icon)
        self.tray_icon.setToolTip("Voice-to-Text (активен)")

        menu = QMenu()

        title_action = QAction("Voice-to-Text", self)
        title_action.setEnabled(False)
        menu.addAction(title_action)

        menu.addSeparator()

        exit_action = QAction("Выйти", self)
        exit_action.triggered.connect(QApplication.instance().quit)
        menu.addAction(exit_action)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.show()

    def _on_hotkey_down(self):
        with self.lock:
            if self.debounce_timer is not None:
                self.debounce_timer.cancel()
                self.debounce_timer = None
                print("[Controller] Debounce: key-up canceled, recording continues.")
                return

            if self.is_recording:
                return

            self.is_recording = True

        self.show_overlay.emit()
        self.recorder.start()

    def _on_hotkey_up(self):
        with self.lock:
            if not self.is_recording:
                return
            if self.debounce_timer is not None:
                self.debounce_timer.cancel()

            self.debounce_timer = threading.Timer(0.2, self._real_hotkey_up)
            self.debounce_timer.start()

    def _real_hotkey_up(self):
        with self.lock:
            self.debounce_timer = None
            if not self.is_recording:
                return
            self.is_recording = False

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
    config_path = _app_dir() / "config.toml"
    if not config_path.exists():
        raise SystemExit(
            f"config.toml not found at {config_path}. "
            "Place config.toml next to the executable (or main.py)."
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
