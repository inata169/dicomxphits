"""Differential and resource checks using authored values and mocked I/O."""
import hashlib
import importlib.util
import json
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import numpy as np
import pytest

from dicomxphits import phits_observation as observer
from dicomxphits import phits_observation_format as fmt
from test_phits_live_observation import MESH, observer_fixture, tally


@pytest.mark.parametrize("batch_mode", ["valid", "malformed", "wrong-count", "rejected-after-confirmation"])
def test_benchmark_requires_complete_batch_observation(tmp_path, monkeypatch, capsys, batch_mode):
    spec = importlib.util.spec_from_file_location(
        "benchmark_live", Path(__file__).resolve().parents[1] / "tools/benchmark_live_observation.py")
    benchmark = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(benchmark)
    original = benchmark.prepare

    def prepare(root, n):
        live, dose, error, mesh = original(root, 3)
        batch = root / "batch.out"
        if batch_mode == "malformed":
            batch.write_text("malformed", encoding="ascii")
        elif batch_mode == "wrong-count":
            batch.write_text(batch.read_text("ascii").replace("10 <---", "9 <---"), encoding="ascii")
        elif batch_mode == "rejected-after-confirmation":
            sample = live.sample
            calls = 0

            def rejecting_sample():
                nonlocal calls
                calls += 1
                if calls == 3:
                    batch.write_text("malformed", encoding="ascii")
                return sample()

            live.sample = rejecting_sample
        return live, dose, error, mesh

    monkeypatch.setattr(benchmark, "prepare", prepare)
    monkeypatch.setattr(benchmark.time, "sleep", lambda _: None)
    root = tmp_path / "benchmark"
    monkeypatch.setattr(sys, "argv", ["benchmark", "--output-directory", str(root)])
    benchmark.main()
    result = json.loads((root / "results.json").read_text("utf-8"))
    assert all(row["full_pair_validated"] for row in result["measurements"])
    assert result["provisional_pass"] is (batch_mode == "valid")
    capsys.readouterr()


def compare(text, count):
    try:
        tokens = text.split()
        fmt.require(len(tokens) == count)
        expected = np.array([fmt.number(token) for token in tokens])
        fmt.require((expected >= 0).all())
    except fmt.ObservationError:
        with pytest.raises(fmt.ObservationError):
            fmt._parse_numeric_page(text, np.empty(count), time.monotonic() + 5)
    else:
        result = np.empty(count)
        fmt._parse_numeric_page(text, result, time.monotonic() + 5)
        assert np.array_equal(result.view(np.uint64), expected.view(np.uint64))


@pytest.mark.parametrize("token", [
    "1.234E-03", "0.000E+00", "9.999E+99", "1.001E-99", "-0.000E+00",
    "+1.234E-03", "1.234D-03", "1.234d-03", ".1", "1.", "1", "1e-999",
    "-1e-999", "1e309", "nan", "inf", "-1", "1e", "1e+", ".", "+",
    "1_0", "0x1", "1.234E-03junk", "1" * 64, "1" * 65,
    "0." + "0" * 61 + "1", "0." + "0" * 62 + "1", "", "1 2",
])
def test_numeric_spellings(token):
    compare(token, 1)


def test_ascii_substitutions_and_varied_floats():
    token = "1.234E-03"
    for index in range(len(token)):
        for code in range(128):
            compare(token[:index] + chr(code) + token[index + 1:], 1)
    rng = np.random.default_rng(17)
    tokens = [f"{a}.{b:03d}E{e:+03d}" for a, b, e in zip(
        rng.integers(0, 10, 20000), rng.integers(0, 1000, 20000),
        rng.integers(-99, 100, 20000))]
    compare(" ".join(tokens), len(tokens))


@pytest.mark.parametrize("space", [" ", "\t", "\r\n", "\v", "\f", "\x1c"])
@pytest.mark.parametrize("length", [9, 64, 65])
def test_scan_boundaries_and_whitespace(space, length):
    token = "0." + "0" * (length - 3) + "1"
    text = space * (fmt.NUMERIC_SCAN_CHARS - 3) + token + space + "1.234E-03"
    compare(text, 2)


@pytest.mark.parametrize("position", [0, 4095, 4096, 6553, 8192])
def test_invalid_distant_cells_and_counts(position):
    tokens = ["1.234E-03"] * 8193
    tokens[position] = "nan"
    compare(" ".join(tokens), len(tokens))
    compare("1.234E-03 " * 4097, 4096)
    compare("1.234E-03 " * 4095, 4096)


@pytest.mark.parametrize("text", [" " * 200000, "1 " * 100000, "1.234E-03 " * 20000],
                         ids=["whitespace", "scalar", "canonical"])
