# Tasks

## 1. Approval and calculation-config contract

- [x] 1.1 Obtain human approval for this proposal, including the inclusive
  centre convention, exact decimal divisibility, resource limits, legacy
  default, and minimal GUI scope. Approved by the primary user on 2026-08-24.
- [ ] 1.2 Add a typed calculation-config loader and semantic validator with a
  built-in legacy default and canonical geometry/digest representation.
- [ ] 1.3 Add the public example and closed JSON Schema for
  `dicomxphits_public_calculation_config_v1`.
- [ ] 1.4 Add focused validation tests for valid, malformed, non-integral, and
  resource-unsafe meshes, including oversized files and numeric tokens,
  compact huge exponents rejected before decimal arithmetic, predicted
  rendered-token overflow, downstream binary64 incompatibility, and DICOM
  fixed-decimal serialization that would zero, collapse, or oversize derived
  geometry, without using real data or external tools.

## 2. Workspace preparation and PHITS rendering

- [ ] 2.1 Add the optional calculation-config path to the workspace-preparation
  API and CLI and validate it before workspace creation or modification.
- [ ] 2.2 Derive PHITS centimetre bin edges and integer counts from the
  inclusive millimetre centre contract using exact decimal arithmetic.
- [ ] 2.3 Load one effective mesh per preparation and render it identically into
  every active segment's 3D T-Deposit section.
- [ ] 2.4 Preserve the no-config 3D tally block byte for byte and keep the PDD
  tally block unchanged for both default and custom 3D meshes; generate any
  custom 3D title only from validated derived mesh values.
- [ ] 2.5 Record the configuration source, optional source-file digest,
  canonical semantic digest, centre vectors, voxel sizes, derived counts, and
  derived edges in preparation evidence.

## 3. Downstream consistency and compatibility

- [ ] 3.1 Retain actual-output mesh parsing and complete active-segment geometry
  equality as mandatory Sumtally gates.
- [ ] 3.2 Retain actual accepted PHITS/Sumtally output as the RTDOSE placement
  authority and reject missing, stale, ambiguous, or inconsistent geometry.
- [ ] 3.3 Add synthetic regression tests for workspace-wide identity,
  mismatched actual outputs, asymmetric/anisotropic RTDOSE placement, legacy
  workspaces, and unchanged dose/MU/coordinate contracts.

## 4. Minimal guided GUI and documentation

- [ ] 4.1 Add one optional Calculation config path field and Browse action to
  the Workspace page without a mesh editor, preset selector, or layout
  redesign.
- [ ] 4.2 Validate a nonblank path as an existing regular file, pass it as one
  workspace-preparation CLI token, and omit it from downstream commands and
  first-version persistent GUI settings.
- [ ] 4.3 Add synthetic GUI path and command-construction tests.
- [ ] 4.4 Document the schema, inclusive centre semantics, conversion examples,
  legacy default, limits, PDD boundary, downstream authority, and non-clinical
  scope.

## 5. Validation and OpenSpec completion

- [ ] 5.1 Run focused calculation-config, renderer, workspace, GUI, Sumtally,
  and RTDOSE tests.
- [ ] 5.2 Run the full public compilation, pytest, public-tree, diff, and status
  checks required by `AGENTS.md` without external scientific execution.
- [ ] 5.3 Inspect the final diff for scope, protected-data, runtime/spec, and
  backward-compatibility compliance.
- [ ] 5.4 After all approved acceptance criteria pass, promote the accepted
  deltas, archive this change, and strictly validate the resulting OpenSpec
  tree before completion reporting.
