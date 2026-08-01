# Project Context

## Purpose

`dicomxphits` is education and research software that prepares the documented
fixed-field 3D-CRT workflow from DICOM inputs through explicit PHITS-related
handoff stages. It is not clinical commissioning, patient QA, or vendor
certification software.

## Technology

- Python 3.12 or newer
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
