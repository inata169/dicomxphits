# Change: Accept completed PHITS geometry recoveries for research-only downstream use

## Why

A fixed-field 3D-CRT segment can finish every PHITS batch with return code
zero, zero lost particles, and zero unrecovered errors, yet record nonzero
`Number of geometry recovering` events at region boundaries. The current
geometry-clean contract correctly fails that segment, and every downstream stage
stays disabled. The supported ordinary remedy is a full PHITS rerun. A
previously documented manual recipe edited `phits.out`,
`segment_execution_summary.json`, and `segment_preflight.json` with recomputed
digests; this falsifies execution evidence and must be replaced rather than
treated as an accepted recovery method.

A research user needs an explicit, auditable operator decision that records
the complete recovering count and region-pair distribution without imposing a
recovering-count or ratio cap. Zero lost particles, zero unrecovered errors,
completed batches, and unchanged execution evidence remain required. After
explicit research-only acknowledgement, Sumtally and RTDOSE can proceed for
research output. Completion or an `nlost` parameter alone grants no downstream
authority and establishes no dose-accuracy or clinical-safety claim.
An uncommitted prototype on the working branch demonstrated feasibility.
It also has defects that would weaken
the ordinary fail-closed path (see `design.md`, gaps G1-G11), so it is treated
as an unapproved prototype, not as the implementation of this proposal.

## What Changes

- Add capability `research-geometry-recovery-acceptance`:
  - revised eligibility: exactly one failed active segment whose only failure
    reason is geometry diagnostics with `geometry_recovering > 0`,
    `lost_particles == 0`, `unrecovered_errors == 0`, return code zero, and
    completed final batch; all other active segments are ordinary successes;
  - no acceptance cap on the recovering count, number of region pairs, or
    recovering-to-history ratio. Record the total and every region-pair count
    in the receipt, and require exact agreement between the re-parsed total,
    the recorded total, and the sum of the pair counts. No configurable
    threshold is added, and malformed or ambiguous diagnostics remain
    ineligible;
  - an explicitly selected retained staging directory, bound to the failed
    invocation without scanning or inference;
  - a read-only preview that derives one canonical plan digest, and a
    confirmation-bound apply that requires the exact digest and an explicit
    research-only acknowledgement;
  - new-only publication of exactly the manifest-derived tally set. Conflicting
    destinations fail before any write, and no partial publication is left;
  - one versioned receipt with workspace-relative paths at
    `analysis/research_geometry_recovery_acceptance.json`, binding every source,
    staging, published, and diagnostic digest, the revised acceptance-policy
    identity, all recovering counts, and the operator's acknowledgement and
    reason;
  - one centralized downstream gate. It accepts either ordinary terminal
    success or a fully revalidated receipt, and it rechecks at every Sumtally
    and RTDOSE stage. Receipt existence alone grants nothing;
  - propagation of a `research_exception` marker and receipt digest into
    Sumtally and RTDOSE execution summaries;
  - an explicit prohibition on edited PHITS evidence and replacement of the
    documented manual workaround.
- MODIFY `phits-segment-runtime` geometry-clean success: the segment stays
  failed. The new capability is the only path that may publish its retained
  tally, and only for research output.
- ADD to `phits-segment-runtime`: future geometry-diagnostic failures preserve
  staging on every supported platform and record its relative path, producing
  execution ID, segment identity, and input/output SHA-256 bindings in the
  formal execution record. Historical evidence is not retrofitted.
- ADD to `phits-segment-retry`: selective retry refuses a workspace that holds a
  research receipt, before any mutation.
- ADD to `guided-gui-workflow`: a research-exception state presentation, a
  research-only banner, an explicit workspace re-read action, and confirmed
  GUI acceptance through the same preview/apply backend as the CLI. The GUI
  shows the counts and complete region-pair distribution, requests a reason,
  and asks whether to continue for research use. The acceptance action reads
  existing evidence, publishes only the validated existing tally set, and
  creates its receipt; it MUST NOT rerun PHITS or launch any external tool.
  Sumtally and RTDOSE remain separately invoked and independently gated.
- MODIFY the related runtime, retry, and GUI success-only clauses to name
  this receipt as the sole research exception. Ordinary success, ordinary PHITS result reuse,
  current-workspace checks, and invocation bindings remain unchanged.

## Impact

Expected implementation areas: `research_geometry_recovery.py`,
`workspace_recovery.validate_segment_execution_for_downstream`,
`prepare_sumtally.py`, `prepare_rtdose.py`, `run_segments.py`, `segment_retry.py`,
GUI stage presentation, the console script in `pyproject.toml`, user troubleshooting
documentation, and synthetic tests.

Unchanged: fixed 6 MV model, 3D-CRT scope, field-size guard, PHITS physics,
geometry, DICOM coordinates and attributes, MU, normalization, dose factors,
and every ordinary fail-closed requirement when no valid receipt exists. The
ordinary geometry-clean success threshold is unchanged. Only the separate
research-acceptance policy removes the one-recovering-event and one-region-pair
limits; lost and unrecovered counts must still be zero. No configurable or
history-ratio acceptance threshold is introduced. Clinical use,
commissioning, patient QA, and vendor certification are not authorized.

Excluded: any external workspace, real PHITS output, real DICOM, or existing
prototype-generated receipt. Prototype receipts use an unsupported schema and
will not validate. Whether to re-accept such a workspace under the new contract
is a separate human decision that requires its own write approval. No PHITS,
Sumtally, or phits2dicom execution is authorized by this proposal. Automated
validation uses synthetic data and fake runners only.

Status: the complete revised proposal, including uncapped recorded recoveries,
zero lost and unrecovered counts, GUI confirmation without PHITS recalculation,
and the success-only consistency qualifications, was approved on 2026-10-27.
Implementation includes prospective staging evidence, the versioned receipt,
preview/apply and verify-only modes, shared downstream validation and audit
markers, and GUI review without recalculation. The operator supplied an example
table and final-batch format; tests use wholly synthetic values in that format.
Real-tool and real-output compatibility are unverified. See `tasks.md` for
validation and archive status.
