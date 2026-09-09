"""Private single-run format probe. Defaults to check-only; no PHITS discovery.

Preparation/testing of this script is NOT permission to execute real PHITS.
The exact plan bytes, paths and launch must be separately human-approved.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone

from dicomxphits.safe_output import WorkspaceOutputGuard
from dicomxphits.workspace_execution import WorkspaceExecutionLease

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
DECK = HERE / "observation-probe.inp"
LEASE = REPO / "src/dicomxphits/workspace_execution.py"
SCHEMA = "dicomxphits_observation_probe_plan_v1"
FILES = {"batch.out": 65536, "phits.out": 8 * 1024**2,
         "deposit-target-3D.out": 8 * 1024**2,
         "deposit-target-3D_err.out": 8 * 1024**2}
CAP = 100 * 1024**2
RESERVE = 65536


def utc():
    return datetime.now(timezone.utc).isoformat()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def safe_path(value):
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ValueError("Expected an explicit absolute path")
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("Expected an explicit absolute path without traversal")
    for part in [*reversed(path.parents), path]:
        if os.path.lexists(part):
            info = part.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise ValueError("Link/reparse path rejected")
    if path.resolve() != path:
        raise ValueError("Noncanonical path rejected")
    return path


def shared_read(path):
    """Open an ordinary file without denying a Windows writer/delete handle."""
    safe_path(str(path))
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        import msvcrt
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
            ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.CreateFileW(str(path), 0x80000000, 7, None, 3, 0x00200000, None)
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            # FileAttributeTagInfo rejects a link replaced between lstat and open.
            attributes = (wintypes.DWORD * 2)()
            kernel.GetFileInformationByHandleEx.argtypes = [wintypes.HANDLE, ctypes.c_int,
                ctypes.c_void_p, wintypes.DWORD]
            if not kernel.GetFileInformationByHandleEx(handle, 9, attributes, ctypes.sizeof(attributes)):
                raise ctypes.WinError(ctypes.get_last_error())
            if attributes[0] & 0x400:
                raise ValueError("Reparse file rejected")
            fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
        except BaseException:
            kernel.CloseHandle(handle)
            raise
    else:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("Expected a regular, unlinked file")
        return os.fdopen(fd, "rb", buffering=0)
    except BaseException:
        os.close(fd)
        raise


def metadata(info):
    return [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns]


def read_sample(path, limit, seconds=2):
    deadline = time.monotonic() + seconds
    with shared_read(path) as stream:
        before = metadata(os.fstat(stream.fileno()))
        if before[2] > limit:
            raise ValueError("File limit exceeded")
        chunks, size = [], 0
        while True:
            if time.monotonic() > deadline:
                raise ValueError("Read deadline exceeded")
            chunk = stream.read(min(65536, limit + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            if size > limit:
                raise ValueError("File limit exceeded")
        after = metadata(os.fstat(stream.fileno()))
    safe_path(str(path))
    current = metadata(path.stat())
    data = b"".join(chunks)
    return data, {"before": before, "after": after, "current": current,
        "stable_metadata": before == after == current and len(data) == after[2],
        "sha256": digest(data)}


def checked_bytes(path, limit):
    data, info = read_sample(path, limit)
    if not info["stable_metadata"]:
        raise ValueError("Artifact changed during preflight")
    return data


def libpath_bytes(installation):
    value = installation.as_posix()
    if any(c in value for c in "\r\n#{}<>\"'"):
        raise ValueError("Unsupported installation path spelling")
    return f"file(1)  = {value} # PHITS install folder name\n".encode("utf-8")


def check_plan(path, expected_plan_sha256=None):
    raw = checked_bytes(safe_path(str(path)), 65536)
    if expected_plan_sha256 is not None and digest(raw) != expected_plan_sha256:
        raise ValueError("Plan digest mismatch")
    plan = json.loads(raw)
    fields = {"schema", "executable", "installation_root", "scratch_parent", "run_dir",
        "evidence_dir", "executable_sha256", "deck_sha256", "collector_sha256",
        "lease_sha256", "libpath_sha256"}
    if not isinstance(plan, dict) or set(plan) != fields or plan["schema"] != SCHEMA:
        raise ValueError("Unsupported plan")
    for key in fields:
        if key.endswith("sha256") and (not isinstance(plan[key], str)
            or re.fullmatch("[0-9a-f]{64}", plan[key]) is None):
            raise ValueError("Expected a lowercase SHA-256 digest")
    paths = {key: safe_path(plan[key]) for key in
        ("executable", "installation_root", "scratch_parent", "run_dir", "evidence_dir")}
    root, scratch = paths["installation_root"], paths["scratch_parent"]
    if not root.is_dir() or not scratch.is_dir() or scratch == Path(scratch.anchor):
        raise ValueError("Installation and dedicated scratch parent must exist")
    if root.is_relative_to(REPO) or REPO.is_relative_to(root):
        raise ValueError("Installation overlaps the repository")
    if (scratch == Path.home() or scratch.is_relative_to(REPO) or REPO.is_relative_to(scratch)
        or scratch.is_relative_to(root) or root.is_relative_to(scratch)):
        raise ValueError("Scratch parent overlaps protected locations")
    exe = paths["executable"]
    if exe != root / "bin/phits335_win_openmp.exe":
        raise ValueError("Only the explicitly selected standard OpenMP executable is supported")
    if paths["run_dir"] == paths["evidence_dir"]:
        raise ValueError("Run and evidence destinations must differ")
    for key in ("run_dir", "evidence_dir"):
        if paths[key].parent != scratch or os.path.lexists(paths[key]):
            raise ValueError("Destinations must be absent direct children of the approved scratch parent")
    data = {"deck": checked_bytes(DECK, 65536), "libpath": libpath_bytes(root)}
    artifacts = {"executable": checked_bytes(exe, 256 * 1024**2),
        "collector": checked_bytes(Path(__file__).resolve(), 1024**2),
        "lease": checked_bytes(LEASE, 1024**2), **data}
    for key, value in artifacts.items():
        if digest(value) != plan[key + "_sha256"]:
            raise ValueError(f"{key} digest mismatch")
    return plan, paths, data, digest(raw)


class Evidence:
    """One shared byte budget for all files, including metadata and streams."""
    def __init__(self, guard, cap=CAP):
        self.guard = guard
        self.cap, self.used, self.sequence = cap, 0, 0
        self.lock = threading.Lock()
        self.disabled = False
        self.reason = None

    def put(self, role, data, info):
        with self.lock:
            if self.disabled:
                return False
            self.sequence += 1
            name = f"{self.sequence:07d}-{role}"
            record = json.dumps({**info, "bytes_file": name + ".bin"}, sort_keys=True).encode()
            if self.used + len(data) + len(record) > self.cap - RESERVE:
                self.disabled, self.reason = True, "evidence-cap"
                return False
            self.used += len(data) + len(record)
            try:
                self.guard.write_bytes(self.guard.case_root / (name + ".bin"), data, overwrite=False)
                self.guard.write_bytes(self.guard.case_root / (name + ".json"), record, overwrite=False)
            except (OSError, ValueError):
                self.disabled, self.reason = True, "evidence-write-failed"
                return False
            return True


def capture_files(root, evidence, previous, started, *, final=False):
    results = {}
    for name, limit in FILES.items():
        if evidence.disabled:
            results[name] = {"status": "capture-disabled"}
            continue
        try:
            data, info = read_sample(root / name, limit)
            info.update(utc=utc(), elapsed=time.monotonic() - started, final=final)
            signature = (info["sha256"], tuple(info["current"]), info["stable_metadata"])
            # Record unchanged confirmations as small metadata-only events.
            unchanged = previous.get(name) == signature
            info["unchanged_confirmation"] = unchanged
            if evidence.put(name, data if final or not unchanged else b"", info):
                previous[name] = signature
            results[name] = {"status": "observed", **info}
        except FileNotFoundError:
            results[name] = {"status": "missing"}
        except (OSError, ValueError):
            results[name] = {"status": "unavailable"}
            with evidence.lock:
                evidence.disabled, evidence.reason = True, "source-read-failed"
    return results


def spawn_owned(lease, command, **kwargs):
    # Popen rather than subprocess.run: interruption must never implicitly kill.
    if os.name == "nt":
        startup = subprocess.STARTUPINFO()
        startup.lpAttributeList = {"handle_list": [lease.handle]}
        os.set_handle_inheritable(lease.handle, True)
        try:
            return subprocess.Popen(command, startupinfo=startup,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW, **kwargs)
        finally:
            os.set_handle_inheritable(lease.handle, False)
    return subprocess.Popen(command, pass_fds=(lease.handle,), **kwargs)


def collect_child(command, run_dir, evidence, lease, *, warning_seconds=600):
    """Testable collector; only execute_plan supplies a real command to the CLI."""
    started = time.monotonic()
    env = os.environ.copy()
    env["OMP_NUM_THREADS"] = "2"
    previous, readers = {}, []
    process = spawn_owned(lease, command, cwd=run_dir, shell=False, env=env,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def drain(stream, role):
        try:
            while chunk := stream.read1(65536):
                evidence.put(role, chunk, {"utc": utc(), "elapsed": time.monotonic() - started})
        except OSError:
            with evidence.lock:
                evidence.disabled, evidence.reason = True, "stream-read-failed"
        finally:
            stream.close()

    interrupted = False
    try:
        for stream, role in ((process.stdout, "stdout"), (process.stderr, "stderr")):
            thread = threading.Thread(target=drain, args=(stream, role), daemon=True)
            thread.start()
            readers.append(thread)
        process.stdin.write(b"file = observation-probe.inp\n")
        process.stdin.close()
        warned = False
        while process.poll() is None:
            try:
                capture_files(run_dir, evidence, previous, started)
                if not warned and time.monotonic() - started >= warning_seconds:
                    print("Probe exceeds observation interval; human decision required. Child not terminated.",
                        file=sys.stderr, flush=True)
                    warned = True
                time.sleep(0.1)
            except KeyboardInterrupt:
                interrupted = True
                print("Collector interrupted; waiting for owned child without terminating it.", file=sys.stderr)
    finally:
        # Preserve ownership even on collector exceptions. No timeout/kill/signal.
        while True:
            try:
                process.wait()
                for reader in readers:
                    reader.join()
                break
            except KeyboardInterrupt:
                interrupted = True
    final = capture_files(run_dir, evidence, previous, started, final=True)
    return {"return_code": process.returncode, "elapsed": time.monotonic() - started,
        "collector_interrupted": interrupted, "capture_disabled": evidence.disabled,
        "capture_reason": evidence.reason, "files": final,
        "assessment": "unassessed: raw format evidence only, not verified PHITS success"}


def execute_plan(path, expected_plan_sha256):
    if os.name != "nt":
        raise ValueError("Real probe is Windows-only")
    if not expected_plan_sha256:
        raise ValueError("Execution requires the separately approved plan digest")
    plan, paths, data, plan_sha = check_plan(path, expected_plan_sha256)
    run, output = paths["run_dir"], paths["evidence_dir"]
    # Exclusive creation; a failed attempt stays on disk and cannot be retried.
    with WorkspaceOutputGuard(paths["scratch_parent"], read_only=True) as parent_guard:
        parent_guard.prepare(run)
        parent_guard.prepare(output)
        run.mkdir()
        output.mkdir()
        with WorkspaceOutputGuard(run) as run_guard, WorkspaceOutputGuard(output) as output_guard:
            run_guard.write_bytes(run / "observation-probe.inp", data["deck"], overwrite=False)
            run_guard.write_bytes(run / "libpath.inp", data["libpath"], overwrite=False)
            evidence = Evidence(output_guard)
            if not evidence.put("plan", json.dumps(plan).encode(), {"approved_plan_sha256": plan_sha}):
                raise ValueError("Cannot persist launch identity; no launch")
            # Recheck frozen executable immediately before the sole launch.
            if digest(checked_bytes(paths["executable"], 256 * 1024**2)) != plan["executable_sha256"]:
                raise ValueError("Executable changed; no launch")
            for key, name in (("deck", "observation-probe.inp"), ("libpath", "libpath.inp")):
                if checked_bytes(run / name, 65536) != data[key]:
                    raise ValueError("Probe input changed; no launch")
            with WorkspaceExecutionLease(run) as lease:
                result = collect_child([str(paths["executable"])], run, evidence, lease)
            result["input_digests_unchanged"] = all(
                digest(checked_bytes(run / name, 65536)) == digest(data[key])
                for key, name in (("deck", "observation-probe.inp"), ("libpath", "libpath.inp")))
            result["plan_sha256"] = plan_sha
            report = json.dumps(result, indent=2).encode()
            if len(report) > RESERVE:
                raise ValueError("Final report exceeds reserved budget")
            output_guard.write_bytes(output / "report.json", report, overwrite=False)
            return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--execute", action="store_true", help="Requires separate human authorization")
    parser.add_argument("--approved-plan-sha256")
    args = parser.parse_args(argv)
    if args.execute:
        result = execute_plan(args.plan, args.approved_plan_sha256)
        print(json.dumps(result, indent=2))
        complete_capture = (result["return_code"] == 0 and not result["capture_disabled"]
            and not result["collector_interrupted"] and result["input_digests_unchanged"]
            and all(info.get("stable_metadata") for info in result["files"].values()))
        return 0 if complete_capture else 2
    _, _, _, sha = check_plan(args.plan, args.approved_plan_sha256)
    print(json.dumps({"check_only": True, "plan_sha256": sha, "execution_authorized": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
