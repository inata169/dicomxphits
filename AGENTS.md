# AI contributor entry point

Read `AI_AGENT_RULES.md` in full before inspecting or changing this repository.
It is the authoritative, provider-neutral safety and iteration policy.

`dicomxphits` is education and research software. Its public v1 scope is the
documented fixed-field 3D-CRT workflow; it is not clinical commissioning,
patient QA, or vendor certification. Follow, in order: the human-approved task,
the existing public specification and safety boundaries, then the tests. Stop
and report any conflict rather than guessing.

Before work, confirm the repository root, branch, status, recent history,
remote, and tags. Read the files relevant to the task and make the smallest
in-scope change. Do not alter runtime behavior, public physics, DICOM meaning,
or protected data unless a human explicitly approves that separate work.

Every direct question to this repository's primary user must present one
concrete proposal that can be answered with `yes` or `no`, and should end in
Japanese with the equivalent of `Is <proposal> acceptable? yes/no`. Do not
bundle independent decisions or permissions into one question. When a decision
is not naturally binary, first state the relevant evidence, propose the safest
concrete option, and ask for a yes/no decision; if rejected, offer the next
concrete option separately. A `no` rejects only the stated proposal and never
authorizes an alternative.

Use the OpenSpec workflow in `openspec/AGENTS.md` for a new capability,
behavioral or public-contract change, architecture change, or other planned
scope expansion. Create the change proposal and delta specifications before
implementation, validate them, and obtain human approval. A human may
explicitly waive or defer the proposal, as happened for work approved before
OpenSpec was added to this repository. A bug fix that only restores already
documented behavior does not require a new change proposal.

OpenSpec cleanup is part of task completion, not a later follow-up. When the
human-approved acceptance criteria and required checks for an active change are
complete, promote its accepted deltas into `openspec/specs/`, move the change to
`openspec/changes/archive/YYYY-MM-DD-<change-id>/`, and validate the resulting
specification tree before the completion report. Do not archive a change that
is incomplete, blocked, or awaiting a required human decision; report why it
remains active instead.

Use the inner loop only for safe failures caused by the current diff: change,
run focused validation, inspect the result and diff, and apply a bounded fix as
defined in `AI_AGENT_RULES.md`. Use the outer loop for specification, physics,
clinical, real-data, real-tool, destructive, external-write, or scope decisions:
report the evidence and wait for a human.

Once the human-approved acceptance criteria are met and the required checks
pass, stop deepening the work. Only a concrete merge-blocking defect in the
current diff may justify another minimal correction round in the same pull
request, up to six review-driven correction rounds total; stop immediately when
no verified merge-blocking defect remains. Treat robustness ideas, refactors,
optional coverage, and future work as non-blocking; do not create a follow-up
branch, pull request, Issue, OpenSpec change, automation, or other work item
unless a human explicitly requests it. After the sixth correction round,
report any remaining possible blocker and stop for a human decision.
The required OpenSpec promotion and archive cleanup above belongs to the
current task and is not a follow-up work item.

Run the applicable focused checks, then the full public checks:

```text
python -m compileall src
python -m pytest -q -p no:cacheprovider
python tools/verify_public_tree.py
git diff --check
git diff --stat
git status --short
```

Work on a feature branch, never force-push or modify tags, and use a reviewable
pull request. A completion report must list changed files, validation commands
and results, unverified items, the stopping outcome, and confirmation that the
runtime and public specification were not changed when they were out of scope.
