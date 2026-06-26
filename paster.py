"""Paste transcribed text into the active window via clipboard + Ctrl+V.

Uses Win32 SendInput directly via ctypes for reliable synthetic keystrokes
(pyautogui's keybd_event-based path is occasionally ignored on Win10/11).
Preserves the user's clipboard contents, restored ~300 ms after paste.
"""
from __future__ import annotations

import sys
import time

import pyperclip


# Virtual-key codes
VK_CONTROL  = 0x11
VK_LCONTROL = 0xA2
VK_RCONTROL = 0xA3
VK_LMENU    = 0xA4   # Left Alt
VK_RMENU    = 0xA5   # Right Alt
VK_LSHIFT   = 0xA0
VK_RSHIFT   = 0xA1
VK_LWIN     = 0x5B
VK_RWIN     = 0x5C
VK_V        = 0x56

INPUT_KEYBOARD  = 1
KEYEVENTF_KEYUP = 0x0002


if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    PUL = ctypes.POINTER(ctypes.c_ulong)

    class _KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", wintypes.WORD),
            ("wScan", wintypes.WORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", PUL),
        ]

    class _INPUT_UNION(ctypes.Union):
        _fields_ = [("ki", _KEYBDINPUT), ("_pad", ctypes.c_byte * 32)]

    class _INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("u", _INPUT_UNION)]

    _SendInput = ctypes.windll.user32.SendInput
    _SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int)
    _SendInput.restype = wintypes.UINT

    def _key_event(vk: int, key_up: bool) -> _INPUT:
        inp = _INPUT()
        inp.type = INPUT_KEYBOARD
        inp.u.ki = _KEYBDINPUT(
            wVk=vk,
            wScan=0,
            dwFlags=KEYEVENTF_KEYUP if key_up else 0,
            time=0,
            dwExtraInfo=None,
        )
        return inp

    def _send(events):
        arr = (_INPUT * len(events))(*events)
        _SendInput(len(events), arr, ctypes.sizeof(_INPUT))

    def _release_modifiers():
        keys = (VK_LCONTROL, VK_RCONTROL, VK_LMENU, VK_RMENU,
                VK_LSHIFT, VK_RSHIFT, VK_LWIN, VK_RWIN)
        _send([_key_event(k, key_up=True) for k in keys])

    def _send_ctrl_v():
        _send([
            _key_event(VK_CONTROL, key_up=False),
            _key_event(VK_V,       key_up=False),
            _key_event(VK_V,       key_up=True),
            _key_event(VK_CONTROL, key_up=True),
        ])

else:
    def _release_modifiers(): pass
    def _send_ctrl_v(): pass


def paste_text(text: str) -> None:
    if not text:
        return

    try:
        original = pyperclip.paste()
    except Exception:
        original = None

    _release_modifiers()
    time.sleep(0.05)

    pyperclip.copy(text)
    time.sleep(0.10)
    _send_ctrl_v()
    time.sleep(0.30)

    if original is not None:
        try:
            pyperclip.copy(original)
        except Exception:
            pass
