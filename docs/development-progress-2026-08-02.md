# Development Progress - 2026-08-02

This dated record summarizes the human-directed work completed or demonstrated
on 2026-08-02. It distinguishes merged repository baselines, an active pull
request, and local non-patient workflow evidence. It is not a clinical
validation record, release note, or automatically approved backlog.

## Repository milestones merged today

The following public-repository milestones were merged into `main`:

- pull request [#3](https://github.com/inata169/dicomxphits/pull/3) added the
  automated Windows CT2PHITS frontend and its frozen handoff;
- pull request [#4](https://github.com/inata169/dicomxphits/pull/4) added the
  durable CT2PHITS handoff documentation;
- pull request [#5](https://github.com/inata169/dicomxphits/pull/5) integrated
  CT2PHITS into the guided GUI;
- pull request [#6](https://github.com/inata169/dicomxphits/pull/6) updated the
  durable project status after the GUI merge; and
- pull request [#7](https://github.com/inata169/dicomxphits/pull/7) recorded
  strict validation with the locally installed OpenSpec CLI.

The guided GUI now presents CT2PHITS, workspace preparation, PHITS segment
execution, Sumtally, and RTDOSE as separate auditable stages. It suggests case
paths from the selected RT Plan, retains stable local tool settings and
per-field Browse history, keeps the non-patient confirmation explicit, and
applies only a verified CT2PHITS handoff to downstream preparation.

## Non-patient Windows workflow demonstrated today

The human explicitly ran the workflow with designated non-patient phantom data
and licensed external tools outside the repository. The observed stage results
were:

1. CT2PHITS completed and produced the frozen downstream handoff.
2. Public 3D-CRT workspace preparation completed.
3. PHITS segment execution completed successfully.
4. Sumtally Generate and Sumtally Run completed successfully after correcting
   their stage ordering and input-path handling.
5. RTDOSE Prepare and RTDOSE Run completed successfully.
6. The coordinate-corrected DICOM RT Dose output was located through the path
   recorded in the RTDOSE execution summary.

This is valuable Windows integration evidence for the designated research
phantom. It does not establish clinical suitability, commissioning, patient
QA, vendor certification, or general dose accuracy. No external installation,
private absolute path, DICOM identifier, calculation output, or local log is
recorded in this repository.

## Usability and workflow corrections

Hands-on operation exposed several issues that were corrected or incorporated
into the active work:

- CT2PHITS launch and long-running state are presented through the GUI instead
  of requiring the user to infer progress from an external directory.
- Tool settings and Browse starting locations persist independently, while the
  safety confirmation remains intentionally non-persistent.
- The GUI makes the required non-patient confirmation more visible and reports
  missing commands or files with stage-specific context.
- Sumtally is treated as two ordered stages: Generate must succeed before Run.
- Failed or stale Sumtally summaries no longer provide ambiguous evidence for
  a later successful run.
- Workspace-relative PHITS include files are resolved against the execution
  workspace before Sumtally runs.
- The RTDOSE CT reference is distinguished from the RTDOSE template and is
  derived from the verified CT2PHITS handoff when available.
- The accepted RTDOSE result is identified by the
  `coordinate_corrected_rtdose_output` field instead of leaving the user to
  search the workspace.

## Active RTDOSE provenance correction

Pull request [#8](https://github.com/inata169/dicomxphits/pull/8) remains open
at the time of this record. Its current branch implements the following
fail-closed corrections:

- the final dose uses `DoseSummationType = PLAN` and one exact reference to the
  validated frozen RT Plan;
- RTDOSE preparation proves full-plan workflow mode, treatment-beam coverage,
  Frame of Reference, and MU consistency;
- referenced non-treatment beams such as `SETUP` are accepted only as skipped,
  zero-segment-MU evidence and do not become active treatment coverage; their
  referenced meterset may be zero but not negative or non-finite;
- Sumtally Generate, Sumtally Run, and RTDOSE preparation are bound to one
  canonical segment-manifest digest;
- the generated Sumtally wrapper, `sumtally.inp`, and produced dose output are
  bound to the recorded execution evidence;
- the frozen RT Plan is bound by the full-file SHA-256 from the completed
  CT2PHITS workspace manifest, with reconstructed segment geometry as the
  legacy fallback;
- the generated `phits2dicom.inp` is hashed at RTDOSE Prepare and revalidated
  immediately before converter launch, together with every file it references;
  and
- the coordinate-corrected DICOM is reopened and its PLAN reference, Frame of
  Reference, absolute dose units, and stored-value preservation are validated
  before success is reported.

These guards change provenance validation and failure behavior only. They do
not change PHITS physics, calculated dose values, MU values, normalization,
machine models, DICOM coordinates, or the documented fixed-field 3D-CRT scope.

## OpenSpec state

OpenSpec CLI `1.6.0` was installed locally and used for strict validation. The
accepted CT2PHITS frontend, guided GUI, and RTDOSE semantic contracts are
present under `openspec/specs/`. Their completed change records are under
`openspec/changes/archive/`; there are no active implementation change
directories at the time of this record.

The latest strict validation reported:

```text
3 passed, 0 failed
```

## Validation evidence for the active branch

After the two final review findings were corrected, the latest development
checks for the active RTDOSE branch were:

```text
Focused RTDOSE/manual-smoke/manifest tests: 54 passed
Full synthetic/mock public suite: 497 passed
Python compileall: passed
Public-tree audit: 97 tracked files passed
OpenSpec strict validation: 3 passed, 0 failed
Git diff check: passed
```

One preceding full-suite attempt passed 496 tests and reproduced the unchanged,
intermittent Windows child-process timeout failure recorded earlier in this
branch. The exact test then passed in isolation, and the clean full-suite retry
passed all 497 tests. The approved RTDOSE work did not alter that unrelated
process-management code, and no guard or test was weakened.

All automated tests used synthetic DICOM and fake or mock external-tool
runners. They did not rerun the real licensed tools or the human's external
workflow data.

## Status at handoff

- The merged baseline through pull request #7 is on `main`.
- Pull request #8 contains the active RTDOSE provenance and Sumtally handoff
  corrections and still requires a clean final review on its latest commit;
  merge is authorized only if that exact review reports no new findings.
- OpenSpec promotion and archive cleanup for the approved RTDOSE contract are
  complete on the pull-request branch.
- No release or tag was created; the public tag remains `v1.0.0`.
- The workplace Dev Container cross-check and optional external GPR comparison
  remain unverified.
- No additional implementation goal is authorized by this progress record.
