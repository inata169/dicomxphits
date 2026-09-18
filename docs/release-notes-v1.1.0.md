# dicomxphits v1.1.0 Release Notes

Status: published on 2026-09-18 for experimental education-and-research
evaluation. The [v1.1.0 GitHub Release](https://github.com/inata169/dicomxphits/releases/tag/v1.1.0)
and annotated tag refer to commit `12ea1b2ff65fac2fde276624ea692327d5fa710d`.
Stable operation across real external-tool workflows has not been established.
Preserve existing inputs and results and evaluate in a separate non-patient
test workspace. This software is not validated for clinical use.

This post-publication status clarification updates the documentation on `main`.
The immutable v1.1.0 source archives remain bound to the release commit above
and retain preparation-era status text, including the old README release label;
they do not contain this clarification or the later Experimental banner.
Use the published GitHub Release and current `main` documentation for current
status. This documentation update does not replace or revalidate those archives.

Version 1.1.0 brings the reviewed post-v1.0.3 workflow additions and fixes to
the education-and-research fixed-field 3D-CRT workflow. Package metadata and
the GUI Help -> About dialog now report 1.1.0.

## Highlights

- Adds an optional regular 3D dose tally mesh configuration, preserving the
  existing 101 x 101 x 101, 3 mm default when omitted. See
  [Calculation Configuration](calculation-configuration.md).
- Adds the standalone, explicitly invoked non-patient phantom CT water
  replacement CLI. It creates a new calculation-only CT series without
  overwriting the source. See
  [Phantom CT Water Replacement](phantom-ct-water-replacement.md).
- Adds segment progress, explicit incomplete-segment retry and stopping after
  the current segment, with existing execution and provenance guards retained.
- Adds guarded live batch/error observation and Structure relative-error
  presentation, with bounded parsing, freshness checks and unavailable states
  for unsupported or invalid evidence.
- Improves GUI preflight responsiveness, controller environment consistency,
  action-button readiness and completion/stop hints.
- Corrects PHITS 3.35 lost-particle suffix handling, rejects CT/accelerator
  overlap, and handles supported combined Sumtally dose/error output. Retained
  relative-error recovery requires evidence from the same invocation.
- Prevents the downstream-summary overwrite option from bypassing the PHITS
  execution-record guard. Explicit incomplete-segment retry remains available.

## Upgrade and compatibility

Python 3.12 and the documented Windows external-tool environment remain the
supported v1 environment. Install the updated package before starting a new
GUI session; an already running GUI retains its imported version and code.

The optional calculation configuration preserves the default mesh when absent.
The water-replacement CLI is separate from the guided GUI workflow. Existing
workspace reuse remains subject to the current provenance and freshness gates;
the version update does not authorize old or incomplete evidence. In particular,
relative-error recovery cannot reconstruct missing same-invocation include
evidence from current files. Preserve existing results and follow the
[workflow guide](workflow_stages.md) and [GUI guide](gui-user-guide.md) for
explicit retry and regeneration requirements.

## Validation boundary

The merged implementation baseline passed 1448 tests with 14 skips before
release preparation. Approved synthetic GUI checks verified live observation,
completion/stop hints and PHITS/Sumtally button readiness. These checks use
authored inputs and fake runners; skipped cases are not verified.

Release-preparation validation passed 7 focused checks and the full suite
(1448 passed, 14 skipped), source compilation, the public-tree audit and Git
whitespace checks. The first full invocation used a repository-internal test
directory and reported 67 failures, including existing workspace-boundary
rejections and restricted Tk/process failures. The unchanged code passed with
a fresh external synthetic-test directory and approved execution permissions;
no assertions or guards were weakened. The final packaging correction passed
6 focused checks, the full suite (1448 passed, 14 skipped) and an isolated
source-distribution inclusion check. Codex re-review found no major issues;
Ubuntu and Windows CI passed for the final PR head and the release commit.

Final-version real PHITS/controller end-to-end execution
and eight-thread performance remain unverified. Synthetic timing acceptance
does not guarantee every observation completes within two seconds; the runtime
deadline and rejection behavior remain unchanged.

The cause of an investigated zero-valued Isocenter output and a historical
intermittent hidden-Tk test failure remains unresolved. Bounded investigation
did not establish a product defect; later passing tests do not establish the
historical failure's cause or a fix. Zero-dose/zero-error observations retain
their existing unavailable behavior.

Historical release evidence in `release_acceptance_evidence.json` targets
v1.0.3 and is not new v1.1.0 physical or external-tool acceptance evidence.
This release preparation does not claim clinical validation, commissioning,
patient QA, vendor certification, new dose-accuracy evidence, or support for
IMRT, dynamic MLC delivery or VMAT.

## Distribution

The published v1.1.0 release provides GitHub source archives only. No Windows
offline ZIP is attached or claimed as validated. The existing withdrawal
policy remains: a future public
offline asset requires separate review and an exact-source candidate that
passes installation, GUI startup and verified uninstallation under the
intended endpoint protection environment. See
[Windows Offline Installation](windows-offline-installation.md).
