# CT2PHITS Frontend Handoff

This document records the durable end-of-session state of the automated
CT2PHITS frontend merged by pull request
[#3](https://github.com/inata169/dicomxphits/pull/3). It is a restart guide,
not an automatically approved backlog or authorization to run external tools.

## Completed state

- Pull request: `#3`, merged by squash
- Main commit: `f792d0ec7f1e9265ad5df939e2e6b3aeb9f6e4bb`
- Final reviewed feature commit: `25a1610cc58eb571c81d53f01c93f0aadbd2a02b`
- Completion date: 2026-08-02 local development record
- Release tag remains `v1.0.0`; no release or tag was created
- The local and remote implementation feature branches were deleted after
  merge

The merged stage is the Windows-only `dicomxphits-run-ct2phits` CLI. It selects
and validates one CT series, creates an isolated workspace below a supplied
RT-PHITS root, snapshots the CT and RT Plan inputs, writes `ct2phits.inp`, runs
the supplied `RTphits_win.bat`, inventories all nine generated files, and hands
the eight downstream DATfiles to the existing validation and asset-preparation
functions.

## Implemented safety and evidence boundaries

The frontend:

- requires Windows and explicit non-patient phantom confirmation;
- uses the human-supplied `RTphits_win.bat` path and never invokes
  `ct2phits_win.exe` directly;
- refuses existing, repository-local, or command-processor-unsafe workspaces;
- rejects unreadable or inconsistent CT series geometry, including shifted or
  irregular stacks and inconsistent pixel spacing;
- verifies source-series membership and source hashes while creating stable CT
  and RT Plan snapshots;
- strictly rejects missing, non-integral, non-finite, or Boolean RT Plan beam
  identifiers instead of coercing them;
- attempts to terminate the Windows process tree on timeout and records any
  process-tree termination failure separately; when
  `process_tree_termination_error` is not null, a human must verify that no
  child process remains before reusing the external workspace;
- preserves timeout, return-code, stdout, stderr, and log-write evidence;
- requires all nine generated files to be newly produced, non-empty regular
  files and records their SHA-256 digests;
- revalidates all snapshots and generated outputs after execution and after
  downstream preparation; and
- removes a partial, unstarted workspace when preparation fails and cleanup is
  possible.

Generated `CTtrans.dat` is part of the nine-file inventory only. The existing
coordinate-processing path creates the validated downstream `CTtrans.inp`.
Downstream workspace preparation must use the frozen
`<ct2phits-workspace>/RTPLAN.dcm`, not the mutable original RT Plan.

The current public contract is
[`openspec/specs/ct2phits-frontend/spec.md`](../openspec/specs/ct2phits-frontend/spec.md).
The completed change record is archived at
[`openspec/changes/archive/2026-08-01-add-ct2phits-frontend/`](../openspec/changes/archive/2026-08-01-add-ct2phits-frontend/).

## Validation evidence

The final Windows validation for the merged content completed with:

```text
python -m pytest tests/test_run_ct2phits.py tests/test_ct2phits_datfiles.py -q -p no:cacheprovider
65 passed

python -m pytest -q -p no:cacheprovider
456 passed

python -m compileall src
passed

python tools/verify_public_tree.py
Public tree audit passed (85 tracked files checked).

git diff --check
passed
```

GitHub Actions `dicomxphits public CI` run `#42` passed the synthetic/mock
compile, full pytest, and public-tree checks on `ubuntu-latest` for the final
feature commit. This is Linux CI evidence, separate from the Windows local
validation above. A final Codex review of that commit reported no major issues.

An explicitly authorized Windows smoke test used a designated non-patient
phantom outside the repository. It completed with return code zero, no timeout,
nine generated files, eight validated raw DATfiles, and six prepared assets.
The input paths, external distributions, and generated results were not added
to Git. PHITS, Sumtally, phits2dicom, and GPR were not run as part of this
frontend task.

## CLI handoff

Use placeholders or explicitly approved external non-patient paths. Never put
real DICOM, official distributions, or generated calculations in this
repository.

```powershell
dicomxphits-run-ct2phits `
  --ct-dicom-root <non-patient-ct-directory> `
  --rtplan <non-patient-rtplan.dcm> `
  --rtphits-root <licensed-rtphits-root> `
  --workspace-root <licensed-rtphits-root>/work/<new-case-id> `
  --timeout-seconds 300 `
  --confirm-non-patient-phantom
```

Pass the frozen handoff to the existing preparation adapter:

```powershell
dicomxphits-prepare-3dcrt-workspace `
  --rtplan <ct2phits-workspace>/RTPLAN.dcm `
  --workspace-root <new-public-workspace> `
  --phits-root-folder <licensed-phits-root> `
  --phits-executable-path <licensed-phits-executable> `
  --phits2dicom-executable-path <licensed-phits2dicom-executable> `
  --ct-datfiles-root <ct2phits-workspace>/DATfiles `
  --ct-reference-dicom <ct2phits-workspace>/CT/CT000001.dcm `
  --confirm-non-patient-phantom
```

## Unverified item

The workplace Dev Container cross-check has not run, so validation in that
specific container environment must not be claimed until a human runs the
following synthetic/mock checks there. This gap does not negate the completed
`ubuntu-latest` Linux CI evidence recorded above:

```bash
python -m pytest tests/test_run_ct2phits.py tests/test_ct2phits_datfiles.py -q -p no:cacheprovider
python -m pytest -q -p no:cacheprovider
python -m compileall src
python tools/verify_public_tree.py
git diff --check
git status --short
```

Do not mount or run RT-PHITS, CT2PHITS, PHITS, Sumtally, phits2dicom, GPR, or
real DICOM in that container. Neither Linux CI nor a future Dev Container
cross-check validates the real Windows RT-PHITS runtime. A future documentation
update may record the container cross-check only after the human explicitly
performs or authorizes it.

## Restart checklist

At the next development session:

1. Read `AGENTS.md`, `AI_AGENT_RULES.md`, and
   [`project-status.md`](project-status.md) in full.
2. Confirm the repository root, `main`, clean status, remote, recent history,
   and tags.
3. Confirm that `main` still contains merge commit `f792d0ec7f1e` or a later
   descendant.
4. Treat the Dev Container cross-check as unverified evidence, not an approved
   implementation project.
5. Ask the human for one concrete next goal before creating another change,
   branch, Issue, pull request, or automation.

There is no known merge-blocking defect carried forward from pull request #3
and no next implementation goal is currently approved.
