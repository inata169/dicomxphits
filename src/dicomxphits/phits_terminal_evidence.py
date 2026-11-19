"""Evidence that a failed PHITS child reached OpenMP finalization."""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

from dicomxphits.phits_observation_format import prepared_contract
from dicomxphits.sumtally_inputs import file_sha256

OPENMP_335 = "phits335_win_openmp.exe"
STACK_OVERFLOW = 0xC00000FD
SCHEMA = "dicomxphits_phits_terminal_evidence_v1"
PHASE = "openmp_finalization_observed_after_last_batch"
MAX_INPUT_BYTES = 4 * 1024**2
MAX_LOG_BYTES = 32 * 1024**2

_BATCH = re.compile(
    r"bat\[\s*([0-9]{1,16})\s*\]\s+ncas\s*=\s*([0-9]{1,20})\.?"
    r"(?:\s*:\s*date\s*=\s*\d{4}-\d{2}-\d{2}\s*:\s*time\s*=\s*\d{2}h\s+\d{2}m\s+\d{2}s)?",
    re.I,
)
_WORKER = re.compile(
    r"OpenMP\s+(PARALLEL PROCESS|FINALIZE)\s+([0-9]{1,9})\s*/\s*([0-9]{1,9})\s+@\s+IP\(MPI\)\s*=\s*0"
)
_WARNINGS = (
    re.compile(r"Warning: All resfile\(s\) do not exist, so new calculation started with istdev = 1"),
    re.compile(r"\*\*\* Warning! emin\([0-9]+\) is changed\. Transport physics is distorted\. Default emin\([0-9]+\) is encouraged"),
)
_ERROR = re.compile(
    r"^\s*(?:\*+\s*)?(?:error(?:[\s!:]|$)|fatal(?:[\s!:]|$)|forrtl:\s*severe|"
    r"lost particle|geometry error|input error|transport error|too many lost particles|"
    r"calculation (?:aborted|stopped|terminated))",
    re.I,
)


def is_stack_overflow(code: object) -> bool:
    return type(code) is int and code in {STACK_OVERFLOW, STACK_OVERFLOW - 2**32}


def is_post_batch_exit(code: object) -> bool:
    if type(code) is not int or not -2**31 <= code < 2**32 or code == 0 or is_stack_overflow(code):
        return False
    return code & 0xFFFFFFFF != 0xC000013A  # STATUS_CONTROL_C_EXIT


def _warning(line: str) -> bool:
    return any(pattern.fullmatch(line) for pattern in _WARNINGS)


def validate_finalization(stdout: str, stderr: str, runtime: dict) -> None:
    """Require ordered console evidence, with no unexplained diagnostic lines."""
    planned, maxcas, threads = (runtime[key] for key in ("maxbch", "maxcas", "threads"))
    if (len(stdout) > MAX_LOG_BYTES or len(stderr) > MAX_LOG_BYTES
            or any(line.strip() and not _warning(line.strip()) for line in stderr.splitlines())):
        raise ValueError("Unsupported PHITS terminal output or error diagnostics")

    last_batch = 0
    started = set()
    finalized = set()
    for entry in stdout.splitlines():
        line = entry.strip()
        if not line or _warning(line):
            continue
        if batch := _BATCH.fullmatch(line):
            ordinal, histories = map(int, batch.groups())
            if finalized or not last_batch < ordinal <= planned or histories != ordinal * maxcas:
                raise ValueError("PHITS terminal batch progress is out of sequence or inconsistent")
            last_batch = ordinal
            continue
        worker = _WORKER.fullmatch(line)
        if worker is None:
            raise ValueError("Unsupported PHITS terminal output or error diagnostics")
        event, identity, total = worker.groups()
        identity = int(identity)
        if int(total) != threads or not 1 <= identity <= threads:
            raise ValueError("PHITS finalization workers disagree with preparation")
        if event == "PARALLEL PROCESS":
            if last_batch or identity in started:
                raise ValueError("PHITS worker startup evidence is out of sequence or duplicated")
            started.add(identity)
        else:
            if last_batch != planned or identity in finalized:
                raise ValueError("PHITS finalization precedes the last batch or duplicates a worker")
            finalized.add(identity)
    if last_batch != planned or len(finalized) != threads or (started and len(started) != threads):
        raise ValueError("PHITS terminal evidence is missing finalization for the prepared workers")


def require_no_recorded_phits_error(log: str) -> None:
    if any(_ERROR.match(line) for line in log.splitlines()):
        raise ValueError("PHITS log contains an error inconsistent with research recovery")


def capture_terminal_evidence(root, staged_input, primary, executable, environment,
                              result, retained, stdout_path, stderr_path, guard):
    """Record only supported output captured by the direct runner at child exit."""
    if (not is_post_batch_exit(result.returncode) or Path(executable).name.lower() != OPENMP_335
            or getattr(result, "args", None) != [executable] or retained["missing_required_outputs"]):
        return None
    staged_input = guard.prepare(staged_input)
    if staged_input.stat().st_size > MAX_INPUT_BYTES:
        return None
    _, runtime = prepared_contract(staged_input.read_text(encoding="utf-8"), primary)
    if str(runtime["threads"]) != environment.get("OMP_NUM_THREADS"):
        return None
    stdout, stderr = result.stdout or "", result.stderr or ""
    validate_finalization(stdout, stderr, runtime)

    logs = {}
    for role, path, captured in (("stdout", stdout_path, stdout), ("stderr", stderr_path, stderr)):
        path = guard.prepare(path)
        expected = captured.replace("\n", os.linesep).encode("utf-8")
        if len(expected) > MAX_LOG_BYTES:
            return None
        digest = hashlib.sha256(expected).hexdigest()
        if path.stat().st_size != len(expected) or file_sha256(path) != digest:
            return None
        logs[role] = {"path": path.relative_to(root).as_posix(), "size": len(expected), "sha256": digest}
    logs["phits_out"] = next(record for record in retained["outputs"] if record["output_path"] == "phits.out")
    return {
        "schema_version": SCHEMA,
        "run_id": retained["run_id"],
        "segment_id": retained["segment_id"],
        "exit_code": result.returncode,
        "runtime": runtime,
        "staging_directory": retained["staging_directory"],
        "logs": logs,
    }
