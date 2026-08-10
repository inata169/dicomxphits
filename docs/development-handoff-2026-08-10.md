# Windows-to-Dev-Container Handoff - 2026-08-10

This dated handoff records the uncommitted Windows security-hardening work and
the evidence needed for a Codex session in the repository Dev Container to
cross-check it on Linux. It is a restart aid for the current change set. It is
not a new implementation backlog, clinical validation record, or authorization
to run real external tools or use real DICOM.

## Handoff baseline

- Repository-relative worktree: the repository root mounted by the Dev
  Container, normally `/workspaces/dicomxphits`.
- Branch: `harden-offline-csv-output`.
- Base and current `HEAD`: `cbcc59b` (`Automate Windows offline installation
  (#32)`), also the current `main` and `origin/main` commit when this handoff was
  written.
- Public release tags remain `v1.0.1` and `v1.0.0`; neither tag was modified.
- The hardening work is entirely uncommitted. No file was staged, committed,
  pushed, or released, and no pull request was created.
- Before this handoff document was added, the working tree contained 24
  modified tracked files with 1,214 insertions and 563 deletions, plus the
  intended untracked files listed below.
- The human completed the final scope, scientific-boundary, privacy, contract,
  and commit-readiness review and accepted all six review criteria. The code
  change set was therefore considered suitable for commit after inclusion and
  review of this handoff document.

The Dev Container session must preserve the complete working tree. It must not
reset, clean, checkout over, mass-renormalize, stage, or commit the changes
unless the human separately requests that exact Git action.

## Approved objective and boundaries

The branch hardens three related areas:

1. deterministic, verified, offline Windows installation;
2. spreadsheet-formula-safe CSV export; and
3. guarded workspace output creation and promotion around PHITS-related fake or
   explicitly authorized external runners.

The implementation remains Python 3.12-only and within the public fixed-field
3D-CRT education and research scope. The review found no intended change to
scientific calculations, DICOM meaning, geometry, coordinates, dose, MU,
normalization, machine-model values, PHITS physics, or supported treatment
technique. The changes do not make a clinical commissioning, patient QA,
vendor-certification, or general compatibility claim.

No real PHITS, RT-PHITS, CT2PHITS, Sumtally, phits2dicom, GPR, real DICOM, real
patient data, facility configuration, licensed distribution, or calculation
output was used or executed. Dev Container validation must retain that same
synthetic/mock boundary.

## Work completed on Windows

### Offline installer and dependency integrity

- `requirements/runtime.txt`, `requirements/test.txt`, and
  `requirements/offline-win64.txt` separate runtime, test, and locked Windows
  wheelhouse inputs.
- `tools/offline_bundle.py`, `tools/prepare_offline_bundle.ps1`,
  `tools/install_offline_verified.ps1`, `tools/offline_install.py`, and
  `install_offline.cmd` implement the verified offline bundle and installation
  flow.
- The base-interpreter virtual-environment command and the created
  environment's pip command now use isolated module resolution:
  `python -I -m venv` and `python -I -m pip`. This prevents a working-directory
  module from shadowing `venv` or `pip` during installation.
- Offline installation retains the no-index/wheelhouse contract. No network
  fallback was added.
- CI, English and Japanese installation documentation, OpenSpec, and tests were
  aligned with this contract.

### CSV export protection

- `src/dicomxphits/csv_security.py` centralizes spreadsheet-formula neutralizing
  behavior for externally influenced CSV cells.
- `src/dicomxphits/rtplan_segments.py` applies the shared serialization path and
  explicitly preserves the intended LF CSV record representation.
- The protection is covered by `tests/test_security_boundaries.py` and the
  existing RT Plan segment tests.

### Guarded workspace outputs

- `src/dicomxphits/safe_output.py` provides the shared output-root guard,
  guarded staging-directory creation, exclusive new-file creation, regular-file
  checks, streaming guarded copy, guarded cleanup, and same-directory temporary
  output followed by atomic replacement.
- `src/dicomxphits/prepare_3dcrt_workspace.py` uses the guard for workspace
  copies and cleanup; the previous direct destination unlink path was removed.
