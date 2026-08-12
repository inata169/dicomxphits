"""Fail-closed helpers for workspace-local filesystem mutations."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import io
import json
import os
from pathlib import Path
import secrets
import shutil
import stat
from typing import Any


FILE_ATTRIBUTE_REPARSE_POINT = 0x0400


class UnsafeWorkspacePathError(ValueError):
    """A workspace output path crosses an unsafe filesystem boundary."""


def _lexists(path: Path) -> bool:
    return os.path.lexists(path)


def _is_reparse_point(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    if is_junction is not None and is_junction():
        return True
    if os.name == "nt":
        try:
            attributes = os.lstat(path).st_file_attributes
        except (AttributeError, OSError):
            return False
        return bool(attributes & FILE_ATTRIBUTE_REPARSE_POINT)
    return False


def _normalized_absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _open_regular_file_for_read(path: Path):
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise UnsafeWorkspacePathError(
            f"Cannot open guarded copy source: {path}"
        ) from exc
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise UnsafeWorkspacePathError(
                f"Copy source is not a regular file: {path}"
            )
        return os.fdopen(descriptor, "rb")
    except Exception:
        os.close(descriptor)
        raise


def _require_lexical_containment(root: Path, target: Path) -> tuple[Path, Path]:
    root_absolute = _normalized_absolute(root)
    target_absolute = _normalized_absolute(target)
    try:
        common = os.path.commonpath((root_absolute, target_absolute))
    except ValueError as exc:
        raise UnsafeWorkspacePathError(
            f"Output path is on a different filesystem root: {target}"
        ) from exc
    if os.path.normcase(common) != os.path.normcase(os.fspath(root_absolute)):
        raise UnsafeWorkspacePathError(
            f"Output path escapes the case root: {target}"
        )
    return root_absolute, target_absolute


if os.name == "nt":  # pragma: no cover - exercised by Windows-only tests
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value
    FILE_READ_ATTRIBUTES = 0x0080
    FILE_SHARE_READ = 0x00000001
    FILE_SHARE_WRITE = 0x00000002
    OPEN_EXISTING = 3
    FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
    FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
    FILE_ATTRIBUTE_TAG_INFO_CLASS = 9

    class _FILE_ATTRIBUTE_TAG_INFO(ctypes.Structure):
        _fields_ = [
            ("FileAttributes", wintypes.DWORD),
            ("ReparseTag", wintypes.DWORD),
        ]

    kernel32.CreateFileW.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.GetFileInformationByHandleEx.argtypes = (
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    )
    kernel32.GetFileInformationByHandleEx.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL


def _open_locked_windows_directory(path: Path) -> int:
    """Open a directory without FILE_SHARE_DELETE and reject reparse points."""

    if os.name != "nt":
        raise AssertionError("Windows directory handles are Windows-only")
    handle = kernel32.CreateFileW(  # type: ignore[name-defined]
        os.fspath(path),
        FILE_READ_ATTRIBUTES,  # type: ignore[name-defined]
        FILE_SHARE_READ | FILE_SHARE_WRITE,  # type: ignore[name-defined]
        None,
        OPEN_EXISTING,  # type: ignore[name-defined]
        FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT,  # type: ignore[name-defined]
        None,
    )
    if handle == INVALID_HANDLE_VALUE:  # type: ignore[name-defined]
        error = ctypes.get_last_error()
        raise UnsafeWorkspacePathError(
            f"Cannot lock workspace directory against replacement: {path} "
            f"(Windows error {error})"
        )
    info = _FILE_ATTRIBUTE_TAG_INFO()  # type: ignore[name-defined]
    if not kernel32.GetFileInformationByHandleEx(  # type: ignore[name-defined]
        handle,
        FILE_ATTRIBUTE_TAG_INFO_CLASS,  # type: ignore[name-defined]
        ctypes.byref(info),
        ctypes.sizeof(info),
    ):
        error = ctypes.get_last_error()
        kernel32.CloseHandle(handle)  # type: ignore[name-defined]
        raise UnsafeWorkspacePathError(
            f"Cannot inspect workspace directory: {path} (Windows error {error})"
        )
    if info.FileAttributes & FILE_ATTRIBUTE_REPARSE_POINT:
        kernel32.CloseHandle(handle)  # type: ignore[name-defined]
        raise UnsafeWorkspacePathError(
            f"Workspace path component is a Windows reparse point: {path}"
        )
    return int(handle)


class WorkspaceOutputGuard:
    """Validate and lock path components for one or more output mutations."""

    def __init__(self, case_root: Path, *, create_root: bool = False) -> None:
        self.case_root = _normalized_absolute(case_root)
        self.create_root = create_root
        self._windows_handles: dict[str, int] = {}

    def __enter__(self) -> WorkspaceOutputGuard:
        try:
            if not _lexists(self.case_root):
                if not self.create_root:
                    raise UnsafeWorkspacePathError(
                        f"Case root does not exist: {self.case_root}"
                    )
            self._hold_case_root_hierarchy(create_missing=self.create_root)
            return self
        except Exception:
            self._close_held_directories()
            raise

    def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
        self._close_held_directories()

    def _close_held_directories(self) -> None:
        if os.name == "nt":  # pragma: no branch - platform-specific cleanup
            for handle in reversed(tuple(self._windows_handles.values())):
                kernel32.CloseHandle(handle)  # type: ignore[name-defined]
        self._windows_handles.clear()

    def _hold_directory(
        self,
        path: Path,
        *,
        label: str = "output directory",
        require_case_containment: bool = True,
    ) -> None:
        if _is_reparse_point(path):
            raise UnsafeWorkspacePathError(
                f"{label.capitalize()} is a symbolic link, junction, or reparse point: {path}"
            )
        if not path.is_dir():
            raise UnsafeWorkspacePathError(f"{label.capitalize()} is not a directory: {path}")
        if require_case_containment:
            try:
                path.resolve(strict=True).relative_to(self.case_root.resolve(strict=True))
            except ValueError as exc:
                raise UnsafeWorkspacePathError(
                    f"{label.capitalize()} resolves outside the case root: {path}"
                ) from exc
        key = os.path.normcase(os.fspath(path))
        if os.name == "nt" and key not in self._windows_handles:
            self._windows_handles[key] = _open_locked_windows_directory(path)

    def _hold_case_root_hierarchy(self, *, create_missing: bool) -> None:
        anchor = Path(self.case_root.anchor)
        if not anchor:
            raise UnsafeWorkspacePathError(
                f"Case root has no filesystem anchor: {self.case_root}"
            )

        current = anchor
        self._hold_directory(
            current,
            label="case-root ancestor",
            require_case_containment=False,
        )
        for part in self.case_root.relative_to(anchor).parts:
            current = current / part
            if not _lexists(current):
                if not create_missing:
                    raise UnsafeWorkspacePathError(
                        f"Case-root path component does not exist: {current}"
                    )
                try:
                    current.mkdir()
                except FileExistsError:
                    pass
            self._hold_directory(
                current,
                label="case-root path component",
                require_case_containment=False,
            )

    def _release_directories_at_or_below(self, path: Path) -> None:
        if os.name != "nt":
            return
        prefix = os.path.normcase(os.fspath(_normalized_absolute(path))).rstrip("\\/")
        keys = [
            key
            for key in self._windows_handles
            if key == prefix or key.startswith(prefix + os.sep)
        ]
        for key in reversed(keys):
            kernel32.CloseHandle(self._windows_handles.pop(key))  # type: ignore[name-defined]

    def prepare(self, target: Path, *, create_parents: bool = False) -> Path:
        root, target = _require_lexical_containment(self.case_root, target)
        if root != self.case_root:
            raise UnsafeWorkspacePathError("Case-root normalization changed unexpectedly")
        relative = target.relative_to(root)
        current = root
        parent_parts = relative.parts[:-1]
        for part in parent_parts:
            current = current / part
            if _lexists(current):
                self._hold_directory(current)
                continue
            if not create_parents:
                raise UnsafeWorkspacePathError(
                    f"Output parent does not exist: {current}"
                )
            try:
                current.mkdir()
            except FileExistsError:
                pass
            self._hold_directory(current)

        if _lexists(target):
            if _is_reparse_point(target):
                raise UnsafeWorkspacePathError(
                    "Output target is a symbolic link, junction, or reparse point: "
                    f"{target}"
                )
            try:
                target.resolve(strict=True).relative_to(root.resolve(strict=True))
            except ValueError as exc:
                raise UnsafeWorkspacePathError(
                    f"Output target resolves outside the case root: {target}"
                ) from exc
        return target

    def prepare_file_target(
        self, target: Path, *, create_parents: bool = False
    ) -> Path:
        """Prepare a file output and reject existing non-regular targets."""

        target = self.prepare(target, create_parents=create_parents)
        if _lexists(target) and not target.is_file():
            raise UnsafeWorkspacePathError(
                f"Output target is not a regular file: {target}"
            )
        return target

    def mkdir(self, path: Path) -> Path:
        marker = path / ".dicomxphits-directory-boundary"
        self.prepare(marker, create_parents=True)
        self._hold_directory(_normalized_absolute(path))
        return _normalized_absolute(path)

    def make_staging_directory(self, parent: Path, *, prefix: str) -> Path:
        """Exclusively create and hold a random workspace-local directory."""

        parent = _normalized_absolute(parent)
        self.prepare(parent / ".dicomxphits-staging-boundary", create_parents=True)
        self._hold_directory(parent)
        for _attempt in range(100):
            candidate = parent / f"{prefix}{secrets.token_hex(8)}"
            self.prepare(candidate)
            try:
                candidate.mkdir()
            except FileExistsError:
                continue
            self._hold_directory(candidate)
            return candidate
        raise UnsafeWorkspacePathError(
            f"Cannot create an exclusive staging directory below: {parent}"
        )

    def write_bytes(
        self,
        path: Path,
        data: bytes,
        *,
        overwrite: bool = True,
    ) -> Path:
        target = self.prepare_file_target(path, create_parents=True)
        if not overwrite:
            descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            return target

        temporary = target.with_name(
            f".{target.name}.dicomxphits-{secrets.token_hex(8)}.tmp"
        )
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            self.prepare_file_target(target)
            os.replace(temporary, target)
        finally:
            if _lexists(temporary):
                self.unlink(temporary)
        return target

    def copy_file(
        self,
        source: Path,
        destination: Path,
        *,
        overwrite: bool = True,
    ) -> Path:
        """Copy a guarded regular file using exclusive or atomic final creation."""

        source = self.prepare(source)
        if not source.is_file():
            raise UnsafeWorkspacePathError(f"Copy source is not a regular file: {source}")
        target = self.prepare_file_target(destination, create_parents=True)

        if not overwrite:
            descriptor: int | None = None
            created = False
            try:
                descriptor = os.open(
                    target,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    0o666,
                )
                created = True
                with _open_regular_file_for_read(source) as source_stream, os.fdopen(
                    descriptor, "wb"
                ) as target_stream:
                    descriptor = None
                    shutil.copyfileobj(source_stream, target_stream)
                    target_stream.flush()
                    os.fsync(target_stream.fileno())
            except Exception:
                if descriptor is not None:
                    os.close(descriptor)
                if created and _lexists(target):
                    self.unlink(target)
                raise
            return target

        temporary = target.with_name(
            f".{target.name}.dicomxphits-{secrets.token_hex(8)}.tmp"
        )
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o666,
        )
        try:
            with _open_regular_file_for_read(source) as source_stream, os.fdopen(
                descriptor, "wb"
            ) as target_stream:
                shutil.copyfileobj(source_stream, target_stream)
                target_stream.flush()
                os.fsync(target_stream.fileno())
            self.prepare_file_target(target)
            os.replace(temporary, target)
        finally:
            if _lexists(temporary):
                self.unlink(temporary)
        return target

    def write_text(
        self,
        path: Path,
        text: str,
        *,
        encoding: str = "utf-8",
        newline: str | None = None,
        overwrite: bool = True,
    ) -> Path:
        if newline is None:
            buffer = io.BytesIO()
            stream = io.TextIOWrapper(buffer, encoding=encoding, newline=None)
            try:
                stream.write(text)
                stream.flush()
                data = buffer.getvalue()
            finally:
                stream.detach()
        elif newline == "":
            data = text.encode(encoding)
        else:
            text = text.replace("\r\n", "\n").replace("\r", "\n").replace(
                "\n", newline
            )
            data = text.encode(encoding)
        return self.write_bytes(path, data, overwrite=overwrite)

    def write_json(self, path: Path, value: Any, *, overwrite: bool = True) -> Path:
        text = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
        return self.write_text(path, text, overwrite=overwrite)

    def unlink(self, path: Path, *, missing_ok: bool = False) -> None:
        target = self.prepare(path)
        if not _lexists(target):
            if missing_ok:
                return
            raise FileNotFoundError(target)
        target.unlink()

    def rmtree(self, path: Path, *, missing_ok: bool = False) -> None:
        target = self.prepare(path)
        if not _lexists(target):
            if missing_ok:
                return
            raise FileNotFoundError(target)
        if not target.is_dir():
            raise UnsafeWorkspacePathError(f"Cleanup target is not a directory: {target}")
        for directory, directory_names, file_names in os.walk(
            target, topdown=True, followlinks=False
        ):
            for name in (*directory_names, *file_names):
                child = Path(directory) / name
                if _is_reparse_point(child):
                    raise UnsafeWorkspacePathError(
                        f"Cleanup target contains a link or reparse point: {child}"
                    )
        # Windows cannot remove a directory while this guard's no-share-delete
        # handle is open. Parent handles remain locked while the inspected tree
        # is released immediately before removal.
        self._release_directories_at_or_below(target)
        shutil.rmtree(target)


def validate_workspace_output_path(case_root: Path, target: Path) -> Path:
    """Validate one existing-or-future output path without mutating it."""

    with WorkspaceOutputGuard(case_root) as guard:
        return guard.prepare(target)
