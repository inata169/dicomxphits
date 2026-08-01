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

Use the inner loop only for safe failures caused by the current diff: change,
run focused validation, inspect the result and diff, and apply a bounded fix as
defined in `AI_AGENT_RULES.md`. Use the outer loop for specification, physics,
clinical, real-data, real-tool, destructive, external-write, or scope decisions:
report the evidence and wait for a human.

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
