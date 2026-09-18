"""Authored synthetic observation benchmark; never executes PHITS or reads real data."""
import argparse
import json
import platform
import statistics
import time
from pathlib import Path

import numpy as np
from dicomxphits.phits_observation import Observer
from dicomxphits.phits_observation_format import Mesh, paired_tally_values


def fixture(n=101, role='dose', variance=1):
    mesh = Mesh('Authored performance fixture', 'dose.out', (n, n, n), ((-15.15, 15.15),) * 3)
    rows = ['[ T-Deposit ]', 'title = ' + mesh.title, 'mesh = xyz']
    for axis in 'xyz':
        rows += [f'{axis}-type = 2', f'{axis}min = -15.15', f'{axis}max = 15.15', f'n{axis} = {n}']
    rows += ['unit = 0', 'material = all', 'output = dose', 'axis = xy', 'file = dose.out', 'part = all', 'epsout = 1',
             'letmat = 0', 'dedxfnc = 0', 'deposit = 0', '2D-type = 3', 'mother = all', '#newpage:']
    step = 30.3 / n
    vals = ['1.234E-03', '0.000E+00', '2.345E+01', '9.876E-09'] if role == 'dose' else ['1.234E-01', '0.000E+00', '2.345E-01', '9.876E-02']
    for page in range(1, n + 1):
        if page > 1:
            rows.append(' newpage:')
        rows += [f'#   no. = {page:2d}   iz  = {page:2d}   part. = all',
                 f'#   z = ( {-15.15+(page-1)*step:.4E} - {-15.15+page*step:.4E} )',
                 f"'no. = {page:2d},  iz = {page:2d}'", 'msuc: {Authored performance fixture}',
                 r'msdl: {\it calculated by \PHITS  3.35}', f'#  ny =   {n}   nx =   {n}',
                 '# ( ( data(x,y), x = 1, nx ), y = ny, 1, -1 )', '',
                 f'hc:  y = {15.15-step/2:.7g} to {-15.15+step/2:.7g} by {step:.7g} ; x = {-15.15+step/2:.7g} to {15.15-step/2:.7g} by {step:.7g} ;']
        tokens = [vals[(i + page) % 4] for i in range(n*n)]
        # Explicit positive center; not a modification of any real calculation.
        if page == n // 2 + 1:
            tokens[(n*n)//2] = vals[0]
        rows += [' '.join(tokens[i:i+10]) for i in range(0, len(tokens), 10)]
        rows += ['', '#' + '-'*78, 'hc: y= 0.005 to 0.995 by 0.01 ; x= 0.5 to 0.5 by 1 ;',
                 ' '.join(str(i) for i in range(1, 101)), 'z: xorg(0.0)',
                 'y: ' + ('Dose [Gy/source]' if role == 'dose' else 'Relative Error'),
                 'e:', 'z: xorg[-1.03/0.05]', 'p: ymin(-1) ymax(1)', '']
    rows += ['# Information for Restart Calculation', '# This calculation was newly started',
             f'# istdev = {variance} # 1:Batch variance, 2:History variance',
             '# resc2 = 1.000E+00 # Total source weight or Total source weight / maxcas',
             '# resc3 = 10 # Total history number or Total batch number',
             '# maxcas = 1000 # History / Batch, only used for istdev=1', '# bitrseed = ' + '0'*64 + ' # bit data of rseed']
    return ('\n'.join(rows) + '\n').encode('ascii'), mesh


def prepare(root, n):
    root.mkdir(parents=True, exist_ok=False)
    dose, mesh = fixture(n)
    error, _ = fixture(n, role="error")
    (root / "dose.out").write_bytes(dose)
    (root / "dose_err.out").write_bytes(error)
    (root / "input.inp").write_text(
        "$OMP = 1\n[ Parameters ]\nmaxcas = 1000\nmaxbch = 10\n"
        + dose.decode("ascii").split("#newpage:")[0], encoding="ascii")
    (root / "phits.out").write_text("Version = 3.350\n", encoding="ascii")
    (root / "batch.out").write_text(
        "10 <--- remaining batch number\n\n" + "-" * 79
        + "\n start calculation\n" + "-" * 79
        + "\n\n date = 2000-01-01\n time = 00h 00m 00\n\n", encoding="ascii")
    live = Observer(root, root, root / "input.inp", root / "dose.out", {"synthetic": True})
    live.feed_stdout(b"OpenMP PARALLEL PROCESS 1/1 @ IP(MPI)=0")
    return live, dose, error, mesh


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-directory", type=Path, required=True,
                        help="New directory for authored fixtures and results; must not exist")
    parser.add_argument("--check-only", action="store_true",
                        help="Check small synthetic full-pair equivalence without timing acceptance")
    parser.add_argument("--load-note", default="Uncontrolled; no claim of isolated load")
    args = parser.parse_args()
    root = args.output_directory.resolve()
    live, dose, error, mesh = prepare(root, 3 if args.check_only else 101)
    if args.check_only:
        scalar = paired_tally_values(dose, error, mesh, 1000,
                                     time.monotonic() + 2, live_maxbch=10)
        fast = paired_tally_values(dose, error, mesh, 1000,
                                   time.monotonic() + 2, live_maxbch=10, live_numeric=True)
        assert all(np.array_equal(a.view(np.uint64), b.view(np.uint64))
                   for a, b in zip(scalar[:2], fast[:2]))
        assert scalar[2] == fast[2]
        assert live.sample()["error"]["value"] is None
        assert live.sample()["error"]["value"] == {"relative_error_percent": 12.34}
        print("Small authored pair: bitwise equivalence and integrated confirmation passed")
        return
    records = []
    for _ in range(5):
        start = time.perf_counter()
        record = live.sample()
        seconds = time.perf_counter() - start
        # offer() sets previous only after full pair validation; reject() clears it.
        # The display reason "updating" alone can also mean an unstable read.
        records.append({"seconds": seconds, "full_pair_validated": live.error.previous is not None,
                        "batch_validated": live.batch.previous is not None and live.last_remaining == 10,
                        "batch": record["batch"], "error": record["error"]})
        time.sleep(max(0, live.interval - seconds))
    elapsed = [row["seconds"] for row in records]
    completed = [row["seconds"] for row in records
                 if row["full_pair_validated"] and row["batch_validated"] and row["seconds"] <= 2]
    confirmed = any(
        row["full_pair_validated"] and row["batch_validated"] and row["seconds"] <= 2
        and row["batch"]["reason"] == "available"
        and row["batch"]["value"] == {"remaining": 10, "prepared_total": 10}
        and row["error"]["reason"] == "available"
        and row["error"]["value"] == {"relative_error_percent": 12.34}
        for row in records)
    result = {
        "scope": "Complete synchronous Observer.sample; excludes worker, publication and GUI",
        "python": platform.python_version(), "numpy": np.__version__,
        "mesh": mesh.counts, "pair_bytes": [len(dose), len(error)],
        "cache": "Freshly authored files; OS cache not flushed", "load_note": args.load_note,
        "measurements": records, "median_seconds": statistics.median(elapsed),
        "mean_seconds": statistics.mean(elapsed), "maximum_seconds": max(elapsed),
        "completed_parse_seconds": completed,
        # Identity failures mask resource-limit as unsupported-identity. Count
        # elapsed budget overruns independently of either channel's reason.
        "timeouts": sum(row["seconds"] > 2 or any(
            row[channel]["reason"] == "resource-limit" for channel in ("batch", "error"))
            for row in records),
        "authored_value_confirmed": confirmed,
        "provisional_pass": statistics.median(elapsed) <= 2 and len(completed) >= 3 and confirmed,
        "timeout_note": "Counts resource-limit rejections or elapsed budget overruns; these are failed attempts, not complete parsing times",
    }
    (root / "results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
