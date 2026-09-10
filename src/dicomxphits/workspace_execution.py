"""Cooperative workspace ownership, inherited by direct PHITS children.

The persistent lock file is never unlinked: deleting a lock file permits two
owners of different file objects. OS ownership, not its contents, is authoritative.
"""
from __future__ import annotations

import os
import stat
import subprocess
import threading
from contextlib import contextmanager
from pathlib import Path

LOCK_NAME = ".dicomxphits-execution.lock"
_local = threading.local()


class WorkspaceBusyError(ValueError):
    pass


def _owners() -> dict:
    if not hasattr(_local, "owners"):
        _local.owners = {}
    return _local.owners


class WorkspaceExecutionLease:
    """Reentrant on the owner thread only; excludes other threads/processes."""

    def __init__(self, root: Path, *, create: bool = True):
        self.root = root.resolve()
        self.key = os.path.normcase(str(self.root))
        self.create = create
        self.owner = None
        self.handle = None
        self.executing = False

    def __enter__(self):
        existing = _owners().get(self.key)
        if existing is not None:
            self.owner = existing
            return existing
        path = self.root / LOCK_NAME
        if os.path.lexists(path):
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise WorkspaceBusyError("Unsafe workspace execution lock")
        elif not self.create:
            raise WorkspaceBusyError("Workspace execution ownership evidence is missing")
        try:
            if os.name == "nt":
                import ctypes
                from ctypes import wintypes

                kernel = ctypes.WinDLL("kernel32", use_last_error=True)
                kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD,
                    wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                    wintypes.HANDLE]
                kernel.CreateFileW.restype = wintypes.HANDLE
                # OPEN_ALWAYS or OPEN_EXISTING, no sharing, open reparse point itself.
                handle = kernel.CreateFileW(str(path), 0x80000000, 0, None,
                    4 if self.create else 3, 0x00200000, None)
                if handle == ctypes.c_void_p(-1).value:
                    raise ctypes.WinError(ctypes.get_last_error())
                self.handle = handle
                self._kernel = kernel
                kernel.CloseHandle.argtypes = [wintypes.HANDLE]
                info = path.lstat()
                if getattr(info, "st_file_attributes", 0) & 0x400:
                    raise WorkspaceBusyError("Unsafe workspace execution lock")
            else:
                import fcntl

                flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                if self.create:
                    flags |= os.O_CREAT
                self.handle = os.open(path, flags, 0o600)
                if not stat.S_ISREG(os.fstat(self.handle).st_mode):
                    raise WorkspaceBusyError("Unsafe workspace execution lock")
                fcntl.flock(self.handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            _owners()[self.key] = self
            return self
        except (OSError, ValueError) as exc:
            self._close()
            raise WorkspaceBusyError(
                "Workspace is busy or ownership cannot be established; no execution started"
            ) from exc

    def _close(self):
        if self.handle is not None:
            if os.name == "nt":
                self._kernel.CloseHandle(self.handle)
            else:
                # Closing (not LOCK_UN) preserves ownership inherited by a child.
                os.close(self.handle)
            self.handle = None

    def __exit__(self, *exc):
        if self.owner is None:
            _owners().pop(self.key, None)
            self._close()

    def run(self, command, **kwargs):
        """Only the selected direct child inherits execution ownership."""
        if self.handle is None:
            raise WorkspaceBusyError("Execution ownership has been released")
        execute = subprocess.run
        if "stdout_observer" in kwargs:
            from dicomxphits.observed_process import run_with_observer
            execute = run_with_observer
        if os.name == "nt":
            startup = subprocess.STARTUPINFO()
            startup.lpAttributeList = {"handle_list": [self.handle]}
            os.set_handle_inheritable(self.handle, True)
            try:
                return execute(command, startupinfo=startup, **kwargs)
            finally:
                os.set_handle_inheritable(self.handle, False)
        return execute(command, pass_fds=(self.handle,), **kwargs)

    @contextmanager
    def invocation(self):
        if self.executing:
            raise WorkspaceBusyError("A PHITS invocation already owns this workspace")
        self.executing = True
        try:
            yield
        finally:
            self.executing = False
