"""Configurable push-to-talk hotkey listener (pynput).

Configured via a list of key names from config.toml. When ALL keys in the list
are held simultaneously, on_press fires. When ANY of them is released after
that, on_release fires.

- Single key (e.g. ["ctrl_r"]) → pure hold-to-talk on one key.
- Combo (e.g. ["alt_r", "space"]) → all must be down to activate.

Right Alt on EU/AltGr layouts is reported as Key.alt_gr; we accept both.
"""
from __future__ import annotations

from pynput import keyboard
from pynput.keyboard import Key


_KEY_MAP: dict[str, tuple] = {
    "ctrl_r":  (Key.ctrl_r,),
    "ctrl_l":  (Key.ctrl_l,),
    "alt_r":   (Key.alt_r, Key.alt_gr),
    "alt_l":   (Key.alt_l,),
    "alt_gr":  (Key.alt_r, Key.alt_gr),
    "shift_r": (Key.shift_r,),
    "shift_l": (Key.shift_l,),
    "space":   (Key.space,),
    "f1":  (Key.f1,),  "f2":  (Key.f2,),  "f3":  (Key.f3,),  "f4":  (Key.f4,),
    "f5":  (Key.f5,),  "f6":  (Key.f6,),  "f7":  (Key.f7,),  "f8":  (Key.f8,),
    "f9":  (Key.f9,),  "f10": (Key.f10,), "f11": (Key.f11,), "f12": (Key.f12,),
    "pause": (Key.pause,),
    "scroll_lock": (Key.scroll_lock,),
}


class HotkeyListener:
    def __init__(self, on_press, on_release, key_names: list[str]):
        if not key_names:
            raise ValueError("key_names must contain at least one key")
        self._on_press_cb = on_press
        self._on_release_cb = on_release
        self._key_groups: list[set] = []
        for name in key_names:
            keys = _KEY_MAP.get(name)
            if keys is None:
                raise ValueError(
                    f"Unknown hotkey {name!r}. Known: {sorted(_KEY_MAP)}"
                )
            self._key_groups.append(set(keys))
        self._down = [False] * len(self._key_groups)
        self._active = False
        self._listener: keyboard.Listener | None = None

    def start(self):
        self._listener = keyboard.Listener(
            on_press=self._handle_press,
            on_release=self._handle_release,
        )
        self._listener.start()

    def stop(self):
        if self._listener:
            self._listener.stop()
            self._listener = None

    def _key_index(self, key):
        for i, group in enumerate(self._key_groups):
            if key in group:
                return i
        return None

    def _handle_press(self, key):
        idx = self._key_index(key)
        if idx is None:
            return
        self._down[idx] = True
        if all(self._down) and not self._active:
            self._active = True
            try:
                self._on_press_cb()
            except Exception:
                import traceback; traceback.print_exc()

    def _handle_release(self, key):
        idx = self._key_index(key)
        if idx is None:
            return
        was_active = self._active
        self._down[idx] = False
        if was_active and not all(self._down):
            self._active = False
            try:
                self._on_release_cb()
            except Exception:
                import traceback; traceback.print_exc()
