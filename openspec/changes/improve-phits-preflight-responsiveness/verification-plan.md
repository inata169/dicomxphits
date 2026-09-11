# Verification plan

## Real boundary-stop attempt did not meet acceptance (2026-09-11)

The separately approved fresh one-invocation attempt performed one normal GUI
launch and one Run click. Windows locked before first commitment; on resumed
observation, the first PHITS child had already exited and result verification
was in progress. No stop, cancel, retry or downstream operation was sent.
The invocation subsequently failed with `Required completed segment artifact
is missing`: the required `deposit-pdd_err.out` was absent, while the primary
3D dose/error outputs existed. Exactly one PHITS child naturally exited 0;
the controller chain exited 2 with gate_failed and zero validated segments.
No other active segment launched. This does not qualify boundary-stop or
successful calculation acceptance.

The failed preflight receipt records 1591.859 seconds, 73793 scanned files and
338845733811 cumulative bytes read, not newly allocated output bytes. Process
records indicate approximately 1011 seconds before child creation, 94 seconds
to child wait return and 488 seconds thereafter to controller wait return.
The GUI terminal duration differed from the stored duration; no claim of exact
GUI timing acceptance is made. All seven OS members ended naturally, with zero
active members, zero limit terminations and no acquisition gaps. The frozen
observer rejected the unexpected controller exit, as required. GUI was closed
normally after controller exit. Outputs, private evidence and residual staging
remain preserved. No real rerun was performed. Keep this change active and
unpublished.

Post-exit input digests remained unchanged, the existing execution lease was
available, and the downstream preflight gate rejected this failed result.
Post-observation checks used the repository venv, PYTHONUTF8=1 and Tk enabled:
focused segment-stop/preflight and GUI-loop/observation tests passed 88 cases
in 38.82 seconds; compileall src passed; full pytest passed 1199 with 11 skips
in 203.28 seconds. Each pytest used a distinct new short ASCII basetemp.
Public-tree audit passed for 331 tracked files; strict active-change and all
16 current-spec validations passed; working/index diff checks passed.
Only this verification record and ignored private records were changed during
resumed observation. Existing staging was preserved. Runtime and normative
specifications were unchanged; no archive, commit, push or release occurred.

Read-only diagnosis then confirmed that the preserved PDD primary output itself
contains the `r.err` relative-error column. PHITS naturally returned 0 with that
PDD output, the 3D primary/error pair and no separate PDD error companion. The
pre-existing segment-success gate requires the manifest-selected 3D primary/
error pair; the new execution binding had instead inferred an error companion
for every declared tally and therefore rejected this valid secondary-output
shape during post-child evidence capture.

After explicit approval, the binding was corrected to require all declared
primary outputs plus only the selected 3D error companion. Secondary error
companions remain allowed persistent outputs and are included in evidence when
present. A fake-runner regression reproduces an embedded PDD `r.err` column
without a companion file and verifies successful downstream validation. The
targeted case passed, followed by 124 focused preflight/retry/runner tests with
one unchanged platform skip. The first focused-suite run used an in-repository
basetemp and produced two environment-only failures (public-tree workspace
rejection and missing child-process source path); the identical suite passed
with an external short ASCII basetemp and explicit source path.

Final public checks used the repository venv, PYTHONUTF8=1, Tk enabled and a
fresh external short ASCII basetemp: compileall passed and full pytest passed
1200 cases with 11 unchanged platform skips in 190.76 seconds. An earlier full
run mistakenly used system Python with pydicom 2.4.4 and produced 45 common
DICOM-write failures (`1155 passed, 11 skipped`); no code was changed for those
failures, and the repository venv with pydicom 3.0.2 passed the identical suite.
Public-tree audit passed for 331 tracked files. Strict validation passed for the
active change and all 16 current specifications. Fresh real boundary-stop
acceptance remains required.

## Real GUI preparation cancellation accepted (2026-09-11)

After the bounded receipt fix, the human separately approved the frozen single
GUI/Run/cancel attempt, complete installation read scope and disclosed calculation
race upper bound. The new workspace contained only the 15 explicitly approved
copied inputs; a fresh observer package/evidence/settings destination was used.
The ordinary GUI, controller command builder, runner and scanner were unchanged.
Computer use selected the new workspace and verified the displayed executable,
maxcas=1000, maxbch=10 and eight OpenMP threads; Run and Cancel preparation were
each clicked once. No preparation regeneration was performed.

The actual GUI showed owned preparing progress (106 files / 1823200396 bytes,
elapsed eight seconds) and an enabled preparation-cancellation control. After
the click it returned to Ready, showed Preparation cancelled and explicitly kept
Sumtally disabled. The terminal receipt was cancelled_before_launch with
child_committed=false, a request identity, matching actual ControllerPipe nonce,
sequence 80, 475 files / 4117609574 bytes and elapsed 19.531 seconds. No execution
summary or calculation result was produced. Receipt/error readback was deferred
until controller exit; no agent polling of workspace progress files occurred
during execution. No access-denial error was observed in this attempt; this does
not measure how often the bounded replacement retries were exercised.

Explicit Popen evidence records one controller creation and wait return 5.
After normal GUI close, independent OS evidence reconciled all six members,
six start records and six exit records, zero active/limit-terminated processes,
no acquisition gaps and a naturally exited root. All three controller layers
exited 5; GUI layers and console host exited 0. No PHITS executable was launched.
Ten negative evidence mutations were rejected. The observer's legacy synthetic
label describes its normalized evidence validator only; actual GUI/receipt/exit
checks establish this real preparation-cancellation acceptance separately.

Post-exit read-only verification matched the nonce/receipt and input digests,
confirmed the downstream validator rejects incomplete preparation and briefly
acquired/released the existing execution lock with create=False. Lock bytes were
unchanged. Workspace membership is exactly the original 15 inputs plus the
persistent ownership file and terminal preflight receipt; all input hashes are
unchanged. The persistent lock filename is expected and is not an active owner.
GUI window absence and complete natural process exit were confirmed.

This passes real GUI preparation-progress/cancellation acceptance. It does not
pass a PHITS calculation or real committed-segment boundary-stop acceptance;
those remain outside this consumed one-invocation approval. Preserve this attempt
and the earlier failures. Keep the change active until remaining acceptance is
met; no promotion/archive, commit, push or release follows from this result.

Post-acceptance public checks used the repository venv with PYTHONUTF8=1 and
DICOMXPHITS_TEST_TK=1, and distinct fresh short ASCII basetemps:

- `python -m pytest -q -p no:cacheprovider --basetemp <fresh-short-ascii-temp> tests/test_segment_preflight.py tests/test_security_boundaries.py tests/test_segment_stop.py tests/test_gui_preflight_loop.py tests/test_phits_observation_tk.py`:
  109 passed, 8 skipped, 42.93 seconds.
- `python -m compileall src`: passed after focused checks.
- `python -m pytest -q -rs -p no:cacheprovider --basetemp <another-fresh-short-ascii-temp>`:
  1199 passed, 11 skipped, 217.28 seconds. Tk ran; nine symlink-privilege and two
  FIFO skips remain unchanged.
- `python tools/verify_public_tree.py`: passed, 331 tracked files.
- `openspec.cmd validate improve-phits-preflight-responsiveness --strict` and
  `openspec.cmd validate --specs --strict`: passed, including all 16 public specs.
- Working/index `git diff --check`, diff/stat and status reviewed. The original
  20 staged files remain unchanged. This turn updated only the public tasks and
  verification record, with new private helper/settings/result files kept ignored
  and evidence outside Git. No runtime, physics, DICOM meaning or normative
  specification change this turn. Stop after the authorized successful attempt;
  remaining real acceptance requires its own plan and approval.

## Approved bounded receipt replacement fix (2026-09-11)

The human approved a minimal production fix and synthetic verification: at most
three replacement attempts and two requested 50 ms waits, only for Windows
WinError 5/32 at atomic replacement of the preflight receipt. The guarded writer
retains the same flushed bytes and temporary file, ownership and directory locks,
and rechecks the target before each attempt. Other paths and errors remain
single-attempt; guard checks are outside the retry exception handler. Persistent
denial still raises and cannot acknowledge cancellation or unlock downstream.
This is publication retry, not automatic PHITS/preparation/scan execution retry.
The requested 100 ms delay is not an upper bound on OS scheduling or I/O duration.

Nine added tests cover one/two transient denials, exhaustion at three attempts,
unrelated errors and outputs, native Windows read handles released/held across
attempts, failed guard revalidation and cancellation durability/downstream gates.
The native cases use actual file opens/replacement failures, with the sleep hook
controlling release deterministically; no wall-clock race or real PHITS is claimed.
The old failed real workspace and private diagnostic evidence were not reused or
changed. No new external private package was needed: pytest generated only fresh
synthetic fixtures. Physics, geometry, DICOM meaning, MU, dose and normative
specifications remain unchanged. This bug fix restores the existing publication
contract; it does not add a new capability or satisfy outstanding real acceptance.

Focused checks used the repository venv with PYTHONUTF8=1 and
DICOMXPHITS_TEST_TK=1, each with a fresh short ASCII basetemp:

- `python -m pytest -q -p no:cacheprovider --basetemp <fresh-short-ascii-temp> tests/test_segment_preflight.py tests/test_security_boundaries.py tests/test_segment_stop.py tests/test_gui_preflight_loop.py tests/test_phits_observation_tk.py`:
  initial seven added cases: 107 passed, 8 skipped, 39.34 seconds; after the two
  guard/durability cases: 109 passed, 8 skipped, 39.55 seconds. Both runs passed;
  the skips are six unavailable symlink cases and two FIFO cases.
- `python -m compileall src`: passed after final focused checks.
- `python -m pytest -q -rs -p no:cacheprovider --basetemp <another-fresh-short-ascii-temp>`:
  1199 passed, 11 skipped, 198.55 seconds. Tk tests and the new Windows native
  reader tests ran; nine symlink-privilege and two FIFO skips remain unchanged.
- `python tools/verify_public_tree.py`: passed, 331 tracked files.
- `openspec.cmd validate improve-phits-preflight-responsiveness --strict` and
  `openspec.cmd validate --specs --strict`: passed, including all 16 public specs.
- Working/index `git diff --check`, diff/stat and status reviewed. Original 20
  staged files preserved, no staging changes. Tracked unstaged changes now comprise
  safe_output.py, test_segment_preflight.py, design.md, tasks.md and this record.
  The bounded runtime fix is complete for synthetic validation. Real cancellation
  and boundary-stop acceptance remain outstanding; no real rerun, failed workspace
  reuse, commit, push, archive or release. A new artifact freeze and separate exact
  approval are required before any real invocation; old frozen code digests no
  longer qualify this modified runtime.

## Approved primitive/guard isolation (2026-09-11; synthetic only)

The human approved a fresh synthetic comparison of Windows replacement and the
existing guard, excluding application changes and real execution. The private
script and interpretation rules were frozen before a single execution. Nine
fresh cases compared bare os.replace, os.replace inside WorkspaceOutputGuard,
and unchanged WorkspaceOutputGuard.write_bytes, each with no reader and with
native read handles using read/write or read/write/delete sharing.

| Reader | Bare replacement | Guarded replacement | Existing guarded writer |
| --- | --- | --- | --- |
| None | Success | Success | Success |
| Read/write sharing | WinError 5 | WinError 5 | WinError 5 |
| Read/write/delete sharing | WinError 5 | WinError 5 | WinError 5 |

All nine observations satisfied the predeclared evidence/integrity checks;
the diagnostic exited 0. This is a completed isolation matrix, not nine successful
writes or a passing fix. The shared-delete cases were explicitly exploratory in
this newly approved diagnosis; the preceding expected-success failure remains
failed and was not rerun or reclassified. Each successful write produced exact
new bytes; each denied write preserved exact old bytes. All native handles closed.
Four bare/guarded-primitive replacement files remain as private failure evidence;
the unchanged writer cleaned only its own generated temporary files.

