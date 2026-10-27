## ADDED Requirements

### Requirement: Retry Refuses Research-Accepted Workspaces

Selective and ordinary PHITS execution SHALL refuse a workspace that holds a
file at the research geometry-recovery receipt path, and SHALL do so before any
staging creation, process launch, or evidence mutation. The refusal SHALL
explain that the user must move the receipt aside before PHITS runs again. The
workflow MUST NOT delete, rewrite, or implicitly invalidate the receipt.

#### Scenario: Retry requested after research acceptance

- **WHEN** a receipt exists and incomplete-segment execution is requested
- **THEN** no process starts, no artifact changes, and the receipt is preserved

#### Scenario: Retry after the receipt is moved aside

- **WHEN** the user has moved the receipt out of the fixed receipt path
- **THEN** existing retry rules apply unchanged

## MODIFIED Requirements

### Requirement: Complete Unique Downstream Evidence After Retry

The workflow SHALL authorize ordinary downstream processing after retry only when fresh
terminal success validates exactly one successful result for every active segment.
Retained and new results MUST be revalidated against the same execution binding.
Current incomplete or invalid evidence MUST take precedence over historical
downstream success. Sumtally MUST NOT include a segment twice or incorporate
intermediate statistics. Existing downstream preservation permissions remain
separate from selective PHITS execution.

The only additional research authority SHALL be a fully revalidated receipt
under `research-geometry-recovery-acceptance`, checked by the shared downstream
gate. It MUST NOT bypass unique segment membership, execution bindings, or
rejection of intermediate statistics.

#### Scenario: Some retained and some newly completed segments

- **WHEN** the union covers every unique active segment and passes fresh full validation
- **THEN** downstream gates may accept one terminal success with each active segment counted once

#### Scenario: Partial or duplicated result set

- **WHEN** any active segment is incomplete or identities are duplicated or inconsistent
- **THEN** old success summaries grant no authority, duplicated or inconsistent identities remain ineligible, and incomplete results keep downstream disabled unless the sole geometry-recovery research exception fully validates through the shared gate
