## MODIFIED Requirements

### Requirement: Exclusive Responsive Stage Execution

The GUI SHALL keep the Tk event loop responsive while an external stage runs
and SHALL prevent another external stage from starting concurrently. It SHALL
continue to use each accepted adapter's existing timeout and failure evidence
rather than adding a bypassing process-cancellation path. The explicit owned
PHITS stop-after-current request SHALL be the sole segment-control exception:
it requests a verified boundary, not child termination or another stage launch.

#### Scenario: Stage in progress

- **WHEN** one external stage is running
- **THEN** other stage actions remain disabled until a controlled result, with only the supported stop-after-current control available for its owning PHITS invocation

## ADDED Requirements

### Requirement: Guided Safe Segment Stop Presentation

The GUI SHALL offer Stop after current segment only for its owned active stop-capable PHITS invocation with retry-capable evidence, including selective execution.
It SHALL distinguish request sent from durably acknowledged Stop pending and
from validated terminal User stopped. Stop-pending MUST NOT enable other stage
actions, workspace selection, or Sumtally. Requests and callbacks MUST remain
bound to current workspace and invocation. After verified stopping the GUI
SHALL show retained/completed and remaining counts and the explicit incomplete
segment action. Full-run ETA MUST NOT be presented as a guaranteed stop time.

#### Scenario: User requests stopping

- **WHEN** the user clicks Stop after current segment
- **THEN** the GUI stays responsive and shows request sent until matching acknowledgement, then Stop pending without suggesting PHITS has already stopped

#### Scenario: Verified stop finishes

- **WHEN** the controller exits with matching valid stopped evidence
- **THEN** the GUI displays User stopped rather than completed/failed, keeps downstream disabled, and offers explicit incomplete-segment preview

#### Scenario: Selection changes or control delivery fails

- **WHEN** run/workspace identity no longer matches or the control channel fails
- **THEN** old callbacks or a sent request cannot claim safe stopping or unlock downstream actions

#### Scenario: Stop is unsupported

- **WHEN** a workspace lacks current owned stop-capable and retry-capable evidence
- **THEN** the GUI explains that boundary stopping is unavailable and does not infer eligibility or offer process killing
