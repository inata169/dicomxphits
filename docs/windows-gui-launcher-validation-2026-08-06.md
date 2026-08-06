# Windows GUI Launcher Validation - 2026-08-06

This dated record summarizes a human-reported Windows-host check of the GUI
launcher and guided workflow after pull request
[#27](https://github.com/inata169/dicomxphits/pull/27). It is a bounded
development record, not clinical validation, commissioning, patient QA, vendor
certification, or a general compatibility claim.

## Scope

The original Code **Download ZIP** installation used Python 3.12.10, created a
repository-local `.venv`, and completed the editable package installation. The
unsigned PowerShell launcher was then rejected by the host execution policy
before GUI code could run. Pull request #27 made `run_gui_venv.cmd` the default
Windows entry point while retaining the equivalent PowerShell launcher for
hosts whose policy permits it.

This is a post-release correction on `main`. It does not move the `v1.0.1` tag,
replace the published GitHub Release assets, or create a new release. A Code
**Download ZIP** archive follows the branch or ref selected on GitHub; the
published v1.0.1 release artifacts remain the artifacts recorded in the
v1.0.1 release documentation.

## Human-reported result

On 2026-08-06, the human reported that both manually exercised Windows cases
passed:

- one case used its existing external workspace path; and
- one case used a duplicate external workspace whose directory name included
  spaces, Japanese text, and a copy suffix.

The external GPR handoff was reported complete for both cases. The agent did
not open the external directories, DICOM, calculation outputs, screenshots, or
GPR result files and did not inspect or record numerical results. Exact
workstation paths and external artifact names are intentionally omitted.

The report supports the bounded conclusion that the current-main Windows GUI
entry point and the two manually exercised path forms completed the reported
workflow. It does not establish compatibility with every Windows policy or
path, and it does not authorize or validate the separate portable-workspace
recovery proposal.

## Repository evidence

Pull request #27 was squash-merged as `857e61b` after two Codex findings were
corrected. The exact-head review of `95f09bb534` reported no major issues,
GitHub Actions pull-request run
[#197](https://github.com/inata169/dicomxphits/actions/runs/31072644956)
passed on Ubuntu and Windows, and main push run
[#198](https://github.com/inata169/dicomxphits/actions/runs/31073067016)
passed. The remote feature branch was deleted.

The automated checks are synthetic/mock evidence. They do not run PHITS,
RT-PHITS, CT2PHITS, Sumtally, phits2dicom, GPR, or real DICOM. The manual report
and automated checks therefore remain separate, bounded forms of evidence.

The documentation change that added this record passed:

```text
Focused public-tree and GUI checks: 94 passed, 1 skipped
Full public suite: 591 passed, 2 skipped
Python compileall: passed
OpenSpec strict validation: 5 passed, 0 failed
Public-tree audit: 136 tracked files passed
Git diff check: passed
```

## Safety and authorization boundary

- No external DICOM, absolute workstation path, licensed tool, calculation
  output, GPR result, or screenshot is stored in this repository.
- No patient-data or clinical-validation claim is made.
- No physics, machine model, coordinate, dose, MU, normalization, DICOM
  semantic, or supported-workflow rule changed in pull request #27.
- `support-portable-workspace-recovery` remains an active proposal at 1/21
  tasks. Task 1.1 is still unapproved, so implementation, promotion, and
  archive remain unauthorized.
