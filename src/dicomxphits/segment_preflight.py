"""Owned preparation receipts; never evidence of a successful PHITS result."""
from __future__ import annotations

import hashlib
import json
import math
import re
import time
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "dicomxphits_segment_preflight_v1"
RELATIVE_PATH = Path("analysis/segment_preflight.json")
CANCEL = "cancel-preparation"
MAX_RECEIPT_BYTES = 8192
_current = ContextVar("phits_preflight", default=None)


class PreparationCancelled(BaseException):
    """Only the owning controller catches this before any child commitment."""


def identity(value):
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value) is not None


def validate_receipt(value, *, root=None, nonce=None):
    fields = {"schema_version", "workspace_root", "run_id", "gui_nonce", "phase",
        "sequence", "elapsed_seconds", "updated_at", "scanned_files", "scanned_bytes",
        "child_committed", "request_id", "summary_sha256", "result_run_id", "cancel_rejected_request_id"}
    if not isinstance(value, dict) or set(value) != fields or value["schema_version"] != SCHEMA:
        raise ValueError("Invalid preflight receipt schema")
    if not all(identity(value[k]) for k in ("run_id", "gui_nonce")):
        raise ValueError("Invalid preflight identity")
    if not isinstance(value["workspace_root"], str) or not Path(value["workspace_root"]).is_absolute():
        raise ValueError("Invalid preflight workspace")
    if root is not None and value["workspace_root"] != str(Path(root).resolve()):
        raise ValueError("Preflight workspace changed")
    if nonce is not None and value["gui_nonce"] != nonce:
        raise ValueError("Stale preflight invocation")
    if value["phase"] not in {"preparing", "verifying", "executing", "cancelled_before_launch", "finished", "failed"}:
        raise ValueError("Invalid preflight phase")
    if any(type(value[k]) is not int or value[k] < 0 for k in ("sequence", "scanned_files", "scanned_bytes")):
        raise ValueError("Invalid preflight counters")
    elapsed = value["elapsed_seconds"]
    if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0:
        raise ValueError("Invalid preflight duration")
    from dicomxphits.run_segments import _parse_utc_text
    _parse_utc_text(value["updated_at"], field_name="updated_at")
    if type(value["child_committed"]) is not bool:
        raise ValueError("Invalid commitment evidence")
    if value["request_id"] is not None and not identity(value["request_id"]):
        raise ValueError("Invalid preparation request")
    if value["cancel_rejected_request_id"] is not None and (
        not identity(value["cancel_rejected_request_id"]) or not value["child_committed"]):
        raise ValueError("Invalid rejected preparation request")
    if value["phase"] == "cancelled_before_launch" and (value["child_committed"] or value["request_id"] is None):
        raise ValueError("Preparation cancellation cannot follow commitment")
    digest = value["summary_sha256"]
    if value["phase"] == "finished":
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("Missing terminal summary binding")
        if not identity(value["result_run_id"]):
            raise ValueError("Missing result invocation identity")
    elif digest is not None or value["result_run_id"] is not None:
        raise ValueError("Incomplete preflight cannot bind terminal success")
    return value


def read_receipt(root, *, nonce=None):
    from dicomxphits.safe_output import WorkspaceOutputGuard
    root = Path(root).resolve()
    path = root / RELATIVE_PATH
    if not path.exists() and not path.is_symlink():
        return None
    with WorkspaceOutputGuard(root, read_only=True) as guard:
        guard.prepare(path)
        with path.open("rb") as stream:
            data = stream.read(MAX_RECEIPT_BYTES + 1)
    if len(data) > MAX_RECEIPT_BYTES:
        raise ValueError("Oversized preflight receipt")
    return validate_receipt(json.loads(data), root=root, nonce=nonce)


class ReceiptTracker:
    """Retain the high-water mark even when an intervening read is invalid."""

    def __init__(self):
        self.last = None

    def accept(self, value, *, root, nonce):
        receipt = validate_receipt(value, root=root, nonce=nonce)
        previous = self.last
        if previous is not None:
            if receipt["run_id"] != previous["run_id"]:
                raise ValueError("Preflight invocation changed")
            if any(receipt[key] < previous[key] for key in (
                "sequence", "elapsed_seconds", "scanned_files", "scanned_bytes", "child_committed"
            )):
                raise ValueError("Preflight evidence regressed")
            if receipt["sequence"] == previous["sequence"] and receipt != previous:
                raise ValueError("Preflight sequence was reused with different evidence")
        self.last = dict(receipt)
        return receipt


def validate_gui_cancellation(value, *, root, nonce, run_id, request_id):
    receipt = validate_receipt(value, root=root, nonce=nonce)
    if receipt["phase"] != "cancelled_before_launch":
        raise ValueError("Missing terminal cancellation")
    if not identity(request_id) or receipt["request_id"] != request_id:
        raise ValueError("Cancellation was not requested by this GUI action")
    if not identity(run_id) or receipt["run_id"] != run_id:
        raise ValueError("Cancellation invocation changed")
    return receipt


