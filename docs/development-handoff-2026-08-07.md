# Development Handoff - 2026-08-07

This dated handoff records the public-feasibility documentation review,
validation, Codex review loop, and pull request #30 closeout completed on
2026-08-07. It is a restart aid, not a new implementation backlog, clinical
validation record, or authorization for additional runtime work.

## Closing Baseline

- The completed baseline before this handoff branch is clean `main` at
  `a7339c19d9b7e274f8e4827d82a97eb2c077774a`, matching `origin/main`.
- Pull request [#30](https://github.com/inata169/dicomxphits/pull/30),
  **Document the public feasibility demonstration**, was squash-merged as
  `a7339c1`.
- The exact-head Codex re-review of `99f0a643ce` reported no major issues, and
  no review thread remained unresolved before merge.
- The remote and local `docs/public-feasibility-demonstration` branches were
  deleted after their tree was confirmed to match the squash-merged result.
- The public release remains `v1.0.1`. The `v1.0.0` and `v1.0.1` tags were
  not changed, and no v1.0.2 version, tag, release, or release note was created.

## Completed Work on 2026-08-07

### Public feasibility account

The public documentation was reviewed against the repository implementation,
automated tests, current specifications, release evidence, and authorized
read-only comparison records. It now distinguishes a working public
implementation from a proposal that the individual interfaces might be
connectable.

The repository describes the bounded fixed-field 3D-CRT chain from non-patient
phantom DICOM CT and RT Plan inputs through CT2PHITS, PHITS segment calculation,
Sumtally aggregation, DICOM RT Dose conversion, coordinate correction, the
external GPR-comparing handoff, and comparison with a TPS-derived RT Dose. This
is presented as a working end-to-end demonstration and an engineering
constructive proof of feasibility within the documented research boundaries.

The detailed account is in the
[Public Feasibility Demonstration](public-feasibility-demonstration.md).
`README.md` contains the shorter reader-facing summary.

### Demonstrated cases and comparison records

The public account records two human-confirmed non-patient end-to-end cases:

- a centered `20 × 20 cm²` water-phantom case, with two comparison records
  around 95% and slightly below 95% in both records; and
- a PHITSgeoTest case with a Gamma Passing Rate of at least 95%.

A fourth record from a separate non-patient phantom remains supporting
comparison evidence. It is not counted as a third end-to-end demonstration
because completion of the full chain was not separately human-confirmed for
that phantom.

All four locally retained comparison records used global `3% / 3 mm` gamma, a
`10%` dose cutoff, global-maximum normalization, linear interpolation, and an
interpolation fraction of 3. The TPS-derived RT Dose was the reference and the
coordinate-corrected PHITS-derived RTDOSE was the evaluation. Exact individual
passing rates, external paths, identifiers, reports, logs, DICOM, screenshots,
and generated calculation outputs were not published.

The retained reports did not identify the exact GPR-comparing version or
commit used for the four runs. The public documentation therefore does not
infer the exact normalization denominator or cutoff-mask implementation from
the setting labels alone.

### Public research model and provenance wording

The built-in configuration is described as a deliberately simplified public
research model, not an exact treatment-unit model, commissioned Monaco model,
vendor-approved model, or clinical digital twin. The documentation records:

- the author-generated 59-bin spectrum derived from part 1 of the IAEA
  `ELEKTA_PRECISE` 6 MV phase-space dataset;
- the identifiers `ELEKTA_PRECISE_6mv_part1.IAEAphsp` and the matching
  `.IAEAheader`;
- the confirmed access date `2025-08-06`;
- a uniform `3 × 3 mm` rectangular photon source centered in a beam-aligned
  source plane located `100 cm` upstream of isocenter; and
- the rectangular MLC and Y-Diaphragm research geometry.

Simplification is framed as a deliberate tradeoff for an openly inspectable,
explainable, and replaceable research baseline that does not require
vendor-confidential drawings, NDA-protected information, facility-specific
commissioning data, or proprietary Monaco beam-model data. Official PHITS,
RT-PHITS, and IAEA data distributions remain external.

### Codex review loop

The first Codex review examined commit `f3ade21886` and identified one P2
documentation defect: `docs/project-status.md` still described the older
v1.0.1 evidence boundary and could be read as contradicting the newer two-case,
four-record account.

Commit `99f0a643ce` corrected the durable status without rewriting the older
history. It identifies the v1.0.1 paragraph as the evidence boundary at that
time, records the later read-only aggregate review, links the detailed
feasibility document, and repeats the non-clinical interpretation limits. The
review thread was answered and resolved.

Codex then re-reviewed exact head `99f0a643ce` and reported no major issues.
Pull request #30 was squash-merged only after that result and the required local
validation passed.

## Validation

The final pull request head passed:

```text
python -m compileall src
python -m pytest -q -p no:cacheprovider
  591 passed, 2 skipped
python tools/verify_public_tree.py
  Public tree audit passed (138 tracked files checked).
git diff --check
  passed
```

This dated handoff update separately passed:

```text
python -m compileall src
python -m pytest -q -p no:cacheprovider
  591 passed, 2 skipped
openspec validate --all --strict
  5 passed, 0 failed
python tools/verify_public_tree.py
  Public tree audit passed (139 tracked files checked).
git diff --check
  passed
```

Additional documentation checks confirmed valid Markdown links and headings,
English public text, and no newly published exact individual GPR value, private
absolute path, DICOM UID, protected artifact, or external result. The
historical v1.0.0 exact result was not reused for the v1.0.1 cases. No
prohibited clinical, compatibility, vendor-approval, or patent conclusion was
introduced.

The tests use synthetic inputs and mock or fake runners. No PHITS, RT-PHITS,
CT2PHITS, Sumtally, phits2dicom, GPR, real DICOM, or Monte Carlo calculation was
executed as part of this documentation work.

## Interpretation and Reproducibility Boundaries

The reported Gamma Passing Rates are bounded non-patient research observations.
They are not a clinical acceptance threshold, treatment QA decision, clinical
accuracy result, commissioning record, patient-specific QA result, or evidence
of general machine or TPS compatibility. The work does not demonstrate IMRT,
dynamic MLC delivery, or VMAT.

The public repository provides an inspectable engineering workflow and stage
contracts for a qualified researcher to assemble and rerun the process with
separately obtained prerequisites. It does not distribute the original phantom
inputs or numerical result package needed for independent numerical
reproduction, and it does not guarantee identical physics or gamma results.

## Runtime, OpenSpec, and Release Boundaries

This work changed documentation only. It did not change runtime code, tests,
the public physics or machine model, DICOM behavior, coordinates, dose, MU,
normalization, supported treatment-technique scope, or current OpenSpec
requirements.

The four current specifications remain unchanged. The separate
`support-portable-workspace-recovery` change remains active at 1/21 tasks;
task 1.1 still requires explicit human approval before runtime implementation.
It was not implemented, promoted, or archived during this work.

## Restart Procedure

At the next development session:

1. Read `AGENTS.md`, `AI_AGENT_RULES.md`, `docs/project-status.md`, this
   handoff, and `openspec/AGENTS.md` in full.
2. Confirm the repository root, branch, status, recent history, remote, tags,
   and worktree list before editing.
3. Confirm that `main` contains `a7339c19d9b7` or a later descendant and that
   `v1.0.1^{}` still resolves to the published v1.0.1 release commit.
4. Keep external DICOM, licensed tools, local comparison records, exact
   individual results, workstation paths, and generated calculations outside
   the public repository.
5. Keep `support-portable-workspace-recovery` proposal-only unless a human
   separately approves task 1.1.
6. Start any separately approved work on a feature branch and run the required
   focused and full public validation before handoff.

The stopping state recorded here is the clean `a7339c1` main baseline with the
public-feasibility documentation merged, its feature branch deleted, no known
merge-blocking documentation defect, and no authorized next runtime goal.
