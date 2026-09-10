"""Deterministic pipe failures; no PHITS executable is used."""
import errno
import io
from types import SimpleNamespace

import pytest

from dicomxphits import observed_process


@pytest.mark.parametrize("operation", ["write", "close"])
@pytest.mark.parametrize("error_number", [errno.EINVAL, errno.EPIPE, errno.EIO])
@pytest.mark.parametrize("returncode", [0, 7])
def test_child_stdin_failure_preserves_result_or_unrelated_error(
    monkeypatch, operation, error_number, returncode,
):
    calls = []

    def fail_if_selected(name):
        calls.append(name)
        if name == operation:
            raise OSError(error_number, "authored pipe failure")

    stdout = io.TextIOWrapper(io.BytesIO(b"identity\r\ndone\r\n"), encoding="utf-8")
    stderr = io.TextIOWrapper(io.BytesIO(b"diagnostic\r\n"), encoding="utf-8")

    def wait():
        calls.append("wait")
        return returncode

    child = SimpleNamespace(
        stdin=SimpleNamespace(write=lambda value: fail_if_selected("write"),
                              close=lambda: fail_if_selected("close")),
        stdout=stdout, stderr=stderr, wait=wait,
    )
    monkeypatch.setattr(observed_process.subprocess, "Popen", lambda *a, **kw: child)
    seen = []
    try:
        if error_number == errno.EIO:
            with pytest.raises(OSError) as raised:
                observed_process.run_with_observer(
                    ["authored-child"], stdout_observer=seen.append,
                    input="authored input", capture_output=True, text=True,
                )
            assert raised.value.errno == errno.EIO
        else:
            result = observed_process.run_with_observer(
                ["authored-child"], stdout_observer=seen.append,
                input="authored input", capture_output=True, text=True,
            )
            assert result.returncode == returncode
            assert result.stdout == "identity\ndone\n"
            assert result.stderr == "diagnostic\n"
            assert calls[:2] == ["write", "close"]
            assert stdout.closed and stderr.closed
        assert "wait" in calls
        assert b"".join(seen) == b"identity\r\ndone\r\n"
    finally:
        stdout.close()
        stderr.close()
