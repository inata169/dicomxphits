# Development handoff — 2026-08-13

This handoff records the repository work and the human-operated Windows GUI
evidence from 2026-08-13. It deliberately separates completed implementation
from two unresolved dose/geometry investigations. The external data, local
paths, DICOM objects, PHITS outputs, screenshots, and comparison artifacts are
not part of this repository.

`dicomxphits` remains education and research software for the documented
fixed-field 3D-CRT workflow. Nothing recorded here establishes clinical dose
accuracy, commissioning, patient QA, or vendor compatibility.

## Stop state

- Branch: `fix-rtdose-gui-error`
- Implementation HEAD immediately before this handoff commit:
  `0e9317bf46f33f134bf4864868fe22ab792406e6`
- The remote branch matched that implementation HEAD before this handoff was
  committed
- Base: `origin/main` at `ac043ca`
- Draft pull request:
  [#37 — Recover RT Dose and correct DICOM voxel mapping](https://github.com/inata169/dicomxphits/pull/37)
- Current GitHub Actions evidence: run #315 passed on both Ubuntu and Windows
- Tags remain unchanged: `v1.0.1` and `v1.0.0`
- The only pre-existing working-tree item before this handoff was the untracked,
  unapproved `openspec/changes/add-rtdose-coordinate-output-choice/` proposal.
  Preserve it without implementation, promotion, archive, or accidental
  staging.

Pull request #37 must remain draft and must not be merged yet. Its CI is green,
but the human-operated comparison found unresolved absolute-dose scaling and
oblique-beam distribution problems after regenerating the output with the
current code.

## Work completed on the current RT Dose branch

### Existing-workspace RT Dose recovery

Commit `b03a7b124c6961ca4a981de78f3ec1af1bc9830c` implements the approved,
fail-closed recovery path for an existing workspace:

- an explicit **Open existing case** action inspects the selected workspace;
- reusable PHITS and Sumtally evidence is verified instead of inferred from
  file existence;
- the primary recovery action runs only the required downstream suffix and
  does not rerun verified PHITS segment execution;
- conflicting downstream artifacts are preserved in bounded recovery history;
- the GUI reports the accepted final DICOM patient-coordinate RT Dose; and
- a missing `BeamMeterset` is treated as effective zero only for a
  manifest-proven skipped non-treatment, zero-MU beam. Missing or invalid
  treatment-beam meterset evidence still fails closed.

The accepted OpenSpec changes were promoted and archived as:

- `2026-08-13-support-portable-workspace-recovery`; and
- `2026-08-13-accept-missing-nontreatment-meterset`.

The human operator successfully used this recovery path to create a DICOM RT
Dose without repeating the completed PHITS calculation. This is bounded manual
evidence only; the agent did not execute or inspect the external tools or
protected artifacts.

### Final RT Dose voxel mapping

Commit `f8227c09a8826e5ec29c0d54d338a4bf6353778f` corrects the final RTDOSE
PixelData transform to the already documented PHITS-to-DICOM mapping. The
accepted array transform is now:

```python
source.transpose(1, 0, 2)[:, :, ::-1]
```

The coordinate-correction evidence schema and axis-mapping identifier were
advanced to version 2. Recovery rejects or rebuilds a stale version-1 corrected
output, and asymmetric synthetic data now protect the left-right reversal.
This commit changes voxel placement only; it does not change dose values,
normalization, MU, or external-tool factors.

### Windows recovery cleanup

GitHub Actions run #313 passed on Ubuntu but exposed a Windows-only cleanup
failure: the guarded cleanup correctly refused to recursively delete a held
directory. Commit `0e9317bf46f33f134bf4864868fe22ab792406e6`
removes only manifest-recorded, validated original files and permits the
directory itself to remain empty. It does not weaken path containment or touch
the verified PHITS outputs. Run #315 then passed on both Ubuntu and Windows.

## Separate safety/UI branches from the same day

These commits are not ancestors of `fix-rtdose-gui-error` and are not included
in pull request #37:

- `feat/safety-ui-energy-guard` at
  `af87da3cd199eb2246a6d3a711eebfc59f68e1b7` centralizes the fixed Elekta
  Precise 6 MV public research model identity, validates included treatment
  beams as photon 6 MV before PHITS input generation, records additive model
  evidence, and adds the model, nominal energy, project web address, and author
  to the shared GUI header. Its approved OpenSpec change was promoted and
  archived as `2026-08-13-strengthen-6mv-safety-and-gui-clarity`.
- `fix/safety-ui-minimum-window-scroll` at
  `85a8d780425408dd1900d3e9d9837fc831242d7c` builds on the preceding branch
  and keeps stage content and primary actions reachable with vertical
  scrolling at the minimum supported window size.

Do not assume that screenshots showing these header and scrolling changes prove
that PR #37 contains them. They were initially displayed from a different
editable checkout because the Windows virtual environment resolved
`dicomxphits` from that checkout.

## Windows GUI environment finding

The Windows virtual environment continued importing an editable installation
from another checkout even after a package reinstall. The human verified the
actual import location and temporarily launched the intended current checkout
by placing its `src` directory first on `PYTHONPATH` for that PowerShell
session, then running the GUI as a module.

This was an environment-resolution workaround, not a committed launcher fix.
Before every further GUI test, print `dicomxphits.gui.__file__` and confirm that
it belongs to the intended checkout. A future launcher-hardening change must be
separately approved and must not be inferred from this handoff.

## Human-operated RT Dose comparison evidence

After the import path was corrected, the human regenerated the final `.fixed`
DICOM RT Dose with current HEAD. The GUI reported successful DICOM
patient-coordinate output. An external 3D viewer/comparison against a TPS RT
Dose then showed all of the following:

- the earlier gross left-right placement error was reduced, but the dose
  distribution still did not match;
- the evaluated absolute dose remained much smaller than the reference;
- the high-dose gradient of the evaluated distribution had a different
  patient-coordinate direction from the reference; and
- the comparison warned that the two `FrameOfReferenceUID` values differed and
  therefore used explicitly allowed absolute DICOM patient coordinates.

The comparison result must therefore be treated as a failed engineering check,
not as validation of the corrected RT Dose. Exact workstation paths, UIDs,
individual comparison values, screenshots, and output files remain outside
Git.

## Unresolved investigation 1: PLAN versus fraction dose

The human's read-only inspection confirmed that the frozen plan contains more
than one planned fraction. Source inspection found no handling of
`NumberOfFractionsPlanned`. Current Sumtally normalization restores the active
treatment MU sum once, while final DICOM processing requires and writes
`DoseSummationType = PLAN`.

This is strong evidence that the generated values may represent one fraction
while the DICOM object claims a complete PLAN dose. It explains most of the
observed scale gap, but it does not explain the distribution-direction
mismatch. It remains a hypothesis until a human approves a dose-semantics
change and synthetic tests prove the intended course-dose contract.

No fraction multiplier, dose scaling, MU change, normalization change, or new
OpenSpec proposal was implemented today. Do not apply a numerical multiplier
directly to the external output as an undocumented workaround.

## Unresolved investigation 2: non-zero gantry direction

The compared plan uses opposed, non-zero oblique beams with field-in-field
segments. Earlier small square fields at gantry zero had high comparison pass
rates, while this oblique multi-beam case failed. Gantry zero cannot expose a
lateral sign error because `sin(0) = 0`.

The current public source construction uses:

```text
PHITS direction = (-sin(gantry), 0, cos(gantry))
```

Combined with the documented mapping
`DICOM = isocenter + 10 * (-PHITS x, PHITS z, PHITS y)`, its lateral DICOM
component appears to become `+sin(gantry)`. The expected IEC/DICOM patient
direction, the accelerator `tr3` transform, the source location, and the beam
axis have not yet been proved mutually consistent for non-zero angles. This is
a strong candidate for the mirrored gradient observed by the human, but it is
not yet a confirmed root cause.

Do not repair this by mirroring only the final RT Dose. If the transport source
or accelerator transform is later proven wrong, dose was transported through
the CT along the wrong path and PHITS must be rerun. An RTDOSE-only recovery
cannot correct that transport geometry.

No gantry-direction runtime change, public-physics change, or OpenSpec proposal
was implemented today.

## Coordinate-output-choice proposal

The untracked `add-rtdose-coordinate-output-choice` proposal records the
separate product request that standard GUI output remain DICOM patient
coordinates while an optional IEC research export is non-DICOM. Its approval
checkbox remains open. It must not be bundled implicitly with the fraction-dose
or gantry-direction fixes, and it must not be used to relabel IEC coordinates
as DICOM patient coordinates.

## Validation evidence

Validation completed before this handoff document was added:

- focused recovery/RTDOSE tests: `119 passed, 4 skipped`;
- full public pytest: `722 passed, 28 skipped`;
- `python -m compileall src`: passed;
- `python tools/verify_public_tree.py`: passed;
- `openspec validate --all --strict`: `9 passed`;
- Git diff checks: passed; and
- GitHub Actions run #315: Ubuntu and Windows jobs passed at exact head
  `0e9317b`.

The documentation-only handoff change then passed source compilation, the full
public pytest suite again (`722 passed, 28 skipped`), strict OpenSpec validation
(`9 passed`), public-tree verification of the intended 189-file tracked tree,
and Git whitespace/status inspection.
No runtime, test, OpenSpec, or public-physics file was changed by the handoff
edit.

These are synthetic/mock development checks. The human-operated external GUI
run successfully produced an output but its comparison exposed the unresolved
problems above. Real external-tool and protected-DICOM execution was not run by
the agent.

## Restart checklist

1. Read `AGENTS.md`, `AI_AGENT_RULES.md`, `openspec/AGENTS.md`,
   `openspec/project.md`, and this handoff in full.
2. Confirm the repository root, branch, HEAD, status, recent graph, remotes,
   tags, and ahead/behind counts. Preserve all local branches, linked worktrees,
   and the untracked coordinate-output-choice proposal.
3. Confirm the intended Python import path before launching any GUI. Do not use
   screenshots from a different editable checkout as current-branch evidence.
4. Keep PR #37 draft. Update its manual-evidence section before review because
   the latest human run both regenerated the current output and found new
   merge-blocking dose/geometry evidence.
5. Address the oblique gantry-direction question first because it can require a
   full PHITS rerun and final-DICOM mirroring cannot repair it. Before runtime
   work, propose one bounded OpenSpec change and obtain explicit human approval.
   Its synthetic acceptance tests should anchor source position, beam direction,
   and accelerator transform in patient coordinates at cardinal angles and at
   representative non-zero oblique angles.
6. Address PLAN-versus-fraction dose as a separate human-approved dose-semantics
   change. Require one unambiguous fraction group, a finite positive planned
   fraction count, explicit provenance, and fail-closed handling before deciding
   where course scaling belongs.
7. After any approved geometry correction, rerun the required PHITS, Sumtally,
   and RTDOSE stages only through an explicitly authorized human-operated
   non-patient workflow. After a dose-only correction, use only the downstream
   suffix justified by the accepted design.
8. Recompare in DICOM patient coordinates, investigate any
   `FrameOfReferenceUID` mismatch explicitly, and record external results only
   within the repository's protected-data boundary.
9. Integrate or publish the separate safety/UI branches only after a separate
   human decision. Expect overlapping `gui.py` changes; do not merge or
   cherry-pick them automatically.

## Stopping outcome

Today's recovery, voxel-mapping, and Windows cleanup commits are pushed on the
draft PR branch and have green cross-platform CI. The safety/GUI work remains
on separate local branches. The regenerated external comparison did not pass,
so PR #37 is intentionally stopped before merge. The next session must obtain
human approval before changing fraction-dose semantics, gantry geometry,
public physics, DICOM meaning, or external execution.