The project guard is not necessary for this denial: the unguarded primitive
reproduced it. Removing directory guards or merely changing a reader's share flags
is therefore not a supported fix. The result isolates the failure below the
project guard, but does not distinguish Windows/filesystem/filter internals or
identify which reader caused the earlier real failure. No security policy, ACL,
guard, existing workspace, old evidence or application source was changed. No
controller, GUI, recorder or real external tool ran in this matrix. Further OS
investigation is not required to claim this limited isolation result; a production
fix remains a separately approved task and must preserve guarded atomic publishing.
Real acceptance remains outstanding; keep the OpenSpec change active.

Post-isolation checks used the repository venv, PYTHONUTF8=1 and
DICOMXPHITS_TEST_TK=1, with distinct fresh short ASCII pytest basetemps:

- `python -m pytest -q -p no:cacheprovider --basetemp <fresh-short-ascii-temp> tests/test_segment_preflight.py tests/test_segment_stop.py tests/test_gui_preflight_loop.py tests/test_phits_observation_tk.py`:
  79 passed, 38.62 seconds.
- `python -m compileall src`: passed after focused checks.
- `python -m pytest -q -rs -p no:cacheprovider --basetemp <another-fresh-short-ascii-temp>`:
  1190 passed, 11 skipped, 187.71 seconds. Tk tests ran. Nine symlink-privilege
  and two FIFO skips remain unchanged.
- `python tools/verify_public_tree.py`: passed, 331 tracked files.
- `openspec.cmd validate improve-phits-preflight-responsiveness --strict` and
  `openspec.cmd validate --specs --strict`: passed, including all 16 public specs.
- Working/index `git diff --check`, diff/stat and status reviewed. The original
  20 staged files are preserved; tracked unstaged edits remain tasks.md and this
  record. The new private diagnostic/evidence is not staged. No runtime, physics,
  DICOM semantics or normative specification changed; no commit/push/archive/release.

## Approved receipt-sharing diagnosis (2026-09-11; partial, stopped)

The human approved read-only cause analysis and a fresh private synthetic
reproduction, explicitly excluding runtime fixes and real PHITS reruns. The
unchanged GUI polls read_receipt; its binary file handle remains open during
stream.read. Session.publish uses the guarded atomic os.replace writer. A private
four-case diagnostic was frozen before execution and used only newly generated
receipts, without a controller, recorder, GUI or real tool. A barrier extended the
actual read_receipt open/read window; the writer and Windows errors were not mocked.

- Reader already closed: publication succeeded, sequence advanced from 1 to 2.
- Actual reader deliberately held open: publication raised PermissionError,
  WinError 5 at temporary-to-receipt replacement, matching the real failure form.
- Native reader with read/write sharing: the same WinError 5 occurred.
- Native reader with read/write/delete sharing: unexpectedly also WinError 5;
  the predeclared expected-success comparison failed.

Thus three case expectations passed and one failed; the diagnostic process exited
1 and stopped, without retries, fixture/reference changes or production changes.
All failed publications preserved the previous receipt bytes and sequence; the
writer cleaned its own temporary files. The diagnostic reader thread finished and
all explicitly opened native handles were closed. Raw evidence remains private.

This establishes that an overlapping read can reproduce the current writer error
on this machine, not that sharing flags alone solve it. It does not identify which
reader, if any, caused the real attempt's denial; GUI and agent readback were not
isolated there. The native shared-delete comparison needs explanation before any
fix is selected. Microsoft documents delete sharing as permitting delete/rename
access, not as an unconditional guarantee that replacement succeeds:
https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew

No failed real workspace or prior evidence was modified/reused, no real tool was
launched, and no runtime, physics, DICOM meaning or normative specification changed.
Keep the change active. Further diagnostic expansion or a fix needs a human
decision; a real invocation still needs a newly frozen plan and exact approval.
Post-diagnosis public checks used the repository venv with PYTHONUTF8=1 and
DICOMXPHITS_TEST_TK=1, and a different fresh short ASCII basetemp for each pytest:

- `python -m pytest -q -p no:cacheprovider --basetemp <fresh-short-ascii-temp> tests/test_segment_preflight.py tests/test_segment_stop.py tests/test_gui_preflight_loop.py tests/test_phits_observation_tk.py`:
  79 passed, 37.80 seconds.
- `python -m compileall src`: passed after focused tests.
- `python -m pytest -q -rs -p no:cacheprovider --basetemp <another-fresh-short-ascii-temp>`:
  1190 passed, 11 skipped, 194.79 seconds. Tk tests ran; the skips comprise nine
  unavailable symlink-privilege cases and two unavailable FIFO cases.
- `python tools/verify_public_tree.py`: passed, 331 tracked files.
- `openspec.cmd validate improve-phits-preflight-responsiveness --strict` and
  `openspec.cmd validate --specs --strict`: passed, including all 16 public specs.
- Working/index `git diff --check`, diff/stat and status reviewed. The original
  20 staged files remain preserved. Tracked unstaged changes are only tasks.md
  and this verification record; the private diagnostic and evidence are not staged.
  No commit, push, archive or release. Public-check success does not override
  the diagnostic exit 1 or satisfy outstanding real acceptance.

## Separately approved real-GUI attempt (2026-09-11; failed)

The human approved one fully specified fresh GUI/Run/preparation-cancellation
attempt, including the complete read-only installation binding and disclosed
calculation race upper bound. The qualified private observer/recorder code was
copied unchanged into a new dedicated package, with new evidence and isolated GUI
settings. The prepared input/source/executable digests passed before launch.

The unmodified GUI launched successfully and selected the prepared workspace and
planned executable. Run was clicked once. Preparation then failed with WinError 5
(access denied) during atomic replacement of the preflight receipt, before any
Cancel preparation action could be issued. The controller naturally exited 2,
not cancellation exit 5. Terminal receipt: phase failed, child_committed false,
no request identity, 112 scanned files / 2277205852 bytes / 10.469 seconds. The
execution summary reports gate_failed. This is not cancellation acceptance.

The GUI showed failure and that Sumtally remained disabled; after acknowledgement
it returned to idle and was closed normally. Independent job accounting reconciled
all six OS members with six start/exit records, no acquisition gaps, zero active
and zero limit terminations. The GUI layers/console host exited 0; the installed
controller launcher/venv/interpreter chain all exited 2, agreeing with explicit
Popen wait evidence. No PHITS executable was launched in this complete family.
The frozen validator rejected the application exit; its expected cancellation
exit was not relaxed. All 15 prepared input hashes remained unchanged.

No Cancel/Stop/retry, PHITS calculation, CT2PHITS, preparation regeneration,
downstream action, forced termination, reference adjustment or code correction
followed. Raw failure receipts and private evidence are retained. That one-launch
approval is consumed and the workspace is now failed, not an automatic reuse
target. The precise access-denial cause remains unproven; further diagnosis or
synthetic reproduction needs a human decision, and a new real invocation needs
its own fixed plan and approval. Keep this change active; do not archive/release.
GUI polling and agent read-only receipt readback occurred during this attempt;
their possible file-sharing effects were not isolated. Do not attribute the
access denial to PHITS, input data or a particular reader without new evidence.

Post-attempt public checks (not a fix or a real retry): repository venv with
PYTHONUTF8=1 and DICOMXPHITS_TEST_TK=1, distinct fresh short ASCII basetemps:

- `python -m pytest -q -p no:cacheprovider --basetemp <fresh-short-ascii-temp> tests/test_segment_preflight.py tests/test_segment_stop.py tests/test_gui_preflight_loop.py tests/test_phits_observation_tk.py`:
  79 passed, 43.06 seconds.
- `python -m compileall src`: passed after focused checks.
- `python -m pytest -q -rs -p no:cacheprovider --basetemp <another-fresh-short-ascii-temp>`:
  1190 passed, 11 skipped, 216.43 seconds. Tk tests ran; nine symlink-privilege
  and two FIFO skips remain unchanged.
- `python tools/verify_public_tree.py`: passed, 331 tracked files.
- `openspec.cmd validate improve-phits-preflight-responsiveness --strict`:
  passed; `openspec.cmd validate --specs --strict`: all 16 passed.
- Working/index `git diff --check`, diff/stat and status reviewed. Original 20
  staged files preserved; tracked unstaged changes remain the two task/verification
  records. No public runtime, physics or normative specification change, commit,
  push, archive or release. Passing synthetic checks do not resolve the real error.

## Natural-lifetime observer check (2026-09-11; synthetic only)

The human approved a separate private adapter retaining scoped observation past
the former 30-second help deadline, excluding real PHITS and the prepared real
workspace. The fresh adapter records a nonterminal elapsed-time warning rather
than ending acquisition for that reason. It continues until the original job
has no active members, the root has naturally exited and pending notifications
are drained. Existing acquisition errors still fail/unverify; this is not an
observer-crash recovery guarantee. No kill, global monitoring or relaxed terminal
identity/parent/accounting check was introduced.

The new package passed both predeclared cases on its first attempt: plain GUI
bootstrap help and actual ControllerPipe-to-installed-console help after a
35-second synthetic idle interval. The latter recorded an observing/nonterminal
warning at 30.016 seconds with three active OS members and an unsignalled root.
The console child was created after the former deadline; complete acquisition
continued for 36.078 seconds, ending with six members, zero active, zero limit
terminations, no gaps and a naturally exited root. There was no visible GUI,
real preparation scan or PHITS calculation. The delay models waiting time only;
it does not certify real GUI configuration, cancellation or calculation timing.

Both captures rejected ten normalized mutations each. Read-only readback passed
the explicit over-30-second/late-child/warning assertions and rejected all 30
raw/log mutations. The unchanged strict validator passed three fabricated
positives and 114 negatives. Recorder and validator copies were unchanged; only
private lifetime handling, the synthetic delayed driver and its checks changed.
No old package was modified or rerun. All new evidence remains private.

This closes the elapsed-time acquisition limit for the bounded synthetic task.
The real invocation command/environment/role plan and runtime/input/artifact
freeze still require completion before exact execution approval. No real Run,
boundary stop, downstream action, archive or release follows from this result.
Public closeout checks used the repository venv with process-local PYTHONUTF8=1
and DICOMXPHITS_TEST_TK=1 and a new short ASCII basetemp for each pytest run:

- `python -m pytest -q -p no:cacheprovider --basetemp <fresh-short-ascii-temp> tests/test_segment_preflight.py tests/test_segment_stop.py tests/test_gui_preflight_loop.py tests/test_phits_observation_tk.py`:
  79 passed, 37.60 seconds.
- `python -m compileall src`: passed after focused tests.
- `python -m pytest -q -rs -p no:cacheprovider --basetemp <another-fresh-short-ascii-temp>`:
  1190 passed, 11 skipped, 196.82 seconds. Tk tests ran; nine symlink-privilege
  and two FIFO skips remain unchanged, with no security-policy changes.
- `python tools/verify_public_tree.py`: passed, 331 tracked files.
- `openspec.cmd validate improve-phits-preflight-responsiveness --strict`:
  passed; `openspec.cmd validate --specs --strict`: 16 passed.
- Working/index `git diff --check`, diff/stat and status checked. The original
  20 staged files remain uncommitted; only the two existing verification/task
  records have tracked unstaged changes. Private code and the updated private
  invocation draft are ignored. Public runtime/physics/specification unchanged;
  no real execution, old-workspace modification, archive, commit or publication.

## Ordinary entrypoint connection checks (2026-09-11; help only)

The human approved a fresh private observer/bootstrap implementation and grouped
help/synthetic qualification, excluding real PHITS, the prepared real candidate
and old verification-workspace reuse. No public runtime or normative delta was
changed. The plain bootstrap imports the existing GUI main and forwards its
ordinary argv, without replacing the GUI builder, validation, tool profile,
runner or scanner. Its help branch was tested; no visible GUI was opened here.

