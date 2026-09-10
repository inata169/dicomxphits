# Synthetic observation probe preparation

These are project-authored diagnostic artifacts, not PHITS distribution files
or a production beam model. They implement only capture for the approved
[verification plan](../../openspec/changes/archive/2026-09-10-add-phits-live-observation/verification-plan.md).
Preparing/testing this kit does **not** authorize real PHITS execution.

## Artifacts and scope

- `observation-probe.inp`: standalone 1 MeV photon pencil beam and water cube,
  27 dose cells, 2 OpenMP threads, 100000 histories per batch and 10 batches.
  It is not a CT/RTPLAN workspace and must not feed Sumtally or RTDOSE.
- `collect.py`: check-only by default; a separate execution mode launches one
  exact executable in fresh private directories and records raw output bytes.
  It neither implements the GUI observer nor interprets PHITS output syntax.
- `tests/test_phits_observation_probe.py`: synthetic files and temporary Python
  children only. The fake executable identity is never launched.

The source uses `s-type=1`, `r0=0`, `z0=z1=-2`, `dir=1`, `e0=1`; the
[PHITS 3.35 manual](https://phits.jaea.go.jp/manual/manualE-phits335.pdf), section
5.3.3, documents the pencil/monoenergetic source parameters. Cell 1 is the water
inside surface 1; cell 2 is vacuum outside surface 1 and inside surface 2;
cell 3 terminates transport outside surface 2. The tally non-mesh settings match
the repository's generated 3D dose tally. The first separately approved probe
used 10000 histories per batch and produced valid final files, but lacked the
required twice-confirmed live pairs. The separately approved second probe
provided the missing live evidence. A third separately approved diagnostic
checked the production observer and a dedicated Tk window with unchanged input.
See the archived change's tasks for the evidence and limits. Every new execution
still requires fresh exact launch approval. Do not change production physics
or guess a parser grammar on the basis of these synthetic helper tests.

## Private plan, before any real execution

After the human selects and authorizes inspection of the exact installation
and scratch parent, prepare a private UTF-8 JSON file outside the repository.
All fields below are required and unknown fields are rejected. This example
has intentional placeholders and cannot pass validation:

```json
{
  "schema": "dicomxphits_observation_probe_plan_v1",
  "executable": "<approved absolute installation>/bin/phits335_win_openmp.exe",
  "installation_root": "<approved absolute installation>",
  "scratch_parent": "<approved absolute dedicated scratch parent>",
  "run_dir": "<scratch parent>/probe-run-001",
  "evidence_dir": "<scratch parent>/probe-evidence-001",
  "executable_sha256": "<SHA-256 of selected executable bytes>",
  "deck_sha256": "<SHA-256 of observation-probe.inp bytes>",
  "collector_sha256": "<SHA-256 of collect.py bytes>",
  "lease_sha256": "<SHA-256 of src/dicomxphits/workspace_execution.py bytes>",
  "libpath_sha256": "<SHA-256 of generated libpath bytes>"
}
```

The library binding is UTF-8 without BOM, forward-slash installation path,
and exactly `file(1)  = <installation> # PHITS install folder name` followed by
one LF. `libpath_bytes()` returns these bytes without writing anything.
Calculate hashes from the actual checked-out files (including their newline
bytes), not from pasted text. Do not put local paths, actual installation data,
or raw PHITS outputs in this repository. No installation dependencies are
discovered, copied, repaired or installed by the checker; their availability
must be established in the separately authorized preflight.

The run and evidence directories must be distinct, absent direct children of
the approved scratch parent. Existing destinations are never reused, even if
empty or left by a failed launch. The parent cannot contain or be contained by
the repository or installation. It must not be a patient/prior-workspace
location; the human's path selection is essential. A path/digest change requires
fresh approval. The checker does not assert that a filename proves version.

### Check-only command (after path-inspection authorization)

With the project's Python 3.12 environment and package available:

```text
python tools/phits_observation_probe/collect.py --plan <private-plan.json>
```

This reads and checks only the exact paths, identities and supplied hashes. It
does not create directories or launch a child, and prints the SHA-256 of the
plan bytes. It is not human execution approval. With no arguments, the script
prints required-argument usage and does not inspect an installation.

### Execution command template (NOT authorized by preparing this kit)

Only after the human approves the exact plan digest, paths and one launch:

```text
python tools/phits_observation_probe/collect.py --plan <private-plan.json> --execute --approved-plan-sha256 <approved-plan-digest>
```

This mode is Windows-only. It creates the two new directories, writes the exact
probe and library binding, captures launch identity, checks executable/input
bytes again, and starts the absolute executable once with `shell=False`,
`file = observation-probe.inp` on stdin and `OMP_NUM_THREADS=2`. The direct child
inherits the existing workspace lease and starts hidden in a separate process
group, so interrupting the collector must not intentionally signal PHITS.
There is no retry, restart, process kill, batch-file edit, cleanup or downstream
launch. PHITS-generated auxiliary files are not executed by the collector.

## Capture and interpretation

The collector checks only `batch.out`, `phits.out`, `deposit-target-3D.out` and
`deposit-target-3D_err.out`. It captures changed bytes and small unchanged-read
confirmations with sequence, time, hash, file identity, size and mtime. An empty
confirmation `.bin` means no duplicate bytes were stored, not an empty PHITS
output; find the preceding same-role/same-hash capture. Final captures keep
their bytes unless collection was disabled. Snapshot metadata is **not** proof
that dose/error files represent one atomic generation.

Stdout and stderr are drained independently into ordered binary chunks.
Metadata, snapshots and stream chunks share a 100 MiB cap with 64 KiB reserved
for `report.json`. On a capture/write/size failure collection is disabled and
streams continue draining without storage. Missing files before creation are
ordinary waiting, not a failure. The final report records raw capture status,
exit code, input digest checks and missing/unavailable files; it never grants
verified PHITS success or parser compatibility. Collector exit 0 indicates a
complete natural capture only; exit 2 indicates incomplete capture. Exceptions
may instead end the collector nonzero while leaving evidence for inspection.

At ten minutes a warning requests human attention; the child is not killed.
There is no wall-time guarantee. The user must supervise the run, and any
emergency termination needs separate authorization. Evidence and run files
remain on disk after success/failure and are never uploaded automatically.

The independent acceptance matrix in the verification plan must still be
assessed manually: version/mode identity, full grammar, geometry diagnostics,
paired metadata, at least two distinct live updates, and reference statistics.
Zero exit alone does not satisfy it. The first probe was inconclusive for live
pair stability; the second satisfied task 2.1. Dedicated real-PHITS/Tk diagnostic
verification and synthetic testing of the actual GUI are recorded separately
from an unperformed full real-GUI workflow test. Retain each previous private
plan and its evidence; never reuse its destinations for a revised probe.
