# Tasks

## Proposal

- [x] Inspect current binding, stop, runtime and GUI contracts and implementation ordering.
- [x] Document bounded design, safety trade-offs and proposed acceptance tests.
- [x] Validate proposal and full public checks; record exact results (including environment-dependent failures in verification-plan.md).
- [x] Obtain human approval of this proposal before runtime implementation.
- [x] Record the completed real boundary-stop result and its installation-scan
  performance rejection.
- [x] Revise the active contract for selected-executable checks and mutable
  `batch.out`; validate it strictly before runtime work.
- [x] Obtain the product decision to display only the primary 3D dose
  Isocenter-voxel `r.err`, excluding PDD, whole-volume and RT Structure
  statistics from this change.
- [x] Obtain fresh human approval of the revised contract before runtime work
  (2026-09-14; safe implementation and synthetic verification authorized).

## Implementation

- [x] Add strict owned preflight receipt and compatibility/downstream precedence rules.
- [x] Add incremental scanner progress/checkpoints without narrowing membership or hashes.
- [x] Serialize prelaunch cancellation against first commitment; preserve existing attempts.
- [x] Service segment-stop acknowledgement during verification without bypassing result gates.
- [x] Align completed-result evidence with the existing segment-success contract after the real PHITS secondary-tally finding.
- [x] Add GUI phase/count presentation, distinct controls and explicit recovery guidance.
- [x] Pass all synthetic acceptance scenarios in verification-plan.md (including opt-in Tk; 2026-09-10 final synthetic run).
- [x] Obtain exact approval and pass real GUI preparation-progress/cancellation acceptance (2026-09-11; no PHITS launch, controller exit 5, complete OS evidence).
- [x] Obtain separate exact approval and pass real committed-segment
  boundary-stop verification (2026-09-11; one segment completed, later segments
  remained pending, downstream disabled and ownership released).
- [x] Run focused checks, compile, full pytest, public-tree audit and strict
  OpenSpec validation at the 2026-09-11 checkpoint (1200 passed, 11 skipped;
  rerun after the revised implementation).
- [x] Remove recursive installation membership/hash capture and add bounded
  selected-executable launch-time validation with explicit evidence scope and
  historical-reader compatibility.
- [x] Exclude mutable PHITS `batch.out` content from required immutable result
  evidence while preserving observation, retention and path safety.
- [x] Update synthetic/fake-runner regression coverage for installation-scan
  removal, executable mutation and mutable `batch.out` without weakening
  completion, stop, ownership or downstream gates.
- [x] Replace full-mesh relative-error statistics with the unique Isocenter-
  containing voxel reference value and add boundary/outside/no-fallback coverage.
- [x] Rerun focused checks and the required full validation after implementation
  (2026-09-14; 1202 passed, 11 skipped; Tk enabled).
- [x] On accepted completion, promote the revised live-observation purpose and
  deltas before archiving the active change.
- [x] Review diff/status and confirm that all synthetic and prior real functional
  acceptance conditions are satisfied before promotion/archive.

All approval, implementation and required verification conditions are now met;
promotion/archive is the remaining in-scope cleanup. Release remains a
separately gated workflow, without a custom ZIP.

## Historical diagnostic log (superseded by the completed 2026-09-14 work)

Historical checkpoint blocker: the real committed-segment boundary-stop behavior passed, but
the controller's repeated installation-wide membership and SHA-256 scans made
performance acceptance fail. The revised bounded executable/`batch.out`
contract was awaiting human approval before runtime implementation. No new real
PHITS invocation is authorized or currently required. Real GUI preparation
cancellation also passed earlier; both one-invocation approvals are consumed.
The diagnostic history below is retained as historical evidence and does not
override this current blocker.
An earlier separately approved real-GUI Run reached preparation but failed on
preflight receipt replacement with WinError 5 and natural controller exit 2.
No cancellation request or PHITS launch occurred. Complete OS evidence and raw
failure receipts were preserved; this one-invocation approval is consumed. Do
not reuse the now-failed workspace or repeat Run. Separately approved fresh
synthetic diagnosis reproduced WinError 5 with the actual reader held open, but
the native shared-delete expected-success comparison also failed. Three of four
case expectations passed; the diagnostic stopped without retry or code fixes.
Subsequently approved primitive/guard isolation completed nine fresh observations:
bare replacement and both guarded paths all succeed without a reader and all
deny with WinError 5 under either held-reader sharing mode. The guard is not
necessary for the failure; removing it is not a supported fix. The old failed
comparison remains failed. Real-attempt attribution and a production fix remain
unresolved at that diagnostic snapshot. The human subsequently approved bounded
Windows preflight-publication retries (three attempts, two requested 50 ms waits).
The minimal guarded-writer fix and nine regression cases are now implemented;
persistent failures and downstream gates remain fail-closed. Real acceptance and
a new exact invocation plan/approval are still required; do not reuse old attempts.
The previous hung synthetic processes were cleaned up under explicit approval.
A fresh private input-pipe correction now passes all four actual ControllerPipe
and CLI-main synthetic cases, with natural OS exits and no remaining job members.
Subsequent visible-GUI synthetic integration passed actual Run and Cancel button
actions through run_stage and ControllerPipe, with controller exit 5 and complete
OS lifecycle evidence. Tool-profile/validation fixtures, a synthetic command
bootstrap and deliberately yielding preparation were used; the unmodified venv
entrypoint was not qualified by that visible-GUI fixture. Subsequent fresh private
help checks now qualify the ordinary module, installed console, plain GUI
bootstrap and actual ControllerPipe-to-console startup paths, with unchanged
application functions and complete natural OS lifetimes. These are help-only
checks, not real tool configuration or PHITS launch/cancellation acceptance.
Do not archive or release on these partial qualifications.

