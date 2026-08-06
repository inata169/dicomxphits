# Development Handoff - 2026-08-06

This dated handoff records the repository state after the Windows GUI launcher
correction and its bounded manual-validation documentation. It is a restart
aid, not a new backlog, clinical validation record, or authorization for
further implementation.

## Closing baseline

- The repository root is `/workspaces/dicomxphits` in the development
  container.
- The completed baseline before this handoff branch is clean `main` at merge
  commit `e2cb54568628b6b1d9121fe3b85eb2b4b224f6f9`, matching
  `origin/main`.
- Pull request [#28](https://github.com/inata169/dicomxphits/pull/28)
  recorded the anonymized Windows manual evidence and refreshed the durable
  baseline. It was squash-merged as `e2cb545`.
- GitHub Actions main push run
  [#203](https://github.com/inata169/dicomxphits/actions/runs/31087022999)
  passed for the pull request #28 merge commit.
- The remote feature branches for pull requests #27 and #28 were deleted. The
  root worktree was returned to clean `main`; there were no additional
  worktrees.

## v1.0.1 release state

The public [v1.0.1 GitHub
Release](https://github.com/inata169/dicomxphits/releases/tag/v1.0.1) remains
published and is not a draft or prerelease. The annotated `v1.0.1` tag still
resolves to release commit
`7db473b12d570026600c03947690d0f6c1fb60f5`.

The launcher correction is a post-release update on `main`. It does not move
the tag, replace the published source distribution or wheel, publish to PyPI,
or create a new release. A GitHub Code **Download ZIP** archive follows the
branch or ref selected on GitHub; it is not the same artifact as the published
v1.0.1 release assets.

## Completed work on 2026-08-06

### Windows GUI launcher correction

Pull request [#27](https://github.com/inata169/dicomxphits/pull/27) corrected
the documented Code **Download ZIP** launch path after an unsigned PowerShell
script was blocked by the Windows host execution policy before GUI code could
run.

The change:

- added `launchers/run_gui_venv.cmd` as the default Windows GUI entry point;
- retained the equivalent PowerShell launcher where policy permits it;
- kept the repository-local `.venv\Scripts` PATH behavior;
- included both launchers in source distributions;
- documented the policy-preserving fallback without recommending `Bypass` or
  weaker machine or organization controls; and
- added Windows metacharacter-path regression coverage.

The first Codex review found that the CMD launcher was missing from
`MANIFEST.in`. The second review found that the missing-venv diagnostic needed
to quote its expanded path inside the batch block. Both defects were corrected,
tested, and re-reviewed. The exact-head review of `95f09bb534` reported no
major issues. Pull-request CI #197 and main push CI #198 passed on Ubuntu and
Windows. Pull request #27 was squash-merged as `857e61b`.

### Bounded Windows manual evidence

After pull request #27, the human reported that two Windows manual cases passed:
one used an existing external workspace path, and one used a duplicate path
containing spaces, Japanese text, and a copy suffix. The external GPR handoff
was reported complete for both.

Pull request #28 recorded this result in
[Windows GUI Launcher Validation - 2026-08-06](windows-gui-launcher-validation-2026-08-06.md)
without adding exact workstation paths, DICOM, screenshots, numerical values,
GPR result files, or generated calculation outputs. The agent did not open or
inspect the external directories or results.

The first Codex review of pull request #28 found stale durable-baseline fields
in `project-status.md`. Commit `06942d1` updated the baseline commit, latest
repository update, review date, CI reference, and public-tree count together.
The exact-head re-review reported no major issues. Pull-request CI #202 and
main push CI #203 passed on Ubuntu and Windows.

## Validation boundary

The completed documentation baseline recorded:

```text
Focused public-tree and GUI checks: 94 passed, 1 skipped
Full public suite: 591 passed, 2 skipped
Python compileall: passed
OpenSpec strict validation: 5 passed, 0 failed
Public-tree audit: 136 tracked files passed
Git diff check: passed
Sensitive-path and identifier scan: no matches
```

This documentation-only handoff change separately passed:

```text
Public-boundary focused tests: 10 passed
Full public suite: 591 passed, 2 skipped
Python compileall: passed
OpenSpec strict validation: 5 passed, 0 failed
Public-tree audit: 137 tracked files passed
Git diff check: passed
Sensitive-path and identifier scan: no matches
```

These checks use synthetic/mock fixtures and do not run PHITS, RT-PHITS,
CT2PHITS, Sumtally, phits2dicom, GPR, or real DICOM. The human report is bounded
research and development evidence only. It is not clinical validation,
commissioning, patient QA, vendor certification, or a general compatibility or
dose-accuracy claim.

## OpenSpec and authorization boundary

The four current specifications and the active
`support-portable-workspace-recovery` change pass strict validation.

`support-portable-workspace-recovery` remains the only active change at 1/21
tasks. Task 1.1, explicit human approval before runtime work, remains unchecked.
The proposal is unapproved for implementation and unimplemented. Do not
implement, promote, or archive it without a separate explicit human decision
and completion of its acceptance criteria.

No runtime code, public specification, physics, machine model, coordinate rule,
DICOM meaning, dose, MU, normalization, or supported-workflow scope changed in
the documentation closeout.

## Restart procedure

At the next development session:

1. Read `AGENTS.md`, `AI_AGENT_RULES.md`, `docs/project-status.md`, this
   handoff, and `openspec/AGENTS.md` in full.
2. Confirm the repository root, branch and status, `main`, `origin/main`,
   recent history, remotes, tags, `git worktree list`, and every worktree's
   uncommitted state.
3. Confirm that `main` contains `e2cb54568628` or a later descendant and that
   `v1.0.1^{}` still resolves to `7db473b12d57`.
4. Check the OpenSpec CLI, active and archived changes, strict validation, and
   all unchecked tasks.
5. Keep `support-portable-workspace-recovery` proposal-only unless the human
   separately approves task 1.1.
6. Preserve external DICOM, absolute workstation paths, licensed tools, GPR
   results, screenshots, and generated calculations outside the repository.
7. Start any approved change on a feature branch, run focused and full public
   validation, and use a reviewable pull request.

The correct stopping state is a clean current-main documentation baseline with
no known merge-blocking defect and no authorized next implementation goal.
