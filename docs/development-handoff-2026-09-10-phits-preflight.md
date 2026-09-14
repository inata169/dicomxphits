# Development handoff — 2026-09-10/11: PHITS preflight verification

## Authoritative continuation from 2026-09-11

The final section, **2026-09-11 end-of-day checkpoint**, is now the
authoritative restart point. It supersedes the 2026-09-10 recorder blocker,
approval state, GUI state and next-session order retained below as history.
Do not repeat those completed investigations or infer another real invocation.

## Resume here, not at the previous handoff

This checkpoint supersedes the restart instructions in
[the September 9 observation-preparation handoff](development-handoff-2026-09-09-phits-observation-preparation.md).
Do not restart stages 1–3, reopen the old stage-4a evidence prerequisite, or
repeat PR #60/#63 correction, review, merge or branch-deletion instructions.

The human ended development for today and requested this handoff. That request
does **not** approve the outstanding recorder-replacement proposal, another
real invocation, cleanup, publication or further implementation tonight.

## Repository checkpoint

- Branch: `feature/improve-phits-preflight-responsiveness`.
- HEAD: `d18478f16f61e60bf9d1ba6244d24a40fa75b23d`.
- Origin: `https://github.com/inata169/dicomxphits.git`.
- No upstream is configured for this feature branch in the local checkout.
- Local `main` and cached `origin/main` point to the same HEAD. No fetch or
  live GitHub/CI query was made during handoff preparation; recheck remote
  state before any future publication claim.
- Tags observed locally: `v1.0.0`, `v1.0.1`, `v1.0.2`, `v1.0.3`.
- The tree is **not clean**: 19 implementation/proposal/test files were staged
  and uncommitted before this document. Preserve them. This handoff adds one
  documentation file; no commit, push, branch switch or deletion is requested.
