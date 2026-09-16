## MODIFIED Requirements

### Requirement: Authoritative combined dose and error evidence

The evaluator SHALL use only the validated all-active-segments Sumtally
combined 3D dose and its paired combined statistical-relative-error grid. It
SHALL bind both grids to terminal Sumtally success, the current workspace,
canonical manifest, mesh geometry, supported combined-`r.err` semantics, and
immutable file and evidence digests. Combined-error parsing and its pairing
with combined dose SHALL be implemented and verified before the evaluator is
available.

The required combined-error evidence SHALL come either directly from the
terminal Sumtally execution summary or from the one exact validated
`sumtally_relative_error_recovery_summary.json` supplemental receipt defined by
the accepted recovery contract. Supplemental evidence is eligible only when
the terminal execution succeeded, direct combined-error evidence is absent,
and the current official dose/error files independently revalidate against the
unchanged execution, generation, manifest, geometry, semantic, and digest
bindings. The evaluator MUST NOT rewrite the terminal summary, scan for
receipts, or let supplemental evidence affect any other stage authority.

The evaluator MUST NOT use live or per-segment values, `deposit-pdd.out`, a
historical workspace result, a retained staging file directly, or an
unverified output as a fallback.

#### Scenario: Valid direct combined evidence is available

- **WHEN** current terminal Sumtally evidence directly proves the combined
  dose and error files, their matching mesh, immutable digests, and supported
  combined statistical-error semantics
- **THEN** those paired grids are the sole numerical source for evaluation

#### Scenario: Valid supplemental combined evidence is available

- **WHEN** terminal Sumtally success lacks direct combined-error evidence but
  the exact fixed recovery receipt and current official dose/error pair prove
  every required unchanged binding
- **THEN** those paired grids are the sole numerical source for Structure
  evaluation without changing terminal or downstream authority

#### Scenario: Combined error meaning or binding is unproved

- **WHEN** direct and supplemental evidence do not establish combined `r.err`
  semantics, dose/error pairing, terminal success, manifest binding, geometry,
  or immutable digests
- **THEN** evaluation is unavailable without falling back to retained staging,
  PDD, live, per-segment, historical, or unverified data
