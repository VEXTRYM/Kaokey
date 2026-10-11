"""Best-effort AT-SPI focus/caret events for the X11 popup.

This is deliberately an optional accelerator. A running application may not
emit events or may not expose a valid Text caret. In those cases the existing
bounded on-demand search remains the authoritative fallback.
"""
from __future__ import annotations

import ctypes
import threading
import time
from collections import deque
from typing import TYPE_CHECKING

from kaokey.platforms.linux.native_accessibility import (
    LinuxAccessibleTarget,
    _ATSPI_CALL_LOCK,
    _load_atspi,
)

if TYPE_CHECKING:
    from kaokey.platforms.linux.native_accessibility import LinuxAccessibility


class _AtspiEvent(ctypes.Structure):
    # Only the fixed leading fields of AtspiEvent are accessed; later fields
    # such as GValue and sender differ across libatspi releases.
    _fields_ = [
        ("type", ctypes.c_char_p),
        ("source", ctypes.c_void_p),
        ("detail1", ctypes.c_int),
        ("detail2", ctypes.c_int),
    ]


_EVENT_CALLBACK = ctypes.CFUNCTYPE(
    None, ctypes.POINTER(_AtspiEvent), ctypes.c_void_p
)
_EVENTS = (
    b"object:state-changed:focused",
    b"object:text-caret-moved",
)
_MAX_EVENTS = 32
_MAX_EVENT_AGE_SECONDS = 30.0
_MAX_CANDIDATES_PER_REQUEST = 8