A separately approved fresh private lifetime adapter now retains observation
beyond the former 30-second help limit. Its delayed synthetic ControllerPipe
case captured the console child created after that limit and all six natural
OS exits; strict evidence checks remain unchanged. This is not real GUI or
preparation-cancellation acceptance. Final real invocation freezing and exact
execution approval remain outstanding.

On 2026-09-11 the human approved a fresh private explicit-wait recorder
candidate. Removing profiling reproduced the identical help-entrypoint failure;
the no-improvement stopping condition was reached again. Existing dummy-chain
and fault checks passed unchanged, but do not qualify the candidate for real
acceptance. Further startup diagnosis requires a new human decision.

The human subsequently approved component isolation and exception diagnosis.
The diagnostic matrix isolated the failure to registering an audit hook before
the main-file attribute exists; it also reproduced without project code or site
initialization. Stream setup and explicit wait wrapping passed both help gates.
The visible failure is at runpy module execution; the lower-level environment
cause remains unproven. A fresh recorder using explicit Popen construction/wait
recording without an audit hook is proposed, not yet implemented or approved.

The human subsequently approved that direct Popen recorder and synthetic checks.
The fresh private candidate passed both help entrypoints with identical baseline
output, all existing chain/fault assertions, and construction/timeout/failure
checks on its first attempt. The recorder startup blocker is resolved for
synthetic use. Independent OS no-child evidence and an exact newly approved real
invocation remain outstanding; the frozen private plan was not changed and real
preparation cancellation/boundary-stop acceptance is still incomplete.

The human approved independent Windows event testing. Ordinary-token subscription
was denied; elevated synthetic probes progressed from a missing parent-filtered
stop event to matching exact-PID start/stop events with a parent-field mismatch.
A broader all-cmd stop query was rejected by automatic approval review and never
executed. The exact-PID alternative preserved scope and raw evidence, but failed
the current check. No acceptance claim, further correction or rerun followed the
validation-reference mismatch. See verification-plan.md for the next proposal.

The human approved start-parent identity plus same-PID/time/exit correlation.
Three new held synthetic children (exits 0/5/7) passed independent OS correlation,
and all 75 invalid-evidence mutations were rejected. Raw stop-parent PID 0 was
preserved. This bounded adjustment is complete; no correction/rerun was needed.
The remaining coverage limits in the current blocker above still apply.

The human approved prearmed, scoped process-family investigation. A fresh Job
Object probe stopped on its first synthetic case: OS accounting and notifications
identified two completed processes, but the fixture expected one and produced
one self-record. The additional process role is unknown. No reference adjustment,
remaining case, negative mutation or rerun followed this stopping condition.
Investigating that discrepancy requires a human decision; this is not real
no-child or launcher-chain acceptance.

The human approved a fresh scoped identity diagnosis. A held synthetic root and
its additional job member were identified as Python and the Windows console
host respectively, with OS parent identity linking the console host to that
root. Both returned zero naturally; final accounting was two total, zero active,
zero limit terminations. This completes identity diagnosis only. The old unnamed
record cannot be retrospectively identified, and no prior failed reference was
changed or rerun. Normal-speed chain coverage and real acceptance remain open.

The human approved documenting proposed process-evidence criteria only. The
draft in verification-plan.md separates logical roles from individually proven
console support, reconciles all lifetimes with OS accounting and rejects missing
or conflicting evidence. It is awaiting reference approval; no private validator
implementation, reference replacement or probe execution is authorized by this
documentation task. Real acceptance and archive remain outstanding.

The human subsequently approved implementation and fresh synthetic checks under
those criteria. The private normalized-record validator passed three fabricated
positive cases and 114 negative mutations. The unheld acquisition probe retained
six complete OS handle lifecycles but its post-exit parent query returned none.
Coverage is explicitly incomplete and the verdict is unverified. Full acquisition
and end-to-end qualification are not implemented; no further launch followed
this stop. See verification-plan.md for the remaining parent-evidence gap.

After read-only investigation, the human approved a held before/after parent
comparison through retained handles. Native OS parent IDs for Python and its
console host matched live CIM and remained identical after natural exit 0.
The first diagnostic passed with the existing limited-query rights. This offers
an environment-specific candidate for the missing evidence, but unheld adapter
integration and end-to-end/real acceptance remain unverified. No old probe was
changed or rerun; no wider API compatibility claim is made.

The human approved integrating retained native parent queries into a new private
normal-speed synthetic observer. The initial case failed during post-exit metadata
retrieval (WinError 31) and stopped the batch. One bounded correction in another
fresh directory restored image lookup to handle acquisition; native parent/exit
queries remained post-exit. All four fixed cases then passed, with the unchanged
validator/checker, 17 adapter negatives and 40 captured-evidence mutations. No
further correction is needed for this bounded synthetic task. Actual application
controller integration and real acceptance remain outside this qualification.

The human approved actual ControllerPipe/controller integration with fake runners.
A fresh private adapter called the existing CLI main with an injected synthetic
runner and authored workspace. Its unchanged validator and adapter negatives
passed, but the first acquisition timed out and could not confirm root exit.
Scoped readback found the launcher, controller, fake leaf and two console hosts
still alive. The exact waiting cause is unproven; the remaining three cases were
not launched. No real execution, force-stop, failed-workspace reuse or acceptance
claim followed. See verification-plan.md for this blocked attempt.
