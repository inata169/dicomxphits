## ADDED Requirements

### Requirement: Guided Incomplete Segment Execution

The GUI SHALL provide a distinct Run incomplete segments action only for a
retry-capable workspace whose read-only plan validates. Before launch it SHALL
show the selected workspace, retained successes, scheduled segments, and that
incomplete segments restart from the beginning, and require explicit confirmation.
The backend MUST revalidate after confirmation. A rejected plan SHALL explain
why a newly prepared workspace is needed without offering inferred legacy reuse.
The normal protection of fully verified existing cases SHALL remain in effect.

#### Scenario: User confirms a valid partial-run plan

- **WHEN** the previewed workspace and evidence still match at launch
- **THEN** the GUI launches only the selective execution action and keeps the event loop responsive

#### Scenario: Preview becomes stale

- **WHEN** selection or evidence changes between preview and confirmation
- **THEN** no execution starts and the GUI requires a new preview

### Requirement: Workspace-Bound Retry Progress

The GUI SHALL bind preview, execution, polling, and terminal callbacks to the
currently selected resolved workspace and invocation. Relevant workspace
selection controls SHALL be locked during ordinary or selective PHITS execution;
an unexpected programmatic selection change MUST invalidate old presentation
updates. Other stage actions and repeated launch requests MUST remain disabled.
Retry progress SHALL distinguish retained successes from newly completed results.
Elapsed time and estimates SHALL describe the new invocation; retained durations
MUST NOT supply its ETA. Sumtally SHALL remain disabled until fresh all-active
terminal evidence validates.

#### Scenario: Selection changes while an invocation is active

- **WHEN** the selected root no longer matches the invocation workspace
- **THEN** polling and terminal callbacks cannot display the old workspace as current or unlock downstream actions

#### Scenario: Retry begins with retained successes

- **WHEN** retained results exist but no segment has completed in the new invocation
- **THEN** the GUI shows the retained count separately and states that ETA awaits a new completion
