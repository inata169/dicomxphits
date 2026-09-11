## MODIFIED Requirements

### Requirement: Exclusive Responsive Stage Execution

The GUI SHALL keep the Tk event loop responsive while an external stage runs
and SHALL prevent another external stage from starting concurrently. It SHALL
continue to use each accepted adapter's existing timeout and failure evidence
rather than adding a bypassing process-cancellation path. The explicit owned
PHITS stop-after-current request SHALL request a verified boundary, not child
termination or another stage launch. The distinct owned Cancel preparation
action MAY cancel preflight only under the `phits-preflight-control` contract
before any PHITS child commitment; it MUST NOT cancel a committed child.

#### Scenario: Stage in progress

- **WHEN** one external stage is running
- **THEN** other stage actions remain disabled until a controlled result, with only the applicable owned preflight or segment-boundary control available

## ADDED Requirements

### Requirement: Distinct Preparation and Verification Presentation

The GUI SHALL display owned preparation/verification phases, elapsed time and
scanned file/byte counts separately from segment and provisional batch progress.
It SHALL distinguish Cancel preparation from Stop after current segment, and
request sent from durable acknowledgement and terminal cancellation/stopping.
It MUST NOT describe an active segment when none is committed, invent ETA or
claim retry eligibility from a preflight receipt. Terminal preflight cancellation
SHALL keep Sumtally disabled and offer only fresh explicitly confirmed preflight.

#### Scenario: User cancels before PHITS starts

- **WHEN** the controller exits 5 with a matching validated cancellation receipt
- **THEN** the GUI shows preparation cancelled with no PHITS launched, not completed or v5 user-stopped

#### Scenario: Verification continues after stop acknowledgement

- **WHEN** no child is running but required result validation remains
- **THEN** the GUI says verification is pending and does not claim a current segment is still calculating