The installed console archive was inspected without execution first. It imports
the existing controller main and identifies the repository venv Python in its
shebang. Exact images, parent-role chains and zero exits were frozen before each
help batch. A newly armed, fresh job observed only that launched family, with
limited-query retained handles, independently queried native parent IDs, natural
exit status and accounting/notification reconciliation. The previous strict
normalized validator and direct Popen recorder were copied unchanged into new
private packages. No profile/audit hook, global subscription, kill limit,
termination, fixture self-role injection or reference relaxation was added.

- Module help: passed, three OS members including one proven console host.
- Installed console help: passed, four OS members including one console host;
  console launcher, venv redirector and Python interpreter matched the plan.
- Plain GUI bootstrap help: passed, three OS members and no window or stage run.
- Actual ControllerPipe to PATH-resolved installed console help: passed, six OS
  members. The exact source ControllerPipe performed its ordinary stdin/stdout/
  stderr pipe setup, nonce append, drain and wait. Its driver supplied help, not
  a simulation workspace or runner override. Help stdout was present, stderr
  empty, return code zero and the client released after exit. PATH resolution,
  source module location and recorded argv/nonce were checked privately.
- All four captures reconciled every member with zero active processes, zero
  limit terminations, no acquisition gaps and naturally completed root waits.
  Startup records agreed with native parents; the actual Popen child creation
  and explicit wait result agreed with the independently observed launcher PID,
  parent and exit. Python records alone were not used to infer no launch.
- Ten normalized mutations per capture were rejected (40 total). Read-only
  revalidation of the actual pipe capture passed and rejected 30 raw/log
  mutations. The unchanged normalized checker passed three mock positives and
  114 negatives. Mock records remain distinct from live OS acquisition.

Both new packages succeeded on their first attempts. No failure, correction,
automatic retry or cleanup occurred. Old packages were read only as approved
source references; all new evidence used fresh destinations. Source inventories
were frozen before launch and rechecked afterwards. Raw evidence, argv, local
paths and digests remain private/ignored, not tracked.

This resolves the bounded ordinary-startup/pipe qualification gap, not real-GUI
acceptance. The observer's runnable test entrypoint remains help-only. A real
invocation still needs its own frozen GUI command/environment, complete role
plan, input/runtime/artifact digests, new evidence destination and exact approval;
these tests do not grant that authority. No prepared real input, PHITS process,
CT2PHITS, Sumtally or downstream conversion was invoked. Preparation cancellation
and committed-segment boundary stopping remain unverified; keep this change active.

Public checks for this implementation round used the repository venv, process-
local PYTHONUTF8=1 and DICOMXPHITS_TEST_TK=1, and a different fresh short ASCII
basetemp for each pytest invocation:

- `python -m pytest -q -p no:cacheprovider --basetemp <fresh-short-ascii-temp> tests/test_segment_preflight.py tests/test_segment_stop.py tests/test_gui_preflight_loop.py tests/test_phits_observation_tk.py`:
  79 passed, 38.11 seconds.
- `python -m compileall src`: passed after focused validation.
- `python -m pytest -q -rs -p no:cacheprovider --basetemp <another-fresh-short-ascii-temp>`:
  1190 passed, 11 skipped, 192.92 seconds. Tk tests ran; skips remain nine
  symlink-privilege cases and two unsupported FIFO cases, without policy changes.
- `python tools/verify_public_tree.py`: passed, 331 tracked files.
- `openspec.cmd validate improve-phits-preflight-responsiveness --strict`:
  passed; `openspec.cmd validate --specs --strict`: all 16 passed.
- Working/index `git diff --check`, diff/stat and status reviewed. Original 20
  staged files remain uncommitted and unchanged in the index. Only tasks and
  this verification record have tracked unstaged changes; private development
  packages and planning artifacts are ignored. No commit, push, PR operation,
  archive, release, public physics or normative specification change occurred.

## Proposal-only checks

Check delta structure and safety/compatibility consistency; run strict OpenSpec
validation for this change and current specs. Run existing focused stop/retry/GUI
tests, then compile, full pytest, public-tree audit and Git diff/status checks.
These checks do not demonstrate the proposed behavior before implementation.

### Proposal validation record (2026-09-10)

Python 3.12 repository environment; no runtime/test source edits or real tool
launches. Commands used the repository environment's Python executable.

- `openspec.cmd validate improve-phits-preflight-responsiveness --strict`: passed.
- `openspec.cmd validate --specs --strict`: 16 passed.
- `python -m pytest -q -p no:cacheprovider --basetemp <fresh-temp> tests/test_segment_stop.py tests/test_segment_retry.py tests/test_gui.py`:
  186 passed, 1 skipped, 59.04 seconds with process-local `PYTHONUTF8=1`.
- `python -m compileall src`: passed.
- `python -m pytest -q -p no:cacheprovider --basetemp <fresh-ascii-temp>`:
  1135 passed, 12 skipped, 209.57 seconds with default encoding mode.
- `python tools/verify_public_tree.py`: passed, including the six staged
  proposal documents (327 indexed files).
- Git working/index diff whitespace checks and status/stat review: passed;
  six proposal documents only, no commit or push.

Environment limitations are not resolved by this proposal: the default pytest
temporary parent was inaccessible (154 setup errors); a fresh non-ASCII parent
with default encoding produced four existing test decode failures. Process-local
UTF-8 resolved those focused failures. The full run on that non-ASCII parent
still produced 3 failures, 1132 passes and 12 skips. The failures were
`test_manual_smoke_happy_path_uses_tmp_path_only`,
`test_protected_source_snapshot_excludes_unmanifested_setup_py`, and
`test_run_rebinds_verified_prepared_evidence_after_workspace_relocation`.
All three passed on a fresh ASCII parent (2.65 seconds), followed by the passing
full ASCII-parent run above. This does not certify arbitrary-path compatibility.
The PowerShell OpenSpec wrapper was blocked by execution policy; the existing
`.cmd` wrapper passed without changing any system policy.

Implementation is now human-approved and in progress. Real-GUI acceptance
remains unperformed. No real timing claim follows from synthetic tests.

### Implementation validation record (2026-09-10; acceptance pending)

- Initial focused failures were an unsupported UTC timestamp suffix and a GUI
  cancellation-result branch inserted in the wrong function. Each was corrected
  and rechecked; the subsequent focused run passed 204 tests with 1 skip.
- An extended focused run stopped with 335 passed, 1 skipped and 1 failed:
  `test_run_rebinds_verified_prepared_evidence_after_workspace_relocation`.
  Its synthetic execution summary reports a missing-file error when writing
  the long atomic coordinate-summary temporary pathname, after conversion.
  The same test passed unchanged using a shorter fresh ASCII temporary parent
  (1 passed, 1.17 seconds). This is consistent with a Windows path-length
  limitation, not evidence of a preflight-gate regression. No RTDOSE validation
  or coordinate semantics were weakened; arbitrary long-path support is not
  certified. Existing failed synthetic artifacts were retained.
- Added coverage that verification-phase presentation retains the existing
  successful-segment ETA: 2 passed, 123 deselected, 1.23 seconds.
- Extended focused command:
  `python -m pytest -q -p no:cacheprovider --basetemp <fresh-short-ascii-temp> tests/test_segment_preflight.py tests/test_segment_stop.py tests/test_segment_retry.py tests/test_gui.py tests/test_prepare_sumtally.py tests/test_prepare_rtdose.py tests/test_workspace_recovery.py`:
  404 passed, 1 skipped, 92.28 seconds. The added ETA parameter case was checked
  separately above and included in the subsequent full run.
- `python -m compileall src`: passed.
- `python -m pytest -q -p no:cacheprovider --basetemp <fresh-short-ascii-temp>`:
  1158 passed, 12 skipped, 201.26 seconds.
- `python tools/verify_public_tree.py`: passed, 329 indexed files.
- `openspec.cmd validate improve-phits-preflight-responsiveness --strict`
  and `openspec.cmd validate --specs --strict`: passed (16 current specs).
- `git diff --check`, `git diff --cached --check`, diff/stat and status review:
  passed. Changes remain staged and uncommitted on the feature branch.

### Receipt boundary checks (2026-09-10)

Inspection found that the GUI discarded its last accepted sequence after an
invalid read, allowing a later stale receipt to be accepted. The GUI now retains
an invocation-local high-water mark across missing, invalid or stale reads and
rejects regressing counters or changed content under the same sequence. A new
explicit invocation starts a new tracker. Terminal cancellation must match both
the GUI's known run and its actual cancellation request; absent identities do
not authorize a cancellation display.

Synthetic additions cover stale nonce/run/sequence, malformed and changed
receipts, missing or mismatched request identity, commitment/cancellation
contradiction, duplicate cancellation, controller failure before launch,
CLI exit 5 without an external executable, and relocated cancellation blocking
historical success. Focused command:
`python -m pytest -q -x -p no:cacheprovider --basetemp <fresh-short-ascii-temp> tests/test_segment_preflight.py tests/test_gui.py`:
159 passed, 1 skipped, 9.94 seconds; no new test failures.

After these boundary changes, `python -m compileall src` passed and the full
`python -m pytest -q -p no:cacheprovider --basetemp <fresh-short-ascii-temp>`
run passed 1171 tests with 12 skips in 203.57 seconds. Public-tree audit (329
indexed files), strict change/current-spec validation (16 current specs), and
working/index whitespace and Git status/stat checks passed. No commit or push.

### Hidden Tk and blocked-read checks (2026-09-10)

`tests/test_gui_preflight_loop.py` builds the real GUI in a dedicated withdrawn
Tk window with synthetic defaults, a fake tool profile/adapter/control pipe, and
the real segment controller. It does not read personal settings, open an
existing GUI, or invoke an external executable. A synthetic file read is held
with an event while real Tk callbacks request cancellation and continue ticking.
During the hold, the receipt is not cancelled, its request is not acknowledged,
the read handle stays open, another thread cannot obtain the workspace lease,
and Sumtally remains disabled. After release, handles close and the GUI displays
verified cancellation within one second; the lease then becomes obtainable.
A second case raises a read error after release and checks that failure takes
precedence over the queued cancellation. Neither case launches a PHITS child.

The first standalone cancellation case passed (1 passed, 3.05 seconds). An
intermediate related-suite run reported 193 passed and 2 skipped, including a
Tk initialization skip; this was not counted as read-failure coverage. Rerunning
the Tk cases exposed a test-harness timeout: it waited for a normal result even
after the GUI correctly handled an exception. The harness now observes worker
exit independently. A subsequent indentation error in test cleanup was fixed.
The same focused command with a fresh short ASCII temporary parent then passed
both cases (2 passed, 2.90 seconds). Tk initialization is only skipped for
missing tkinter or a non-Windows environment without a display; unexpected Tk
errors are not silently skipped. Scheduled test callbacks are cancelled during
cleanup. No runtime source changes were required in this verification round.

The subsequent full run did NOT pass: 1172 passed, 1 failed, 12 skipped and
4 warnings in 205.93 seconds. The read-failure Tk case timed out again, despite
the standalone pass. Warnings include Tk variable destruction outside the main
loop and a worker attempting to schedule a callback after the loop ended. This
indicates unresolved test lifecycle/thread isolation; it does not establish a
real PHITS defect. No real PHITS was invoked. The repeated timeout reaches the
repository inner-loop stopping condition, so no further automatic correction
or rerun was made. A proposed next step is per-case subprocess isolation with
deterministic thread/Tk teardown, without removing or weakening assertions;
that correction requires a new human decision. The integrated acceptance
remains incomplete. Compilation, public-tree audit (330 indexed files), strict
OpenSpec validation and Git whitespace checks passed, but do not override the
failed full suite.

### Human-approved Tk process isolation (2026-09-10)

After the stopping report, the human explicitly approved isolating each Tk
case in its own Python subprocess and rerunning validation without weakening
assertions. The parent pytest process no longer creates a Tcl interpreter.
Each child uses the same synthetic controller/GUI assertions, preserves the
one-second display bound after read release, and keeps its event loop alive
until all tracked workers exit. The parent checks a normal child exit, a passed
assertion marker and empty stderr, so late thread/Tk errors are not ignored.
The bounded child-process timeout applies only to this synthetic test harness,
not PHITS or any runtime control. Missing-Tk/display skips remain explicit.

