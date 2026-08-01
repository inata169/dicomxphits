# AI agent rules

This is the provider-neutral policy for Codex, Claude Code, and other coding
agents working in this public repository. Existing code, documentation, and
tests are the source of truth. If they conflict with these rules or the approved
task, do not reconcile the difference by inference: preserve the repository,
record the evidence, and ask a human.

## Public scope and safety claims

- `dicomxphits` is education and research software.
- The v1 public workflow is fixed-field 3D-CRT. Do not add IMRT, dynamic MLC,
  or VMAT support without a separately approved public-scope decision.
- Preserve the exact existing field-size guard and the documented centered
  `20 x 20 cm2` effective-aperture boundary. Do not widen, clip, recenter, or
  add tolerances to it.
- Do not weaken fail-closed behavior, including rejection of a stale public
  dose factor after machine-model changes.
- Do not claim clinical commissioning, clinical validity, patient QA, vendor
  certification, endorsement, or compatibility beyond the documented tests.

## Protected material

Do not add, generate, copy, or commit:

- real-patient DICOM, patient identifiers, or real UIDs;
- real institution, machine, or facility-specific configuration or calibration;
- credentials, tokens, passwords, private keys, or populated `.env` files;
- official PHITS or RT-PHITS distribution files;
- original IAEA phase-space or header files;
- unapproved material from a private repository;
- local PHITS, Sumtally, phits2dicom, or GPR results; or
- configuration containing a personal-computer absolute path.

The only tracked DICOM currently allowed is the reviewed, project-authored,
sanitized template `templates/phits2dicom_rtdose_template.dcm`. Never open it as
part of a repository-boundary audit. Do not add a blanket `*.dcm` ignore rule:
a new tracked DICOM requires explicit human review and an allowlist change.

## External execution

Run PHITS, Sumtally, ct2phits, phits2dicom, GPR, long Monte Carlo calculations,
or any workflow using a real DICOM outside this repository only when a human
explicitly requests that exact execution. Ordinary development, the Dev
Container, and CI use synthetic data, mocks, and fake runners. Do not install,
mount, or discover real external tools or datasets on an agent's initiative.

## Inner AI loop

An agent may automatically correct only failures introduced by the current
diff in these groups:

- Python syntax, compilation, lint, type, or JSON-schema checks;
- focused pytest failures;
- mock external-tool contract tests;
- document formatting, link, encoding, or line-ending defects; and
- an unambiguous regression caused by the current diff.

For one failure group, make at most three correction attempts and rerun the same
focused validation after every attempt. Stop earlier if the same failure occurs
twice, the remaining error or validation delta does not shrink, a hard-coded
test bypass or weaker validation would be needed, the specification/test/
fixture/reference may be wrong, or an out-of-scope change would be required.
Record each observed failure and result; do not hide or delete evidence.

## Pull request stopping rule

Completion is defined by the human-approved task and acceptance criteria, not
by the absence of any possible improvement. Once those criteria are met and
the required validation passes:

- stop expanding or deepening the pull request;
- consider further review feedback only when it identifies a concrete
  merge-blocking defect in the current diff, such as a safety, security, or
  privacy exposure, a violated approved requirement, a required-validation
  failure, or an unambiguous regression;
- treat a reviewer severity label such as P1 as an indicator, not sufficient
  authority by itself: the reported defect must be verified against the code
  and approved scope;
- allow at most one additional review-driven correction round, keep it minimal,
  and make it on the same branch and pull request;
- treat robustness suggestions, refactors, optional coverage, stylistic
  preferences, and future capabilities as non-blocking for that pull request;
  and
- do not create a follow-up branch, pull request, Issue, OpenSpec change,
  automation, or other work item unless a human explicitly requests it.

If the final correction round reveals another possible blocker, report the
evidence and stop for a human decision instead of starting a recursive review
loop. A human decides whether to mark the pull request ready or merge it; an
agent may report evidence and recommend that action but must not merge
automatically.

## Outer human loop

Do not decide any of the following automatically. Report the evidence and stop:

- a public-scope or specification change;
- a change in DICOM coordinates, geometry, units, dose, MU, normalization, or
  dose factors;
- a change to source spectra, MLC, jaws, machine geometry, PHITS physics, or
  physical tolerances;
- clinical suitability, commissioning, patient QA, or vendor approval;
- work involving patient, institution, facility, or vendor data;
- real external-tool execution;
- destructive operations, writes outside the approved workspace, or scope
  expansion; or
- any need to weaken a guard, test, audit, or validation.

The human-facing stop report must include the observation, current diff,
completed validation, remaining uncertainty, and the smallest decision needed.

## Permissions, Git, and completion

Default to repository-scoped writes, no network, and approval for sandbox
escalation. Never select danger-full-access as a project default. Do not add
extra writable roots, credentials, Docker socket access, privileged containers,
or host network access.

Start from a clean, expected branch and remote. Use a feature branch; do not
commit directly to `main`, force-push, rewrite history, modify tags, publish a
release, or merge a pull request automatically. Preserve unrelated user work.

Before handoff, run focused validation, the full test and compilation suite,
`python tools/verify_public_tree.py`, and Git diff/status checks. Report exact
commands and outcomes, the branch and commit/PR when created, anything not run
and why, and whether runtime code or the public specification changed.
