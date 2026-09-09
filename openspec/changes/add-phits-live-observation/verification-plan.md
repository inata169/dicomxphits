# Minimal synthetic PHITS 3.35 output-format verification plan

## Status and authority

This document is a plan only. The human authorized its preparation, not a real
PHITS launch, installation discovery, inspection of external data, or creation
of an external workspace. No real command below has been run. The human later
authorized preparation of the input and collector only; the project-authored
kit is now at `tools/phits_observation_probe/`, with fake-child tests. Actual
paths, frozen private plan and real execution approval remain outstanding.

This is the evidence-acquisition prerequisite for task 2.1, not a change to
public physics or a new clinical workflow. The synthetic transport model below
is exclusively a proposed file-format probe. It does not replace, calibrate,
validate or alter the fixed 6 MV/3D-CRT beam model.

## Question to answer

For one positively identified PHITS 3.35 Windows OpenMP invocation, establish:

1. The version/mode marker and when it becomes observable.
2. The complete `batch.out` record, including counter, ancillary fields and
   record boundaries, before/during/after batch updates.
3. The full multi-slice 3D T-Deposit dose/error grammar: input echo, page/slice
   identities, mesh ordering, numeric data, ending markers, and available
   history/restart metadata needed to reject unmatched pairs.
4. Whether those files become readable during execution and whether two
   successive stable, matching samples can actually be obtained.

Do not use the desired parser as the only oracle. Preserve raw observations
privately and compare their structure independently with the official manual.
One successful probe establishes only the observed variant, not every 3.35
setting or proof of atomic writes.

## Proposed single-run envelope

| Item | Proposed value |
| --- | --- |
| Executable | Human-selected PHITS 3.35 Windows OpenMP executable; no PATH search |
| Runs | Exactly one; no automatic retry, restart or parameter sweep |
| Threads | 2; input `$OMP = 2` and child `OMP_NUM_THREADS=2` |
| Calculation size | `maxcas=10000`, `maxbch=10`; 100000 requested source histories |
| Mode | Fresh ordinary transport (`icntl=0`); no negative `istdev`, MPI or continuation |
| Source | Synthetic 1 MeV monoenergetic photon pencil beam along positive z |
| Geometry | Homogeneous water cube, x/y/z from -1.5 to 1.5 cm; vacuum between water and an outer cube with edges -3 to 3 cm on each axis; particles outside the outer cube are terminated |
| Source position | x=y=0, z=-2 cm, outside water and strictly inside outer boundary |
| Material | Synthetic H2O at 1 g/cm3, no CT, DICOM, facility or machine data |
| Dose mesh | 3 by 3 by 3 cells over the cube; all three z slices must be observed |
| Tally | T-Deposit, `mesh=xyz`, `output=dose`, `axis=xy`, `part=all`, `material=all`, `unit=0`, `epsout=1` |
| Files | Relative `deposit-target-3D.out` and its PHITS-generated error companion; default `batch.out` and `phits.out` |

The final deck must use the existing generated 3D tally's non-mesh settings.
Do not change the production renderer, calculation config, `itall`, `istdev`,
`epsout`, transport cutoffs, dose factors or other defaults to make observation
easier. The small mesh, source and water geometry exist only in this isolated
probe. No PDD, accelerator, source spectrum file, patient anatomy, RTPLAN, MU,
Sumtally, phits2dicom, GPR, dose conversion or convergence decision is involved.
Leave time/seed settings at the reviewed fresh-run defaults and record their
effective values when available; do not claim bitwise OpenMP reproducibility.

These are deck requirements, not a claim of PHITS-validated input syntax.
Before execution approval, author and review the complete deck, library binding
and collector, including source/surface syntax and every output destination.
Do not substitute the pytest fake-runner workspace: it contains synthetic
placeholder executable/library identities and is not a real PHITS input kit.

## Paths and execution approval gate

The following must be explicitly selected and reviewed before any launch:

- The exact absolute executable and installation/library root, plus SHA-256
  of the executable. A filename alone is not proof of version or OpenMP mode.
- A new, absent, dedicated run directory and evidence directory under a
  human-approved scratch parent outside this repository and outside any
  clinical, failed or prior calculation workspace.
- The complete reviewed input and collector bytes and their SHA-256 digests.
- The final concrete launch record below, substituted with exact approved
  paths. Local paths and installation details remain private, not in Git.

No recursive search for installations or results, distribution copying,
overwrite, deletion or migration is authorized. Reject pre-existing targets,
links/reparse points and ambiguous containment. Library dependencies may point
only into the explicitly approved installation; treat that installation as
read-only. If the tool requires an installation write, stop for a decision.

### Launch record template (not executable shell text)

```text
argv: [<approved-absolute-phits335-openmp-executable>]
cwd: <approved-new-probe-directory>
stdin bytes: file = observation-probe.inp\n
shell: false
child environment override: OMP_NUM_THREADS=2
stdout/stderr: independently drained to approved private evidence files
launch count: 1
```

