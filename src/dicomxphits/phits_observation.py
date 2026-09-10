"""Optional controller-owned observation; never authoritative execution evidence."""
from __future__ import annotations

import hashlib
import json
import os
import stat
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from dicomxphits.phits_observation_format import (
    MAX_HEADER_BYTES, MAX_TALLY_BYTES, ObservationError, checkpoint,
    paired_statistics, parse_batch, parse_identity, prepared_contract, require,
)
from dicomxphits.segment_retry import digest_object

RELATIVE_PATH = Path("analysis/phits_observation.json")
SCHEMA = "dicomxphits_phits_observation_v1"


def safe_path(root, path):
    root, path = Path(root), Path(path)
    require(root.is_absolute() and path.is_absolute() and ".." not in path.parts, "unsafe-path")
    require(path.is_relative_to(root), "unsafe-path")
    for part in (*reversed(path.parents), path):
        info = part.lstat()
        require(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400, "unsafe-path")
    require(path.resolve() == path, "unsafe-path")


def shared_open(root, path):
    """Use short shared handles: never deny PHITS write/delete access."""
    safe_path(root, path)
    if os.name == "nt":
        import ctypes
        import msvcrt
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
            ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.CreateFileW(str(path), 0x80000000, 7, None, 3, 0x00200000, None)
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            attributes = (wintypes.DWORD * 2)()
            kernel.GetFileInformationByHandleEx.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
            if not kernel.GetFileInformationByHandleEx(handle, 9, attributes, ctypes.sizeof(attributes)):
                raise ctypes.WinError(ctypes.get_last_error())
            require(not attributes[0] & 0x400, "unsafe-path")
            fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
        except BaseException:
            kernel.CloseHandle(handle)
            raise
    else:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "unsafe-path")
        return os.fdopen(fd, "rb", buffering=0)
    except BaseException:
        os.close(fd)
        raise