`python -m pytest -q -x -rs -p no:cacheprovider --basetemp <fresh-short-ascii-temp> tests/test_gui_preflight_loop.py`:
2 passed, 4.72 seconds. No runtime source or public-contract change was needed.

After isolation, `python -m compileall src` passed and
`python -m pytest -q -rs -p no:cacheprovider --basetemp <fresh-short-ascii-temp>`
passed 1173 tests with 12 explicit environment-dependent skips in 179.00
seconds. Both new Tk cases ran and passed; no thread/Tk warnings were reported.
`python tools/verify_public_tree.py` passed (330 indexed files), as did
`openspec.cmd validate improve-phits-preflight-responsiveness --strict`,
`openspec.cmd validate --specs --strict` (16 current specs), and Git working/index
whitespace, stat and status checks. The earlier failed results remain recorded
above. Changes remain staged and uncommitted on the feature branch; no push,
archive or release was performed.

These synthetic tests do not certify real-device I/O deadlines or real PHITS
execution. Private real-GUI acceptance remains required before archive.

### Downstream GUI precedence and explicit continuation (2026-09-10)

The human approved a bounded correction after the acceptance comparison found
that RTDOSE GUI state ignored newer preflight evidence. A synthetic reproducer
failed as expected: an existing prepared RTDOSE was still reported as prepared
after a new preparing receipt. The GUI now uses the existing preflight
downstream validator, displays `PHITS incomplete`, and disables Sumtally/RTDOSE
actions (including recovery) for incomplete or invalid preflight evidence.
The overwrite option cannot bypass this state. Legacy workspaces without a
receipt continue through their existing validation. No runtime dependencies,
physics, dose, coordinate semantics or result validators were weakened.

Tests cover historical prepared and completed RTDOSE against preparing,
cancelled, failed and malformed receipts. The isolated Tk tests also assert
the actual downstream buttons and navigation state after cancellation/failure.
New controller tests verify both ordinary and selective cancellation followed
by explicit fresh preflight: existing file bytes/mtimes are unchanged by
cancellation, a selective preview still validates the original parent, only
pending segments run, retained segment bytes/mtimes remain unchanged, and fresh
success passes downstream gates and clears the GUI preflight block.

The initial corrected focused run passed 167 tests with 1 skip (15.76 seconds).
With completed-result and retained-output checks added,
`python -m pytest -q -x -p no:cacheprovider --basetemp <fresh-short-ascii-temp> tests/test_gui.py tests/test_segment_preflight.py tests/test_gui_preflight_loop.py`
passed 171 tests with 1 skip in 16.24 seconds. The reproducer was corrected in
one runtime correction round; no real tool was launched.

Final checks for this correction: `python -m compileall src` passed;
`python -m pytest -q -rs -p no:cacheprovider --basetemp <fresh-short-ascii-temp>`
passed 1183 tests with 12 environment-dependent skips in 184.07 seconds.
`python tools/verify_public_tree.py` passed (330 indexed files), strict change
validation and all 16 current specs passed, and working/index whitespace and
Git diff/stat/status checks passed. Changes remain staged and uncommitted.
Real-PHITS acceptance, archive and release remain outstanding.

No real PHITS, Sumtally or phits2dicom executable was launched by these tests.

### Acceptance completion attempt and startup instrumentation blocker (2026-09-10)

The human requested completing testing without repeated routine confirmation.
Real external execution remains separately authorized. Startup-only private
checks compared module `--help`, the installed controller console entrypoint
`--help`, and a dummy Python script, both with and without the private recorder.
All three baseline cases passed. With the recorder, the dummy script passed,
but both help entrypoints failed before preparation with a `runpy` import error
and an absent `__main__.__file__` attribute. This reproduces the observed GUI
controller startup failure without real inputs or a PHITS launch; it does not
establish the precise Python-level cause.

A single private-only correction filtered profiling callbacks before inspecting
frame globals. The identical six-condition rerun produced the same failure.
The original recorder, failed candidate and both diagnostic results were kept
outside Git. The repeated-failure stopping rule was reached; no further recorder
correction or real invocation was made. A human decision is needed to replace
the startup-wide profiling approach. Neither this candidate nor passing dummy
tests establish independent OS process-tree evidence or real cancellation.

Unaffected public validation continued. The related focused suite passed 430
tests with one directory-symlink privilege skip in 80.63 seconds. Acceptance
coverage was then extended with six synthetic cases in
`tests/test_segment_preflight.py`: cancellation at every enumerator/hash
checkpoint including the final precommit checkpoint; durable cancellation,
no commitment/summary/downstream authority, released ownership and unchanged
runtime bytes/mtimes; progress published before a large hash finishes; and
rejection of added, removed or renamed runtime files. The checkpoint sweep
uses the observed baseline checkpoint count, not assumed fixed counts.

`python -m pytest -q -x -p no:cacheprovider --basetemp <fresh-short-ascii-temp> tests/test_segment_preflight.py`
passed all 43 tests in 11.21 seconds. No public runtime, physics or specification
contract was changed in this round. Required private real-GUI acceptance remains
incomplete, so this change must not be promoted, archived or released yet.

Compilation passed, followed by the default full suite: 1189 passed, 12 skipped
in 245.75 seconds. The opt-in synthetic Tk observation/layout test was then
enabled separately with `DICOMXPHITS_TEST_TK=1`. Its first run failed because the
older harness activated the execution guard without creating the controller
now used for the preflight nonce. Actual `run_selected` constructs a
`ControllerPipe` before refreshing progress; the harness now does the same.
`Popen`, stage execution and settings writes remain forbidden, and all existing
layout, stale-data, invocation-reset and terminal-state assertions are retained.
The identical focused Tk command then passed (1 passed, 1.88 seconds) after this
single test-only correction. This is synthetic GUI coverage, not real PHITS
acceptance. The original failing result is not superseded by the earlier full
run, which had skipped this opt-in case.

Final synthetic commands used the repository Python environment, process-local
`PYTHONUTF8=1`, and a fresh short ASCII temporary parent:

- `python -m compileall src`: passed after the Tk harness correction.
- With `DICOMXPHITS_TEST_TK=1`,
  `python -m pytest -q -rs -p no:cacheprovider --basetemp <fresh-short-ascii-temp>`:
  1190 passed, 11 skipped, 195.02 seconds. The remaining skips are nine
  symlink-privilege cases and two unsupported FIFO cases, not Tk coverage.
  Both isolated preflight Tk cases and the opt-in observation/layout case ran.

The approved synthetic scenarios are complete; this does not remove the private
real-GUI gate or authorize changing the failed recorder strategy without the
human decision required by the stopping rule.

### Approved explicit-wait recorder attempt (2026-09-11)

The human approved replacing the private startup-wide profiling approach with
explicit child wait/exit recording and synthetic checks. A fresh private
candidate wraps `subprocess.Popen.wait`, retaining the existing audit events,
sequence/lifecycle records and visible logging failures. Original recorder and
diagnosis artifacts were preserved; no frozen real-execution plan was replaced.

The unchanged six-condition entrypoint check was run once against the candidate.
Baseline module/console help passed with exit 0 and empty stderr. Instrumented
module/console help again failed with exit 1 and the same `runpy` import /
missing `__main__.__file__` error. The script dummy passed with its expected
exit 5 both with and without instrumentation. Removing profiling did not resolve
startup, so profiling alone is not an established root cause. The precise
mechanism remains unproven. The unchanged failure/no-improvement stopping rule
was reached; no further candidate correction or startup rerun was performed.

The previous private dummy tests were copied without changing their assertions.
They passed worker-thread child exits 0/5/7, three-level propagation, the
production `ControllerPipe` with a dummy leaf, missing/truncated log rejection,
startup-open failure, abrupt exit and injected write failure rejection. A new
help-completeness and wait-timeout check was not run because its help prerequisite
failed. These synthetic results do not establish independent OS process-tree
evidence or real cancellation. No real tool or GUI was launched.

The candidate and failed startup evidence remain private. The change stays
active, with real preparation cancellation and boundary-stop acceptance pending.
Further bounded startup diagnosis requires a new human decision after this stop.

Public validation used the repository Python 3.12 environment, process-local
`PYTHONUTF8=1` and `DICOMXPHITS_TEST_TK=1`, and a different fresh short ASCII
`--basetemp` for each pytest invocation:

- `python -m pytest -q -rs -p no:cacheprovider --basetemp <fresh-short-ascii-temp> tests/test_segment_preflight.py tests/test_segment_stop.py tests/test_segment_retry.py tests/test_gui.py tests/test_gui_preflight_loop.py tests/test_phits_observation_tk.py tests/test_prepare_sumtally.py tests/test_prepare_rtdose.py tests/test_workspace_recovery.py`:
  437 passed, 1 skipped, 86.40 seconds.
- `python -m compileall src`: passed.
- `python -m pytest -q -rs -p no:cacheprovider --basetemp <different-fresh-short-ascii-temp>`:
  1190 passed, 11 skipped, 207.86 seconds. The nine symlink-privilege and two
  unsupported FIFO skips remain; all three Tk cases ran.
- `python tools/verify_public_tree.py`: passed, 331 indexed files.
- `openspec.cmd validate improve-phits-preflight-responsiveness --strict`:
  passed; `openspec.cmd validate --specs --strict`: all 16 passed.

Public source, tests and normative specifications were unchanged in this
session; only this verification record and the active task blocker were updated.
The original 20-file staged implementation was preserved. Private candidates
and results were not staged; original private recorder/diagnosis file contents
and modification times matched the pre-work snapshot. No commit, push, archive
or publication was performed.

### Approved startup component isolation (2026-09-11)

After the explicit-wait candidate stopped, the human approved a bounded
diagnostic separating audit hooks, logging initialization and wait wrapping.
A new private directory preserves all source probes, per-case output and JSON
reports without modifying the earlier candidates or frozen real plans.

The 21-case matrix tested module help, installed console help and a script dummy
under seven configurations. Empty instrumentation, recorder imports, stream/
lifecycle setup, and stream plus explicit wait wrapping passed all three
entrypoints. A no-op audit hook alone, filtered audit logging, and the full
configuration each failed both help entrypoints with the same startup error;
their script dummies still passed. Registering an audit hook was therefore
sufficient to reproduce the observed failure in this environment. Profiling,
log writes and wait wrapping were not necessary for reproduction.

Four further synthetic import probes showed that `-S -c` reproduces the failure
without site initialization or project imports when the main-file attribute is
absent. Turning optional frozen modules off did not resolve it. Running a
synthetic script file, or setting a main-file attribute as a diagnostic control,
allowed the import. The attribute-setting control is not a recorder fix.
The visible Python exception path ends at `FrozenImporter.exec_module`,
`importlib._bootstrap` line 1176, `exec(code, module.__dict__)`, with the same
missing `__main__.__file__` AttributeError. No project/recorder frame identifies
the lower-level source of that error; its precise environmental cause remains
unproven.

Eight minimal operation probes compared audit disabled/enabled under `-S -c`.
Heartbeat, compile and execution of synthetic `pass` succeeded both ways; only
the audit-enabled runpy import failed. No profile or trace hook was active.
The probes catch tested exceptions into their reports: harness exit 0 indicates
diagnostic completion, not successful tested imports or real acceptance.

The bounded diagnosis is complete. It supports proposing direct Popen creation
and wait recording without registering an audit hook, preserving existing
evidence assertions; that new implementation awaits a human decision. Neither
this diagnostic nor that proposed Python-level recorder establishes independent
OS process-tree evidence. No real tool or GUI was invoked, and the active
change's real acceptance remains outstanding.

Post-diagnosis public checks used the repository Python 3.12 environment and
process-local `PYTHONUTF8=1`, with a new short ASCII basetemp for each pytest run:

- `python -m pytest -q -p no:cacheprovider --basetemp <fresh-short-ascii-temp> tests/test_verify_public_tree.py`:
  10 passed, 0.06 seconds.
