# Development handoff — 2026-08-14

This handoff records the completed RT Dose geometry/course-dose work, the
Windows offline-installer repair, the human-operated evidence, and the newly
observed GUI integration gap at the end of 2026-08-14.

`dicomxphits` remains education and research software for the documented
fixed-field 3D-CRT workflow. Nothing here establishes clinical dose accuracy,
commissioning, patient QA, or vendor compatibility. External DICOM objects,
PHITS outputs, GPR artifacts, screenshots, installed runtimes, and local case
directories are not repository content.

## Stop state

- Repository: `C:\Repositories\dicomxphits`
- Branch: `fix-offline-bundle-directory-lock`
- Runtime implementation HEAD before this handoff document:
  `00352a7354e9f1ca7b231324000acf4dc022c30e`
- `origin/fix-offline-bundle-directory-lock` matched that HEAD before this
  handoff was added.
- Base `origin/main`:
  `e534be951629519cec1dfa920c3711fa74a177b8`
- Pull request
  [#38 — Fix offline bundle directory-lock self-conflict](https://github.com/inata169/dicomxphits/pull/38)
  is open, draft, unmerged, and mergeable.
- GitHub Actions run #342 passed on PR #38 implementation HEAD `00352a7`.
- Pull request
  [#37 — Recover RT Dose and correct DICOM voxel mapping](https://github.com/inata169/dicomxphits/pull/37)
  was merged into `main` as `e534be9` on 2026-08-14. It is closed and is no
  longer draft.
- Tags `v1.0.1` and `v1.0.0` remain unchanged.
- The only working-tree item that predates PR #38 and this handoff is the
  untracked, unapproved
  `openspec/changes/add-rtdose-coordinate-output-choice/`. Preserve it without
  implementation, modification, promotion, archive, or accidental staging.

Do not merge, ready, close, or delete PR #38 without a new human decision. The
tested local ZIP is an ignored artifact rather than a tracked release asset.

## PR #37 completed: gantry direction and PLAN course dose

The reported left/right problem was not repairable by another final-DICOM
mirror. The code-level transport defect was double compensation:

- the former source/tr3 `-sin(gantry)` convention compensated for the old RT
  Dose output orientation;
- final DICOM PixelData later gained the explicit PHITS-X reversal required by
  the published DICOM mapping; and
- the old source/tr3 compensation remained, so nonzero gantry geometry was
  compensated twice.

PR #37 now derives source position, source direction, accelerator `tr3`, and
the central axis to isocenter from one versioned geometry contract. The source
X convention uses the corrected `+sin(gantry)` relationship with matching
`tr3` signs. Synthetic patient-coordinate anchors cover gantry 0, 90, 180,
270 degrees and representative oblique angles. Gantry zero remains unchanged.
Obsolete geometry evidence is rejected, and affected nonzero-gantry results
must be recalculated beginning with PHITS rather than repaired only in the
final DICOM.

PR #37 also implements the approved PLAN course-dose contract:

```text
course dose = one-fraction Sumtally dose × NumberOfFractionsPlanned
```

The public path requires one unambiguous Fraction Group and a positive integral
planned fraction count. The Sumtally base normalization remains unchanged; the
fraction count is applied exactly once as the effective converter factor, and
final PixelData is not multiplied a second time. Fraction-only correction can
reuse verified PHITS/Sumtally outputs and restart from RTDOSE Prepare. A case
affected by the obsolete nonzero-gantry contract must restart from PHITS.

The accepted OpenSpec changes were promoted and archived as:

- `openspec/changes/archive/2026-08-14-fix-iec-gantry-direction/`; and
- `openspec/changes/archive/2026-08-14-fix-plan-fraction-dose-semantics/`.

PR #37 also contains the earlier existing-workspace recovery, BeamMeterset
exception for manifest-proven skipped zero-MU non-treatment beams, final RT
Dose PixelData coordinate correction, and subsequent fail-closed recovery
hardening. Do not lose or revert those changes when porting the separate GUI
branches described below.

## Human PHITS/DICOM/GPR evidence and provisional acceptance

After explicit human approval, the corrected workflow was exercised on the
designated anonymized non-patient phantom case based on
`C:\Repositories\dicom-phits_inp\DICOM\JCMP_BreastR1\anonymised`.

- The primary user reported that the external research workflow completed.
- The primary user reported no abnormal dose-distribution or absolute-dose
  behavior and accepted the corrected geometry and PLAN course-dose semantics.
- The agent did not run or inspect PHITS, Sumtally, phits2dicom, GPR, real
  DICOM, or calculation outputs.

This is provisional acceptance of the corrected left/right geometry and PLAN
course-dose semantics only. It is not clinical dose-accuracy acceptance. A
higher-statistics calculation is optional future research verification and was
not a merge blocker for PR #37.

## PR #38 completed implementation: Windows offline installer

The requested local artifact is:

```text
C:\Repositories\dicomxphits\dist\dicomxphits-offline-win64-1.0.1.zip
SHA-256 7AB6F4D4C9F2A95F770FD995041C78197F45A1B4471C85EE8C03AE2F770CE603
manifest source HEAD 00352a7354e9f1ca7b231324000acf4dc022c30e
manifest file records 208
```

Three Windows bootstrap defects were found and corrected:

1. Initial checksum verification retained payload handles with
   `FileShare.Read`, conflicting with the bootstrap's own DELETE-access child
   directory locks. Initial verification now also shares delete access; after
   path locks are established, every payload is rehashed and reopened with the
   original strict read-only sharing.
2. A parent PowerShell whose current directory was the extracted bundle root
   prevented a DELETE-access handle from being acquired on that root and caused
   Windows error 32. The authenticated and rehashed `install_offline.cmd` is
   now the strict root-rename sentinel, while every protected child directory
   retains the strong DELETE-access/no-delete-sharing handle.
3. The verified stage used
   `Join-Path [System.Environment]::SystemDirectory ...` without parentheses.
   PowerShell interpreted the type expression as a provider name. It now uses
   `Join-Path ([System.Environment]::SystemDirectory) ...` and has direct
   regression coverage.

The final tests reproduce the real user launch path: a PowerShell process keeps
the extracted bundle root as its current directory and runs
`.\install_offline.cmd`. They also prove that both the root and a protected
child directory remain non-renamable, resolve the exact Windows system
PowerShell, and rehash/read-lock all payloads before the verified stage.

Validation on implementation HEAD `00352a7`:

- focused real-launch/lock tests: passed;
- offline installer/bundle suite: 58 passed;
- full repository suite with the pinned pydicom 3.0.2 environment:
  775 passed, 10 skipped;
- `python -m compileall src`: passed;
- `python tools/verify_public_tree.py`: passed, 200 tracked files;
- `openspec validate --all --strict`: 10 passed, 0 failed;
- `git diff --check`: passed; and
- GitHub Actions run #342: passed.

## Human end-to-end offline installation evidence

The primary user extracted the final ZIP to
`C:\Repositories\dicomxphits-offline-win64-1.0.1` and ran
`.\install_offline.cmd` from PowerShell.

The human-provided log confirms:

- initial SHA-256 and manifest verification passed;
- protected payload files and paths were locked;
- the expected administrator PowerShell constructed the authenticated
  application-local CPython 3.12.10 x64 runtime below
  `C:\ProgramData\dicomxphits\offline-runtimes\a8fe4f...`;
- a repository-local `.venv` was created;
- pip used `--no-index`, `--require-hashes`, and the protected local
  wheelhouse;
- NumPy 2.5.1, pydicom 3.0.2, setuptools 84.0.0, wheel 0.47.0, packaging
  26.3, and dicomxphits 1.0.1 installed successfully;
- Python, tkinter, NumPy, pydicom, and dicomxphits imports/version checks
  passed; and
- the log ended with `Offline installation completed successfully`.

The visible administrator PowerShell is intentional: the installer starts the
absolute Windows system PowerShell with `-Verb RunAs` only after bundle
verification and holds the parent process until protected runtime construction
finishes. The command prompt is also expected from the `.cmd` bootstrap or the
optional `COMSPEC /d /c launchers\run_gui_venv.cmd` GUI launcher. The log shows
no evidence of an unexpected executable or online pip source. No separate
antivirus scan was run or claimed.

## Newly observed GUI integration gap

After the successful installation, the GUI opened but did not show the newest
safety/header presentation. The human screenshot shows the older header and a
Workspace page whose lower primary action is not reachable in the visible
minimum-height layout. The user specifically reports:

- buttons cannot be pressed or reached;
- `6 MV only` is absent;
- `Web site` is absent; and
- `Inata` is absent.

This is not evidence that the final offline installation selected an old
editable checkout. The installed package correctly reflects manifest source
HEAD `00352a7`. That HEAD is based on merged PR #37 plus PR #38 and does not
contain the two separate safety/UI branch commits preserved from 2026-08-13.

The missing UI is present only on these retained branches:

- `feat/safety-ui-energy-guard` at
  `af87da3cd199eb2246a6d3a711eebfc59f68e1b7`; and
- `fix/safety-ui-minimum-window-scroll` at
  `85a8d780425408dd1900d3e9d9837fc831242d7c`, which builds on `af87da3`.

`af87da3` adds the fixed Elekta Precise 6 MV research-model identity and guard,
plus model, nominal energy, project web address, and author in the shared GUI
header. `85a8d78` adds minimum-window vertical scrolling so stage content and
primary actions remain reachable.

Those branches were deliberately not merged or cherry-picked into PR #37 or
PR #38 under the prior human instruction to preserve them separately. Their
merge base with current `main` is the older `ac043ca`; meanwhile PR #37 added
large geometry, dose-semantics, recovery, GUI, test, and OpenSpec changes.
Therefore a wholesale branch merge or unreviewed cherry-pick is unsafe and may
revert or conflict with accepted PR #37 behavior.

## Exact recommended restart sequence

1. Re-read `AGENTS.md`, `AI_AGENT_RULES.md`, `openspec/AGENTS.md`,
   `openspec/project.md`, and this handoff in full.
2. Confirm repository root, current branch, HEAD, status, recent graph, remote,
   tags, and upstream divergence.
3. Reconfirm through the GitHub plugin that PR #38 is still open/draft and that
   its exact-head CI is green. Do not merge or ready it without a new human
   decision.
4. Treat the GUI issue as a missing-integration problem, not as another offline
   installer or `.venv` resolution problem. Before any code change, prove the
   installed/current import path with:

   ```powershell
   .\.venv\Scripts\python.exe -I -c "import dicomxphits.gui; print(dicomxphits.gui.__file__)"
   ```

5. Inspect the deltas in `af87da3` and `85a8d78` against current `main`/PR #38.
   Preserve PR #37's geometry, PLAN dose, recovery, and evidence contracts.
6. Propose one bounded integration branch from the then-current accepted base.
   Port the already approved 6 MV safety/header behavior first, then the
   minimum-window scrolling fix. Do not merge either old branch wholesale.
   Ask the primary user for a yes/no approval before starting that integration.
7. Run focused GUI, beam-model, workspace, recovery, dose-semantics, and
   gantry-geometry tests, followed by all public checks.
8. Rebuild the offline ZIP from the exact integration HEAD and confirm its
   manifest HEAD. Extract it to a new empty folder; do not reuse the existing
   installed folder for acceptance.
9. Human GUI acceptance must explicitly confirm the fixed 6 MV identity,
   project website, Hiroki Inata author line, vertical scrolling at minimum
   size, and reachable/enabled primary actions on all five workflow pages.

Do not attempt this integration in the current stopping session. Do not delete
or overwrite the human's successful installed folder. Do not modify the
unapproved coordinate-output-choice proposal. Do not rerun real PHITS, Sumtally,
phits2dicom, GPR, or protected DICOM evidence without separate explicit human
approval.

## Final boundary

The RT Dose transport direction and PLAN course-dose defects are implemented,
validated synthetically, provisionally accepted by the human comparison, and
merged through PR #37. The offline installer now passes both automated Windows
coverage and human end-to-end installation, but PR #38 remains draft and
unmerged. The newly reported GUI problem is explained by two intentionally
unintegrated branches; it remains the first task for the next session after a
fresh yes/no scope decision.
