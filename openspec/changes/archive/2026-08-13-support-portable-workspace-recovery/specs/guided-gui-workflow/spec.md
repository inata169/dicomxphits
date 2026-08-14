# Guided GUI Workflow Delta

## ADDED Requirements

### Requirement: Guided Existing-Workspace Recovery

The GUI SHALL provide an explicit existing-workspace selection path that is
distinct from Browse controls that construct a proposed new workspace. It
SHALL inspect portable evidence without external execution, display the highest
current verified stage and the first stage requiring recovery, and provide one
safe next action. It MUST NOT require the user to infer relocation recovery by
repeatedly invoking stages and interpreting existing-output errors.

#### Scenario: Existing relocated workspace selected

- **WHEN** a user explicitly selects a workspace whose recorded root differs
  from its current root
- **THEN** the GUI performs bounded read-only inspection and displays current,
  historical-recoverable, or invalid evidence without running an external tool

#### Scenario: Existing same-computer workspace selected after restart

- **WHEN** the GUI is restarted and the user explicitly selects an existing
  3D-CRT workspace
- **THEN** the GUI reconstructs the current verified stage from workspace
  evidence without requiring CT2PHITS, Workspace Prepare, or PHITS to be
  invoked as probes

#### Scenario: Standard frozen handoff is available

- **WHEN** the selected workspace name ends in `-3dcrt` and the corresponding
  `-ct2phits` directory below the validated standard RT-PHITS work root has a
  completed summary and all three documented handoff artifacts
- **THEN** the GUI restores the frozen RT Plan, CT reference, and DATfiles from
  that one validated bounded candidate without scanning other directories

#### Scenario: Standard frozen handoff is unavailable

- **WHEN** the deterministic CT2PHITS handoff candidate is absent or invalid
- **THEN** the GUI requests one existing CT2PHITS workspace selection and does
  not require three independent path selections or guess a replacement

#### Scenario: Verified PHITS with historical downstream summaries

- **WHEN** PHITS segment evidence is current and verified but copied Sumtally
  or RTDOSE evidence requires regeneration
- **THEN** the GUI identifies Sumtally Generate as the first recovery action
  and does not instruct the user to rerun CT2PHITS, Workspace Prepare, or PHITS

#### Scenario: Recovery requires replacement permission

- **WHEN** historical downstream summaries or outputs conflict with fresh
  recovery evidence
- **THEN** the GUI explains that the conflicting Sumtally and RTDOSE material
  will move into a new workspace-local recovery history, confirms that PHITS
  segment outputs remain unchanged, and requires explicit non-persistent
  permission before enabling the recovery action

#### Scenario: Missing Sumtally generation summary after verified PHITS

- **WHEN** the generation summary is missing but another accepted downstream
  summary records matching manifest and active-segment output digests
- **THEN** the GUI reports that PHITS results remain reusable and offers
  Sumtally Generate as the first recovery action instead of exposing a raw file
  error

#### Scenario: One primary RT Dose action

- **WHEN** verified PHITS evidence permits downstream recovery and the user
  confirms workspace-local preservation of conflicting downstream artifacts
- **THEN** one Create DICOM RT Dose action runs only the required suffix of
  Sumtally Generate, Sumtally Run, RTDOSE Prepare, and RTDOSE Run, stopping on
  the first failed accepted adapter

#### Scenario: Existing case protects expensive upstream stages

- **WHEN** a verified existing workspace is open for downstream recovery
- **THEN** new-case Workspace Prepare and PHITS execution actions are disabled
  and the GUI states that the existing PHITS outputs will remain unchanged

#### Scenario: Recovery completes

- **WHEN** the accepted RTDOSE Run summary and its current corrected artifact
  validate
- **THEN** the GUI displays the `.fixed.dcm` path as the standard DICOM patient-
  coordinate output and provides a direct way to open its folder

#### Scenario: Recovery cannot continue

- **WHEN** a required summary or artifact is missing or invalid
- **THEN** the GUI explains the user-visible problem, whether verified PHITS
  results remain reusable, and the next safe action without using a raw
  exception or internal JSON pathname as the only dialog text

#### Scenario: Relocation evidence is invalid

- **WHEN** a required artifact is missing, changed, external, or ambiguously
  mapped
- **THEN** the GUI keeps dependent actions disabled and identifies the failed
  evidence and required safe resolution without relying only on red text

## MODIFIED Requirements

### Requirement: Guided RTDOSE State and Reprepare Recovery

The GUI SHALL derive the guided RTDOSE state from readable, successful RTDOSE
Prepare and Run summaries whose required current-workspace artifacts and
portable bindings also validate. It SHALL present `Not run` when neither
summary proves success, `Prepared` when only Prepare proves current success,
`Completed` when Run proves current success, and a distinct recovery-needed
state when copied historical success cannot prove the current artifact. In
`Prepared`, it SHALL disable Prepare and enable Run by default. It SHALL NOT
claim success from an unreadable or unsuccessful summary, a missing current
output, an unsafe path binding, or failed current evidence. When the user
explicitly enables the non-persistent downstream-summary overwrite permission
while preparation must be regenerated, the GUI SHALL enable the safe recovery
action while leaving the RTDOSE adapter's validation gates authoritative.

#### Scenario: Successful preparation

- **WHEN** RTDOSE Prepare has a readable successful summary and all required
  preparation artifacts validate in the current workspace, while RTDOSE Run
  does not prove current success
- **THEN** the GUI shows `Prepared`, disables Prepare by default, enables Run,
  and guides the user to Run rather than repeating Prepare

#### Scenario: Successful conversion

- **WHEN** RTDOSE Run has a readable successful summary and its documented
  coordinate-corrected output exists at the accepted current path and passes
  the recorded binding and semantic evidence
- **THEN** the GUI shows `Completed` and disables both RTDOSE actions

#### Scenario: Historical success with missing current output

- **WHEN** a copied RTDOSE Run summary reports success but the accepted current
  coordinate-corrected output is missing or cannot be safely rebound
- **THEN** the GUI does not show `Completed`, displays that recovery is needed,
  and keeps unsafe dependent actions disabled

#### Scenario: Unreadable or unsuccessful evidence

- **WHEN** an RTDOSE summary is missing, unreadable, malformed, does not report
  success, or fails current-workspace evidence validation
- **THEN** that summary does not establish a successful guided state or unlock
  its dependent action

#### Scenario: Explicit reprepare recovery

- **WHEN** RTDOSE preparation is historical or invalidated by regenerated
  upstream evidence and the user enables downstream replacement permission
- **THEN** the GUI enables the applicable preparation recovery and leaves the
  RTDOSE adapter responsible for accepting or rejecting the new evidence

#### Scenario: Non-persistent recovery permission

- **WHEN** the GUI is restarted after replacement permission was selected
- **THEN** replacement permission returns to false and recovery actions again
  require explicit permission
