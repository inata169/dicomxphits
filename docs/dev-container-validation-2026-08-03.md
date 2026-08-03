# Dev Container Validation - 2026-08-03

This dated record documents the human-authorized Dev Container cross-check of
the merged repository baseline from pull request #1 through pull request #9.
It is synthetic/mock development evidence, not clinical validation, patient
QA, vendor certification, dose-accuracy evidence, or real-tool validation.

## Environment and method

The repository's `.devcontainer/devcontainer.json` was started with Dev
Containers CLI `0.82.0` using
`mcr.microsoft.com/devcontainers/python:1-3.12-bookworm`. The resulting Linux
container used Python `3.12.11` and the non-root `vscode` user. The repository
was mounted at `/workspaces/dicomxphits`.

The container was started from the Windows repository with the Dev Containers
CLI. The checks were invoked in that container with `docker exec`; the VS Code
window was not required to be attached to the container for this execution.
Inside the container, a temporary clone was created below `/tmp`, and each
pull request's squash commit was checked out in order. The host checkout
remained on `main` and clean throughout the validation.

For every commit, the package and test dependencies were installed and the
following checks were run:

```bash
python -m pip install -e ".[test]"
python -m compileall src
python -m pytest -q -p no:cacheprovider
python tools/verify_public_tree.py
git diff --check
git diff --stat
git status --short
```

## Results by pull request

| Pull request | Squash commit | Full pytest result | Public-tree result |
| --- | --- | --- | --- |
| #1 | `7d2f511a3136da6d35b857b42c8e048e9f1f5c84` | 397 passed | 75 tracked files passed |
| #2 | `e57e86f9075d9982095af3185d5da49853d6b41a` | 397 passed | 76 tracked files passed |
| #3 | `f792d0ec7f1e9265ad5df939e2e6b3aeb9f6e4bb` | 455 passed, 1 skipped | 85 tracked files passed |
| #4 | `7202c1a1c6ba34b00d498f88ac2283771a67e882` | 455 passed, 1 skipped | 86 tracked files passed |
| #5 | `bc6296d5f6949f461e7d50b86db6a0b4579e048d` | 469 passed, 1 skipped | 91 tracked files passed |
| #6 | `1a8aa870713010b19f9703ce092637059ab1479e` | 469 passed, 1 skipped | 91 tracked files passed |
| #7 | `caa6452068d3b2cc6396e43a1a55fdbb8a0d3f61` | 469 passed, 1 skipped | 91 tracked files passed |
| #8 | `854e5e216f501403e725fc39a085abd3ddc2d2e2` | 507 passed, 1 skipped | 98 tracked files passed |
| #9 | `ebcd53529e7ff37e4edc66f4500a73ed8edf7e09` | 507 passed, 1 skipped | 98 tracked files passed |

Package installation, Python compilation, pytest, public-tree audit, Git diff
checks, and clean-status checks returned success for all nine commits. The one
skip from pull request #3 onward is the expected Windows-only process-tree test
in `tests/test_run_ct2phits.py`, skipped on Linux when `os.name != "nt"`.

The CT2PHITS-focused command documented in the frontend handoff was also run
separately at the pull request #3 squash commit:

```bash
python -m pytest tests/test_run_ct2phits.py tests/test_ct2phits_datfiles.py -q -p no:cacheprovider
```

It completed with `64 passed, 1 skipped`. The skip was the same expected
Windows-only process-tree test.

## Validation boundary

All automated checks used repository test fixtures, synthetic DICOM, and fake
or mock external-tool runners. The container did not mount or execute
RT-PHITS, CT2PHITS, PHITS, Sumtally, phits2dicom, GPR, real DICOM, patient
data, facility data, licensed distributions, or real calculation results.

This cross-check confirms that the public synthetic/mock development checks
pass in the documented Dev Container environment through pull request #9. It
does not validate the real Windows RT-PHITS runtime or any clinical workflow.
