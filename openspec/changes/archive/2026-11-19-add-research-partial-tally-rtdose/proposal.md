# Add research-only RT Dose export from retained partial PHITS tallies

## Why

A PHITS process can report the last planned batch and terminate before it
writes the final tallies and geometry diagnostics. A complete on-disk tally
pair can still represent the preceding batch. Its restart metadata identifies
the statistics actually saved. The existing geometry-recovery acceptance
requires a zero exit code and completed diagnostics, so it cannot handle
this failure.

## What Changes

- Add an explicit research export action for a retained PHITS 3.35 Windows
  OpenMP tally set one batch short of the prepared budget after a recorded
  terminal stack overflow. Initially require one active fixed-field 3D-CRT
  segment that satisfies the existing full-plan delivery contract.
- Preview and confirm the exact retained snapshot. Preserve the failed
  invocation and describe the saved and planned batch counts, exit code, and
  unavailable end-of-run geometry diagnostics in the export provenance.
- Aggregate using the existing Sumtally numerical contract and convert using
  the existing RTDOSE numerical and spatial contracts. Write a separately
  labelled RT Dose and a digest-bound receipt in a dedicated research output
  directory. The export adds no particle transport.

## Impact

- Adds a research-only GUI action and output status. The standard workflow,
  selective retry, and accepted geometry-recovery workflow keep their
  existing authority and status rules.
- Reuses existing plan, field-size, model, calibration, normalization,
  geometry, and DICOM validation. The research RT Dose carries a standard
  descriptive attribute identifying the partial tally and its batch count.
- Implementation validation uses synthetic artifacts and fake runners.
  Testing real tools or converting an existing local case requires separate
  explicit authorization.

See the [design](design.md), [implementation checklist](tasks.md), and
requirement deltas for the [research export](specs/research-partial-tally-rtdose/spec.md),
[GUI](specs/guided-gui-workflow/spec.md), and
[retry boundary](specs/phits-segment-retry/spec.md).