- `src/dicomxphits/run_segments.py` runs fake or authorized PHITS runners in a
  guarded staging execution tree, copies workspace-local includes into that
  tree, and promotes declared results only after successful execution and
  validation.
- `src/dicomxphits/prepare_sumtally.py` stages its wrapper and relative inputs,
  runs in the staged working directory, and promotes validated outputs. Its
  `phits_started` state is set only by a callback immediately before runner
  invocation, after guard validation.
- `src/dicomxphits/prepare_rtdose.py` stages the template, CT, dose, and PHITS
  inputs, rewrites only execution-time phits2dicom input paths, validates the
  single expected RTDOSE output, and promotes it atomically. Input ordering,
  factor text, and trailing-newline count are preserved.
- Text writing again matches the platform-default newline behavior when no
  newline mode is specified. Callers that require byte-stable or LF behavior
  pass an explicit newline mode.

### Specifications and security policy

- The accepted hardening deltas were promoted to
  `openspec/specs/csv-export-security/`,
  `openspec/specs/workspace-output-security/`, and the existing Windows offline
  installation specification.
- The completed change was archived under
  `openspec/changes/archive/2026-08-10-harden-security-boundaries/`.
- Two existing RTDOSE requirement lines were reformatted so the OpenSpec CLI
  recognizes their unchanged `SHALL` and `SHALL NOT` clauses. Their meaning was
  not changed.
- `SECURITY.md`, `.github/dependabot.yml`, and
  `docs/windows-security-regression-checklist.ja.md` record the public security
  and Windows review boundaries.
- The unrelated active
  `openspec/changes/support-portable-workspace-recovery/` proposal remains
  proposal-only and must not be implemented as part of this handoff.

## Security-review findings closed on Windows

The final review closed five merge-blocking findings:

1. Offline installer module shadowing during `venv` and pip invocation was
   closed by isolated `-I -m` execution.
2. PHITS, Sumtally, and phits2dicom adapters no longer give the runner a final
   output destination; execution occurs against staged paths followed by
   guarded promotion.
3. Direct cleanup of an existing destination no longer bypasses the output
   guard.
4. The safe text writer no longer changes Windows default newline translation;
   explicit CSV and byte-preserving callers retain their required newline
   behavior.
5. Sumtally no longer reports that PHITS started when guard validation fails
   before runner invocation.

Regression checks first demonstrated the original defects: both installer
commands lacked `-I`, the guarded writer emitted LF where Windows
`Path.write_text` emitted CRLF, and the segment runner received the final
workspace as its working directory. The corresponding checks pass after the
fixes.

## Windows validation evidence

The final Windows checks used Python 3.12 and the repository's expected
pydicom 3.0.2 and NumPy 2.5.1 dependency set. The full suite was invoked with
system pytest while the repository `.venv` site-packages directory was placed
on `PYTHONPATH`, because that environment contained the locked runtime
dependencies but not pytest. This Windows-only invocation detail should not be
copied into the Dev Container; install the normal `.[test]` environment there.

Final results:

```text
python -m pytest -q -p no:cacheprovider --basetemp <temporary-directory-outside-repository>
  649 passed, 5 skipped in 32.35s

six focused owning test files
  209 passed, 5 skipped in 17.76s

eleven explicitly selected Windows-only tests
  11 passed in 9.83s

python -m compileall src
  passed

python tools/verify_public_tree.py
  Public tree audit passed (154 tracked files checked).

openspec validate --all --strict
  8 passed, 0 failed

python -I -m venv --help
  passed

.venv\Scripts\python.exe -I -m pip --version
  passed; pip 25.0.1 resolved from the repository environment

git diff --check
  passed; Git printed only expected Windows LF-to-CRLF checkout warnings
```

These Windows results predate the Dev Container follow-up correction that
changes the phits2dicom runner working directory from the persistent final
`rtdose/DATfiles` directory to the guarded `.p2d-*` staging tree. They remain
evidence for the earlier baseline, but they are not final Windows acceptance
evidence for the corrected working tree. Rerun the focused phits2dicom checks
in `docs/windows-security-regression-checklist.ja.md`, followed by the focused
owning suite and complete public validation, before commit readiness is
claimed.