- Recent integrated history: `9f43e8f` (PR #63, observation), `5a6eae8`
  (PR #65, preserve observed child results on stdin closure), `d18478f`
  (PR #64, dependency update). These are historical integrated changes,
  not a review or CI result for the current uncommitted preflight work.

The human's intended release boundary is stages 1–4a, **without a custom
Windows offline ZIP**. Release remains pending; do not reuse the older
v1.0.3 release evidence as acceptance of this new candidate.

## Completed work versus current work

Stages 1–3 are integrated. Stage 4a's exact-output prerequisite, implementation
and approved closeout are complete in the archived
[observation change](../openspec/changes/archive/2026-09-10-add-phits-live-observation/tasks.md).
Its dated earlier blocked statements are historical, not the current checklist.
Prior real probe evidence exists privately; it does not verify today's new
preflight cancellation or authorize another PHITS launch.

The current human-approved change is
[`improve-phits-preflight-responsiveness`](../openspec/changes/improve-phits-preflight-responsiveness/proposal.md).
Read its [design](../openspec/changes/improve-phits-preflight-responsiveness/design.md),
[tasks](../openspec/changes/improve-phits-preflight-responsiveness/tasks.md),
[verification plan and failure history](../openspec/changes/improve-phits-preflight-responsiveness/verification-plan.md),
and both delta specifications before continuing.

Implemented, with synthetic acceptance passing:

- Exclusive workspace ownership and early invocation-bound preflight receipt
  (`dicomxphits_segment_preflight_v1`, `analysis/segment_preflight.json`).
- Incremental file/byte progress and checkpoints between directory entries and
  hash reads of at most 1 MiB. Complete runtime membership and SHA-256 binding
  are retained; this is not a faster-scan guarantee or a persistent hash cache.
- Explicit preparation cancellation serialized against first child commitment;
  durable `cancelled_before_launch` and exit 5, distinct from v5 stopped/exit 4.
- Stop acknowledgements during later verification without skipping committed
  result validation, publication or ownership cleanup.
- GUI phase/control presentation, receipt identity/high-water checks, and
  precedence of newer incomplete preflight evidence over historical success
  for Sumtally, RTDOSE and recovery.

Real-GUI acceptance is **not complete**. The change remains active. Do not
promote/archive it, mark release acceptance passed, or publish it on the basis
of the passing fake-runner/Tk tests.

## Exact stopping point: private recorder blocks controller startup

One separately authorized GUI Run action was attempted. It failed before
preparation with a `runpy` import error and an absent `__main__.__file__`
attribute. The captured controller exit was 1, not cancellation exit 5.
No Cancel/Stop/second Run was issued for that attempt. Its one-invocation
approval is consumed.

There was no recorded PHITS spawn request, no new preflight/execution receipt,
and the last checked frozen preparation/input digests were unchanged. This is
consistent with controller startup failure, **not** passing no-child/cancellation
acceptance. The private Python recorder does not prove a complete independent
OS process tree; intermediary launcher ancestry was not fully captured.

Startup-only diagnosis then compared three entrypoints with and without the
recorder: module `--help`, installed controller console `--help`, and a dummy
Python script exiting 5. No simulation or actual DICOM was needed:

| Condition | Module help | Console help | Dummy script |
| --- | --- | --- | --- |
| No recorder | Pass | Pass | Pass |
| Original recorder | Startup failure | Startup failure | Pass |
| One minimally corrected private recorder | Same failure | Same failure | Pass |

The attempted correction filtered profile callbacks by function name before
accessing frame globals. It did not fix the failure. The original recorder and
both diagnostic runs were retained. The precise Python mechanism remains
unproven; do not describe the application or prepared inputs as the root cause.

The repeated-failure stopping rule was reached. **The last proposal is awaiting
approval**, not approved by the request to end work:

> Replace only the private startup-wide profiling approach with explicit
> child-process wait/exit recording, then verify it using help entrypoints and
> synthetic process chains, preserving error/exit evidence and all assertions.

This is a proposed approach, not a proven fix. It does not authorize real PHITS
or weakening independent evidence requirements. Do not silently substitute the
failed candidate into an already frozen private plan.

## GUI and private preparation state

The last observed existing GUI was an instrumented instance, not an approved
fresh launch configuration. Re-identify any current window/process next time;
do not trust old handles, PIDs, screenshot coordinates or an open window as
evidence that a corrected recorder is loaded. No existing GUI was closed as
part of this handoff, and its continued presence is not reverified here.

The prepared candidate alias is `preflight-cancel-006`: four active segments,
two setup fields excluded, `maxcas=1000`, `maxbch=10`, eight OpenMP threads.
The older `005` candidate used `maxcas=10000` and must not be substituted.
The existing completed CT2PHITS handoff was explicitly selected through
`Select CT2PHITS workspace...`; all three frozen fields displayed
`Verified existing handoff` in the last GUI observation.

The left navigation still displayed CT2PHITS `Not started`, Workspace
`Invalid existing case`, PHITS `Not reusable`, and downstream `Blocked`.
The existing-case inspection separately verified through `Workspace prepared`
and rejected PHITS-result reuse because required segment output was absent.
`apply_existing_handoff_state` updates frozen fields and handoff status, not
the navigation status. Distinguish these presentation/recovery facts from the
separate controller-startup error. Do not force success labels, recreate inputs
over an occupied workspace, or rerun CT2PHITS merely to clear the navigation.

Private artifacts remain outside Git. Names below are relative identifiers
within the previously approved private verification area, not authorization
to discover another directory or read unrelated workspaces:

- `private-preflight-cancel-006-instrumented.json`: frozen inputs/recorder and
  GUI-readiness addendum; old execution permission is consumed. A readiness
  status or stored approval flag alone is not fresh execution authority.
- `preflight-cancel-evidence-006/instrumented-gui-002/`: startup attempt,
  `run-attempt-001.md`, `open-existing-case.md`, `handoff-association.md`, logs.
- `logger-prototype-006/`: original recorder, dummy-chain tests and GUI launcher.
- `logger-diagnosis-007/RESULT.md`, `check_entrypoints.py`, `sitecustomize.py`:
  bounded diagnosis and failed correction. `entrypoints-ubed2wvn` is the
  original comparison; `entrypoints-88yeg3hd` is the unsuccessful correction.

Use the exact private paths/digests from the approved conversation and plans
only within an authorized scope. If that context is unavailable, ask for the
smallest concrete path/read approval rather than searching installations or
old workspaces. Do not commit populated plans, actual outputs, identifiers,
distribution files or personal-computer absolute paths. No cleanup is requested.

## Last implementation verification

Commands used the repository Python environment with process-local
`PYTHONUTF8=1` and a **fresh short ASCII** pytest temporary directory.
Never reuse `--basetemp`: pytest may remove its contents.

| Check | Result |
| --- | --- |
| Related preflight/stop/retry/GUI/downstream focused suite | 430 passed, 1 skipped; 80.63 s |
| `python -m pytest -q -x -p no:cacheprovider --basetemp <fresh-temp> tests/test_segment_preflight.py` after six acceptance additions | 43 passed; 11.21 s |
| Default full pytest before opt-in Tk harness correction | 1189 passed, 12 skipped; 245.75 s |
| Opt-in `tests/test_phits_observation_tk.py`, same focused command after one test-only correction | 1 passed; 1.88 s |
| `python -m compileall src` after that correction | Passed |
| `DICOMXPHITS_TEST_TK=1`, `python -m pytest -q -rs -p no:cacheprovider --basetemp <fresh-temp>` | 1190 passed, 11 skipped; 195.02 s |
| `python tools/verify_public_tree.py` on final staged implementation | Passed, 330 indexed files |
| `openspec.cmd validate improve-phits-preflight-responsiveness --strict` | Passed |
| `openspec.cmd validate --specs --strict` | 16 passed |
| Working/index `git diff --check`, stat and status | Passed; changes staged, not committed |

Remaining skips: nine symlink-privilege cases and two unsupported FIFO cases.
Both isolated preflight Tk cases and the opt-in observation/layout test ran.
Do not change OS security settings to remove these skips.

The first opt-in Tk test failed because its older harness activated the
execution guard without constructing the controller now required for the
preflight nonce. The harness was aligned with `run_selected` by constructing
`ControllerPipe`; external process launch and settings writes remain forbidden.
Existing layout, stale-data and reset assertions were not weakened. Earlier
hidden-Tk lifecycle failures and their approved isolation fix remain recorded
in the verification plan; do not erase them or confuse them with today's
unresolved private recorder failure.

Public diff inventory before this handoff: six active OpenSpec files;
`src/dicomxphits/{gui,prepare_rtdose,prepare_sumtally,run_segments,segment_preflight,segment_retry,segment_stop,sumtally_inputs,workspace_recovery}.py`;
and `tests/{test_gui,test_gui_preflight_loop,test_phits_observation_tk,test_segment_preflight}.py`.
The final test-completion round changed only tests and validation/task records,
not production behavior. Earlier approved preflight runtime changes remain
staged. This handoff itself is documentation-only and does not alter physics,
geometry, DICOM semantics, MU, dose conversion or normative public contracts.

## Handoff-only closeout validation

After adding this document, the same repository environment was checked again:

- `python -m pytest -q -p no:cacheprovider --basetemp <fresh-temp> tests/test_verify_public_tree.py`:
  10 passed, 0.07 seconds.
- `python -m compileall src`: passed.
- With process-local `PYTHONUTF8=1` and `DICOMXPHITS_TEST_TK=1`,
  `python -m pytest -q -rs -p no:cacheprovider --basetemp <fresh-temp>`:
  1190 passed, 11 skipped, 196.32 seconds; same environment limitations above.
- `python tools/verify_public_tree.py`: passed, 331 indexed files including
  this handoff. All six relative Markdown links resolve.
- Strict active-change validation and all 16 current specifications passed;
  working/index whitespace, diff/stat and status were checked.

Final state: 20 staged, uncommitted files including this handoff, with no
unstaged diff. HEAD/branch unchanged. No commit, push, real-tool invocation,
cleanup, promotion/archive or release was performed. This document is the only
file added by the end-of-day handoff task; the prior 19-file diff was preserved.

## Next-session order

1. Read `AI_AGENT_RULES.md`, `AGENTS.md`, this document and the active change.
   Reconfirm root, branch, index/working diff, history, remote and tags. Preserve
   the uncommitted implementation; do not reset, stash away or replace it.
2. Report the passing synthetic tests and the separate recorder/real-GUI
   blocker. Keep routine safe work grouped, as requested by the human.
3. Obtain the one outstanding yes/no decision for the bounded private recorder
   replacement above. The previous end-of-day request was not a yes to it.
4. If approved, validate the actual console/module help entrypoints, dummy
   child chains and failure propagation before proposing any real invocation.
   Observe the repository correction limits; do not weaken evidence to pass.
5. Only when viable, reconcile exact private artifacts, runtime configuration,
   destination eligibility and digests. Do not assume the prior failed-attempt
   workspace or existing GUI can be reused. Freeze a new/revised private plan
   within explicit authority and request approval for the exact one invocation.
6. Verify preparation cancellation first. The later committed-segment boundary
   stop requires its own exact approval and natural child completion. No
   automatic retry, kill, extra history, batch/immediate stop or downstream run.
7. Assess the approved verification plan, keeping fake and real evidence
   separate. Only after all acceptance criteria pass, perform the required
   same-change OpenSpec promotion/archive and strict validation. Commit/push,
   PR transitions, merge/deletion and release require appropriate fresh scope;
   do not infer authority from the earlier PR #63 workflow.

The full installation hash boundary remains intact. Existing failed/stopped
workspaces and residual staging are not cleanup targets. Running, cancelled,
stopped, partial or unverified results must never reach Sumtally as success.
Do not promise an elapsed completion time from the old stage estimates; update
estimates only when new actual evidence supports them.

## 2026-09-11 end-of-day checkpoint

This section supersedes every earlier stopping point and next-session order in
this document. The branch remains
`feature/improve-phits-preflight-responsiveness`, based on
`d18478f16f61e60bf9d1ba6244d24a40fa75b23d`. The intended checkpoint is the
tip of that same remote feature branch; inspect `git log -1`, status and both
index/working diffs after fetching it. The active OpenSpec change remains
unarchived. No PR, merge, branch deletion, tag change or release was performed.

The private recorder blocker was resolved without changing public runtime
code. Startup-wide Python profiling was replaced in the private harness by
explicit child creation/wait/exit records. Module and installed-entrypoint help,
dummy process chains, failure propagation, synthetic controller cases and a
visible synthetic Tk cancellation path were qualified. The recorder and raw
evidence remain private and outside Git.

The separately approved real GUI boundary-stop attempt then completed. Exactly
one PHITS child was launched; its independently recorded exit code was 0 and
its request-to-wait duration was 96.89 seconds. The controller exited 4 after
the requested segment boundary, with one active segment successful, three
active segments still pending, zero failed, and Sumtally disabled. All seven
observed OS members exited, the terminal receipt matched, downstream validation
rejected the stopped result, the workspace lease was released, and all 15
frozen inputs were unchanged. The GUI was observed in that stopped state and
closed normally. No second Run, retry, history increase, batch stop, immediate
stop, Sumtally or other real tool was invoked.

Functional boundary stopping therefore passed, but performance acceptance
failed. PHITS itself took about 97 seconds while the controller took about
2142.719 seconds (35 minutes 43 seconds). Code inspection attributes the large
overhead to repeated complete membership and SHA-256 scans of the configured
PHITS installation. This installation-wide scan is not useful for the requested
workflow and must be removed before acceptance. Do not archive or describe the
current implementation as ready.

The human directed the next revision to use the following simpler contract:

- Do not enumerate or hash the configured PHITS installation tree.
- Check the explicitly selected PHITS executable at launch, while continuing
  to bind workspace inputs and validate required results, exit/stop evidence,
  ownership and downstream eligibility.
- Treat the exact PHITS `batch.out` control/progress files as mutable. They may
  be monitored or retained, but a user edit such as changing the remaining
  batch count from `0` to `-1` must not produce an artifact-mutation error.
- A mutable `batch.out` is not completion evidence by itself. An early or
  partial result must still satisfy the existing result and stop/completion
  gates before downstream use; incomplete, stopped or unverified work must not
  be passed to Sumtally as normal success.
- Preserve fixed 6 MV and fixed-field 3D-CRT physics, geometry, DICOM semantics,
  MU, dose conversion, declared dose-output validation and path safety.

This direction is approved at the product level, but its detailed OpenSpec
wording has not yet been revised or approved. The current proposal/design/delta
still says complete installation membership and SHA-256 validation is retained;
that text is stale for the next implementation. Update the active proposal,
design, tasks, verification plan and relevant delta first, run strict OpenSpec
validation, and obtain one concrete yes/no approval of that reviewable contract
before changing runtime code.

A PHITS PDD tally may carry relative error values inside `deposit-pdd.out`.
The current unstaged correction therefore requires an error companion only for
the manifest-selected primary 3D dose output. All declared primary outputs are
still required, and optional error companions are bound when present. A focused
regression test covers a secondary PDD output with embedded relative error.

The final checkpoint validation used the repository virtual environment,
`PYTHONUTF8=1`, Tk tests enabled, and fresh short ASCII pytest basetemps.
The focused public-tree tests passed 10 in 0.07 seconds; compilation passed; the
full suite passed 1200 with 11 skipped in 213.12 seconds. Public-tree audit
passed for 331 tracked files. Active-change strict validation and all 16
current-spec strict validations passed, as did Git whitespace/diff/status
checks. Earlier focused preflight tests passed 124 with 1 skipped. A
system-Python run failed 45 tests because it used an older pydicom; the required
repository-venv run passed without a runtime workaround. Preserve that failure
history.

At this checkpoint the original 20 staged paths and six tracked unstaged
updates were preserved, then all tracked changes were intended for a single
incomplete-work checkpoint commit. Ignored private closure helpers and all
external plans, paths, PHITS outputs and raw recorder evidence remain local and
must not be added. The pushed checkpoint is for development transfer only; it
does not represent completed acceptance or publication readiness.

### Next-session order

1. Read the repository rules, this authoritative checkpoint, and the complete
   active OpenSpec change. Confirm the feature-branch tip, status, remote and
   tags. Do not restart stages 1–4a or the completed recorder investigation.
2. Revise the active OpenSpec contract for bounded executable checking and
   mutable `batch.out`, validate it strictly, and request its one yes/no human
   approval before runtime implementation.
3. Implement the smallest revision, updating tests that currently require
   installation membership/hash mutation detection and adding meaningful
   mutable-`batch.out` coverage. Keep all other result/downstream guards.
4. Run focused tests, compilation, the Tk-enabled full suite with a fresh short
   ASCII basetemp, public-tree audit, strict OpenSpec validation and final Git
   diff/status checks.
5. Use fake runners and synthetic Tk checks for development. Ask separately
   before any new real PHITS invocation. Use GPT-6 Astra and announce it before
   any Computer Use GUI action; use GPT-5.6 Sol for other work.
6. Only after the revised acceptance criteria pass, promote/archive the active
   OpenSpec change and validate it. Obtain separate authorization for subsequent
   commit/push, PR actions, merge, branch deletion or release as applicable.

## 次回の開始プロンプト

> 2026-09-11 の続きです。AI_AGENT_RULES.md と AGENTS.md を読み、
> docs/development-handoff-2026-09-10-phits-preflight.md と
> openspec/changes/improve-phits-preflight-responsiveness/ の文書を確認してください。
> feature/improve-phits-preflight-responsiveness のtip、status、diff、history、remote、tagsを
> 確認し、2026-09-11 end-of-day checkpointを最新の再開点として扱ってください。
> private記録器の問題と実GUIの境界停止確認は完了済みです。再実行しないでください。
> 実PHITS自体は約97秒でしたが、C:\phits全体の反復走査によりcontroller全体が約35分43秒となり、
> 性能受入は不合格です。C:\phits全体の走査を廃止し、選択した実行ファイルとworkspace内の
> 必要な証拠だけを確認する方針です。batch.outは手動変更可能な制御・進捗ファイルとして、
> 変更だけでartifact mutation errorを出さないでください。未完了・停止済み・未検証結果は
> Sumtallyへ正常完了として渡さないでください。
> まずOpenSpecのproposal、design、tasks、verification plan、deltaをこの方針へ更新し、strict検証後、
> runtime変更前に一つの具体的なyes/no質問で承認を求めてください。
> fixed 6 MV・3D-CRTのphysics、geometry、DICOM semantics、MU、線量換算を変更しないでください。
> focused、compile、Tk有効の全pytest、public-tree audit、OpenSpec strict、Git確認を行い、
> pytest basetempは毎回新しい短いASCIIパスにしてください。新しい実PHITS起動は別途承認が必要です。
> 受入完了前にarchiveせず、commit、push、PR、merge、branch削除、releaseを推測しないでください。