- `python -m compileall src`: passed.
- With `DICOMXPHITS_TEST_TK=1`,
  `python -m pytest -q -rs -p no:cacheprovider --basetemp <different-fresh-short-ascii-temp>`:
  1190 passed, 11 skipped, 194.65 seconds; the same nine symlink-privilege and
  two FIFO limitations remain, and the three Tk cases ran.
- `python tools/verify_public_tree.py`: passed, 331 indexed files.
- `openspec.cmd validate improve-phits-preflight-responsiveness --strict` and
  `openspec.cmd validate --specs --strict`: passed, including all 16 current specs.
- `git diff --check`, `git diff --cached --check`, working/index diff stats and
  `git status --short`: passed/reviewed. The original 20 staged files remain;
  only tasks.md and this verification record have additional unstaged edits.

Original private recorder/diagnosis contents and modification times still match
the pre-work snapshot. No runtime, physics, DICOM, MU, dose conversion or normative
public specification change was made in this diagnostic step. No commit, push,
real-tool invocation, archive or release was performed.

### Approved direct Popen recorder (2026-09-11)

The human approved a new private recorder that avoids audit hooks and directly
records Popen construction and successful waits. It binds the request sequence
to the created PID and subsequent wait return, records construction failure
separately, and excludes environment/stream contents. If creation logging fails
after a child starts, it waits naturally before surfacing that error; no timeout
or termination is added. The private source and results remain outside Git.

On its first candidate, all six baseline/instrumented module-help, installed
console-help and dummy conditions passed. The earlier startup error did not
reproduce, and a separate check confirmed identical help stdout and complete
lifecycle records. Existing worker-thread 0/5/7, three-level chain, ControllerPipe
dummy, missing/truncated record, startup-open failure, abrupt exit and write-fault
assertions passed. The write-failure stimulus alone was adapted from the removed
audit heartbeat to the direct record function; assertions were not weakened.

Additional checks passed keyword/executable/cwd and environment/stream forwarding
without sentinel environment/stdin contents entering logs; request/PID/wait
linkage; missing-executable failure without created-child evidence; and a
post-creation recording fault that waits for natural child completion and exposes
the error. The prior deferred explicit-wait check now passed: no profile hook,
no exit record on wait timeout, and the actual natural exit 7 recorded. There was
no failed correction round for this candidate.

The private startup and synthetic recorder gate is satisfied. This remains
Python-level instrumentation, not independent OS process-tree evidence. Read-only
review of the existing frozen private plan confirmed its independent no-child
requirement and prohibition on silently substituting non-independent evidence.
That plan, old failure evidence, workspaces and staging were not changed/reused.
Independent evidence and a new exact real-invocation approval remain required;
no live GUI or real PHITS acceptance was performed. The change remains active.

Read-only availability checks found the Windows `Win32_ProcessStartTrace` and
`Win32_ProcessStopTrace` class definitions, including PID/parent PID and exit
status. The initial sandboxed metadata query was denied; the same authorized
read outside the sandbox succeeded. No event subscription, process capture or
system/security setting change was performed. Metadata availability alone does
not qualify an independent observer; synthetic validation remains needed.

Final public validation used the repository Python 3.12 environment with
process-local `PYTHONUTF8=1` and `DICOMXPHITS_TEST_TK=1`. Each pytest invocation
used a different fresh short ASCII basetemp:

- `python -m pytest -q -rs -p no:cacheprovider --basetemp <fresh-short-ascii-temp> tests/test_segment_preflight.py tests/test_gui_preflight_loop.py tests/test_phits_observation_tk.py tests/test_verify_public_tree.py`:
  56 passed, 16.54 seconds.
- `python -m compileall src`: passed.
- `python -m pytest -q -rs -p no:cacheprovider --basetemp <different-fresh-short-ascii-temp>`:
  1190 passed, 11 skipped, 190.69 seconds. All three Tk cases ran; remaining skips
  are the same nine symlink-privilege and two unsupported FIFO cases.
- `python tools/verify_public_tree.py`: passed, 331 indexed files.
- `openspec.cmd validate improve-phits-preflight-responsiveness --strict` and
  `openspec.cmd validate --specs --strict`: passed; all 16 current specs valid.
- `git diff --check`, `git diff --cached --check`, working/index stats and
  `git status --short`: passed/reviewed. The original 20 staged files are intact;
  only tasks.md and this record have additional unstaged changes.

Original private recorder/diagnosis SHA-256 and modification-time snapshots
matched again. No public runtime, tests, physics, geometry, DICOM, MU, dose
conversion or normative specification was changed in this step. Private files
were not staged; no commit, push, real-tool execution, archive or release occurred.

### Approved independent Windows process-event feasibility (2026-09-11)

The human approved synthetic validation of Windows process start/stop evidence.
An ordinary-token subscription was denied before child creation. Read-only token
inspection confirmed no enabled administrator token. A scoped elevated helper
then observed a direct synthetic cmd child start and its native exit 7, but no
stop event arrived under the stop query's parent-PID filter. The check failed;
the evidence was retained and no child was killed.

A proposed wider cmd stop-event subscription was rejected by automatic approval
review because it could collect unrelated process metadata outside the approved
single-child scope. It was not executed or copied into the private verification
area. A safer, separately approved exact-PID alternative held a synthetic cmd
child on stdin, subscribed only to its PID's stop event and then allowed normal
completion. Both events arrived with matching child PID, chronological timestamps
and matching native/OS exit 7. The OS start event had the expected parent PID;
the stop event reported parent PID 0. The unchanged equality assertion failed
with `Parent PID mismatch`. This is not a passed observer qualification.

The observed field behavior requires reconsidering the diagnostic's reference
criterion, so the repository stopping rule was applied before any further
correction or rerun. The proposed criterion would use the start event to establish
parent identity, then correlate its known PID and ordered timestamps with the
stop event, preserving the raw stop parent value. Missing, duplicated, wrong-PID,
reversed-time and inconsistent-exit evidence must continue to fail. This proposed
adjustment requires a human decision; it has not been implemented.

Owned temporary subscriptions/queues were cleaned up and the helpers exited.
No unrelated process metadata was persisted, no system/security settings or
persistent WMI filters were changed, and no real GUI or PHITS was invoked.
Short-lived unheld trees, independent launcher ancestry and real no-child
acceptance remain unverified. Private reports retain all three attempts and the
approval rejection. Earlier private recorders/plans, failed workspaces and staging
were preserved. The active change cannot be promoted or archived on this evidence.

Public checks after the stopped diagnostic used repository Python 3.12 and
process-local `PYTHONUTF8=1`; every pytest invocation used a new short ASCII
basetemp:

- `python -m pytest -q -p no:cacheprovider --basetemp <fresh-short-ascii-temp> tests/test_verify_public_tree.py`:
  10 passed, 0.07 seconds.
- `python -m compileall src`: passed.
- With `DICOMXPHITS_TEST_TK=1`,
  `python -m pytest -q -rs -p no:cacheprovider --basetemp <different-fresh-short-ascii-temp>`:
  1190 passed, 11 skipped, 190.37 seconds. The three Tk cases ran; remaining skips
  are the same nine symlink-privilege and two unsupported FIFO cases.
- `python tools/verify_public_tree.py`: passed, 331 indexed files.
- `openspec.cmd validate improve-phits-preflight-responsiveness --strict` and
  `openspec.cmd validate --specs --strict`: passed, all 16 current specs valid.
- `git diff --check`, `git diff --cached --check`, working/index stats and
  `git status --short`: passed/reviewed; original 20-file staging preserved, with
  additional unstaged changes only in tasks.md and this verification record.

Original recorder/diagnosis file SHA-256 and modification-time snapshots matched.
No public runtime, test, physics, geometry, DICOM, MU, dose-conversion or normative
specification change was made. No private artifact was staged, and no real-tool
invocation, commit, push, archive or release occurred. Passing public checks do
not override the failed independent-event qualification described above.

### Approved start-parent and stop-event correlation (2026-09-11)

The human approved using OS start evidence for parent identity and correlating
stop evidence through the same known PID, ordered OS timestamps and matching
exit status, while preserving raw stop-parent metadata and negative checks.
A fresh private helper captured exactly three direct synthetic cmd children,
held on stdin until their exact-PID stop subscriptions were armed. Start queries
remained observer-parent/name scoped, and stop queries remained exact-PID scoped.
No all-process subscription or rejected wider query was executed.

All three new captures (expected/native/OS exits 0/5/7) passed the revised strict
correlation. Raw stop parent PID was 0 in each and remained unchanged. Validation
requires a complete capture, the prior subscription gate, known parent/child
identities, exact query scope, one start and one stop, process names, start-parent
identity, strictly increasing OS times inside the capture window and consistent
exit codes. A contradictory nonzero stop-parent field still fails. Separate
event queues may deliver out of order, so validation uses their OS timestamps.

Each captured record was copied in memory for 25 negative tests (75 total), all
rejected: missing/duplicated events, wrong PID/start parent, contradictory stop
parent, reversed/equal/out-of-window timestamps, wrong expected/native/OS exit,
missing raw metadata, boolean PID, malformed time, wrong name/type/schema,
incomplete or no-child records, late subscription and broadened query scope.
Queue-order and null/zero/matching raw stop-parent controls also passed. Capture
bytes were unchanged; private results contain their SHA-256 values. PowerShell
syntax and Python compilation passed, with no failed correction or rerun.

This approved bounded correlation adjustment is complete. It qualifies held,
known direct synthetic children only, not unheld short-lived launcher ancestry,
absence of setup gaps or real no-child evidence. An empty event set cannot be
accepted as no launch. Real GUI/PHITS acceptance and fresh exact invocation
approval remain outstanding; the change remains active. Own event subscriptions
were released and the helper exited; no real tool, prior workspace/staging,
global settings, public runtime or normative specification was changed.

Public verification used repository Python 3.12 and process-local `PYTHONUTF8=1`,
with a different fresh short ASCII basetemp for every pytest invocation:

- `python -m pytest -q -p no:cacheprovider --basetemp <fresh-short-ascii-temp> tests/test_verify_public_tree.py`:
  10 passed, 0.07 seconds.
- `python -m compileall src`: passed.
- With `DICOMXPHITS_TEST_TK=1`,
  `python -m pytest -q -rs -p no:cacheprovider --basetemp <different-fresh-short-ascii-temp>`:
  1190 passed, 11 skipped, 196.07 seconds; all three Tk cases ran. The nine
  symlink-privilege and two unsupported FIFO skips remain unchanged.
- `python tools/verify_public_tree.py`: passed, 331 indexed files.
- `openspec.cmd validate improve-phits-preflight-responsiveness --strict` and
  `openspec.cmd validate --specs --strict`: passed; all 16 current specs valid.
- `git diff --check`, `git diff --cached --check`, working/index stats and
  `git status --short`: passed/reviewed. Original 20-file staging remained intact,
  with additional unstaged changes only in tasks.md and this verification record.

The original private recorder/diagnosis SHA-256 and modification-time snapshots
matched again. No public runtime/tests, physics, geometry, DICOM, MU, dose
conversion or normative specification change was made; no private file was
staged. No real PHITS invocation, commit, push, archive or release occurred.

### Prearmed scoped Job Object investigation (2026-09-11)

The human approved investigating prearmed process-family observation and normal-
speed synthetic launcher/controller checks. Microsoft documentation describes
Job Object descendant association and lifetime process accounting, but explicitly
does not guarantee ordinary completion-port notification delivery. Notifications
alone therefore cannot establish no-child evidence. Relevant primary references:

- https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects
- https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_associate_completion_port
- https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_accounting_information

A fresh private synthetic probe associated a completion port with an empty job,
created its synthetic root suspended, assigned it to that job, then resumed it.
Descendants were not held on stdin or observer handshakes. No resource limits,
kill-on-close, breakaway options, persistent settings or system-wide subscription
were configured. Python syntax compilation passed.