An earlier test invocation accidentally combined system pydicom 2.4.4 with the
newer expected dependency set and failed in a pydicom helper. That result was
diagnosed as an interpreter/dependency mismatch, not a repository failure, and
is not acceptance evidence. Repository-local test temporary files created
during diagnosis were individually reviewed and removed; none remained in the
final status.

The handoff-document validation repeated the checks without changing runtime
code. Its first focused invocation could not create the selected external
pytest base directory under the restricted sandbox and ended with 52 passes
and 162 setup errors, all reporting the same `PermissionError`. Repeating the
same synthetic/mock command with permission to use that external temporary
directory passed with 210 tests and 4 expected skips. The complete suite then
passed with 649 tests and 5 expected skips in 30.14 seconds. Compilation,
strict OpenSpec validation (8 passed, 0 failed), and the 154-file public-tree
audit also passed. The sandbox setup errors were environmental and did not
write repository test artifacts.

## Dev Container follow-up correction

The Dev Container cross-check found one merge-blocking mismatch in the earlier
working tree: phits2dicom received the persistent final `rtdose/DATfiles`
directory as its process working directory. A synthetic fake runner could
therefore create cwd-relative files in the final directory, and a DICOM written
only to the final expected path was accepted even when no staged output existed.

The minimal correction changes the runner cwd to the guarded `.p2d-*` data
directory, promotes an expected DICOM only when exit code 0 produced it in that
staging directory, and requires successful guarded promotion before RTDOSE
postprocessing or success status. The regression test failed before the source
change and passed afterward. Final Dev Container results for the corrected tree
were 206 passed and 9 Windows-only skips in the focused suite, 644 passed and
11 Windows-only skips in the complete suite, successful compilation, 8 strict
OpenSpec validations, and a successful 154-file public-tree audit and diff
check. Current-tree Windows acceptance remains pending the procedure in
`docs/windows-security-regression-checklist.ja.md`.

## Current file scope to preserve

The modified tracked files at the handoff baseline are:

```text
.github/workflows/ci.yml
docs/windows-offline-installation.ja.md
docs/windows-offline-installation.md
install_offline.cmd
openspec/specs/rtdose-dicom-semantics/spec.md
openspec/specs/windows-offline-installation/spec.md
src/dicomxphits/dose_semantics.py
src/dicomxphits/fix_coordinates.py
src/dicomxphits/prepare_3dcrt_workspace.py
src/dicomxphits/prepare_rtdose.py
src/dicomxphits/prepare_sumtally.py
src/dicomxphits/rtdose_plan_references.py
src/dicomxphits/rtplan_segments.py
src/dicomxphits/run_segments.py
src/dicomxphits/sumtally_inputs.py
tests/test_offline_bundle.py
tests/test_offline_install.py
tests/test_manual_smoke_workflow.py
tests/test_prepare_3dcrt_workspace.py
tests/test_prepare_rtdose.py
tests/test_prepare_sumtally.py
tests/test_run_segments.py
tools/offline_bundle.py
tools/offline_install.py
tools/prepare_offline_bundle.ps1
```

The intended untracked paths, in addition to this handoff document, are:

```text
.github/dependabot.yml
SECURITY.md
docs/windows-security-regression-checklist.ja.md
openspec/changes/archive/2026-08-10-harden-security-boundaries/
openspec/specs/csv-export-security/
openspec/specs/workspace-output-security/
requirements/
src/dicomxphits/csv_security.py
src/dicomxphits/safe_output.py
tests/test_security_boundaries.py
tools/install_offline_verified.ps1
```

Treat any additional untracked path as unexpected until a human confirms it.
The public-tree audit examines tracked files; it does not replace manual review
of this untracked list.

## Dev Container cross-check procedure

At the beginning of the Dev Container Codex session:

1. Read `AGENTS.md`, `AI_AGENT_RULES.md`, `openspec/AGENTS.md`,
   `openspec/project.md`, and this handoff in full.
