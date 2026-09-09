# Change: Add segment progress reporting

## Why

Direct PHITS segment execution can take a long time, while the GUI currently
shows only that the whole stage is running. The operator cannot see which
segment is active, how many active segments have completed, or a bounded
estimate of the remaining time. The execution summary is normally finalized
only after the segment loop, so an interrupted run also loses durable evidence
of earlier segment completions from that invocation.

## What Changes

- Persist fail-closed segment execution progress atomically before execution,
  at each segment transition, and after each segment result is validated.
- Record active-segment totals, the current segment, validated completed
  results, elapsed durations, and explicit overall execution state in a new
  version of the existing segment execution summary.
- Keep readers compatible with successful version-2 summaries while requiring
  version-3 progress records to satisfy their stricter structure.
- Display active-segment progress, current segment, elapsed time, and a clearly
  labelled approximate remaining time and finish time in the GUI.
- Preserve the rule that only a complete successful execution summary can
  authorize Sumtally or existing-workspace PHITS reuse.

This change does not add batch-level progress, statistical-error display,
stopping, resumption, selective rerun, additional histories, convergence
control, or job scheduling. It does not inspect or parse a PHITS output while
the external process is still writing it.

## Impact

- Affected specifications: `phits-segment-runtime`, `guided-gui-workflow`
- Expected implementation areas: `src/dicomxphits/run_segments.py`,
  `src/dicomxphits/gui.py`, and their focused synthetic tests
- Existing successful version-2 execution summaries remain readable.
- Runtime physics, source, MLC and jaw geometry, DICOM semantics, dose, MU,
  normalization, absolute-dose calibration, and PHITS input content remain
  unchanged.
- Automated validation uses synthetic workspaces and fake runners. Any real
  external-tool execution remains separately approval-gated and is not part of
  this proposal.
