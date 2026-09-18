# Tasks

- [x] Reproduce generated-input rejection using project-authored fixtures.
- [x] Implement the bounded input-directive correction without changing generated inputs.
- [x] Run focused observation/generator checks (55 passed, 1 skipped).
- [x] Prepare the proposed batch-variance observation contract and boundaries.
- [x] Validate this proposal with strict OpenSpec checks.
- [x] Obtain human approval for live batch-variance output support.
- [x] Implement isolated live-mode parsing, pairing, and format identity handling.
- [x] Add authored positive batch/history fixtures, mismatched-mode/metadata,
      budget-boundary, invalid-value, stale/reset, and unchanged-artifact tests.
- [x] Confirm shared post-completion parser acceptance remains unchanged.
- [x] Run focused and full public checks; review the final diff.
- [x] Record whether separately authorized real-run observation was performed.
- [x] Promote accepted deltas, archive this completed change, and validate the tree.
- [x] Create a reviewable PR without private paths, records, or calculation data (draft PR #77).

## Validation notes

Human approval for this extension was received on 2026-09-17. Focused checks:
70 passed, 1 skipped. The first focused run had two presentation-unavailable
failures (68 passed, 1 skipped); an unchanged rerun passed. The cause of those
initial failures was not established; no timing or acceptance guard was relaxed.

No real external-tool execution or modified live-GUI verification was performed
for this change. Those checks remain explicitly unverified and require their
own exact execution authorization. All added fixtures are project-authored.

Full public pytest: 1310 passed, 14 skipped (451.93 seconds). Compilation,
public-tree audit, Git whitespace checks, and strict OpenSpec validation passed.

## PR review correction on 2026-09-18

Codex identified fractional live integer metadata accepted after binary-float
rounding. The finding was reproduced against the parsing order. Live istdev,
resc3 and maxcas now use exact decimal integrality checks and retain integer
values for mode, budget and pair comparisons. Shared non-live acceptance is
unchanged. Added fractional-rounding, large-budget and D-exponent regressions.
Focused observation tests: 69 passed. Full public checks and remote review
are recorded on the pull request before merge. This correction restores the
already specified supported-mode/integral-budget contract; no new capability.
