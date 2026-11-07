"""The Windows per-port named mutex, owned by the main thread until shutdown."""

import ctypes
from typing import Any

_WAIT_OBJECT_0, _WAIT_ABANDONED = 0x0, 0x80
_ctypes: Any = ctypes  # Win32-only ctypes names are absent from POSIX type stubs.


class WindowsPortLock:
    def __init__(self, port: int):
        self._kernel32 = _ctypes.WinDLL("kernel32", use_last_error=True)
        self._handle = self._kernel32.CreateMutexW(None, False, f"Local\\Ozvuchka-{port}")
        if not self._handle:
            raise _ctypes.WinError(_ctypes.get_last_error())
        self._owned = False

    def acquire(self) -> bool:
        result = self._kernel32.WaitForSingleObject(self._handle, 0)
        self._owned = result in (_WAIT_OBJECT_0, _WAIT_ABANDONED)
        return self._owned

    def close(self) -> None:
        if self._handle:
            if self._owned:
                self._kernel32.ReleaseMutex(self._handle)
                self._owned = False
            self._kernel32.CloseHandle(self._handle)
            self._handle = None
