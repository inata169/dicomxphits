# Extend research RT Dose export to evidenced post-batch PHITS failures

## Why

The research export currently accepts a retained partial tally after one
specific Windows stack-overflow exit. Other nonzero exits may leave the same
usable snapshot when the process reached finalization after the last planned
batch. The last batch number and the exit code alone cannot establish that
sequence.

## What Changes

- Add an eligibility route for further nonzero exits from the supported
  PHITS 3.35 Windows OpenMP executable. Require invocation-bound evidence
  that the last planned batch was reported and the OpenMP workers entered
  finalization afterward.
- Keep the existing single-segment, full-plan and retained-tally checks.
  Accept only a complete matching snapshot saved one batch before the
  planned total. Preserve the original exit code and record the validated
  failure evidence in the preview and export receipt.
- Preserve existing stack-overflow eligibility and verification of previously
  issued receipts. Keep ordinary recovery, downstream authorization, dose
  semantics and the research-only label under their existing contracts.

## Impact

The segment adapter needs to bind terminal log evidence to future failed
invocations. The research preview and receipt verification will consume the
bound evidence. Tests will use authored logs and fake runners. Export will
reuse the existing aggregation and conversion steps without new particle
transport.

See the [design](design.md), [implementation checklist](tasks.md), and
[requirement delta](specs/research-partial-tally-rtdose/spec.md).
