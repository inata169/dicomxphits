# Design: research-only recorded geometry recovery acceptance

## Context

The geometry-clean success requirement in `phits-segment-runtime` treats any
nonzero lost-particle, geometry-recovering, or unrecovered-error count as a
failed segment, and downstream stages require terminal success. This change
adds one narrow alternative authority. It is modeled on the existing
`sumtally-relative-error-recovery` pattern: explicit staging selection, a
read-only preview with a canonical plan digest, confirmation-bound new-only
apply, and a supplemental receipt that never rewrites original evidence.

## Decisions

1. **Original evidence is immutable.** The execution summary, preflight record,
   manifest, `phits.out`, and staging files keep their exact bytes. The failed
   segment stays `failed` in every record and presentation.
2. **Zero loss with recorded recoveries.** The requested revision keeps
   `lost_particles == 0` and `unrecovered_errors == 0`, and permits any
   positive integer `geometry_recovering` count with no acceptance upper bound,
   ratio cap, or configurable threshold. Multiple region pairs are allowed;
   every pair and its count must be recorded and the pair counts must sum to
   the re-parsed and summary-recorded total. Existing bounded parsing and
   resource safeguards remain required. Zero recoveries follow the ordinary
   success path, and malformed, missing, contradictory, or ambiguous evidence
   remains ineligible. Eligibility remains limited to exactly one failed
   active segment with completed final batches and no other failure reason.
3. **Explicit staging, no discovery.** The user names one staging directory
   directly below `analysis/`. The tool proves that it belongs to the failed
   invocation through recorded execution evidence. When the binding cannot be
   proven, acceptance is unavailable.
4. **Manifest-derived output set.** The published set is exactly the required
   tally outputs that the manifest derives for that segment. Globbing,
   omissions, and extra files are rejected.
5. **Re-parse, do not trust.** `phits.out` is re-parsed with the existing
   bounded geometry-summary parser, and it must agree with the summary and the
   receipt. Completion requires that the final batch equals the prepared
   `maxbch`.
6. **Preview, then confirmed apply.** Apply requires the exact preview digest,
   an explicit research-only acknowledgement, and the workspace execution
   lease. It recomputes the plan before mutation, validates every source before
   the first write, and creates the receipt new-only and last.
   Eligibility never automatically applies acceptance. The preview and receipt
   bind the revised acceptance-policy identity, complete recovering total and
   region-pair distribution, and the explicit operator acknowledgement and
   reason. An `nlost` parameter or process completion alone is not authority.
7. **One gate, every stage.** `validate_segment_execution_for_downstream` is the
   only branch point. Each of Sumtally Generate, Sumtally Run, RTDOSE Prepare,
   and RTDOSE Run revalidates the receipt and recomputes every digest.
8. **Portable identity.** The receipt stores only workspace-relative paths and
   no absolute root, user name, or identifier, so relocation recovery can
   revalidate it.
9. **Retry refuses, never revokes.** Selective retry stops before mutation when
   a receipt exists. Nothing deletes, rewrites, or silently invalidates a
   receipt.
10. **No DICOM change in this proposal.** The research marker is recorded in
    execution summaries only. Any RTDOSE DICOM attribute marking is a separate
    human decision.
11. **Confirmed GUI and CLI acceptance.** The human approved adding GUI
    acceptance on the condition that it does not recalculate PHITS. The GUI
    explicitly selects the retained staging and uses the same read-only
    preview and digest-bound apply backend as the CLI. It displays the selected
    workspace, segment, complete counts and region-pair distribution,
    completion evidence, and research-only notice, and requests a reason
    before asking whether to continue. Only an affirmative confirmation supplies
    the acknowledgement. Cancel, window closure, an empty reason, stale
    evidence, or invalid eligibility cannot create a receipt or unlock actions.
    Verification means reading and re-parsing saved files and checking hashes;
    it does not execute transport. Acceptance publishes only the validated
    existing tally set and receipt, without launching PHITS, Sumtally, or
    phits2dicom. The existing Sumtally and RTDOSE actions are invoked separately
    and each revalidates the receipt; the GUI remains responsive during checks.
12. **Prospective staging evidence.** Approved on 2026-10-27: for future
    geometry-diagnostic failures, the segment adapter preserves staging on
    every supported platform and records a versioned binding in the formal
    execution record. It identifies the workspace-relative staging directory,
    segment, producing execution ID, staged inputs matching the pre-execution
    binding, and retained output SHA-256 values, including `phits.out`.
    This is failure evidence only, not downstream authority. Acceptance
    revalidates that binding; matching file content alone is insufficient.
    Historical records without it remain ineligible and MUST NOT be rewritten
    to retrofit evidence. Failed capture never fabricates a valid binding.

## Prototype gaps addressed