class X11CaretEventTracker:
    """Own a GLib event pump and short-lived references to AT-SPI objects.

    Event callbacks only keep references; they never make synchronous D-Bus
    requests. PID and caret validation run in the already asynchronous popup
    capture worker, so browser accessibility requests cannot freeze Qt.
    """

    def __init__(self) -> None:
        self._mutex = threading.Lock()
        self._recent: deque[tuple[int, float]] = deque()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._callback: object | None = None
        self._library = None
        self._listener: int | None = None
        self.diagnostics = "event listener not ready"

    def start(self) -> None:
        if self._thread is not None:
            return

        self._thread = threading.Thread(
            target=self._run,
            name="kaokey-x11-atspi-events",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        library = self._library

        if library is not None:
            try:
                library.glib.g_main_context_wakeup(None)
            except Exception:
                pass

        thread = self._thread

        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=0.75)

    def _run(self) -> None:
        library = None
        listener = None
        registered: list[bytes] = []

        try:
            library = _load_atspi()

            if library is None or self._stop.is_set():
                self.diagnostics = "AT-SPI unavailable for event subscription"
                return

            atspi = library.atspi
            atspi.atspi_event_listener_new.argtypes = [
                ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
            ]
            atspi.atspi_event_listener_new.restype = ctypes.c_void_p
            atspi.atspi_event_listener_register.argtypes = [
                ctypes.c_void_p, ctypes.c_char_p, ctypes.c_void_p,
            ]
            atspi.atspi_event_listener_register.restype = ctypes.c_int
            atspi.atspi_event_listener_deregister.argtypes = [
                ctypes.c_void_p, ctypes.c_char_p, ctypes.c_void_p,
            ]
            atspi.atspi_event_listener_deregister.restype = ctypes.c_int
            atspi.atspi_accessible_get_application.argtypes = [
                ctypes.c_void_p, ctypes.c_void_p,
            ]
            atspi.atspi_accessible_get_application.restype = ctypes.c_void_p

            library.gobject.g_object_ref.argtypes = [ctypes.c_void_p]
            library.gobject.g_object_ref.restype = ctypes.c_void_p
            library.glib.g_main_context_iteration.argtypes = [
                ctypes.c_void_p, ctypes.c_int,
            ]
            library.glib.g_main_context_iteration.restype = ctypes.c_int
            library.glib.g_main_context_wakeup.argtypes = [ctypes.c_void_p]
            library.glib.g_main_context_wakeup.restype = None

            self._callback = _EVENT_CALLBACK(self._on_event)
            listener_ptr = atspi.atspi_event_listener_new(
                ctypes.cast(self._callback, ctypes.c_void_p), None, None
            )

            if not listener_ptr:
                self.diagnostics = "AT-SPI event listener creation failed"
                return

            listener = int(listener_ptr)
            self._listener = listener
            self._library = library

            for event_type in _EVENTS:
                if atspi.atspi_event_listener_register(
                    ctypes.c_void_p(listener), event_type, None
                ):
                    registered.append(event_type)

            if not registered:
                self.diagnostics = "AT-SPI event registration unavailable"
                return

            self.diagnostics = "listening for focus/caret events"

            while not self._stop.is_set():
                # No nested Qt event loop; GLib dispatch is non-blocking.
                library.glib.g_main_context_iteration(None, 0)
                self._stop.wait(0.02)
        except Exception as error:
            self.diagnostics = (
                f"AT-SPI event listener error: {type(error).__name__}: {error}"
            )
        finally:
            if library is not None:
                with _ATSPI_CALL_LOCK:
                    if listener is not None:
                        for event_type in registered:
                            try:
                                library.atspi.atspi_event_listener_deregister(
                                    ctypes.c_void_p(listener), event_type, None
                                )
                            except Exception:
                                pass

                        library.unref(listener)

                    with self._mutex:
                        old = list(self._recent)
                        self._recent.clear()

                    for pointer, _ in old:
                        library.unref(pointer)

            self._listener = None
            self._library = None
            self._callback = None

    def _on_event(
        self,
        event: ctypes.POINTER(_AtspiEvent),
        _data: ctypes.c_void_p,
    ) -> None:
        # Callback may run in a GLib or a Qt-owned thread. Keep it short and
        # never let a Python exception cross the C ABI.
        try:
            if self._stop.is_set() or not event:
                return

            data = event.contents
            source = int(data.source) if data.source else 0
            kind = data.type or b""

            if not source:
                return

            if kind.startswith(b"object:state-changed:focused"):
                if data.detail1 != 1:
                    return
            elif kind.startswith(b"object:text-caret-moved"):
                if data.detail1 < 0:
                    return
            else:
                return

            library = self._library

            if library is None:
                return

            # GObject reference counting is thread-safe. Never acquire
            # _ATSPI_CALL_LOCK in a GLib callback: a concurrent accessibility
            # read may itself require the GLib context to dispatch a reply.
            owned = library.gobject.g_object_ref(
                ctypes.c_void_p(source)
            )

            if not owned:
                return

            with self._mutex:
                self._recent.append((int(owned), time.monotonic()))
                expired = []

                while len(self._recent) > _MAX_EVENTS:
                    expired.append(self._recent.popleft())

            for pointer, _ in expired:
                library.unref(pointer)
        except Exception:
            return

    def capture_target(
        self,
        accessibility: LinuxAccessibility,
        expected_pid: int | None,
    ) -> LinuxAccessibleTarget | None:
        """Return an owned, verified Text target, or None for normal search."""
        library = accessibility.library

        if library is None or not expected_pid or self._stop.is_set():
            self.diagnostics = "no usable event candidate"
            return None

        candidates: list[tuple[int, float]] = []
        inspected = 0
        matched = 0
        chosen: int | None = None

        with _ATSPI_CALL_LOCK:
            with self._mutex:
                for pointer, observed in reversed(self._recent):
                    if len(candidates) >= _MAX_CANDIDATES_PER_REQUEST:
                        break

                    if time.monotonic() - observed > _MAX_EVENT_AGE_SECONDS:
                        continue

                    owned = library.gobject.g_object_ref(
                        ctypes.c_void_p(pointer)
                    )

                    if owned:
                        candidates.append((int(owned), observed))

            try:
                for pointer, _ in candidates:
                    inspected += 1
                    app = library.atspi.atspi_accessible_get_application(
                        ctypes.c_void_p(pointer), None
                    )

                    if not app:
                        continue

                    try:
                        pid = library.process_id(int(app))
                    finally:
                        library.unref(int(app))

                    if pid != expected_pid:
                        continue

                    matched += 1
                    text = library.text_interface(pointer)

                    if text is None:
                        continue

                    try:
                        offset = library.caret_offset(text)
                    finally:
                        library.unref(text)

                    if offset is not None:
                        chosen = pointer
                        break
            finally:
                for pointer, _ in candidates:
                    if pointer != chosen:
                        library.unref(pointer)

        self.diagnostics = (
            f"event_candidates={inspected}, pid_matches={matched}, "
            f"event_target={'found' if chosen is not None else 'none'}"
        )

        if chosen is None:
            return None

        return LinuxAccessibleTarget(chosen, library)