def test_deadline_during_scanning_and_fallback(text, monkeypatch):
    ticks = iter([0, 0, 3])
    monkeypatch.setattr(fmt.time, "monotonic", lambda: next(ticks, 3))
    with pytest.raises(fmt.ObservationError, match="resource-limit"):
        fmt._parse_numeric_page(text, np.empty(len(text.split())), 2)


def test_chunk_scratch_bound_and_long_unbroken_token():
    for count in (10201, 100000):
        chunks = fmt._numeric_chunks("1 " * count, time.monotonic() + 5)
        sizes = [len(chunk) for chunk in chunks]
        assert sum(sizes) == count and max(sizes) <= fmt.NUMERIC_CHUNK_TOKENS
    compare("1" * (fmt.NUMERIC_SCAN_CHARS * 2), 1)


@pytest.mark.parametrize("variance", [1, 2])
@pytest.mark.parametrize("damage", ["none", "seed", "mesh", "role", "count", "zero", "numeric", "ending"])
def test_full_pair_matches_scalar(variance, damage):
    dose = tally(values=["1.234E-03"] * 8).replace(b"# istdev = 2", f"# istdev = {variance}".encode())
    error = tally("error", ["1.234E-01"] * 8).replace(b"# istdev = 2", f"# istdev = {variance}".encode())
    if damage == "seed": error = error.replace(b"0" * 64, b"1" * 64)
    if damage == "mesh": error = error.replace(b"nx = 2", b"nx = 3")
    if damage == "role": error = dose
    if damage == "count": error = error.replace(b"# resc3 = 1.00000000000000000E+01", b"# resc3 = 11")
    if damage == "zero": error = error.replace(b"1.234E-01", b"0.000E+00")
    if damage == "numeric": error = error.replace(b"1.234E-01", b"nan", 1)
    if damage == "ending": error = error[:-2]
    def parse(fast):
        return fmt.paired_isocenter_error(dose, error, MESH, 10,
            time.monotonic() + 5, live_maxbch=10, live_numeric=fast)
    try:
        expected = parse(False)
    except fmt.ObservationError:
        with pytest.raises(fmt.ObservationError):
            parse(True)
    else:
        assert parse(True) == expected


def test_shared_default_does_not_use_fast_numeric(monkeypatch):
    def forbidden(*args):
        pytest.fail("shared scalar path selected live optimization")
    monkeypatch.setattr(fmt, "_parse_numeric_page", forbidden)
    assert fmt.paired_isocenter_error(tally(), tally("error"), MESH, 10,
        time.monotonic() + 5) == {"relative_error_percent": 10.0}


@pytest.mark.parametrize("prefix", [False, True])
def test_read_digest_and_same_metadata_changed_bytes(tmp_path, prefix):
    path = tmp_path / "authored.out"
    data = b"a" * 150000
    path.write_bytes(data)
    before = path.stat()
    limit = 70000 if prefix else len(data)
    raw, signature = observer.read_snapshot(tmp_path, path, limit, time.monotonic() + 5, prefix=prefix)
    assert raw == data[:limit] and signature[1] == hashlib.sha256(raw).hexdigest()
    path.write_bytes(b"b" * len(data))
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    raw2, signature2 = observer.read_snapshot(tmp_path, path, limit, time.monotonic() + 5, prefix=prefix)
    assert signature[0] == signature2[0] and signature[1] != signature2[1]
    assert signature2[1] == hashlib.sha256(raw2).hexdigest()


@pytest.mark.parametrize("mutation", ["replace", "truncate"])
def test_read_rejects_changes_after_handle_read(tmp_path, monkeypatch, mutation):
    path = tmp_path / "authored.out"
    path.write_bytes(b"abc")
    original = observer.shared_open
    @contextmanager
    def changing(root, target):
        with original(root, target) as stream:
            yield stream
        if mutation == "truncate":
            path.write_bytes(b"a")
        else:
            replacement = tmp_path / "replacement"
            replacement.write_bytes(b"abc")
            replacement.replace(path)
    monkeypatch.setattr(observer, "shared_open", changing)
    with pytest.raises(fmt.ObservationError, match="updating"):
        observer.read_snapshot(tmp_path, path, 100, time.monotonic() + 5)


def test_channel_independence_and_timeout_timestamp(tmp_path, monkeypatch):
    live, _ = observer_fixture(tmp_path)
    live.sample()
    accepted = live.sample()
    (live.staging / "batch.out").write_bytes(b"malformed")
    record = live.sample()
    assert record["batch"]["state"] == "stale"
    assert record["error"]["state"] == "available"
    assert record["error"]["sample_utc"] == accepted["error"]["sample_utc"]
    def timeout(*args, **kwargs):
        raise fmt.ObservationError("resource-limit")
    monkeypatch.setattr(observer, "paired_isocenter_error", timeout)
    record = live.sample()
    assert record["error"]["state"] == "stale"
    assert record["error"]["reason"] == "resource-limit"
    assert record["error"]["sample_utc"] == accepted["error"]["sample_utc"]
