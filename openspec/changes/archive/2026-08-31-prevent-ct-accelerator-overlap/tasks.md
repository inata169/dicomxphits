# Tasks

## 1. Proposal and approval

- [x] 1.1 Obtain authorization to create the
  `prevent-ct-accelerator-overlap` OpenSpec proposal and stop at
  implementation review. Authorized by the primary user on 2026-08-31.
- [x] 1.2 Obtain human approval of this proposal's CSG ownership rule,
  geometry-clean runtime gate, v5 invalidation, and calibration-factor
  reacceptance conditions before changing runtime behavior. Approved by the
  primary user on 2026-08-31; external-tool execution and numerical-factor
  reacceptance remained separate decisions.

## 2. CT and accelerator geometry composition

- [x] 2.1 Implement accelerator-envelope exclusion from the CT wrapper using
  verified PHITS transformed-cell semantics.
- [x] 2.2 Preserve CT lattice, coordinates, materials, outside air, source cone,
  SAD/SSD, accelerator, jaw/MLC, transport, tally, and dose/MU settings outside
  the stated topology correction.
- [x] 2.3 Add synthetic renderer and transformed-cell tests for supported
  gantry/collimator angles and the invariant that accelerator cell `2` is the
  excluded region. Real region sampling remains part of separately authorized
  PHITS validation.

## 3. PHITS geometry-diagnostic gate

- [x] 3.1 Add a bounded parser for the supported `phits.out` geometry summary
  and record its normalized counts in segment execution evidence.
- [x] 3.2 Require an unambiguous zero-error summary for success and reject
  nonzero, missing, malformed, duplicate, or contradictory summaries before
  publishing segment outputs.
- [x] 3.3 Add fake-runner tests proving a zero return code and tally file cannot
  bypass the geometry gate.

## 4. Provenance and recovery

- [x] 4.1 Advance newly prepared combined geometry provenance from v4 to v5 in
  every workspace and segment evidence location.
- [x] 4.2 Reject reuse of v4 or older, missing, mixed, or ambiguous PHITS
  transport without gantry, collimator, field-size, FOV, or non-overlap
  exceptions.
- [x] 4.3 Require new v5 preparation followed by PHITS, Sumtally, and RTDOSE and
  add synthetic recovery regression tests.

## 5. Absolute-dose calibration binding

- [x] 5.1 Extend the approved public-dose-factor identity to bind the transport
  topology contract and fail closed when a v5 workspace requests the currently
  v4-bound factor.
- [x] 5.2 Produce repository-safe evidence that the reference calibration
  geometry is non-overlapping and old/new transport regions are semantically
  equivalent, without presuming numerical factor acceptance. The reviewed
  reference bounds are disjoint and the synthetic CSG regression proves set
  equivalence when no intersection exists; no protected data is committed.
- [x] 5.3 Obtain separate human approval for any real PHITS comparison and for
  reaccepting the existing numerical factor under v5; otherwise leave absolute
  dose fail-closed pending newly accepted evidence. The primary user explicitly
  reaccepted the unchanged `8.7608E+11 source/MU` factor for v5 on 2026-08-31.
  No external PHITS comparison was authorized, performed, or used as evidence.
- [x] 5.4 Add synthetic tests for stale factor rejection and topology-bound
  accepted-factor evidence. The accepted numerical value remains unchanged and
  its v5 topology reacceptance is recorded separately from its derivation.

## 6. Documentation and validation

- [x] 6.1 Document the topology rule, diagnostic gate, v5 migration, expected
  correction of overlapping cases, and evidence-based calibration reuse.
- [x] 6.2 Run focused geometry, runtime, recovery, calibration, and workspace
  tests using synthetic data and fake or mock runners. The final focused run
  passed with 194 tests and one skip.
- [x] 6.3 Run all public checks required by `AGENTS.md` and inspect the final
  diff for scope, protected-data, runtime/spec, and backward-compatibility
  compliance. The repository `.venv` full suite passed with 916 tests and ten
  skips; compilation, public-tree audit, diff check, and active-change strict
  validation also passed. A system-Python run using unpinned pydicom 2.4.4 was
  diagnostic only and was superseded by the pinned pydicom 3.0.2 environment.
- [x] 6.4 After all approved acceptance criteria and required checks pass,
  promote the accepted deltas, archive the change, and strictly validate the
  resulting OpenSpec tree. The accepted deltas were promoted and the change
  was archived on 2026-08-31; final strict validation passed.
