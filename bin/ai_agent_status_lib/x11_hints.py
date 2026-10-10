"""Keep the widget's X11 windows above, on every workspace and off the taskbar.

Qt has no "sticky" flag, and a frameless ``Qt.Tool`` window comes out of Qt's xcb
backend unlike the GTK window this project used to ship: it is transient for the
application's group leader and advertises several window types (UTILITY, KDE
OVERRIDE, NORMAL). Muffin/Mutter also drop ``_NET_WM_STATE_ABOVE`` now and then.
This module talks EWMH to the window manager directly through libX11 (ctypes, no
``wmctrl`` needed), the way GTK did:

* ``WM_TRANSIENT_FOR`` is removed and ``_NET_WM_WINDOW_TYPE`` set to UTILITY only;
* ABOVE, STICKY, SKIP_TASKBAR and SKIP_PAGER are requested with ``_NET_WM_STATE``
  client messages, and ``_NET_WM_DESKTOP`` is set to "all desktops".

Requests are idempotent, so the widget simply repeats them every second. Without
libX11 (macOS, Windows, Wayland-only) ``X11Hints.open()`` returns None.
"""

from __future__ import annotations

import ctypes
import ctypes.util
from typing import Callable

NET_WM_STATE_ADD = 1
SOURCE_APPLICATION = 1
ALL_DESKTOPS = 0xFFFFFFFF
SUBSTRUCTURE_NOTIFY_MASK = 1 << 19
SUBSTRUCTURE_REDIRECT_MASK = 1 << 20
CLIENT_MESSAGE = 33
XA_ATOM = 4
XA_WM_TRANSIENT_FOR = 68
PROP_MODE_REPLACE = 0
STATES = ("_NET_WM_STATE_ABOVE", "_NET_WM_STATE_STICKY", "_NET_WM_STATE_SKIP_TASKBAR", "_NET_WM_STATE_SKIP_PAGER")


class XClientMessageEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("window", ctypes.c_ulong),
        ("message_type", ctypes.c_ulong),
        ("format", ctypes.c_int),
        ("data", ctypes.c_long * 5),
    ]


class XEvent(ctypes.Union):
    _fields_ = [("xclient", XClientMessageEvent), ("pad", ctypes.c_long * 24)]


def load_libx11() -> ctypes.CDLL | None:
    name = ctypes.util.find_library("X11")
    if not name:
        return None
    try:
        lib = ctypes.CDLL(name)
    except OSError:
        return None
    lib.XOpenDisplay.restype = ctypes.c_void_p
    lib.XOpenDisplay.argtypes = [ctypes.c_char_p]
    lib.XCloseDisplay.argtypes = [ctypes.c_void_p]
    lib.XDefaultRootWindow.restype = ctypes.c_ulong
    lib.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
    lib.XInternAtom.restype = ctypes.c_ulong
    lib.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
    lib.XSendEvent.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_long, ctypes.POINTER(XEvent)]
    lib.XChangeProperty.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_void_p, ctypes.c_int]
    lib.XDeleteProperty.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong]
    lib.XFlush.argtypes = [ctypes.c_void_p]
    return lib


class X11Hints:
    """One private X connection that re-asserts the floating-window hints."""

    def __init__(self, lib: ctypes.CDLL, display: int, log: Callable[[str], None]) -> None:
        self.lib = lib
        self.display = display
        self.log = log
        self.root = lib.XDefaultRootWindow(display)
        self.atoms: dict[str, int] = {}
        self.typed: set[int] = set()

    @classmethod
    def open(cls, log: Callable[[str], None] = lambda _message: None) -> "X11Hints | None":
        lib = load_libx11()
        if lib is None:
            return None
        display = lib.XOpenDisplay(None)
        if not display:
            return None
        return cls(lib, display, log)

    def atom(self, name: str) -> int:
        if name not in self.atoms:
            self.atoms[name] = self.lib.XInternAtom(self.display, name.encode("ascii"), 0)
        return self.atoms[name]

    def client_message(self, window: int, message_type: str, *data: int) -> None:
        event = XEvent()
        message = event.xclient
        message.type = CLIENT_MESSAGE
        message.send_event = 1
        message.window = window
        message.message_type = self.atom(message_type)
        message.format = 32
        for index, value in enumerate(data[:5]):
            message.data[index] = ctypes.c_long(value).value
        self.lib.XSendEvent(self.display, self.root, 0, SUBSTRUCTURE_REDIRECT_MASK | SUBSTRUCTURE_NOTIFY_MASK,
                            ctypes.byref(event))

    def set_utility_type(self, window: int) -> None:
        """GTK's shape: a UTILITY window that is not transient for anything."""
        self.lib.XDeleteProperty(self.display, window, XA_WM_TRANSIENT_FOR)
        value = (ctypes.c_ulong * 1)(self.atom("_NET_WM_WINDOW_TYPE_UTILITY"))
        self.lib.XChangeProperty(self.display, window, self.atom("_NET_WM_WINDOW_TYPE"), XA_ATOM, 32,
                                 PROP_MODE_REPLACE, value, 1)

    def apply(self, window: int) -> None:
        """Request above + sticky + skip taskbar/pager for a mapped top-level window."""
        if window not in self.typed:
            self.set_utility_type(window)
            self.typed.add(window)
        for first, second in zip(STATES[::2], STATES[1::2]):
            self.client_message(window, "_NET_WM_STATE", NET_WM_STATE_ADD, self.atom(first), self.atom(second),
                                SOURCE_APPLICATION, 0)
        self.client_message(window, "_NET_WM_DESKTOP", ALL_DESKTOPS, SOURCE_APPLICATION, 0, 0, 0)
        self.lib.XFlush(self.display)

    def forget(self, window: int) -> None:
        self.typed.discard(window)

    def close(self) -> None:
        if self.display:
            self.lib.XCloseDisplay(self.display)
            self.display = 0
