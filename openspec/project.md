# Project Context

## Purpose

`dicomxphits` is education and research software that prepares the documented
fixed-field 3D-CRT workflow from DICOM inputs through explicit PHITS-related
handoff stages. It is not clinical commissioning, patient QA, or vendor
certification software.

## Current Source Candidate

- The source candidate is `v1.1.1`, preparing the merged PR #83/#84 repairs
  and PR #85 operating manuals as an experimental patch release.
- v1.1.1 publication requires a separate human decision. No new capability,
  normative specification or physical validation is introduced. See
  [candidate release notes](../docs/release-notes-v1.1.1.md).

## Current Public Release

- The current public release is `v1.1.0`, tagged at commit
  `12ea1b2ff65fac2fde276624ea692327d5fa710d` (2026-09-18).
- v1.1.0 is experimental education-and-research software. Automated tests and
  bounded synthetic GUI checks passed, but stable real external-tool operation
  and final-version PHITS/controller end-to-end execution remain unverified.
- No custom Windows offline asset is published for v1.1.0. The v1.0.2 custom
  offline asset was withdrawn and removed; its historical identity remains
  documented in `docs/release-notes-v1.0.2.md`.
- Release publication does not expand the normative public scope below. The
  accepted contracts remain under `openspec/specs/`, and no active OpenSpec
  change remains at the v1.1.0 publication checkpoint. Historical v1.0.3
  acceptance evidence is not v1.1.0 external-tool validation.

## Technology

- Python 3.12 only for the v1 supported environment; Python 3.11 and earlier
  and Python 3.13 and later are outside the v1 support range
- `pydicom` and `numpy`
- `pytest` with synthetic DICOM and fake or mock external-tool runners
- Windows adapters for explicitly authorized local external-tool execution
- Git feature branches and reviewable pull requests

## Public Scope and Safety

- The public v1 workflow is fixed-field 3D-CRT within its documented effective
  aperture boundary.
- Existing DICOM coordinate, geometry, unit, dose, MU, normalization, and
  physics contracts must not be changed by inference.
- Real patient DICOM, official PHITS or RT-PHITS distributions, facility data,
  credentials, personal paths, and real calculation outputs are not tracked.
- Ordinary development and CI use only synthetic inputs and mock runners.
- Real external tools run only for an exact execution explicitly requested by
  a human and outside the repository.

## Development Conventions

- Keep changes small, focused, typed where practical, and compatible with the
  existing package architecture.
- Preserve fail-closed behavior and existing public safety guards.
- Use an inner implementation loop only for safe failures introduced by the
  current diff, within the bounds in `AI_AGENT_RULES.md`.
- Stop for human decisions involving specifications, physics, clinical meaning,
  real data, real tools, destructive actions, or scope expansion.
- Run focused checks before the full compilation, pytest, public-tree, and Git
  diff/status checks required by `AGENTS.md`.

## OpenSpec Workflow

- Current accepted contracts live under `openspec/specs/` after promotion.
- Proposed or unmerged work lives under `openspec/changes/<change-id>/`.
- New capabilities and behavioral or public-contract changes require a proposal,
  task checklist, requirement deltas, validation, and human approval before
  implementation unless the human explicitly waives or defers that sequence.
- Active changes remain under `openspec/changes/` only while implementation,
  required validation, or a required human decision remains.
- Task completion includes promoting accepted deltas into `openspec/specs/` and
  moving the change to
  `openspec/changes/archive/YYYY-MM-DD-<change-id>/` before handoff.
- Incomplete or blocked changes remain active with their unresolved condition
  reported; they are not archived merely for directory cleanup.
- OpenSpec documents are written in English and contain no machine-specific
  absolute paths or protected evidence.

## External Contracts

PHITS, RT-PHITS, Sumtally, phits2dicom, and GPR-comparing remain external. This
repository may validate inputs, prepare workspaces, invoke explicitly approved
adapters, and record execution metadata, but it does not redistribute those
tools or claim clinical validation.