The first case expected a single script process without an explicit child spawn.
OS accounting instead reported two lifetime processes and zero active processes;
two distinct start and exit notifications matched those counts. Only one script
self-record existed. The known root returned zero and no limit termination was
reported. The additional process's identity/role remains unverified; neither
its parent relationship nor its exit code was inferred from the count or root
status. This is a failed fixture/reference assumption, not accepted evidence.

The probe stopped at that assertion: remaining three cases and negative mutations
were not executed. No expected count was changed, no automatic rerun occurred,
and all failed artifacts were retained. Job handles were closed without killing
processes. Existing private recorders and workspaces were not modified. The
next human decision is a bounded investigation of the additional synthetic
process before any revised reference or further trial. Real acceptance remains
outstanding; no real PHITS, public runtime or normative specification changed.

The original recorder/diagnosis trees were read without modification. A fresh
hash/time inventory succeeded, but the saved comparison baseline contained an
earlier access-denied diagnostic and could not support a complete equality
claim. No new claim of verified byte-for-byte preservation is made here.

Public focused checks passed (10 tests, 0.06 seconds) and compileall passed.
The first full pytest invocation could not create its fresh short ASCII basetemp
inside the sandbox: 460 passed, 2 skipped, 739 setup errors in 28.96 seconds.
This access-denied result was retained; no code or assertion was changed to
address it. A separately reviewed invocation used another fresh short ASCII
basetemp outside the sandbox. This does not rerun the stopped private probe.

The reviewed full run passed: 1190 passed, 11 skipped in 178.74 seconds with
`PYTHONUTF8=1` and `DICOMXPHITS_TEST_TK=1`; Tk tests ran, with nine symlink and
two FIFO platform skips. Commands were repository Python
`-m pytest -q -p no:cacheprovider --basetemp <fresh-short-ascii-temp> tests/test_verify_public_tree.py`,
`-m compileall src`, and
`-m pytest -q -rs -p no:cacheprovider --basetemp <different-fresh-short-ascii-temp>`.
`python tools/verify_public_tree.py` passed (331 indexed files),
`openspec.cmd validate improve-phits-preflight-responsiveness --strict` and
`openspec.cmd validate --specs --strict` passed (16 current specs), and
`git diff --check`, `git diff --cached --check`, diff stats and status were
checked. Original staging remained 20 files; unstaged tracked edits remained
limited to tasks.md and this record. No commit, push, promotion, archive or
release occurred because private real acceptance remains incomplete.

### Approved scoped additional-process identity diagnosis (2026-09-11)

The human approved a new synthetic diagnostic to identify the additional process.
A fresh unnamed Job Object contained only the new synthetic root and associated
members. The root was assigned before resume, then held briefly by a diagnostic
release-file gate. Membership enumeration was limited to this job. Read-only
process handles were opened for its listed PIDs; membership and liveness were
checked before image inspection. A separate read-only CIM query selected exactly
those PIDs and returned only process ID, parent ID and name. Handles remained
open, and members were confirmed alive after the query. No system-wide process
enumeration, event subscription or unrelated process inspection was performed.

The new observation identified the Python root and conhost.exe in the Windows
system directory. OS parent metadata linked conhost.exe to that exact synthetic
root. Its role as the Windows Console Host is documented by Microsoft:
https://learn.microsoft.com/en-us/windows/console/definitions
The gate was released, both observed handles signaled natural exit with code 0,
and job accounting reported two lifetime members, zero active and zero limit
terminations. The helper completed on its first invocation; Python compilation
passed. Private source and capture digests were recorded outside Git.

This explains the two-member pattern in the new held diagnostic. The earlier
unnamed, completed process cannot be identified retrospectively from that record;
its console-host identity remains an inference, not a proven historical fact.
No signature/security audit of the system executable was performed or claimed.
The result neither qualifies normal-speed short-lived chain coverage nor supplies
real no-child acceptance. No blanket console-host exclusion or changed expected
count was implemented, and the previous failed probe was not rerun. Existing
records were retained. The bounded identity task is complete; the next step is
to agree on an evidence-based fixture/reference before further chain validation.
Public runtime, normative specifications, fixed physics, geometry, DICOM meaning,
MU and dose conversion were untouched. No real PHITS, prior staging/workspace,
security setting, kill operation, commit, push, archive or release was involved.

Public checks used repository Python with `PYTHONUTF8=1` and a new short ASCII
basetemp for each pytest invocation:

- `python -m pytest -q -p no:cacheprovider --basetemp <fresh-short-ascii-temp> tests/test_verify_public_tree.py`:
  10 passed, 0.06 seconds.
- `python -m compileall src`: passed.
- With `DICOMXPHITS_TEST_TK=1`,
  `python -m pytest -q -rs -p no:cacheprovider --basetemp <different-fresh-short-ascii-temp>`:
  1190 passed, 11 skipped, 176.90 seconds; Tk tests ran. Skips remained nine
  symlink-privilege and two unsupported FIFO cases.
- `python tools/verify_public_tree.py`: passed, 331 indexed files.
- `openspec.cmd validate improve-phits-preflight-responsiveness --strict` and
  `openspec.cmd validate --specs --strict`: passed, including all 16 current specs.
- `git diff --check`, `git diff --cached --check`, working/index stats and
  `git status --short`: checked. Original 20-file staging was retained; only
  tasks.md and this record gained unstaged tracked edits. Private diagnostics
  remain excluded from Git. The preceding failed probe source digest still
  matched its recorded value; its evidence was not revised.

## Process-evidence criteria (approved for private synthetic implementation)

The initial approval covered documentation only. After reviewing that draft,
the human approved private validator implementation and fresh synthetic checks
under these criteria. Previously stopped probes remain preserved, not reused.
The criteria do not amend public runtime contracts or replace the separately
gated private real-GUI acceptance below. Implementation progress is recorded
after the historical documentation-only snapshot.

### Scope and fixture definition

- Freeze each synthetic case's launcher/controller/fake-leaf roles, allowed
  parent edges, expected individual exit codes, observation boundary and source
  digests before execution. Use a fresh private capture directory. Do not adjust
  expected roles or counts after observing a mismatch.
- Define logical application roles separately from OS support processes. A
  no-fake-leaf case means no fake leaf launched, not zero OS processes. A root
  and its console support may still exist; this is not real no-PHITS evidence.
- The initial proposed console-support allowance is at most one console host
  per explicitly listed console-client role. Each observed host requires its
  own evidence; no other support roles are implicitly allowed. A different
  arrangement requires review, not an expanded allowance during a failing run.
- Limit inspection to the fresh target process family. Prepare the observation
  boundary before the root can execute. Do not introduce global subscriptions,
  security changes, resource limits, forced termination or detached/unobserved
  execution to satisfy the criterion. Record unsupported creation/breakaway
  paths as coverage gaps, not evidence of absence.

### Required evidence and reconciliation

| Check | Proposed evidence | Not sufficient |
| --- | --- | --- |
| Process identity | OS image identity and PID lifetime binding inside the scoped run, with creation/time or retained-handle evidence preventing PID-reuse confusion | Filename, PID alone or a previous run's identity |
| Parent/role | Independent OS parent evidence tied to the same process lifetime and allowed case edge; fixture self-records corroborate application roles | Job membership or a self-record alone |
| Console support | Resolved Windows system console-host image and OS parent matching a declared console client; retain its full lifecycle evidence | Matching conhost.exe by basename or subtracting one from the total |
| Exit | Observed individual natural termination and exit code for every member, including support processes; compare declared application exits and require support exit 0 | Root exit 0, job-empty state or an exit notification lacking a code |
| Coverage | Complete, run-bound start/end evidence plus final OS lifetime accounting and no active members or limit terminations | Empty event queues or matching counts alone |

For a captured family, require the set of independently identified lifetimes to
match both start and terminal records, and their cardinality to equal final OS
lifetime accounting. Every member needs exactly one classified role and terminal
result. Support processes stay in this reconciliation; they are not discarded.
Raw observations remain immutable. Multiple observations may be reconciled only
through explicit lifetime/event identity; ambiguous duplicates or conflicting
records are rejected rather than silently deduplicated. Keep raw stop-parent
metadata; a missing/zero stop parent does not replace independently proven parent
identity, while contradictory metadata blocks acceptance.

### Outcomes and planned negative cases

- `qualified-synthetic`: all evidence and declared expectations match for that
  case only. Nonzero application exits such as 5/7 may be expected synthetic
  outcomes; they are never reclassified as successful PHITS completion.
- `unverified`: required identity, parent, exit or coverage evidence is missing,
  the observer starts late, or a short-lived process is gone before its identity
  can be bound. This is not a pass and cannot be used as no-launch evidence.
- `failed`: observed identities, graph, counts, exit codes or boundaries conflict
  with the frozen case. Preserve evidence and apply repository stopping rules.
- Negative cases would cover unknown members; same-name/wrong-path console hosts;
  wrong parents; PID reuse; missing/duplicate/conflicting starts or exits; missing
  or wrong individual exit codes; late setup; empty notifications with nonzero
  OS accounting; truncated logs; active members; and unsupported coverage paths.
  Mutated fixtures remain separate from immutable captured evidence.

Held identity diagnostics and normal-speed chain qualification must be reported
separately. Holding a process to collect its identity does not demonstrate that
an unheld short-lived chain can be observed. The existing private prototypes do
not yet demonstrate all required normal-speed evidence; this proposal promises
no such capability. If it cannot be obtained within the approved scope, stop as
unverified instead of weakening these requirements. No result from this observer
is handed to Sumtally or used to override existing downstream completion gates.

Approval of documentation alone does not authorize implementation or execution.
Any later synthetic implementation decision remains separate from exact real
PHITS invocation approval, acceptance, OpenSpec promotion/archive and release.

### Documentation-only verification snapshot (2026-09-11)

No private diagnostic or real tool was executed for this drafting task. Only
tasks.md and this document were edited; existing staging and private evidence
were retained. The proposed criteria remain unimplemented and untested.

Repository Python checks used `PYTHONUTF8=1`, with a fresh short ASCII basetemp
for each pytest invocation:

- `python -m pytest -q -p no:cacheprovider --basetemp <fresh-short-ascii-temp> tests/test_verify_public_tree.py`:
  10 passed, 0.06 seconds.
- `python -m compileall src`: passed.
- With `DICOMXPHITS_TEST_TK=1`,
  `python -m pytest -q -rs -p no:cacheprovider --basetemp <different-fresh-short-ascii-temp>`:
  1190 passed, 11 skipped, 233.12 seconds; Tk cases ran. Nine symlink-privilege
  and two unsupported FIFO skips remained unchanged.
- `python tools/verify_public_tree.py`: passed, 331 indexed files.
- `openspec.cmd validate improve-phits-preflight-responsiveness --strict` and
  `openspec.cmd validate --specs --strict`: passed, including all 16 current specs.
- `git diff --check`, `git diff --cached --check`, diff stats and
  `git status --short`: checked; original 20-file staging retained, additional
  unstaged tracked edits limited to the two documents above.

These public checks do not qualify the proposed private evidence criteria or
real acceptance. No runtime, normative specification, physics, geometry, DICOM,
MU or dose conversion changed. No commit, push, promotion, archive or release
was performed. Stop after presenting this draft for a human decision.

### Approved validator and normal-speed acquisition probe

A fresh private normalized-evidence validator implements role/image/parent/exit,
lifetime, scope and accounting checks, with distinct qualified-synthetic,
unverified and failed outcomes. A separate frozen plan supplies expectations.
Three fabricated positive fixtures (application exits 0/5/7) passed; 114 negative
mutations were classified as expected. These tests cover missing identity,
parent, exit, lifetime and raw metadata; wrong roles, images, parents, exits and
sources; invalid/reused PIDs; out-of-window lifetimes; accounting, scope and run
mismatches; late/held/incomplete capture; empty/duplicate/conflicting lifecycle
records; and same-name/wrong-path console hosts. Original mock inputs were
unchanged. This validates normalized-record logic only, not OS provenance,
capture completeness or all planned negative scenarios. Python compilation passed.