The stdin convention and environment override follow `phits_launcher_input()`
and `phits_environment()` in `src/dicomxphits/run_segments.py`. No wrapper batch
file, ANGEL process, GUI stage, installation launcher or automatic downstream
command is invoked. The proposed collector uses a directly owned child and the
existing inherited execution-lease mechanism; it must be reviewed with a fake
child before real launch. PHITS-generated auxiliary files remain within the
fresh run directory; the collector does not interpret or execute their contents.

Once paths, deck and collector are frozen, ask one explicit yes/no question
authorizing that exact single launch and its specified output locations.
Approval of this plan, preparation of those artifacts, or a path confirmation
is not execution approval. If a path or digest changes, return for approval.

## Read-only capture protocol

Start the collector before launch. Read only the four named PHITS files in
the approved run directory plus the directly owned stdout/stderr streams.
The dose error filename must be confirmed against the approved tally convention;
do not recursively search for an alternative when it is missing.

- Every 100 ms, at most one capture job checks file identity, size and mtime.
  This diagnostic cadence is deliberately distinct from the proposed GUI's
  maximum one-per-second sampling and does not change that contract.
- Copy changed candidate bytes to uniquely named files in the separate private
  evidence directory; record UTC and monotonic times and before/after metadata.
  Mark interrupted/changed reads as unstable evidence, not valid samples.
- Limit individual batch reads to 64 KiB and each small probe tally or summary
  to 8 MiB. Use chunked reads, bounded queues and short-lived shared read handles
  that do not deny PHITS write/delete access. Never lock PHITS output files for
  the duration of calculation, and never rewrite them to obtain a stable read.
- Cap all recorded evidence, including stream logs, at 100 MiB. At the cap or
  on capture failure, stop storing observations, continue draining streams
  without accumulating memory, and report an inconclusive capture. Do not kill
  the child, block its pipes or free its inherited lease prematurely.
- After natural child exit, take one final bounded copy of each expected file,
  record the exit code and final source-file digests, and close the collector.

This is diagnostic collection, not the production observer implementation.
Neither the snapshot filename nor stable mtime proves matching batch identity.
Keep unstable samples for private diagnosis; no raw output is committed.

## Stop and resource conditions

Before launch, missing dependencies, identity/path uncertainty, occupied target
directories, a failed fake-child collector check or changed input digests mean
no launch. Do not fix a real-tool failure by changing physics or installing
libraries automatically.

The 100000-history workload is fixed, not a wall-clock guarantee. The user must
remain available for the supervised probe. At ten minutes without natural exit,
notify the user and stop any additional work, while preserving child ownership
and draining its streams. No automatic timeout, signal, kill, `batch.out` edit,
or repeat launch is authorized. Any emergency termination needs a separate
explicit decision and would make the test incomplete, not a verified safe stop.

If the run finishes before intermediate snapshots are captured, preserve final
format evidence and report live-update evidence as inconclusive. Do not increase
histories, change threads or run again without separate approval. Preserve the
new probe directory on both success and failure; cleanup is not part of this plan.

## Acceptance matrix and report

| Check | Sufficient observation | Otherwise |
| --- | --- | --- |
| Version and mode | Unambiguous 3.35 marker, selected executable digest and OpenMP evidence consistent with launch | Identity unsupported; do not relabel an older/newer output |
| Batch format | Complete final record and at least two distinct in-run observations whose fields/order can be documented | Final grammar may be recorded; live progress remains unverified |
| 3D dose/error format | All 27 cells in three slices, matching roles/meshes and available history/restart metadata; exact endings documented | Do not fill missing slices or invent pairing metadata |
| Live tally observation | At least two distinct in-run matching pairs; each with two stable consecutive captures | Do not claim that final outputs establish live readability |
| Reference statistics | Independent calculation of positive-cell count, excluded count, median and maximum; no accuracy target | Zero/poor statistics are not an excuse to increase workload |
| Natural completion | Child exit recorded, required files present and geometry diagnostics assessed | Nonzero exit, missing/invalid diagnostics or files means failed/inconclusive probe |
| Noninterference | Approved input digests unchanged; collector writes only evidence files; final output digests stable after exit | Investigate without changing guards or reusing results |

Do not require every intermediate counter value to be sampled. Do not equate
counter zero with successful transport. Collector read overhead must be reported;
this one run cannot prove performance equivalence to an unobserved run.

The private report records exact paths, command, input/executable/collector
digests, timestamps, settings, exit outcome, capture limits, observed markers,
missing evidence and each matrix result. The public development record may
contain only sanitized structural conclusions, limitations and independently
authored synthetic fixtures. Review for local paths and protected information
before sharing; do not upload raw PHITS outputs or official distribution files.

If the available metadata cannot establish the approved observation contract,
report that conflict for a human decision. Do not quietly weaken the contract,
mark task 2.1 complete, or promote/archive the active change. A successful probe
does not authorize batch stopping, additional history or production data reuse.

## Reference boundary

The basis remains the [PHITS 3.35 manual](https://phits.jaea.go.jp/manual/manualE-phits335.pdf),
sections 3.2, 4.9 and 5.2.2. The live public HTML manual now identifies itself as
3.37 and is not evidence of exact 3.35 output compatibility. This plan is designed
to acquire the missing target-version observations, not to assert that they
have already been obtained.
