# Guided GUI Workflow Delta

## ADDED Requirements

### Requirement: Guided RTDOSE State and Reprepare Recovery

The GUI SHALL derive the guided RTDOSE state from readable, successful RTDOSE
Prepare and Run summaries. It SHALL present `Not run` when neither summary
proves success, `Prepared` when only Prepare proves success, and `Completed`
when Run proves success. In `Prepared`, it SHALL disable Prepare and enable Run
by default. It SHALL NOT claim success from an unreadable or unsuccessful
summary. When the user explicitly enables the non-persistent downstream-summary
overwrite permission while the state is `Prepared`, the GUI SHALL re-enable
Prepare so invalidated preparation evidence can be regenerated without
weakening the RTDOSE adapter's validation gates.

#### Scenario: Successful preparation

- **WHEN** RTDOSE Prepare has a readable successful summary and RTDOSE Run does
  not
- **THEN** the GUI shows `Prepared`, disables Prepare by default, enables Run,
  and guides the user to Run rather than repeating Prepare

#### Scenario: Successful conversion

- **WHEN** RTDOSE Run has a readable successful summary
- **THEN** the GUI shows `Completed` and disables both RTDOSE actions

#### Scenario: Unreadable or unsuccessful evidence

- **WHEN** an RTDOSE summary is missing, unreadable, malformed, or does not
  report success
- **THEN** that summary does not establish a successful guided state or unlock
  its dependent action

#### Scenario: Explicit reprepare recovery

- **WHEN** RTDOSE is `Prepared` and the user enables downstream-summary
  overwrite permission because upstream evidence must be regenerated
- **THEN** the GUI immediately re-enables Prepare and leaves the RTDOSE adapter
  responsible for accepting or rejecting the new preparation

#### Scenario: Non-persistent recovery permission

- **WHEN** the GUI is restarted after overwrite permission was selected
- **THEN** overwrite permission returns to false and `Prepared` again defaults
  to Run as the next action
