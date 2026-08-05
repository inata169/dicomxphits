# Development Handoff - 2026-08-05

This dated handoff records the repository state at the end of the v1.0.1
development and release session. It is a restart aid, not a new backlog,
clinical validation record, or authorization for further implementation.

## Closing baseline

- The repository root is `/workspaces/dicomxphits` in the development
  container.
- The completed baseline before this handoff branch is clean `main` at merge
  commit `902425dc99ba9f57d3cc83690d4f903d9f602eb6`, matching `origin/main`.
- Pull request [#25](https://github.com/inata169/dicomxphits/pull/25)
  recorded the durable release closeout and was merged as `902425d` after its
  exact-head Codex review reported no major issues.
- GitHub Actions run
  [#186](https://github.com/inata169/dicomxphits/actions/runs/30978200520)
  passed for the pull request #25 merge commit on `main`.
- The remote `agent/record-v101-release-closeout` branch was deleted. The root
  worktree was returned to clean `main`; there were no additional worktrees.

## v1.0.1 release state

The public [v1.0.1 GitHub
Release](https://github.com/inata169/dicomxphits/releases/tag/v1.0.1) is
published and is not a draft or prerelease. The annotated `v1.0.1` tag resolves
to release commit `7db473b12d570026600c03947690d0f6c1fb60f5`; the later
documentation-only closeout commit intentionally does not move the tag.

The published files and recorded SHA-256 digests are:

- `dicomxphits-1.0.1.tar.gz`:
  `1afbbf75d7d8baaf9914c0263ce15a3073581fc7df0681b83e1ac5eff7e3cc3e`
- `dicomxphits-1.0.1-py3-none-any.whl`:
  `da46087c3d4dc0944fc3561055b4b6fcc312b156bfdb376892bc209b6e2bb55a`

A fresh public download reproduced both digests. Both distributions passed
`twine check`; the wheel installed into a fresh isolated Python 3.12
environment with matching package and runtime version `1.0.1`; and all eleven
installed console entry points returned success for `--help` without executing
external tools. The package was not published to PyPI.

## Completed implementation and documentation

- Pull request #18 completed the active-treatment MU normalization,
  `sumfactor`, SETUP exclusion, `phits2dicom` factor `1.0`, canonical segment
  manifest digest, and fail-closed GUI RTDOSE state corrections.
- Pull request #19 completed the accepted RTDOSE isocenter translation and
  final-DICOM coordinate-placement validation. Its OpenSpec delta was promoted
  and the change was archived.
- Pull request #20 added the v1.0.x GUI user guide and aligned the README with
  the implemented workflow and bounded companion-repository links.
- Pull requests #23 through #25 recorded the bounded manual evidence boundary,
  prepared and published v1.0.1, and closed out the durable repository status.

No runtime code, physics rule, DICOM meaning, coordinate rule, dose, MU,
normalization, machine model, or supported-workflow scope remains pending from
those completed pull requests.

## Validation boundary

The final release preparation checks recorded:

```text
Focused release checks: 86 passed
Full public suite: 589 passed, 1 skipped
Python compileall: passed
OpenSpec strict validation: 5 passed, 0 failed
Public-tree audit: 133 tracked files passed
Distribution build and twine check: passed
Fresh isolated wheel install and 11 CLI help checks: passed
```

This documentation-only handoff change separately passed:

```text
Public-boundary focused tests: 10 passed
Full public suite: 589 passed, 1 skipped
Python compileall and OpenSpec strict validation: passed
Public-tree audit: 134 tracked files passed
Git diff check: passed

The human also reported completion of one explicitly authorized external
non-patient research workflow through the guided stages and an external GPR
comparison. That evidence is deliberately bounded: exact paths, DICOM,
numerical results, screenshots, GPR files, and generated calculation outputs
remain outside Git. It is not clinical validation, commissioning, patient QA,
vendor certification, or a general dose-accuracy claim.

## OpenSpec state and authorization boundary

The accepted RTDOSE coordinate and MU-related changes are archived, and their
accepted contracts are present under `openspec/specs/`.

`support-portable-workspace-recovery` is the only active change. It remains a
proposal at 1/21 completed tasks. Task 1.1, explicit human approval before
runtime work, is unchecked. It is unapproved for implementation and
unimplemented. Do not implement, promote, or archive it without a separate
explicit human decision and completion of its acceptance criteria.

There is no approved next implementation goal. PyPI publication, a new
release, new workflow support, or any change to physics, geometry, coordinates,
dose, MU, normalization, DICOM semantics, machine configuration, or clinical
claims requires a new explicit human decision.

## Restart procedure

At the next development session:

1. Read `AGENTS.md`, `AI_AGENT_RULES.md`, `docs/project-status.md`, and
   `openspec/AGENTS.md` in full.
2. Confirm the repository root, current branch and status, `main`,
   `origin/main`, recent history, remotes, tags, `git worktree list`, and the
   uncommitted state of every worktree.
3. Confirm that `main` contains `902425dc99ba` or a later descendant and that
   `v1.0.1^{}` still resolves to `7db473b12d57`.
4. Check the OpenSpec CLI, active and archived changes, strict validation, and
   every unchecked task. Keep `support-portable-workspace-recovery` separate
   from completed release work.
5. Read the current specification and Docs relevant to the newly approved
   goal before changing files.
6. Preserve external DICOM, absolute workstation paths, licensed tools, GPR
   result files, screenshots, and generated outputs outside the repository.
7. Start any approved repository change on a feature branch, run focused and
   full public validation, and use a reviewable pull request.

The correct stopping state for this session is a completed v1.0.1 release with
no known merge-blocking defect and no authorized follow-up implementation.
