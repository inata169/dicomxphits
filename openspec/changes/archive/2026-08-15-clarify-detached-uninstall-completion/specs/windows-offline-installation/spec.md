## ADDED Requirements

### Requirement: Observable Detached Uninstall Completion

English and Japanese offline-installation documentation SHALL state that the
verified parent's `cleanup scheduled` message and return of control to the
calling terminal indicate an intermediate handoff to the detached elevated
finalizer, not completed removal and not failure. The documentation SHALL
instruct the operator to allow that finalizer to reach a terminal outcome and
MUST NOT advise rerunning uninstall or manually deleting targets while cleanup
is still in progress.

The documentation SHALL define successful completion as the final elevated
absence check passing for every exact installation-owned target followed by
removal of the bounded cleanup staging. It SHALL define failed completion as
retained bounded cleanup staging containing the reported `failure.json` with
the exact remaining installation-owned paths. Observation of the extracted
bundle immediately after the parent returns MUST NOT by itself be described as
uninstall failure.

#### Scenario: Cleanup is still in progress after prompt return

- **WHEN** the verified parent reports that cleanup was scheduled and returns
  control while the extracted installation still exists
- **THEN** documentation identifies that state as detached cleanup in progress
  and instructs the operator to wait rather than retry or delete targets

#### Scenario: Detached cleanup succeeds

- **WHEN** the detached finalizer removes every exact installation-owned target,
  verifies their absence, and removes its bounded cleanup staging
- **THEN** documentation identifies the uninstall as successfully completed

#### Scenario: Detached cleanup fails

- **WHEN** the detached finalizer cannot remove one or more exact targets and
  retains bounded cleanup staging with the reported `failure.json`
- **THEN** documentation identifies the uninstall as failed and directs the
  operator to the exact remaining-path evidence without broadening cleanup