2. Confirm the repository root, branch, `HEAD`, status, recent history, remote,
   tags, and worktree list. The expected branch and `HEAD` are the values in the
   handoff baseline, but the status must include this new handoff document.
3. Preserve all tracked and untracked work. Do not run `git clean`, reset the
   branch, restore files, or normalize line endings.
4. Confirm Python 3.12 and install or refresh the Dev Container's normal test
   environment only if required by the container setup:

   ```bash
   python --version
   python -m pip install -e ".[test]"
   ```

   Dependency installation may require setup-time network access and must use
   the repository's established Dev Container process. Ordinary Codex work
   remains network-disabled. Do not weaken the lock or substitute newer
   dependencies merely to obtain a passing result.
5. Run the focused synthetic/mock tests that own the corrected boundaries:

   ```bash
   python -m pytest \
     tests/test_offline_install.py \
     tests/test_security_boundaries.py \
     tests/test_run_segments.py \
     tests/test_prepare_sumtally.py \
     tests/test_prepare_rtdose.py \
     tests/test_prepare_3dcrt_workspace.py \
     -q -p no:cacheprovider
   ```

6. Run the complete public validation:

   ```bash
   python -m compileall src
   python -m pytest -q -p no:cacheprovider
   openspec validate --all --strict
   python tools/verify_public_tree.py
   git diff --check
   git diff --stat
   git status --short
   ```

7. Inspect the complete diff, including every untracked file, for the protected
   material listed in `AI_AGENT_RULES.md`. Confirm that no credentials, patient
   information, real DICOM, external-tool output, temporary file, or
   workstation-specific path was introduced.
8. Report Linux results separately from the Windows evidence. Expected
   platform-conditioned skips are acceptable only when the test itself clearly
   identifies the Windows-only reason. Do not assume the exact Windows pass and
   skip counts must match Linux.

If the bind-mounted Windows checkout appears broadly modified because of line
endings, first use the non-mutating diagnosis in `docs/development.md`:

```bash
git status --short
git diff --ignore-cr-at-eol --quiet
```

Do not mass-renormalize the worktree. A repository-local `core.autocrlf`
adjustment is allowed only when the existing documented diagnosis proves that
line endings are the sole cause and the human-approved worktree remains
preserved.

## Dev Container acceptance criteria

The cross-check is complete when all of the following hold:

- the focused and full synthetic/mock suites have no unexplained failure;
- compilation, strict OpenSpec validation, public-tree audit, and diff check
  pass;
- Linux behavior preserves the same staged-runner and guarded-promotion
  invariants as Windows;
- platform newline behavior matches `Path.write_text` by default while
  explicit LF and byte-preserving call sites retain their contracts;
- installer command construction remains isolated and offline even though the
  real Windows CMD and PowerShell launchers cannot be executed natively on
  Linux;
- the changed-file scope matches the intended list above, including the
  handoff document, with no protected or temporary artifact;
- no scientific, DICOM-semantic, dose, MU, coordinate, normalization, physics,
  clinical-scope, or Python-version boundary has changed; and
- all unverified real-tool and Windows-native integration items remain reported
  as such instead of being inferred from Linux tests.

The main remaining compatibility uncertainty is execution against real PHITS,
Sumtally, and phits2dicom installations. The human accepted synthetic fake-runner
evidence without a new real-tool run for this change. The Dev Container must not
attempt to close that uncertainty by mounting, discovering, or executing those
tools.

## Stopping state

The Dev Container cross-check found that phits2dicom still received the
persistent final `rtdose/DATfiles` directory as its working directory. The
follow-up correction runs it from guarded staging and accepts only an expected
staged regular file for guarded promotion. Linux validation and the Windows
recheck in `docs/windows-security-regression-checklist.ja.md` must both pass
before commit readiness is claimed. Report exact commands, platform-specific
skips, final file scope, and remaining uncertainty. Do not start optional
refactoring, create follow-up work, run real external tools, or perform Git
publication actions without a separate human request.
