## ADDED Requirements

### Requirement: Clipped CT placement evidence binding

When the frozen CT2PHITS manifest records a clipped placement reference, the
evaluator SHALL require the public 3D-CRT preparation record to carry the same
selected-slice placement origin as the completed CT2PHITS execution summary.
It SHALL retain the full-series origin for source CT and RTSTRUCT mapping.

#### Scenario: Placement evidence differs

- **WHEN** the clipped frontend placement origin and 3D-CRT preparation
  placement origin differ or either is absent
- **THEN** Structure relative-error evaluation is unavailable without inferring
  a replacement coordinate or tolerance