| ID | Prototype behavior | Requirement that resolves it |
|---|---|---|
| G1 | Sumtally skipped preflight when the receipt file merely existed | Receipt-Bound Downstream Authority (existence grants nothing) |
| G2 | Generation-time `require_success=True` validation was removed | Receipt-Bound Downstream Authority (ordinary path unchanged) |
| G3 | Absolute `workspace_root` stored and compared | Versioned Workspace-Relative Receipt; Relocation |
| G4 | Implicit scan of `.phits-segment-run-*` | Explicit Staging Selection and Invocation Binding; Prospective Retained Staging Invocation Evidence |
| G5 | `deposit-*.out` glob publication | Explicit Staging Selection (manifest-derived set) |
| G6 | Only summary counts trusted | Eligibility (re-parsed three-way agreement) |
| G7 | Return code used as completion proof | Eligibility (final batch equals `maxbch`) |
| G8 | Fixed operator-decision string | Preview-Bound Confirmed Apply (explicit acknowledgement) |
| G9 | Receipt written without new-only protection | Preview-Bound Confirmed Apply (new-only, lease) |
| G10 | Undefined retry interaction | phits-segment-retry ADDED requirement |
| G11 | No downstream trace of the exception | Research Exception Propagation and Audit |

## Human decisions outside this proposal

- Whether an external workspace that was processed with the prototype may be
  re-accepted under the new contract. That requires a separate write approval.
- Whether RTDOSE DICOM attributes should carry a research-exception marker.
  That would change DICOM meaning.
- Allowing nonzero lost particles or unrecovered errors, more than one failed
  active segment, or a different count/ratio policy beyond this requested
  proposal revision.

## Risks

- The region-pair table and final-batch grammar are based on the operator's
  supplied example, not an independently verified original nonzero output.
  The tracked fixture uses newly invented synthetic region numbers and counts.
  Unsupported layouts fail closed. The example's instructions to zero counts,
  relabel failure as success, and recompute evidence hashes are expressly
  rejected; they are not part of the implementation.

- Recovering events remain transport anomalies. The revised policy imposes
  no recovering-count cap and makes no dose-accuracy or clinical-safety claim.
  The operator must review the complete counts and distribution and give an
  explicit research-only acknowledgement and reason. Original failure evidence
  stays unchanged, and every downstream summary carries the receipt-bound
  research exception. Human acknowledgement is not evidence of physical
  validity or a substitute for completion, integrity, and zero-loss checks.
- The staging-to-invocation binding may be unprovable for older execution
  records. Acceptance then remains unavailable and explains the missing
  evidence; it never starts a rerun. Any separately requested PHITS rerun or
  external-workspace re-acceptance remains a distinct human decision.

## Consistency qualifications in the revised proposal

The current `phits-segment-runtime` requirement `Durable Segment-Boundary
Progress Evidence` says that only terminal-success records may authorize
Sumtally or PHITS reuse and that failed records must not authorize a downstream
stage. The revised delta qualifies that restriction explicitly so implementers
do not infer which rule takes precedence. The same research exception is
qualified consistently in retry, compatible-summary, and GUI progress clauses.

The revised runtime delta uses this replacement for that requirement's final
normative paragraph, subject to approval of the complete revised proposal:

> Ordinary downstream authority and ordinary PHITS result reuse SHALL require
> a terminal record whose overall status is `success` and whose active segments
> satisfy the accepted successful-segment evidence. All other records MUST NOT
> themselves authorize downstream processing. Only the separate
> `research-geometry-recovery-acceptance` capability MAY authorize research
> Sumtally and RTDOSE use of existing tallies through a fully revalidated receipt.
> That exception MUST NOT authorize PHITS segment execution or change any failed
> execution status.

All other progress, persistence, invocation, timing, provenance, and
ordinary-success checks in the current requirement would remain unchanged.

The same narrow consistency qualification appears in these existing retry and
GUI success-only clauses. It makes the receipt exception explicit wherever it
conflicts with an exclusive success condition:

- In `phits-segment-retry`, `Complete Unique Downstream Evidence After Retry`
  would retain fresh terminal success as the ordinary downstream condition
  and explicitly defer the sole research exception to the shared receipt gate.
  Unique segment membership, execution bindings, and rejection of intermediate
  statistics would remain required. Its partial-result scenario would refer to
  the same exception without making any other partial result eligible.
- In `phits-segment-runtime`, `Compatible Segment Execution Summary Versions`
  would qualify its version-4 retry downstream scenario by referring to the
  same fully revalidated receipt exception. Existing schema, provenance, and
  historical-evidence checks would remain unchanged; this would not make old
  records without the newly required staging binding eligible.
- In `guided-gui-workflow`, `Guided PHITS Segment Progress Presentation` would
  keep terminal success as the only condition for displaying PHITS completion.
  Its failed-run scenario would allow downstream research actions only through
  the fully revalidated receipt while continuing to display PHITS as failed.
- In `guided-gui-workflow`, `Workspace-Bound Retry Progress` would keep its
  current-workspace/invocation checks and ordinary all-active success gate,
  with only the same shared receipt gate allowed as research authority.

This explicitly permits downstream research reuse of the saved tallies; it
must not be read as requiring PHITS transport to run again. It does not turn a
failed segment into an ordinary retained success for selective retry.

An invalid or absent receipt would preserve every ordinary disabled state.
These qualifications are included only in the proposed deltas. Current
specifications and runtime code remain unchanged pending approval and
implementation of the revised proposal.
