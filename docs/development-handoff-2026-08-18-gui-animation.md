# Development handoff - 2026-08-18 GUI animation anonymization

This handoff records the bounded documentation-only work that anonymized the
guided GUI workflow animation for display in `README.md`. It does not change
runtime behavior, OpenSpec, public physics, DICOM meaning, dose, MU,
normalization, geometry, or treatment scope.

## Repository baseline

The work was performed against:

- branch `docs/record-2026-08-17-handoff`;
- HEAD `4b4aa6b7845eeedfe7629d7b051e94b1e8080b05`.

The following pre-existing working-tree changes belong to another task and
were preserved:

- modified `docs/development-handoff-2026-08-17.md`;
- modified `docs/project-status.md`;
- untracked `docs/development-handoff-2026-08-18.md`.

No commit, push, pull request, merge, release, or tag operation was performed.

## Completed documentation change

The final public candidate is:

`docs/assets/dicomxphits-gui-workflow.gif`

It contains the five GUI stages in this order:

1. CT2PHITS;
2. Workspace;
3. PHITS;
4. Sumtally;
5. RTDOSE.

`README.md` now embeds the animation immediately below
`## Workflow at a Glance`, before the explanatory paragraph and numbered
workflow. The added text is:

```markdown
![Guided dicomxphits 3D-CRT workflow](docs/assets/dicomxphits-gui-workflow.gif)

The animation shows the guided staged workflow with local paths and identifiers
redacted.
```

The animation addition did not otherwise change README wording. This pull
request separately updates the portable-recovery paragraph to reflect the
already accepted v4 geometry contract from pull request #47.

## Privacy treatment

The unredacted animation exposed local absolute paths, an external workspace
name, dataset-like identifiers, derived handoff paths, executable and template
paths, generated-result paths, and Activity log content. The unredacted GIF
was never staged or committed in this worktree.

All 25 frames were edited deterministically with Pillow. Fully opaque,
single-color rectangles derived from each field's GUI background were applied
to:

- RT Plan, CT DICOM folder, and CT2PHITS case-output values;
- all three CT2PHITS Derived handoff values;
- Workspace, optional machine-configuration, and advanced handoff values;
- the displayed maxcas, maxbch, and OpenMP thread values;
- PHITS root and executable values;
- RTDOSE template, CT reference, converter executable, and final-output values;
- every Activity log body; and
- both contributing stage masks in every cross-fade frame.

Public labels, workflow stage names, buttons, generic status text, colors, and
layout were retained. No generative image model was used. No DICOM, external
workspace, PHITS, Sumtally, phits2dicom, GPR, calculation result, dose value,
or patient material was opened or copied into the repository.

The external source screenshots remain outside the repository and must not be
copied or staged. They are named `GUI-CT2PHITS.png`, `GUI-Workspace.png`,
`GUI-PHITS.png`, `GUI-Sumtally.png`, and `GUI-RTdose.png`.

## Animation metadata

The required animation metadata was preserved:

| Property | Before | After |
| --- | ---: | ---: |
| Dimensions | `800 x 609` | `800 x 609` |
| Frame count | `25` | `25` |
| Total duration | `7280 ms` | `7280 ms` |
| Loop value | `0` | `0` |
| File size | `1,179,205 bytes` | `798,984 bytes` |
| Disposal method | `0` | `2` |

The exact per-frame duration sequence remains:

```text
380, 380, 380, 120, 120,
380, 380, 380, 120, 120,
380, 380, 380, 120, 120,
380, 380, 380, 120, 120,
380, 380, 760, 120, 120
```

Full-frame disposal method `2` is intentional. It prevents content from a
previous animation frame from remaining visible behind a later redaction.

The final SHA-256 is:

```text
4130955722663d562f49b3a0e4292fc7662eaadb9dc9cf6635ef70bbda4ff76e
```

## Verification performed

- Read all 25 unredacted input frames in memory without exporting an
  unredacted frame or contact sheet.
- Reviewed all 25 sanitized frames in a sanitized-only contact sheet.
- Reviewed every normal stage and all ten cross-fade frames.
- Verified every approved mask rectangle is opaque and flat; transition
  overlaps use at most three flat background colors.
- Verified dimensions, frame count, exact duration list, total duration, and
  loop value from the final repository file.
- Verified the README relative link resolves to the final GIF.
- Verified `git diff --check` succeeds.
- Inspected `git diff --stat`, `git status --short`, and the isolated README
  diff.

GIF palette re-encoding caused only small mask-external color quantization
differences. The measured maximum RGB difference was `(5, 7, 6)`, with no
layout or text change outside the approved masks.

An automated OCR engine was not available. The absence of readable local
paths and identifiers was therefore established by complete frame review,
field-level opaque masks, and mask-region pixel checks rather than a separate
OCR pass.

Repository validation then completed with the version-metadata focused test
passing, Python source compilation succeeding, and the public-tree audit
passing with 241 tracked files including the GIF. The full public suite
reproduced the unchanged local environment baseline: 812 passed, 10 skipped,
and the same 45 environment-dependent failures recorded for pull request #47,
with no new failure from this documentation diff. The first sandboxed attempt
could not access pytest's normal temporary root; an in-repository basetemp
altered external-workspace test conditions, so the final recorded run used the
normal temporary root with the required filesystem permission.

## Current working-tree boundary

At animation-preparation handoff time, `README.md` was modified and
`docs/assets/` was untracked. The human subsequently authorized inclusion of
the sanitized GIF in pull request #46 together with the intended documentation
updates. The pre-existing documentation changes listed above remain part of
that same reviewed integration and must not be discarded or overwritten.

A separate local worktree had previously staged an unredacted GUI GIF and the
five GUI screenshot copies. Those GUI artifacts were removed from that
worktree's index and filesystem; unrelated manga work in that worktree was
left untouched.

## Next-agent stopping boundary

The final integration review independently inspected a sanitized-only contact
sheet covering all frames and the normal stage frames at original resolution.
It also confirms the SHA-256 and metadata against this handoff before staging.
Stage only the reviewed sanitized GIF and intended documentation changes.
Never stage the external screenshots, recreate an unredacted repository GIF,
or add an unredacted backup.

Do not modify runtime code, OpenSpec, physics, DICOM semantics, dose, MU,
normalization, geometry, treatment scope, the pre-existing documentation
changes, or publication state as part of this documentation task.
