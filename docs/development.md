# Development

See [Project status](project-status.md) for the durable completion baseline,
unverified items, and the human-approved starting point for future work.

Use Python 3.12 or newer. Development and automated validation must use public
source, synthetic inputs, mocks, and fake runners. Never put real patient or
facility data, credentials, official PHITS/RT-PHITS files, original IAEA
phase-space files, or real-tool results in this repository.

## Windows Local

From the repository root, use an existing project environment or create a
repository-local virtual environment. Do not modify a machine-wide Python
installation. Install and validate with:

```powershell
python -m pip install -e ".[test]"
python -m compileall src
python -m pytest -q -p no:cacheprovider
python tools/verify_public_tree.py
git diff --check
```

If the Python launcher is required, use `py -3.12` in place of `python`.

## Dev Container

In a Dev Container-capable editor, open this repository and choose **Reopen in
Container**. The container uses Linux, Python 3.12, the non-root `vscode` user,
and mounts only this repository as `/workspaces/dicomxphits`. Its repeatable
post-create command installs `.[test]`; rerunning that command is safe.
Pulling the image and installing dependencies during container setup may need
network access. That setup-time access is separate from the disabled network
access for normal Codex agent work and must not carry into that runtime.

Inside the container, run the same `compileall`, pytest, and public-tree audit
commands shown above. This is a development environment, not a production
runtime image. It intentionally has no privileged mode, Docker socket, host
network, host tool folders, patient-data mounts, credentials, PHITS tools, or
real DICOM inputs.

After the CT2PHITS frontend mock tests pass on Windows, repeat this cross-check
in the workplace Dev Container:

```bash
python -m pytest tests/test_run_ct2phits.py -q -p no:cacheprovider
python -m pytest -q -p no:cacheprovider
python -m compileall src
python tools/verify_public_tree.py
git diff --check
git status --short
```

The Dev Container check is synthetic/mock validation only. Do not mount or run
RT-PHITS, CT2PHITS, PHITS, Sumtally, phits2dicom, GPR, or real DICOM there.
Until these commands are actually run in that container, report the Linux/Dev
Container validation as unverified rather than passed.

Windows Local and the Dev Container cover Python development, synthetic and
mock tests, documentation, and the public-boundary audit. Real PHITS, Sumtally,
ct2phits, phits2dicom, GPR, real DICOM, and long calculations are outside this
loop. Only after explicit human approval may a developer run the requested real
tool check on the Windows host, with inputs and outputs kept outside Git.

## Codex project settings

`.codex/config.toml` selects `workspace-write`, on-request approval reviewed by
the user, and disabled sandbox network access. Codex loads project-local
configuration only when this repository is treated as a trusted project. After
changing the file, start a new Codex chat or session because an existing session
may retain its earlier configuration. Do not mix this legacy sandbox form with
permission-profile settings or add writable roots without human review.

## Development loop

Read `AGENTS.md` and `AI_AGENT_RULES.md`. Confirm a clean expected branch,
remote, history, and tags; make the smallest approved change; run focused
validation; inspect its output and the diff; and apply only bounded safe fixes.
Then run the full commands above. Finish with success, a non-converging failure,
or a human-decision stop, and provide the validation evidence in every case.
