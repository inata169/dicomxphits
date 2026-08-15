## ADDED Requirements

### Requirement: Observable Detached Uninstall Completion

English and Japanese offline-installation documentation SHALL state that the
verified parent's `cleanup scheduled` message and return of control to the
calling terminal indicate an intermediate handoff to the detached elevated
finalizer, not completed removal and not failure. The documentation SHALL
instruct the operator to allow that finalizer to reach a terminal outcome and
MUST NOT advise rerunning uninstall or manually deleting targets while cleanup
is still in progress.

The documentation SHALL identify the exact protected `failure.json` message
`Final cleanup staging removal is pending.` as a pending sentinel written after
the installation-owned targets pass their absence check and before the child
removes bounded cleanup staging. Retained staging with that exact sentinel MUST
remain classified as in progress, not failed. Successful completion SHALL mean
that the bounded cleanup staging also disappears. Failed completion SHALL mean
that retained bounded cleanup staging contains a different error message with
the exact remaining installation-owned paths. A missing, unreadable, malformed,
or non-progressing pending report SHALL be classified as indeterminate and
preserved for investigation without rerunning uninstall, manually deleting
targets, or broadening cleanup. Observation of the extracted bundle immediately
after the parent returns MUST NOT by itself be described as uninstall failure.

#### Scenario: Cleanup is still in progress after prompt return

- **WHEN** the verified parent reports that cleanup was scheduled and returns
  control while the extracted installation still exists
- **THEN** documentation identifies that state as detached cleanup in progress
  and instructs the operator to wait rather than retry or delete targets

#### Scenario: Detached cleanup succeeds

- **WHEN** the detached finalizer removes every exact installation-owned target,
  verifies their absence, and its child removes bounded cleanup staging
- **THEN** documentation identifies the uninstall as successfully completed

#### Scenario: Cleanup staging self-removal is pending

- **WHEN** installation-owned targets are absent but retained cleanup staging
  contains the exact `Final cleanup staging removal is pending.` message
- **THEN** documentation identifies cleanup as still in progress and does not
  describe the pending report as terminal failure

#### Scenario: Detached cleanup fails

- **WHEN** the detached cleanup cannot remove one or more exact targets and
  retains bounded cleanup staging after replacing the pending sentinel with a
  different error message
- **THEN** documentation identifies the uninstall as failed and directs the
  operator to the exact remaining-path evidence without broadening cleanup

#### Scenario: Cleanup outcome is indeterminate

- **WHEN** retained cleanup staging has no readable well-formed report or its
  pending sentinel does not progress to disappearance or a different error
- **THEN** documentation identifies neither success nor terminal failure and
  instructs the operator to preserve evidence without retry or manual deletion