One fresh, unheld, normal-speed synthetic launcher/controller/fake-leaf chain
was then started in a fresh job assigned before root resume, with its completion
port prearmed. Its role/exit plan and capture-source digest were written before
launch. The source inventory was also recorded privately after the run; a full
prelaunch package-digest freeze is not claimed for this acquisition probe.
Membership-confirmed handles were retained for all six observed members. OS
images identified three Python processes and three console hosts; each retained
handle supplied creation/exit times and natural exit code 0. Six start and six
exit notifications matched final accounting: six total, zero active, zero limit
terminations. No support member was subtracted or automatically classified by
its name alone.

The exact-retained-PID CIM parent query was performed after termination and
returned no records. Thus all six OS parent relationships remain unverified;
self-reports and job membership were not substituted. The acquisition prototype
has no qualified normal-speed start-parent adapter and explicitly sets coverage
incomplete. The validator returned unverified, not qualified-synthetic. It is a
partial acquisition prototype, not an end-to-end implementation of all approved
criteria; the mocked positives do not change that limitation. No parent evidence
was fabricated, no failed/stopped capture was reused, and no further launch or
correction followed this coverage stop.

The next unresolved step is a scoped way to retain independent parent evidence
for short-lived processes before that information disappears. This may require
a separately reviewed acquisition approach; no broad subscription, security
setting change or relaxed criterion is authorized by the partial result. Public
runtime/specifications and physics were untouched. Real PHITS, Sumtally, private
real-workspace reuse, forced termination, auto reruns, commit, push, archive and
release remain outside this execution and were not performed.

Public verification after the private checks used repository Python with
`PYTHONUTF8=1` and a new short ASCII basetemp for every pytest invocation:

- `python -m pytest -q -p no:cacheprovider --basetemp <fresh-short-ascii-temp> tests/test_verify_public_tree.py`:
  10 passed, 0.35 seconds.
- `python -m compileall src`: passed.
- With `DICOMXPHITS_TEST_TK=1`,
  `python -m pytest -q -rs -p no:cacheprovider --basetemp <different-fresh-short-ascii-temp>`:
  1190 passed, 11 skipped, 290.23 seconds; Tk tests ran, with the same nine
  symlink-privilege and two unsupported FIFO skips.
- `python tools/verify_public_tree.py`: passed, 331 indexed files.
- `openspec.cmd validate improve-phits-preflight-responsiveness --strict` and
  `openspec.cmd validate --specs --strict`: passed, including all 16 current specs.
- `git diff --check`, `git diff --cached --check`, working/index stats and
  `git status --short`: checked. Original 20-file staging was retained, with
  unstaged tracked changes still limited to tasks.md and this verification plan.

The private validator/checker/acquisition sources and result summary are outside
Git; their source hashes are recorded privately. There was one private mock-check
invocation and one acquisition invocation, no correction round or automatic
rerun. Public passing checks do not resolve the unverified acquisition verdict.

### Approved retained-handle parent comparison

Following a separately approved read-only investigation, the human approved a
new private synthetic comparison of parent IDs before and after natural exit.
The diagnosis used NtQueryInformationProcess(ProcessBasicInformation), looked up
dynamically, only on retained, membership-confirmed handles in its fresh job.
The frozen prelaunch plan recorded source SHA-256, the comparison criterion,
pointer/structure sizes and the existing limited-query/synchronize access mask.
No extra privileges, PEB/memory reads, driver, global enumeration, subscription
or security setting change was used.

The held synthetic Python root and its console host both returned NTSTATUS 0
and the expected 48-byte structure on this 64-bit runtime. For each process,
native PID equalled GetProcessId(handle), and native parent PID before exit
equalled both the live exact-PID CIM parent and native parent after exit. Handles
were held continuously through the comparison. Both processes exited naturally
with code 0, and final job accounting was two total, zero active and zero limit
terminations. The source and result digests are recorded privately. Python
compilation and the first diagnostic invocation passed; no correction or rerun
was needed. Previously stopped probes and their references were not modified.

The observation corrects the earlier overly broad suggestion that parent
information must always be captured before exit: a retained handle supported
post-exit retrieval here, unlike the previous post-exit CIM enumeration. This
does not guarantee that an observer can retain every short-lived handle in time,
nor qualify the unheld acquisition adapter, normal-speed chain validation or
real no-PHITS acceptance. No such integration or additional private launch was
performed in this bounded diagnostic task.

Microsoft documents the parent-ID field and warns that this internal API and
its layout may change. Success here is environment-specific, not a portable
public-runtime contract. Reference:
https://learn.microsoft.com/en-us/windows/win32/api/winternl/nf-winternl-ntqueryinformationprocess
The native query's mere success does not establish all acceptance conditions;
scope, lifetimes, roles, exits and accounting still require their existing checks.
Public runtime, physics, geometry, DICOM, MU, dose and normative specs are
unchanged. No real tool, forced termination, commit, push, archive or release
occurred; full real acceptance remains outstanding.

Public verification used repository Python with `PYTHONUTF8=1`, with a new short
ASCII basetemp for every pytest invocation:

- `python -m pytest -q -p no:cacheprovider --basetemp <fresh-short-ascii-temp> tests/test_verify_public_tree.py`:
  10 passed, 0.07 seconds.
- `python -m compileall src`: passed.
- With `DICOMXPHITS_TEST_TK=1`,
  `python -m pytest -q -rs -p no:cacheprovider --basetemp <different-fresh-short-ascii-temp>`:
  1190 passed, 11 skipped, 183.13 seconds; Tk tests ran. Nine symlink-privilege
  and two unsupported FIFO skips were unchanged.
- `python tools/verify_public_tree.py`: passed, 331 indexed files.
- `openspec.cmd validate improve-phits-preflight-responsiveness --strict` and
  `openspec.cmd validate --specs --strict`: passed, including all 16 current specs.
- `git diff --check`, `git diff --cached --check`, working/index stats and
  `git status --short`: checked; original 20-file staging retained. Additional
  unstaged tracked edits remain limited to tasks.md and this verification plan;
  the new private diagnosis and result summary are excluded from Git.

### Approved normal-speed retained-parent integration

The human approved a new private observer integrating the retained native parent
query with normal-speed synthetic families. Existing normalized-evidence
validator and its checks were copied unchanged. Adapter tests added a fabricated
positive and 17 negatives for native API status/length/PID/parent errors, lost or
duplicated lifecycle evidence, accounting/setup gaps, active or limit-terminated
members, self/OS contradictions and invalid support identities/exits. Both the
unchanged 3-positive/114-negative suite and these adapter tests passed.

The first integration candidate moved image lookup as well as parent lookup
after process exit. Its first case observed six starts/exits but failed during
post-exit metadata retrieval with WinError 31, before completing its first
identity record. The precise failing API was not separately labelled in that
initial record. The batch stopped; its remaining three cases did not run.
All failed sources, plans and records remain unchanged in that private directory.

One bounded correction was made in a different fresh private directory: restore
image lookup to the previously successful handle-acquisition point, retain
post-exit native parent/time/exit queries, and label acquisition stages for any
later error. The validator, expected roles, exit codes and support allowance
were not relaxed. Identical focused private checks passed again. Source hashes
for the complete four-file candidate package and all four case definitions were
frozen before the new batch, with a case plan before every launch and source
consistency checks before and after each case.

The corrected adapter prearmed each fresh job before root execution, retained
membership-confirmed handles without descendant holds or handshakes, collected
native parent IDs on those handles after exit, and reconciled all identified
lifetimes against start/end notifications and OS lifetime accounting. Application
self-records corroborated role assignments, not OS parent identity. Every support
member remained counted and required the approved image, parent, lifetime and
exit checks. Job notifications lack a stop-parent field: normalized null records
its absence; native parent evidence is separate and never inserted into raw events.

| Fixed synthetic case | Application exits | OS lifetime total | Result |
| --- | --- | --- | --- |
| Launcher/controller/fake leaf | 0 / 0 / 0 | 6 | qualified-synthetic |
| Launcher/controller/fake leaf | 5 / 5 / 5 | 6 | qualified-synthetic |
| Launcher/controller/fake leaf | 7 / 7 / 7 | 6 | qualified-synthetic |
| Launcher/controller, no fake leaf | 5 / 5 | 4 | qualified-synthetic |

All 22 observed member handles returned native status 0; all support exits were
0. Every case ended with zero active members, zero limit terminations and no
acquisition gaps. Each normalized capture also underwent ten separate in-memory
negative mutations: missing parent/exit/start, wrong parent/exit/image, duplicate
end, late setup, empty members and wrong accounting. All 40 were rejected without
altering the captured evidence. This is one successful batch after one bounded
correction, not a retry-until-pass policy. No further correction or launch followed.
A readback-only PowerShell aggregation initially had a syntax error; correcting
that command read the existing results and did not relaunch any target.

This completes the approved bounded normal-speed synthetic integration, not
general process-tracing completeness. The named launcher/controller/fake leaf
are roles in a dedicated fixture, not the application controller, venv entrypoint
or PHITS. Their no-fake-leaf case is not a real preparation-cancellation check.
Actual controller integration, all relevant launch paths, private real-GUI
acceptance and a fresh exact real invocation approval remain outstanding. Internal
API availability and timely handle capture remain conditional; missing evidence
still blocks acceptance. No global monitoring, privilege changes, PEB reads,
forced termination, old-workspace reuse, real tools, public runtime or normative
specification changes were involved. The active OpenSpec change is not archived.

Public verification used repository Python with `PYTHONUTF8=1` and a fresh short
ASCII basetemp per pytest invocation:

- `python -m pytest -q -p no:cacheprovider --basetemp <fresh-short-ascii-temp> tests/test_verify_public_tree.py`:
  10 passed, 0.06 seconds.
- `python -m compileall src`: passed.
- With `DICOMXPHITS_TEST_TK=1`,
  `python -m pytest -q -rs -p no:cacheprovider --basetemp <different-fresh-short-ascii-temp>`:
  1190 passed, 11 skipped, 176.74 seconds; Tk tests ran. The nine symlink-privilege
  and two unsupported FIFO skips were unchanged.
- `python tools/verify_public_tree.py`: passed, 331 indexed files.
- `openspec.cmd validate improve-phits-preflight-responsiveness --strict` and
  `openspec.cmd validate --specs --strict`: passed, including all 16 current specs.
- `git diff --check`, `git diff --cached --check`, working/index stats and
  `git status --short`: checked. Original 20-file staging was retained; additional
  unstaged tracked edits remain only in tasks.md and this plan. Private candidate
  packages and summaries remain excluded from Git. No commit/push/release occurred.

## Actual controller synthetic integration attempt (2026-09-11)

The human explicitly approved the existing-controller fake-runner integration,
excluding real PHITS. A fresh private package retained the normal-speed observer
and unchanged evidence validator. Its launcher uses the real ControllerPipe;
the controller invokes the existing run_segments.main with only a private runner
injection, existing authored test fixtures and a fixed synthetic run identity.
The planned cases were one successful fake leaf, leaf exits 5 and 7 (each mapped
by the real CLI to controller exit 3), and injected pre-scan cancellation with
controller exit 5 and no leaf. This is not an actual GUI cancellation action.
Package and repository Python source hashes were frozen before launch. The new
capture source SHA-256 was
`b6f63939c47bd20c698fabaa6b73abc7f440fd98e583e7b003d6e263286a029d`.

The existing fabricated validator checks passed (3 positive, 114 negative), as
did the unchanged adapter checks (1 positive, 17 negative). The first normal
case recorded five new-process notifications but no exits within the bounded
acquisition. After its additional cleanup wait, the root still had not exited;
the verdict was unverified, not success. The batch stopped with one case run.
No correction, remaining case, forced termination or target rerun followed.