def require_current_result(root, summary):
    """A historical summary cannot supersede a newer unfinished preparation."""
    receipt = read_receipt(root)
    if receipt is None:
        return
    if receipt["phase"] != "finished" or receipt["result_run_id"] != summary.get("run_id"):
        raise ValueError("Current PHITS preparation is incomplete; downstream remains disabled")
    path = Path(root) / "analysis/segment_execution_summary.json"
    from dicomxphits.safe_output import WorkspaceOutputGuard
    with WorkspaceOutputGuard(Path(root), read_only=True) as guard:
        guard.prepare(path)
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
            stream.seek(0)
            actual = json.load(stream)
    if digest != receipt["summary_sha256"]:
        raise ValueError("Preflight terminal summary changed")
    if actual != summary:
        raise ValueError("Supplied execution evidence differs from the bound summary")


def require_finished_preflight(root):
    """Additional gate for downstream adapters with existing summary contracts."""
    if read_receipt(root) is None:
        return
    from dicomxphits.safe_output import WorkspaceOutputGuard
    path = Path(root) / "analysis/segment_execution_summary.json"
    with WorkspaceOutputGuard(Path(root), read_only=True) as guard:
        guard.prepare(path)
        with path.open(encoding="utf-8") as stream:
            summary = json.load(stream)
    require_current_result(root, summary)
    from dicomxphits.run_segments import validate_segment_execution_summary
    validate_segment_execution_summary(summary, require_success=True)


def checkpoint(*, files=0, size=0):
    current = _current.get()
    if current is not None:
        current.checkpoint(files=files, size=size)


def current_session():
    return _current.get()


class Session:
    def __init__(self, root, nonce, run_id, control):
        if not identity(nonce) or not identity(run_id):
            raise ValueError("Invalid preparation identity")
        self.root = Path(root).resolve()
        self.control = control
        self.poll = None
        self.started = time.monotonic()
        self.last_write = float("-inf")
        self.receipt = dict(schema_version=SCHEMA, workspace_root=str(self.root),
            run_id=run_id, gui_nonce=nonce, phase="preparing", sequence=0,
            elapsed_seconds=0.0, updated_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            scanned_files=0, scanned_bytes=0, child_committed=False,
            request_id=None, summary_sha256=None, result_run_id=None, cancel_rejected_request_id=None)

    def publish(self, phase=None, *, force=False):
        from dicomxphits.prepare_3dcrt_workspace import write_json
        now = time.monotonic()
        changed = phase is not None and phase != self.receipt["phase"]
        if phase is not None:
            self.receipt["phase"] = phase
        if not force and not changed and now - self.last_write < 0.25:
            return
        self.receipt.update(sequence=self.receipt["sequence"] + 1,
            elapsed_seconds=max(0.0, now - self.started),
            updated_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
        validate_receipt(self.receipt, root=self.root)
        write_json(self.root / RELATIVE_PATH, self.receipt, case_root=self.root)
        self.last_write = now

    def handle_cancel(self, request):
        if request.get("operation") != CANCEL:
            return False
        valid = (set(request) == {"operation", "workspace_root", "run_id", "request_id", "gui_nonce"}
            and request.get("workspace_root") == str(self.root)
            and request.get("run_id") == self.receipt["run_id"]
            and request.get("gui_nonce") == self.receipt["gui_nonce"]
            and identity(request.get("request_id")))
        if not valid or self.receipt["child_committed"]:
            if valid:
                self.receipt["cancel_rejected_request_id"] = request["request_id"]
                self.publish(force=True)
            self.control.report("Preparation cancellation rejected; no preparation cancellation was acknowledged.")
            return True
        self.receipt["request_id"] = request["request_id"]
        # Persist before raising, and only on the serialized owner thread.
        self.publish("cancelled_before_launch", force=True)
        raise PreparationCancelled()

    def checkpoint(self, *, files=0, size=0):
        self.receipt["scanned_files"] += files
        self.receipt["scanned_bytes"] += size
        if self.poll is not None:
            self.poll()
        elif self.control is not None:
            for request in self.control.take():
                if not self.handle_cancel(request):
                    self.control.reject()
        self.publish()

    def commit(self):
        self.checkpoint()
        self.receipt["child_committed"] = True
        self.publish("executing", force=True)

    def finish(self, summary):
        path = self.root / "analysis/segment_execution_summary.json"
        with path.open("rb") as stream:
            self.receipt["summary_sha256"] = hashlib.file_digest(stream, "sha256").hexdigest()
        self.receipt["result_run_id"] = summary["run_id"]
        self.publish("finished", force=True)

    def __enter__(self):
        self.publish(force=True)
        self.token = _current.set(self)
        return self

    def __exit__(self, kind, value, traceback):
        _current.reset(self.token)
        if kind is not None and kind is not PreparationCancelled:
            self.receipt["summary_sha256"] = None
            self.receipt["result_run_id"] = None
            self.publish("failed", force=True)
