"""Invocation-scoped cooperative stop control; never terminates a PHITS child."""
from __future__ import annotations

import json
import queue
import re
import sys
import subprocess
import threading
import uuid
from collections.abc import Callable, Mapping

MAX_CONTROL_BYTES = 4096
OPERATION = "stop-after-current"


class StopControl:
    """A reader queues bounded messages; only the execution owner accepts them."""

    def __init__(self, report: Callable[[str], None] | None = None):
        self._messages: queue.Queue = queue.Queue(maxsize=16)
        self._closed = threading.Event()
        self.report = report or (lambda message: print(message, file=sys.stderr))

    def reject(self):
        self.report("Stop request rejected; no stop acknowledgement was granted.")

    def feed(self, record: bytes):
        if self._closed.is_set():
            return
        try:
            if len(record) > MAX_CONTROL_BYTES:
                raise ValueError("oversized")
            value = json.loads(record.decode("utf-8"))
            if not isinstance(value, dict):
                raise ValueError("not an object")
            self._messages.put_nowait(value)
        except (ValueError, UnicodeError, RecursionError, queue.Full):
            self.reject()

    def read(self, stream):
        """Use an unbuffered stream for a daemon reading controller stdin."""
        try:
            while not self._closed.is_set():
                record = stream.readline(MAX_CONTROL_BYTES + 1)
                if not record:
                    return
                if len(record) > MAX_CONTROL_BYTES:
                    self.reject()
                    while record and not record.endswith(b"\n"):
                        record = stream.readline(MAX_CONTROL_BYTES + 1)
                    continue
                if not record.endswith(b"\n"):
                    self.reject()
                    return
                self.feed(record)
        except (OSError, ValueError):
            self.reject()
        finally:
            stream.close()

    def start_reader(self, stream):
        threading.Thread(target=self.read, args=(stream,), daemon=True).start()

    def take(self):
        # A bounded batch cannot starve execution under a flooding sender.
        for _ in range(16):
            try:
                yield self._messages.get_nowait()
            except queue.Empty:
                return

    def close(self):
        self._closed.set()


def valid_request(value, *, workspace: str, run_id: str) -> bool:
    return (isinstance(value, dict)
        and set(value) == {"operation", "workspace_root", "run_id", "request_id"}
        and value.get("operation") == OPERATION
        and value.get("workspace_root") == workspace
        and value.get("run_id") == run_id
        and isinstance(value.get("request_id"), str)
        and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value["request_id"]) is not None)


def run_while_polling(runner, poll, *args, **kwargs):
    """Keep summary writes on the owner thread while its direct child runs.

    Even persistence failure/interrupt must wait for the child before staging
    cleanup or lease release. No cancellation, timeout, or kill is introduced.
    """
    completed = threading.Event()
    result = []
    errors = []

    def worker():
        try:
            result.append(runner(*args, **kwargs))
        except BaseException as exc:
            errors.append(exc)
        finally:
            completed.set()

    thread = threading.Thread(target=worker)
    thread.start()
    try:
        while not completed.wait(0.05):
            poll()
        poll()
    finally:
        thread.join()
    if errors:
        raise errors[0]
    return result[0]


def validate_stop_evidence(summary: Mapping):
    from dicomxphits.run_segments import _is_nonnegative_number, _parse_utc_text

    if type(summary.get("stop_control_enabled")) is not bool or "stop_requested" not in summary:
        raise ValueError("Missing stop capability evidence")
    stop = summary["stop_requested"]
    if stop is not None:
        if not isinstance(stop, dict) or set(stop) != {
            "request_id", "run_id", "workspace_root", "acknowledged_at",
            "acknowledged_elapsed_seconds", "boundary_segment",
        }:
            raise ValueError("Malformed stop acknowledgement")
        envelope = {key: stop[key] for key in ("request_id", "run_id", "workspace_root")}
        envelope["operation"] = OPERATION
        binding = summary.get("execution_binding")
        if (not summary["stop_control_enabled"]
            or not valid_request(envelope, workspace=summary["workspace_root"], run_id=summary["run_id"])
            or not isinstance(binding, dict) or binding.get("retry_unavailable")):
            raise ValueError("Stop acknowledgement is not eligible for this invocation")
        # Wall clocks may move; only parse UTC, use monotonic time for ordering.
        _parse_utc_text(stop["acknowledged_at"], field_name="acknowledged_at")
        elapsed = stop["acknowledged_elapsed_seconds"]
        if not _is_nonnegative_number(elapsed) or elapsed > summary["elapsed_seconds"]:
            raise ValueError("Invalid stop acknowledgement duration")
        boundary = stop["boundary_segment"]
        if boundary is not None:
            if not isinstance(boundary, dict) or set(boundary) != {"segment_id", "manifest_ordinal", "active_ordinal"}:
                raise ValueError("Malformed stop boundary")
            matches = [item for item in summary["segments"] if all(item.get(k) == v for k, v in boundary.items())]
            if len(matches) != 1 or matches[0].get("started_at") is None:
                raise ValueError("Stop boundary is not a committed segment")
    if summary["stage_status"] == "stopped":
        if (stop is None or summary.get("current_segment") is not None
            or summary["failed"] or summary["remaining_active_segment_count"] <= 0
            or any(i["status"] not in {"pending", "success", "skipped"} for i in summary["segments"])):
            raise ValueError("Invalid terminal stopped evidence")


class ControllerPipe:
    """GUI-owned stdin pipe to one controller; stdout/stderr are always drained."""

    def __init__(self):
        self.process = None

    def run(self, command, *, cwd, **kwargs):
        process = subprocess.Popen([*command, "--control-stdin"], cwd=cwd,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", shell=False)
        self.process = process
        output = ["", ""]

        def drain(stream, index):
            try:
                output[index] = stream.read()
            finally:
                stream.close()

        readers = [threading.Thread(target=drain, args=(stream, index))
            for index, stream in enumerate((process.stdout, process.stderr))]
        for reader in readers:
            reader.start()
        try:
            code = process.wait()
        finally:
            self.process = None
            # Nothing closes PHITS stdin or signals a child. This pipe belongs
            # only to the controller that has exited.
            process.stdin.close()
            for reader in readers:
                reader.join()
        return subprocess.CompletedProcess(command, code, *output)

    def send(self, workspace: str, run_id: str):
        process = self.process
        if process is None or process.poll() is not None:
            raise ValueError("No active owned PHITS controller")
        request_id = uuid.uuid4().hex
        request = {"operation": OPERATION, "workspace_root": workspace,
            "run_id": run_id, "request_id": request_id}
        record = json.dumps(request, ensure_ascii=True) + "\n"
        if len(record.encode("utf-8")) > MAX_CONTROL_BYTES:
            raise ValueError("Stop request exceeds the supported size")
        process.stdin.write(record)
        process.stdin.flush()
        return request_id
