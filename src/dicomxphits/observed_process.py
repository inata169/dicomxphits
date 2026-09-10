"""Capture normal child results while exposing a bounded stdout identity prefix."""
from __future__ import annotations

import errno
import subprocess
import threading


def run_with_observer(command, *, stdout_observer, input, capture_output, text, **kwargs):
    """Same text result as the direct runner; observation callbacks cannot fail it.

    No file is added to the PHITS allocation, and no extra child is launched.
    The caller supplies the existing inherited lease through Popen kwargs.
    """
    if capture_output is not True or text is not True:
        raise ValueError("Observed runner requires the existing text capture contract")
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, **kwargs)
    chunks = [[], []]
    errors = []

    def drain(stream, index):
        try:
            while chunk := stream.buffer.read1(65536):
                chunks[index].append(chunk)
                if index == 0:
                    try:
                        stdout_observer(chunk)
                    except Exception:
                        pass
        except BaseException as exc:
            errors.append(exc)

    readers = [threading.Thread(target=drain, args=(stream, index))
               for index, stream in enumerate((process.stdout, process.stderr))]
    for reader in readers:
        reader.start()
    try:
        try:
            process.stdin.write(input)
        except BrokenPipeError:
            pass
        except OSError as exc:
            # Match subprocess.run when a Windows child closes its stdin.
            if exc.errno != errno.EINVAL:
                raise
        try:
            process.stdin.close()
        except BrokenPipeError:
            pass
        except OSError as exc:
            if exc.errno != errno.EINVAL:
                raise
        code = process.wait()
    finally:
        # Never release the inherited lease while the owned child survives.
        process.wait()
        for reader in readers:
            reader.join()
    try:
        if errors:
            raise errors[0]
        output = [b"".join(value).decode(stream.encoding, stream.errors).replace("\r\n", "\n").replace("\r", "\n")
                  for value, stream in zip(chunks, (process.stdout, process.stderr))]
        return subprocess.CompletedProcess(command, code, *output)
    finally:
        process.stdout.close()
        process.stderr.close()
