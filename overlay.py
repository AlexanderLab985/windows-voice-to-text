"""Frameless, topmost, click-through pill overlay with a live equalizer."""
from __future__ import annotations

import time

from PySide6.QtCore import Qt, QTimer, QRect
from PySide6.QtGui import QPainter, QColor, QFont, QBrush, QPen
from PySide6.QtWidgets import QWidget, QApplication


N_BARS = 16


class OverlayWindow(QWidget):
    WIDTH = 220
    HEIGHT = 48

    def __init__(self, ui_config: dict):
        super().__init__()
        self.accent = QColor(ui_config.get("accent_color", "#5DADE2"))
        self.bg = QColor(0x1E, 0x1E, 0x1E, 235)
        self.levels: list[float] = [0.0] * N_BARS
        self.processing = False
        self._rec_start_ts = 0.0

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.resize(self.WIDTH, self.HEIGHT)
        self._position_bottom_center()

        self._repaint_timer = QTimer(self)
        self._repaint_timer.timeout.connect(self.update)
        self._repaint_timer.setInterval(33)  # ~30 fps

    def _position_bottom_center(self):
        screen = QApplication.primaryScreen().availableGeometry()
        x = (screen.width() - self.WIDTH) // 2
        y = screen.height() - self.HEIGHT - 120
        self.move(x, y)

    # Slots — all invoked on the Qt main thread via signals from Controller.
    def show_recording(self):
        self.processing = False
        self._rec_start_ts = time.time()
        self.levels = [0.0] * N_BARS
        self._position_bottom_center()  # re-check in case of screen change
        self.show()
        self._repaint_timer.start()

    def hide_recording(self):
        # Keep visible — transition to processing is handled by set_processing
        pass

    def update_levels(self, levels):
        new = list(levels)
        if len(self.levels) != len(new):
            self.levels = new
            return
        # Asymmetric smoothing: rise fast, fall slow — classic VU-meter feel.
        rise, fall = 0.55, 0.18
        self.levels = [
            cur + (tgt - cur) * (rise if tgt > cur else fall)
            for cur, tgt in zip(self.levels, new)
        ]

    def set_processing(self, is_processing: bool):
        self.processing = is_processing
        if not is_processing:
            self._repaint_timer.stop()
            self.hide()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Pill background
        painter.setBrush(QBrush(self.bg))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect(), 24, 24)

        margin = 14
        timer_w = 50
        eq_area_w = self.WIDTH - 2 * margin - timer_w
        gap = 2
        bar_w = max(2, (eq_area_w // N_BARS) - gap)

        if self.processing:
            # Pulsing dot while awaiting STT result
            phase = (time.time() * 2) % 1.0
            alpha = int(120 + 135 * (0.5 + 0.5 * abs(phase - 0.5) * 2))
            c = QColor(self.accent)
            c.setAlpha(alpha)
            painter.setBrush(QBrush(c))
            painter.drawEllipse(self.rect().center(), 5, 5)
            return

        # Equalizer
        painter.setBrush(QBrush(self.accent))
        x = margin
        y_center = self.HEIGHT // 2
        max_h = self.HEIGHT - 16
        for lvl in self.levels:
            h = max(2, int(lvl * max_h))
            rect = QRect(x, y_center - h // 2, bar_w, h)
            painter.drawRoundedRect(rect, 2, 2)
            x += bar_w + gap

        # Timer on the right
        elapsed = time.time() - self._rec_start_ts
        m = int(elapsed) // 60
        s = int(elapsed) % 60
        timer_str = f"{m}:{s:02d}"
        painter.setPen(QPen(QColor(210, 210, 210)))
        font = QFont()
        font.setPointSize(10)
        font.setBold(True)
        painter.setFont(font)
        timer_rect = QRect(self.WIDTH - margin - timer_w + 5, 0, timer_w - 5, self.HEIGHT)
        painter.drawText(timer_rect, Qt.AlignVCenter | Qt.AlignRight, timer_str)