Read-only CIM limited to the five captured PIDs confirmed the synthetic Python
launcher, controller and fake leaf, plus two console hosts, were still alive.
The sandboxed CIM read was denied; the same exact-PID read passed after sandbox
approval, without OS privilege changes or a global process query. The synthetic
segment summary remained running with no return code. The precise wait location
and cause are unproven; inherited controller stdin is a hypothesis, not a finding.
These artifacts and processes must not be treated as successful results or sent
to Sumtally. No real tool was launched. All prior failed packages were preserved.

The observation command itself remains an open execution session because its
descendants have not exited. Cleanup of these exact synthetic processes requires
a separate human decision; no permission is inferred to kill them or manipulate
their pipes. No real-GUI estimate is reliable until this blocker is resolved.
The active change remains unarchived. Runtime and normative specifications were
not edited; only this plan and tasks.md have additional unstaged tracked changes.

Public checks after this blocked attempt used repository Python, PYTHONUTF8=1,
DICOMXPHITS_TEST_TK=1 and distinct new short ASCII basetemps:

- `python -m pytest -q -p no:cacheprovider --basetemp <fresh-short-ascii-temp> tests/test_segment_stop.py tests/test_segment_preflight.py tests/test_gui_preflight_loop.py tests/test_phits_observation_tk.py tests/test_verify_public_tree.py`:
  89 passed in 36.39 seconds.
- `python -m compileall src`: passed after focused tests.
- `python -m pytest -q -rs -p no:cacheprovider --basetemp <different-fresh-short-ascii-temp>`:
  1190 passed, 11 skipped in 178.19 seconds; opt-in Tk tests ran. Skips remain
  nine unavailable symlink privileges and two unsupported FIFOs.
- `python tools/verify_public_tree.py`: passed, 331 indexed files.
- `openspec.cmd validate improve-phits-preflight-responsiveness --strict` and
  `openspec.cmd validate --specs --strict`: passed, all 16 current specs valid.
- `git diff --check`, `git diff --cached --check`, stats and status checked;
  original 20-file staging retained. No commit, push, release or archive.

These existing public checks do not qualify the blocked private acquisition or
replace its three unexecuted cases. Its remaining processes were not terminated.

## Private input-pipe correction and synthetic qualification (2026-09-11)

After explicit cleanup approval, the three old synthetic Python processes were
matched by PID, creation time and full command, retained by handle, then forcibly
terminated. Their two console hosts also exited; no member of that old five-PID
set remained. Old logs, workspaces and failed verdict were preserved. That cleanup
does not constitute natural completion or qualify the old case.

Read-only diagnosis found that the private fake runner discarded the input
provided by run_segments and inherited controller stdin instead. After separate
approval, a fresh package forwarded that input through subprocess.run's dedicated
pipe and added exclusive stage markers around controller/main/fake waits and
leaf input reading. The leaf checks receipt of the synthetic input and EOF.
The public controller/runtime, validator, expected roles/exits and acquisition
deadline were unchanged. Source SHA-256:
`2a2726b575fb11abc2c377598f3f024f6d736aa6581d04d965894d8186a2702a`.

The first new batch passed all four fixed cases:

- Successful fake leaf: one fake call, controller exit 0, five OS members.
- Fake leaf exits 5 and 7: one fake call each, controller exit 3, five OS members
  each; failed results rejected by downstream validation.
- Injected pre-scan cancellation: zero fake calls, controller exit 5, three OS
  members, cancelled-before-launch receipt, no segment summary or downstream
  acceptance. Cancellation was injected, not sent by an actual GUI interaction.

All cases had zero active members, zero limit terminations, natural root exit,
complete OS identity/parent/lifetime accounting and qualified-synthetic verdicts.
The unchanged fabricated validator checks (3 positives/114 negatives), adapter
checks (1 positive/17 negatives) and 40 captured-evidence negative mutations passed.
The three leaf cases recorded input read completion and return; controller/main
and fake waits completed. No timeout, retry or forced termination occurred in the
new batch. The old stall did not recur after correcting the input contract, but
the old process's exact blocked native call was never captured and is not proven.

This completes the approved bounded synthetic correction. No real PHITS, real
GUI action, venv-entrypoint qualification, old-workspace reuse or public runtime/
physics/specification change occurred. Fresh real acceptance plans and exact
invocation approvals remain outstanding; OpenSpec stays active and unpublished.

Public checks for this correction (repository Python, PYTHONUTF8=1, Tk enabled,
distinct new short ASCII basetemps for every pytest invocation):

- `python -m pytest -q -p no:cacheprovider --basetemp <fresh-short-ascii-temp> tests/test_segment_stop.py tests/test_segment_preflight.py tests/test_gui_preflight_loop.py tests/test_phits_observation_tk.py tests/test_verify_public_tree.py`:
  89 passed in 39.84 seconds.
- `python -m compileall src`: passed after focused validation.
- `python -m pytest -q -rs -p no:cacheprovider --basetemp <different-fresh-short-ascii-temp>`:
  1190 passed, 11 skipped in 177.73 seconds; opt-in Tk tests ran. The skips were
  nine symlink-privilege limitations and two unsupported FIFOs.
- `python tools/verify_public_tree.py`: passed, 331 indexed files.
- `openspec.cmd validate improve-phits-preflight-responsiveness --strict` and
  `openspec.cmd validate --specs --strict`: passed; all 16 current specs valid.
- `git diff --check`, `git diff --cached --check`, working/index stats and
  `git status --short`: checked; original 20-file staging retained. Additional
  unstaged tracked changes remain only in tasks.md and this plan. Private source
  packages and generated evidence were not staged. No commit/push/release/archive.

## Visible GUI process-observer synthetic integration (2026-09-11)

The human explicitly approved a new private GUI-path integration with authored
synthetic data and fake runners, excluding the prepared real-acceptance candidate
and real PHITS. A fresh package runs gui.main and the real Tk builder under the
prearmed Job Object observer. The GUI's actual Run and Cancel preparation buttons
were clicked once each using the scoped Windows Computer Use interface. The
existing run_stage, ControllerPipe, control stdin and run_segments.main performed
the request delivery and result handling. No cancellation message was injected
directly into StopControl by this fixture.

Test substitutions are material and explicit: defaults and tool-profile/readiness
validation are fixture-scoped, the command builder routes only this synthetic
stage to a Python bootstrap with an injected fake runner, personal settings saves
are prohibited, and a yielding preparation checkpoint loop provides up to 180
seconds for GUI interaction. That loop reports zero scanned files/bytes rather
than fabricated work. The observer has a 600-second interaction budget, not the
15-second normal-speed fixture deadline. This is not real scan timing evidence
or qualification of an unmodified venv/console entrypoint or real tool profile.

Frozen capture source SHA-256:
`f1b71e6fd5ea3c02f44c7e7bb7b56c6b54fa3dc03994ebc6fc3f5224b0ba0da8`.
Frozen GUI harness SHA-256:
`4c60c23144e5c8d9ac2e8f3d15a5db60cc7c2ef7acbaf497cdadb6b2ab7b8ec4`.
The normalized validator and its negative assertions were unchanged.

The first acquisition passed. GUI state transitioned from preparing with Cancel
enabled to Preparation cancelled / no PHITS launched; downstream controls stayed
disabled. Workspace, run, GUI nonce and request evidence matched; controller exit
was 5, stderr empty, owned pipe released and fake-runner calls zero. The GUI was
closed normally only after its active stage cleared and terminal checks passed;
its process returned 0 with no callback errors. OS accounting reconciled three
members (GUI Python, its console host, controller Python), natural exits 0/0/5,
zero active members, zero limit terminations, no acquisition gaps and successful
native parent queries. The independent verdict is qualified-synthetic for this
case only. The inherited acquisition label 'normal-speed synthetic job family'
does not override the deliberate yielding/interaction timing described above.

Fabricated validator checks passed (3 positives/114 negatives), adapter checks
passed (1 positive/17 negatives), and all 10 captured-evidence mutations were
rejected. No target rerun, forced termination, PHITS process, real-acceptance
workspace access or old workspace reuse occurred. Initial window capture showed
an occluding application; no input was sent there. The uniquely selected test
window was activated and re-observed before any input. Its close operation was
followed by observer-confirmed natural process exit rather than trusting the
immediate window-list snapshot alone.

This completes only the approved visible-GUI synthetic connection. Real runtime
hashing, actual configuration/launch artifact freeze, preparation cancellation on
the real acceptance inputs and committed-segment boundary stopping remain open.
The active change is not promoted, archived, committed or published. Public
runtime, physics and normative specifications were not changed.

Public checks after this visible-GUI case used repository Python, PYTHONUTF8=1,
DICOMXPHITS_TEST_TK=1 and a distinct new short ASCII basetemp per pytest command:

- `python -m pytest -q -p no:cacheprovider --basetemp <fresh-short-ascii-temp> tests/test_segment_stop.py tests/test_segment_preflight.py tests/test_gui_preflight_loop.py tests/test_phits_observation_tk.py tests/test_verify_public_tree.py`:
  89 passed in 41.37 seconds.
- `python -m compileall src`: passed after focused validation.
- `python -m pytest -q -rs -p no:cacheprovider --basetemp <different-fresh-short-ascii-temp>`:
  1190 passed, 11 skipped in 209.64 seconds; opt-in Tk tests ran. Nine symlink
  privilege limitations and two unsupported FIFO skips were unchanged.
- `python tools/verify_public_tree.py`: passed, 331 indexed files.
- `openspec.cmd validate improve-phits-preflight-responsiveness --strict` and
  `openspec.cmd validate --specs --strict`: passed; all 16 current specs valid.
- `git diff --check`, `git diff --cached --check`, stats and status checked;
  original 20-file staging preserved. Only tasks.md and this verification plan
  have additional unstaged tracked changes; private harness/evidence not staged.

## Synthetic implementation acceptance

- Many small files and one large fake runtime file: progress precedes scan
  completion; assert checkpoints between entries and reads no larger than 1 MiB.
  Instrument work counts, not a hardware-dependent whole-tree deadline.
- Inject a cancellation at each checkpoint: no child starts, receipt is durable,
  exit is 5, no complete binding is invented and no downstream gate opens.
- Deterministically race first commitment and cancellation in both orders;
  accepted cancellation prevents commitment, committed execution rejects it.
- Stop during a later binding scan: acknowledgement occurs without waiting for
  the whole scan, but committed-result validation/publication is not skipped.
- Add/remove/rename/change runtime files (including same-size/same-mtime changes),
  input includes, calibration and outputs: preserve existing fail-closed checks.
- Persistence failure, stale nonce/run/root, unknown schema, controller death,
  duplicate requests and blocking I/O: never fabricate acceptance/terminal state,
  release ownership prematurely or start another child.
- Cancelled selective preflight preserves parent/result bytes and mtimes; new
  preview still validates original evidence. Cancellation is not a retry source.
- Current cancellation/running receipt plus historical success: downstream and
  relocated/read-only recovery cannot accept historical success as current.
- Existing v2-v5 success, stopped, failure and retry behavior stays unchanged;
  full completion racing final-segment stopping still yields verified success.
- Fake Tk loop remains responsive; controls and phase labels distinguish
  preparing, request-sent, acknowledgement, verifying, cancelled and stopped.
  Synthetic responsiveness target: acknowledgement within 1 second with a
  yielding fake scanner; separately assert checkpoint bounds without sleeps.

## Private real-GUI acceptance, separately authorized

Freeze exact installation/workspace/input/plan digests outside Git. Never reuse
previous stopped/failed workspaces or staging without explicit approval.
Separately approve each execution. First verify cancellation while preparing:
no PHITS launch and no need to finish the full scan. Then, under a new explicit
approval, verify a committed segment finishes naturally after a boundary-stop
request, remaining work stays pending and Sumtally stays disabled. Record
preflight, acknowledgement, validation and total elapsed times independently.
Do not confuse this with batch/r.err, selective-retry or full release acceptance;
those require their own evidence. No automatic rerun or history increase.

Keep all actual paths, output text, identities, raw results and plans private.
Report fake-test results and real verification separately. Update estimates
after the first real check; no unconditional speed or completion promise.
