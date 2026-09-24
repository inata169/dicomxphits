# dicomxphits v1.1.1 Release Notes

Status: experimental release candidate, prepared from main at
`7bc132bc54d83cf575aefa46d00328933918a88d` on 2026-09-25.
No v1.1.1 tag or GitHub Release has been created. Publication requires explicit
human authorization after review.

## Purpose and main changes

Version 1.1.1 preserves the v1.1.0 capabilities as a patch release for
third-party education and research evaluation. It combines:

- [PR #83](https://github.com/inata169/dicomxphits/pull/83): refreshes
  existing-case downstream recovery after successful PHITS retry, including
  first Sumtally recovery from fully validated current v4/v5 PHITS evidence.
- [PR #84](https://github.com/inata169/dicomxphits/pull/84): accepts complete
  minute/second CPU-duration observations, retries transient Windows sidecar
  publication conflicts on a new sample, and checks source-content hashes
  when determining whether retained Structure results are still current.
- [PR #85](https://github.com/inata169/dicomxphits/pull/85): adds matching
  [Japanese](instruction/_manual/gui-manual.ja.md) and
  [English](instruction/_manual/gui-manual.en.md) GUI operating manuals.
- Direct beginner links from README Start Here, aligned source metadata,
  GUI About/help version text and candidate documentation.

This preparation adds no workflow capability. Existing provenance, freshness,
execution, STOP, completion and downstream authorization guards are retained.

## Scope and important limitations

Only the documented fixed-field 3D-CRT education and research workflow is in
scope. This is not clinical validation, commissioning, patient QA, vendor
certification or clinical-machine dose calibration. IMRT, dynamic MLC and VMAT
remain outside the public workflow.

Stable operation of the complete real external-tool workflow is not
guaranteed. Passing synthetic/mock tests does not guarantee real PHITS
operation. Preserve inputs and results and use a separate authorized
non-patient workspace. Live observations are provisional; neither low relative
error nor zero observed remaining batches establishes completion or convergence.

## Verification evidence and boundaries

| Category | Recorded evidence | Candidate limitation |
| --- | --- | --- |
| Automated tests | PR #85 recorded 1474 passed, 15 skipped; PR #83/#84 include retry/recovery, observation and Structure regression tests. Candidate checks are recorded below. | Skips are not passes; fake runners do not establish real-tool success. |
| Synthetic GUI tests | The bilingual manual records authored GUI sessions for layout, preparation cancellation, STOP, retry and downstream recovery; hidden-Tk regression tests cover the repaired handoff. | These sessions did not run real PHITS. |
| Manually confirmed GUI behavior | Historical human reports cover bounded Windows GUI/workflow use; manual preparation inspected synthetic screens. See the [launcher record](windows-gui-launcher-validation-2026-08-06.md) and [manual verification](instruction/_manual/gui-verification.en.md). | No new human acceptance of this exact candidate is claimed. |
| Real PHITS execution | Historical bounded non-patient end-to-end demonstrations are documented in [Public Feasibility Demonstration](public-feasibility-demonstration.md). The PR #84 investigation also read existing output with permission. | The repaired GUI has not undergone a new real PHITS/controller end-to-end run, sustained live observation, or real retry/STOP/recovery acceptance. The cause of the original observation shutdown was not proven. |
| Real Sumtally / RTDOSE | The historical bounded demonstrations included aggregation and coordinate-corrected RTDOSE. | Those results do not establish the repaired retry-to-downstream chain on this candidate; no new real Sumtally or phits2dicom execution was performed. |
| Physical dose validation | Historical bounded phantom/TPS gamma comparisons retain their documented conditions and interpretation limits. | No new physical dose validation, clinical acceptance threshold or machine commissioning is claimed. |

Real-data Structure hashing performance, long-duration observation and natural
Windows conflict recovery remain unverified. The proposed
[real-PHITS verification conditions](instruction/_manual/verification-conditions.ja.md)
remain unapproved and unexecuted. The reported approximately five minutes for
maxcas 4,000,000 has not been confirmed as a per-batch measurement; it is not a
validated total-time estimate.

### Candidate checks

Windows / Python 3.12 candidate validation (2026-09-25):

- Focused version, historical evidence, retry recovery, live observation and
  Structure tests: **78 passed** (20.30 s).
- GUI About/help selection: **3 passed, 133 deselected** (0.55 s).
- Editable-install focused check: **1 skipped**, because setuptools/wheel
  build tools are absent. No built wheel, sdist or offline bundle is validated.
- Full public suite, run once: **1474 passed, 15 skipped** (197.11 s).
  Skips comprise 11 symlink-privilege cases, two unavailable FIFO cases,
  one interactive-Tk case and one missing-build-tools case. They are not
  successful executions.
- Source compilation and public-tree audit: passed (397 tracked files).
- Changed-document UTF-8 and 118 tracked local links/anchors, bilingual
  12-chapter structure, metadata/About/help version consistency: passed.
- Git whitespace checks and scope review: passed. The sdist manifest explicitly
  includes these notes; this is a static inclusion check, not a build result.

Commands, using the existing development Python environment:

```text
python -m pytest -q -p no:cacheprovider tests/test_version_metadata.py tests/test_release_acceptance_evidence.py tests/test_gui_retry_recovery.py tests/test_phits_live_observation.py tests/test_structure_relative_error.py
python -m pytest -q -p no:cacheprovider tests/test_gui.py -k "help_menu_exposes_website_author_and_current_version or gui_help_is_side_effect_free_and_states_public_scope"
python -m pytest -q -p no:cacheprovider tests/test_offline_install.py::test_pep660_editable_install_does_not_mutate_source_tree
python -m pytest -q -p no:cacheprovider -rs
python -m compileall src
python tools/verify_public_tree.py
git diff --check
git diff --cached --check
git diff --stat
git diff --cached --stat
git status --short
```

The initial restricted focused run returned 44 passed and 34 setup errors.
A single-test diagnostic confirmed WinError 5 while pytest enumerated its
temporary directory. The same focused suite passed with approved execution
permissions; no code, assertions or guards were changed to resolve that
environmental failure. No real external tools were used.

The source is ready for review as an experimental patch candidate. Publication
requires human acceptance of the documented limits and a separate tag/Release
instruction; current-candidate remote CI and real-tool acceptance are not
claimed by these local results.

## GUI manual review

Both manuals were reviewed against the candidate source and existing tests for
Tool settings, CT2PHITS, Workspace Prepare, PHITS execution/progress, STOP,
incomplete retry, opening existing cases, downstream recovery, Sumtally,
RTDOSE, Structure relative error, folder handling and troubleshooting.
The procedures retain the PR #83/#84 repaired behavior; only their candidate
applicability and About-version guidance needed updating. This is a source
review, not a new interactive or real-tool acceptance run.

## Relationship to v1.1.0 and upgrade

The published v1.1.0 tag and source archives remain unchanged at
`12ea1b2ff65fac2fde276624ea692327d5fa710d`. They do not include PR #83/#84/#85.
The [historical v1.1.0 release record](release-notes-v1.1.0.md) remains intact.
v1.1.1 collects the subsequent merged fixes and manuals; a candidate version
string does not mean it has already been released.

Use Python 3.12 and the documented Windows external-tool environment. Install
the candidate into its intended environment before starting a new GUI session;
Help -> About must show 1.1.1. An already running GUI keeps its imported code.
Existing workspaces remain subject to their provenance and freshness checks.
Do not rewrite calculation inputs or records to force compatibility.

No new Windows offline bundle is prepared or accepted. The existing
[offline-distribution policy](windows-offline-installation.md) remains in force.
Review, merge, tagging and GitHub Release publication remain human decisions.
