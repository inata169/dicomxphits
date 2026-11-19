# Design

## Establish the observed phase

Use the stdout from the directly launched child. Read the final planned
batch progress record and the supported PHITS OpenMP finalization lines
in order within that stream. Check that the progress agrees with the
bound `phits.out`, and that finalization accounts for the effective
OpenMP worker count from the prepared execution. Worker reports can arrive
in any order. The parser must identify each worker once.

This evidence establishes that PHITS entered finalization after reporting
the last planned batch. The subsequent nonzero child return code reports
failure. The evidence does not identify the routine that failed. The
preview describes the observed sequence and reports the original code.

Timeouts, user stops, controller or launcher failures, and records with
early input, transport, or geometry errors remain ineligible. Treat a
missing, malformed or unrecognized error record as a blocker when it prevents
the system from establishing the observed sequence or ruling out a
contradictory recorded failure. Warnings in the supported format remain
visible in the source logs.

## Bind the record when the invocation ends

The segment adapter already collects stdout, stderr and `phits.out` when
the child exits. Capture a versioned evidence record at that boundary for
the additional recovery route. Bind the launch and exit, execution and
segment identities, prepared batch and thread configuration, retained
staging, and the paths and SHA-256 digests of the terminal logs. Preview
re-reads the bounded records and confirms the order and identity. Preserve
the same check through confirmation, publication, and receipt verification
using the existing research export revalidation.

The presence of a log file, a timestamp, a last-batch counter, or a user
description of a crash is insufficient. Historical runs with other exit
codes need the prospective binding. Existing stack-overflow snapshots
and receipts continue to use their established evidence contract.

## Keep the saved tally and export semantics

Retain the current complete dose and error grid checks, prepared mesh
comparison, tally provenance, batch-variance metadata, and restart seed
comparison. The saved seed must match the start of the reported final
batch. This scope continues to cover the case where final geometry
diagnostics were unavailable. Known geometry errors remain ineligible.

The export uses the saved tally values and existing normalization.
Save the evidence route and observed phase alongside the real exit code
and saved and planned batch counts. Reopening an existing receipt uses
the evidence contract recorded when that export was accepted.
