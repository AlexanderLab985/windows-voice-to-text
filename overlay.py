"""Frameless, topmost, click-through minimal status overlay."""
from __future__ import annotations

import time
import math

from PySide6.QtCore import Qt, QTimer, QRect
from PySide6.QtGui import QPainter, QColor, QFont, QBrush, QPen
from PySide6.QtWidgets import QWidget, QApplication


N_BARS = 16


class OverlayWindow(QWidget):
    WIDTH = 136
    HEIGHT = 36

    def __init__(self, ui_config: dict):
        super().__init__()
        self.accent = QColor(ui_config.get("accent_color", "#5DADE2"))
        self.bg = QColor(18, 18, 18, 218)
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
        # Smooth the microphone levels heavily. The overlay is intentionally
        # calm: it should confirm that recording is active without twitching.
        new = list(levels)
        if len(self.levels) != len(new):
            self.levels = new
            return

        rise, fall = 0.42, 0.16
        self.levels = [
            cur + (tgt - cur) * (rise if tgt > cur else fall)
            for cur, tgt in zip(self.levels, new)
        ]

    def set_processing(self, is_processing: bool):
        self.processing = is_processing
        if is_processing:
            self._position_bottom_center()
            self.show()
            self._repaint_timer.start()
        else:
            self._repaint_timer.stop()
            self.hide()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Compact dark pill. Keep it deliberately quiet: no equalizer, no large
        # labels, just a status dot and a timer/text hint.
        painter.setBrush(QBrush(self.bg))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect(), self.HEIGHT // 2, self.HEIGHT // 2)

        margin = 14
        dot_x = margin + 5
        center_y = self.HEIGHT // 2

        font = QFont()
        font.setPointSize(10)
        font.setBold(False)
        painter.setFont(font)

        if self.processing:
            # Subtle breathing dot while awaiting STT result.
            phase = (time.time() * 1.6) % 1.0
            alpha = int(105 + 95 * (0.5 + 0.5 * abs(phase - 0.5) * 2))
            c = QColor(self.accent)
            c.setAlpha(alpha)
            painter.setBrush(QBrush(c))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(dot_x - 4, center_y - 4, 8, 8)

            painter.setPen(QPen(QColor(220, 220, 220)))
            text_rect = QRect(32, 0, self.WIDTH - 46, self.HEIGHT)
            painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, "processing")
            return

        # Recording state: static accent dot + elapsed time + tiny calm
        # microphone visualizer. Keep the same compact dimensions.
        painter.setBrush(QBrush(self.accent))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(dot_x - 4, center_y - 4, 8, 8)

        elapsed = time.time() - self._rec_start_ts
        m = int(elapsed) // 60
        s = int(elapsed) % 60
        timer_str = f"{m}:{s:02d}"
        painter.setPen(QPen(QColor(220, 220, 220)))
        text_rect = QRect(32, 0, 38, self.HEIGHT)
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, timer_str)

        viz_x = 78
        viz_y = center_y
        bar_w = 3
        gap = 4
        max_h = 14
        grouped_levels = self._visualizer_levels()
        painter.setBrush(QBrush(self.accent))
        painter.setPen(Qt.NoPen)
        for i, lvl in enumerate(grouped_levels):
            # Slow breathing floor keeps the visualizer alive even in pauses,
            # while live levels gently raise the bars during speech.
            breath = 0.18 + 0.10 * (0.5 + 0.5 * math.sin(time.time() * 2.1 + i * 0.9))
            value = min(1.0, max(breath, lvl * 1.55))
            h = max(3, int(value * max_h))
            x = viz_x + i * (bar_w + gap)
            painter.drawRoundedRect(QRect(x, viz_y - h // 2, bar_w, h), 2, 2)

    def _visualizer_levels(self) -> list[float]:
        if not self.levels:
            return [0.0] * 5

        groups = [
            self.levels[0:3],
            self.levels[3:6],
            self.levels[6:10],
            self.levels[10:13],
            self.levels[13:16],
        ]
        return [sum(group) / len(group) if group else 0.0 for group in groups]
