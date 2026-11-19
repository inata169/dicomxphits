## MODIFIED Requirements

### Requirement: Complete Unique Downstream Evidence After Retry

The workflow SHALL authorize ordinary downstream processing after retry only when fresh
terminal success validates exactly one successful result for every active segment.
Retained and new results MUST be revalidated against the same execution binding.
Current incomplete or invalid evidence MUST take precedence over historical
downstream success. The existing Sumtally stages MUST NOT include a segment
twice or incorporate intermediate statistics. Existing downstream
preservation permissions remain separate from selective PHITS execution.

For the existing downstream stages, the only additional research authority
SHALL be a fully revalidated receipt under
`research-geometry-recovery-acceptance`, checked by the shared downstream
gate. It MUST NOT bypass unique segment membership, execution bindings, or
rejection of intermediate statistics. The separate export under
`research-partial-tally-rtdose` MUST NOT supply execution or Sumtally
evidence for these stages.

#### Scenario: Some retained and some newly completed segments

- **WHEN** the union covers every unique active segment and passes fresh full validation
- **THEN** downstream gates may accept one terminal success with each active segment counted once

#### Scenario: Partial or duplicated result set

- **WHEN** any active segment is incomplete or identities are duplicated or inconsistent
- **THEN** old success summaries grant no authority, duplicated or inconsistent identities remain ineligible, and incomplete results keep downstream disabled unless the sole geometry-recovery research exception fully validates through the shared gate

#### Scenario: A separate research export is present

- **WHEN** the workspace has a previously exported research-only partial-tally
  RT Dose and lacks the authority required by the existing downstream gate
- **THEN** the export does not unlock existing Sumtally or RTDOSE stages