def file_identity(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def read_snapshot(root, path, limit, deadline, *, prefix=False):
    checkpoint(deadline)
    with shared_open(root, path) as stream:
        before = file_identity(os.fstat(stream.fileno()))
        require(prefix or before[2] <= limit, "resource-limit")
        chunks, size = [], 0
        while size < min(before[2], limit):
            checkpoint(deadline)
            chunk = stream.read(min(65536, min(before[2], limit)-size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
        after = file_identity(os.fstat(stream.fileno()))
    safe_path(root, path)
    require(before == after == file_identity(path.stat()) and size == min(before[2], limit), "updating")
    raw = b"".join(chunks)
    checkpoint(deadline)
    return raw, (before, hashlib.sha256(raw).hexdigest())


class Candidate:
    def __init__(self):
        self.previous = None
        self.signature = None
        self.accepted = None
        self.tick = None
        self.utc = None
        self.reason = "waiting"

    def offer(self, signature, value, tick):
        if signature != self.previous:
            self.previous = signature
            self.reason = "updating"
            return
        if signature != self.signature:
            self.signature, self.accepted, self.tick = signature, value, tick
            self.utc = datetime.now(timezone.utc).isoformat()
        self.reason = "available"

    def reject(self, reason):
        self.previous = None
        self.reason = reason

    def record(self, now):
        age = None if self.tick is None else max(0, now-self.tick)
        state = self.reason
        # Retained values after any rejected candidate are never labelled current.
        if self.accepted is not None and (state != "available" or age >= 5):
            state = "stale"
        return {"state": state, "reason": self.reason, "sample_utc": self.utc,
                "sample_age_seconds": age, "value": self.accepted}


class Observer:
    """One sampling worker and one result slot; only the owner writes sidecars."""
    def __init__(self, root, staging, staged_input, dose_path, binding, *, interval=1.0):
        self.root, self.staging, self.dose_path = root, staging, dose_path
        self.error_path = dose_path.with_name(dose_path.stem + "_err" + dose_path.suffix)
        self.binding = binding
        self.mesh, self.runtime = prepared_contract(staged_input.read_text("utf-8"), dose_path.relative_to(staging).as_posix())
        self.interval = max(1.0, interval)
        self.batch, self.error = Candidate(), Candidate()
        self.stdout = bytearray()
        self.lock = threading.Lock()
        self.closed = threading.Event()
        self.latest = None
        self.sequence = 0
        self.published = 0
        self.last_remaining = None
        self.thread = None

    def feed_stdout(self, chunk):
        with self.lock:
            if not self.closed.is_set():
                self.stdout.extend(chunk[:max(0, MAX_HEADER_BYTES-len(self.stdout))])

    def sample(self):
        deadline = time.monotonic()+2
        try:
            header, _ = read_snapshot(self.staging, self.staging / "phits.out", MAX_HEADER_BYTES, deadline, prefix=True)
            with self.lock:
                stdout = bytes(self.stdout)
            parser = parse_identity(header, stdout, self.runtime["threads"])
        except (OSError, ValueError, UnicodeError):
            self.batch.reject("unsupported-identity")
            self.error.reject("unsupported-identity")
            parser = None
        if parser:
            try:
                raw, signature = read_snapshot(self.staging, self.staging / "batch.out", MAX_HEADER_BYTES, deadline)
                remaining = parse_batch(raw, self.runtime["maxbch"])
                require(self.last_remaining is None or remaining <= self.last_remaining, "counter-regression")
                self.last_remaining = remaining
                self.batch.offer(signature, {"remaining": remaining, "prepared_total": self.runtime["maxbch"]}, time.monotonic())
            except (OSError, ValueError, UnicodeError) as exc:
                self.batch.reject(reason_for(exc))
            try:
                dose, ds = read_snapshot(self.staging, self.dose_path, MAX_TALLY_BYTES, deadline)
                error, es = read_snapshot(self.staging, self.error_path, MAX_TALLY_BYTES, deadline)
                result = paired_statistics(dose, error, self.mesh, self.runtime["maxcas"], deadline)
                self.error.offer((ds, es), result, time.monotonic())
            except (OSError, ValueError, UnicodeError) as exc:
                self.error.reject(reason_for(exc))
        now = time.monotonic()
        return {"schema_version": SCHEMA, "binding": self.binding, "parser": parser,
                "published_monotonic": now, "batch": self.batch.record(now), "error": self.error.record(now)}

    def start(self):
        def work():
            while not self.closed.is_set():
                start = time.monotonic()
                try:
                    record = self.sample()
                    with self.lock:
                        if not self.closed.is_set():
                            self.sequence += 1
                            self.latest = {**record, "sequence": self.sequence}
                except Exception:
                    # Optional worker failure never propagates to the execution owner.
                    self.closed.set()
                    return
                self.closed.wait(max(0, self.interval-(time.monotonic()-start)))
        self.thread = threading.Thread(target=work, daemon=True)
        self.thread.start()

    def publish(self, guard):
        if self.closed.is_set():
            return
        with self.lock:
            record = self.latest
        if record is None or record["sequence"] == self.published:
            return
        try:
            raw = json.dumps(record, allow_nan=False).encode("utf-8")
            require(len(raw) <= MAX_HEADER_BYTES, "resource-limit")
            guard.write_bytes(self.root / RELATIVE_PATH, raw)
            self.published = record["sequence"]
        except Exception:
            self.closed.set()

    def close(self, guard):
        self.closed.set()
        if self.thread is not None:
            self.thread.join(timeout=2.1)
        try:
            path = self.root / RELATIVE_PATH
            if os.path.lexists(path):
                guard.unlink(path)
        except Exception:
            pass


def reason_for(exc):
    if isinstance(exc, FileNotFoundError):
        return "waiting"
    if isinstance(exc, ObservationError):
        allowed = {"resource-limit", "updating", "unsafe-path", "counter-regression",
                   "pair-mismatch", "mesh-mismatch", "no-evaluable-cells", "invalid-numeric"}
        return str(exc) if str(exc) in allowed else "unsupported-format"
    return "unavailable"


def observation_binding(summary, current):
    binding = summary["execution_binding"]
    entries = [entry for entry in binding["segments"] if entry["segment_id"] == current["segment_id"]]
    require(len(entries) == 1)
    entry = entries[0]
    tool = binding["tool"]
    require(tool is not None)
    return {"workspace_root": summary["workspace_root"], "run_id": summary["run_id"],
            "segment": current, "manifest_sha256": binding["manifest_sha256"],
            "input_sha256": digest_object(entry["inputs"]),
            "executable_sha256": tool["executable_sha256"],
            "environment_sha256": entry["environment_sha256"]}


def make_observer(root, staging, staged_input, dose_path, context):
    if context is None:
        return None
    try:
        tool = context["execution_binding"]["tool"]
        require(os.name == "nt" and tool is not None)
        require(Path(tool["executable"]) == Path(tool["root"]) / "bin/phits335_win_openmp.exe")
        # Never overwrite a path used as a bound input, output or preparation file.
        reserved = RELATIVE_PATH.as_posix()
        entries = context["execution_binding"]["segments"]
        require(all(reserved not in entry["writes"] and all(e["path"] != reserved for e in entry["inputs"]) for entry in entries))
        return Observer(root, staging, staged_input, dose_path,
                        observation_binding(context, context["current_segment"]))
    except Exception:
        return None


class Presentation:
    """Small sidecar reader bound to an already validated owned live summary."""
    def __init__(self):
        self.reset()

    def reset(self):
        self.binding = None
        self.sequence = 0
        self.last_read = float("-inf")
        self.record = None

    def refresh(self, root, summary, *, active, now=None):
        now = time.monotonic() if now is None else now
        if not active or not summary or summary.get("stage_status") != "running" or not summary.get("current_segment"):
            self.reset()
            return "Observation unavailable: no owned active segment."
        try:
            binding = observation_binding(summary, summary["current_segment"])
            require(binding["workspace_root"] == str(root.resolve()))
            if binding != self.binding:
                self.reset()
                self.binding = binding
            if now-self.last_read >= 1:
                self.last_read = now
                raw, _ = read_snapshot(root, root / RELATIVE_PATH, MAX_HEADER_BYTES, time.monotonic()+0.1)
                record = json.loads(raw)
                require(isinstance(record, dict) and set(record) == {"schema_version", "binding", "parser", "published_monotonic", "batch", "error", "sequence"})
                require(record.get("schema_version") == SCHEMA and record.get("binding") == binding)
                require(type(record.get("sequence")) is int and record["sequence"] >= max(1, self.sequence))
                require(record.get("parser") in {None, "phits-3.35-windows-openmp-xyz-xy-history-v1"})
                require(type(record.get("published_monotonic")) in {int, float} and math_finite(record["published_monotonic"]) and 0 <= record["published_monotonic"] <= now)
                require(record["sequence"] != self.sequence or record == self.record)
                self.record, self.sequence = record, record["sequence"]
            require(self.record is not None)
            return format_record(self.record, now)
        except Exception:
            self.record = None
            return "Observation unavailable: missing, stale, unsupported or invalid record."


def math_finite(value):
    import math
    return math.isfinite(value)


def format_record(record, now):
    parts = ["Provisional current-segment observation (not completion or convergence)"]
    for kind in ("batch", "error"):
        channel = record[kind]
        require(isinstance(channel, dict) and set(channel) == {"state", "reason", "sample_utc", "sample_age_seconds", "value"})
        state = channel["state"]
        require(state in {"waiting", "available", "updating", "stale", "unsupported-identity",
                          "unsupported-format", "unavailable", "resource-limit", "pair-mismatch",
                          "mesh-mismatch", "counter-regression", "unsafe-path", "no-evaluable-cells", "invalid-numeric"})
        value = channel["value"]
        if value is None:
            parts.append(f"{kind}: {state}")
            continue
        age = channel["sample_age_seconds"]
        require(record["parser"] == "phits-3.35-windows-openmp-xyz-xy-history-v1")
        require(isinstance(channel["sample_utc"], str) and len(channel["sample_utc"]) < 64)
        sampled = datetime.fromisoformat(channel["sample_utc"])
        require(sampled.tzinfo is not None)
        require(type(age) in {float, int} and math_finite(age) and age >= 0)
        age += max(0, now-record["published_monotonic"])
        label = "stale" if state != "available" or age >= 5 else "provisional"
        if kind == "batch":
            require(isinstance(value, dict) and set(value) == {"remaining", "prepared_total"})
            remaining, total = value["remaining"], value["prepared_total"]
            require(type(remaining) is int and type(total) is int and 0 <= remaining <= total and total > 0)
            parts.append(f"Observed remaining batches {remaining}; prepared total {total} ({label}, age {age:.1f}s)")
        else:
            require(isinstance(value, dict) and set(value) == {"total_cells", "valid_cells", "excluded_cells", "coverage", "median_percent", "maximum_percent"})
            total, valid, excluded = (value[k] for k in ("total_cells", "valid_cells", "excluded_cells"))
            require(all(type(n) is int for n in (total, valid, excluded)) and 0 < valid <= total <= 10_000_000 and excluded == total-valid)
            median, maximum, coverage = (value[k] for k in ("median_percent", "maximum_percent", "coverage"))
            require(all(type(n) in {int, float} and math_finite(n) for n in (median, maximum, coverage)))
            require(0 < median <= maximum and coverage == valid/total)
            parts.append(f"Per-cell r.err median {median:.3g}%, max {maximum:.3g}%; valid {valid}/{total} ({coverage:.1%}), unevaluable {excluded} ({label}, age {age:.1f}s)")
    return "\n".join(parts)
