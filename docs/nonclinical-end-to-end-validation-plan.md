# Non-Clinical End-to-End Validation Plan

## Status and authority

This document defines a proposed validation procedure for the current public
fixed-field 3D-CRT workflow after pull request #70. It is a planning artifact
only. It does not authorize a real PHITS, RT-PHITS, Sumtally, phits2dicom, GPR,
or GUI execution and does not authorize access to real patient data.

Every external-tool execution described below requires a new, explicit human
approval for the exact frozen executable, inputs, destination, settings, and
launch count. Approval of this document alone is not execution approval.
Release work is outside this plan and remains a separate decision.

The validation is for education and research software. A successful result is
workflow and performance evidence for one bounded non-patient phantom case. It
is not clinical commissioning, patient QA, vendor certification, treatment
approval, or a general dose-accuracy claim.

## Objective

Validate one fresh, supervised passage through the current guided Windows
workflow while collecting enough evidence to answer four questions:

1. Can the current public adapters complete the documented non-patient phantom
   chain without bypassing a stage gate?
2. Do completion, provenance, geometry, dose, and stale-result checks remain
   fail closed at every downstream boundary?
3. Does the post-completion Structure relative-error action introduced through
   PR #70 operate only from the accepted combined dose/error evidence and
   present only the documented scalar statistics and counts with non-clinical
   labeling?
4. What wall time, CPU, memory, disk-I/O, and workspace growth are observed on
   the approved host, especially before the first PHITS child starts and while
   the GUI polls retained results?

## Fixed scope

The proposed validation uses exactly one confirmed non-patient phantom case in
the documented public v1 fixed-field 3D-CRT scope. The preferred case is a
centered water phantom with an effective aperture no larger than the exact
documented `20 x 20 cm2` boundary. The final RT Plan must use only supported
fixed photon treatment fields and the package-owned nominal 6 MV public
research model.

The core chain is:

```text
non-patient phantom CT + RT Plan
  -> CT2PHITS frozen handoff
  -> 3D-CRT workspace preparation
  -> PHITS active-segment execution
  -> Sumtally generation and execution
  -> RTDOSE preparation and conversion
  -> coordinate-corrected PLAN RT Dose validation
  -> post-completion RT Structure relative-error evaluation
```

An external GPR comparison is an optional extension. It needs a suitable
non-patient TPS-derived RT Dose and a separate execution approval. Its result
is recorded as a research observation and is not a clinical pass/fail gate.

The validation must not:

- add IMRT, dynamic MLC, or VMAT inputs;
- widen, clip, recenter, or add tolerance to the field-size guard;
- change geometry, coordinate, MU, normalization, dose-factor, physics,
  source-spectrum, history, batch, thread, or tally settings after the frozen
  launch record is approved;
- use a patient dataset or facility-specific configuration or calibration;
- copy official tool distributions, raw DICOM, raw output, private logs,
  machine-specific paths, or real UIDs into the repository;
- use GPR to repair, rescale, or authorize an otherwise rejected result;
- inject mutations into real inputs or results to test negative cases; or
- retry, restart, overwrite, delete, or publish anything automatically.

## Required inputs

All real-tool and DICOM inputs remain outside the repository. Before any launch,
the private run record must identify and freeze the following items.

Before an agent or validation process opens, hashes, copies, inventories, or
parses any candidate DICOM, a human must identify the exact candidate paths
without agent-side directory discovery and separately approve one bounded
read-only identifier review and freeze operation for those files. This set must
include any optional reference RT Dose or external RTDOSE template that would be
used. Discovery of patient or identifying data stops that operation and does
not authorize copying, calculation, or review of another candidate set.

The same rule applies independently to every real-tool distribution and other
external input. Before any such file or directory metadata is opened, hashed,
inventoried, or parsed, a human must identify the exact path or finite file set
without agent-side discovery and approve the bounded read-only review and
freeze for that one group. The CT2PHITS artifacts, PHITS installation
root/executable, phits2dicom executable, optional GPR checkout/file set, and any
external calculation configuration are separate groups; approval of one does
not authorize inspection of another. A directory approval permits only the
explicitly described root metadata and preidentified finite files, never a
recursive distribution search.

| Input | Required evidence |
| --- | --- |
| Source CT series | Confirmed non-patient phantom; series membership; supported axial HFS orientation; file count and SHA-256 for every selected slice |
| Source RT Plan | Same Frame of Reference as the CT; supported fixed-field 3D-CRT geometry; beam/control-point inventory; field-size result; full-file SHA-256 |
| RT Structure Set | Same Frame of Reference and referenced CT series; one preselected structure with non-empty in-CT coverage; full-file SHA-256 |
| Optional TPS RT Dose | Non-patient reference; matching Frame of Reference; `GY` units; full-file SHA-256 |
| PHITS | Explicit PHITS 3.35-style Windows OpenMP executable and installation root; executable SHA-256; no PATH search |
| RT-PHITS launcher | Explicit `RTphits_win.bat` path and SHA-256; reviewed batch control flow and environment expansion; ordinary-file and no-link/reparse evidence |
| CT2PHITS executable | Exact absolute executable reached by the reviewed batch path; version evidence and SHA-256; ordinary-file and no-link/reparse evidence |
| CT2PHITS HU table | Explicit `HumanVoxelTable.data` path, required markers, SHA-256, and ordinary-file and no-link/reparse evidence |
| phits2dicom | Explicit Windows executable path and SHA-256 |
| RTDOSE template | The reviewed package template or another separately reviewed compatible non-patient template; SHA-256 |
| Optional GPR tool | Explicit checkout/root, exact version or commit, entry point, and relevant file digests |
| Calculation settings | Exact `maxcas`, `maxbch`, OpenMP threads, and optional calculation-config bytes and SHA-256 |
| Destinations | New absent case workspace and evidence directory under an approved scratch root outside the repository |
| Host | OS/build, CPU model and logical-core count, installed RAM, storage type, Python 3.12 environment, package commit, and available disk space |

The source set must pass a private identifier review before it is frozen. A
plain-language case alias may be used in a sanitized report, but source
filenames, UIDs, hashes, and absolute paths stay in the private record.

## Resource budget to freeze before execution

No real launch may start while any entry in this table is undecided. The values
are host- and case-specific approval inputs, not new public product limits.

| Budget | Value to approve |
| --- | --- |
| Minimum free space before launch | `<bytes>` on the selected scratch volume |
| Maximum permitted workspace growth | `<bytes>` |
| Warning time before first PHITS child commitment | `<seconds>` |
| Warning time for each PHITS segment | `<seconds>` |
| Warning time for the complete core chain | `<seconds>` |
| Host memory warning threshold | `<bytes or percent>` |
| Sustained disk-I/O warning threshold | `<bytes/second and duration>` |
| Sampling interval | Proposed: `1 second` |
| Maximum measurement-log size | `<bytes>` |
| Action at a warning threshold | Proposed: notify the operator and request a decision; do not kill or retry automatically |

Crossing a warning threshold is not permission to terminate an external tool.
Any stop policy must be included in the exact execution approval. For PHITS,
the documented **Stop after current segment** path is preferred when it is
available and separately authorized. An emergency process termination makes
the run incomplete and must be recorded as such.

## Evidence collector boundary

Resource collection must be observational and must not alter the workflow
inputs or outputs. Before real use, exercise the collector against fake child
processes and temporary synthetic workspaces.

For the GUI and the complete approved descendant process tree, recursively
including Python stage adapters, `cmd.exe`, reviewed batch processes, and the
actual external-tool children, record:

- UTC and monotonic stage start/end times;
- exit code and the accepted stage status;
- process identity, creation time, parent/child relationship, and exit status
  without trusting a reused process ID;
- sampled CPU time or utilization;
- working-set and private-memory samples, including the observed peak;
- cumulative read/write bytes and sampled throughput when available;
- scratch-volume free space and workspace byte count before and after each
  stage; and
- collector sampling gaps, errors, and its own CPU, memory, and output size.

The collector must retain final cumulative CPU and I/O counters for descendants
that exit, include short-lived descendants through process-start/exit events or
an equivalently justified mechanism, sum CPU and I/O without double counting,
and calculate sampled aggregate memory across the live approved tree. Missing a
computing descendant or its final counters makes performance acceptance
inconclusive rather than permitting a partial low estimate.

Record separately:

- GUI selection to preflight start;
- preflight start to durable request/receipt states;
- preflight start to first PHITS child commitment;
- each PHITS segment duration;
- Sumtally generation and execution durations;
- RTDOSE preparation and conversion durations;
- post-completion Structure evaluation duration;
- at least one idle retained-result polling interval after display; and
- total core-chain wall time.

The collector may inspect only the approved process tree, workspace, and
evidence directory. It must not enumerate the PHITS installation, inspect other
processes, upload telemetry, hold output files open across a calculation, or
parse full numerical arrays merely to measure performance. If collection fails,
the calculation result may still be reviewed for functional evidence, but the
performance result is inconclusive.

## Pre-execution gates

Complete these gates in order. A failure stops preparation; it is not repaired
by relaxing a guard or editing the frozen case.

1. Confirm the repository commit, clean tracked tree, public tags, and absence
   of active OpenSpec changes.
2. Run the repository's focused synthetic GUI/runtime/Structure checks and the
   full public checks with the repository `.venv`.
3. Verify that the scratch and evidence destinations are absent, outside the
   repository, on an approved volume, and have no symbolic-link or Windows
   reparse-point ancestors within the writable path.
4. After the separate approval for the exact candidate file set, perform only
   the approved bounded read-only review and freeze operation. Confirm that
   every DICOM object is from the approved non-patient phantom and that its
   modality, series membership, Frame of Reference, orientation, references,
   and required Structure selection are unambiguous.
5. After the separate CT2PHITS-artifact review approval, perform only that
   bounded read-only review and freeze operation. Review the exact effective
   command in `RTphits_win.bat`, resolve the CT2PHITS executable that it reaches,
   and bind the batch, executable, and HU-table bytes by SHA-256. Do not launch
   a tool or recursively search for an installation.
6. After the separate PHITS review approval, inspect only the exact
   human-identified installation-root metadata and executable, and freeze the
   approved executable path, version evidence, ordinary-file/no-link state, and
   SHA-256. Do not enumerate or inspect the remaining distribution.
7. After the separate phits2dicom review approval, inspect only the exact
   human-identified executable and freeze its path, ordinary-file/no-link state,
   version evidence, and SHA-256.
8. If GPR is requested, after its separate review approval, inspect only the
   exact human-identified checkout-root metadata and preidentified finite entry
   point, executable, script, and dependency file set. Freeze its version or
   commit and relevant digests without recursive checkout discovery.
9. If an external calculation configuration is requested, after its separate
   review approval, inspect only that exact human-identified ordinary file and
   freeze its no-link state, complete bytes, and SHA-256.
10. Freeze the already reviewed input evidence, tool identities, declarative
    calculation settings, destinations, collector, resource budgets, launch
    order, and stop policy in the private run record. This gate must not inspect
    a new external path.
11. Review the full frozen record, then obtain explicit approval for the next
   exact action. Immediately before requesting that approval and again
   immediately before the action, recheck every approved input, executable,
   script, configuration, and destination for that stage against its applicable
   frozen evidence: ordinary-file path, no-link/reparse state and full-file
   SHA-256; directory path, membership and no-link/reparse state; exact setting;
   or required destination absence/identity. A mismatch invalidates the
   approval. The stage-specific checks below are additional and do not narrow
   this invariant.

## Execution procedure

The primary validation path is the guided Windows GUI because it exercises the
current preparation, progress, stop, retained-result, and Structure-result
presentation. The operator remains present throughout all real-tool stages.

### 1. CT2PHITS frontend

1. After exact approval for one GUI launch, start the GUI once from the exact
   reviewed package commit. Starting the GUI does not authorize a tool launch.
2. Select the frozen standard or explicitly reviewed custom tool profile.
3. Select the frozen CT series and RT Plan and make the explicit non-patient
   phantom confirmation.
4. Verify the derived CT2PHITS destination is the approved new absent path.
5. Immediately before launch, recheck the approved ordinary-file paths and
   SHA-256 values for `RTphits_win.bat`, the exact CT2PHITS executable reached
   through its reviewed command, and `HumanVoxelTable.data`.
6. After exact execution approval, run the CT2PHITS stage once.
7. Require a successful summary, all nine expected generated files, the frozen
   RT Plan, selected CT membership, and recorded SHA-256 evidence.

### 2. Workspace preparation

1. Confirm that the GUI populated the frozen handoff paths from the accepted
   CT2PHITS summary.
2. Enter the exact approved `maxcas`, `maxbch`, thread count, and optional
   calculation-config path.
3. After exact workspace-preparation approval, prepare the workspace once. This
   stage must not execute PHITS.
4. Review the segment manifest, public-model identity, fixed-field guard,
   runtime parameters, CT/accelerator geometry evidence, and preparation
   summaries before continuing.

### 3. PHITS active segments

1. Recheck all frozen digests and available resource headroom.
2. After exact execution approval, start one ordinary all-active-segment
   controller invocation. Its frozen launch count is at most one PHITS child
   for each exact active segment listed in the reviewed manifest. Do not enable
   automatic retry.
3. During execution, confirm the GUI remains responsive, prevents concurrent
   stage launches, distinguishes preparation from committed execution, and
   shows only invocation-bound progress.
4. Treat `batch.out`, estimated finish time, and the live Isocenter-voxel
   relative error as provisional. None is completion or stopping authority.
5. On natural completion, require successful evidence for every active
   segment, clean Category-I geometry diagnostics, expected output paths, and
   accepted output digests.

### 4. Sumtally

1. Generate the all-active-segments `totalfield` Sumtally input.
2. Confirm `segment_mu` weights, active-treatment MU-sum `sumfactor`, `GY`
   input-dose semantics, manifest binding, wrapper/input digests, and complete
   recursive dependency evidence.
3. Immediately before launch, recheck the approved ordinary-file path and
   SHA-256 of the exact PHITS executable that will run Sumtally.
4. After exact execution approval, run Sumtally once.
5. Require a newly created or byte-changed expected dose output, successful
   execution evidence, and stable source/dependency digests.

### 5. RTDOSE

1. After exact RTDOSE-preparation approval, prepare conversion once from the
   accepted Sumtally result, frozen RT Plan, approved template, and selected CT
   reference. This step must not launch phits2dicom.
2. Confirm that converter compatibility changes are confined to private staged
   copies and that accepted Sumtally inputs remain byte-for-byte unchanged.
3. Immediately before launch, recheck the approved ordinary-file path and
   SHA-256 of the exact phits2dicom executable.
4. After exact execution approval, run phits2dicom once.
5. Require a fresh coordinate-corrected output that independently validates as
   `DoseUnits = GY`, `DoseSummationType = PLAN`, references the frozen RT Plan,
   applies the planned fraction count exactly once, preserves physical dose
   through coordinate correction, and passes the documented voxel-placement
   checks with maximum absolute component residual no greater than
   `0.000001 mm`.

### 6. Post-completion Structure relative error

1. Select the frozen RT Structure Set and the preselected unique `ROINumber`
   only after accepted all-active-segment Sumtally completion.
2. Immediately before approval and action, recheck the RT Structure Set's
   approved ordinary-file/no-link path and full-file SHA-256 and confirm that
   the preselected unique `ROINumber` still comes from those exact bytes.
3. After exact approval for this real-DICOM evaluation, trigger the explicit
   Structure evaluation action once.
4. Confirm that the display contains only the unweighted arithmetic mean,
   defined median, linearly interpolated P95, mapped-Structure voxel count,
   above-threshold count, eligible count, and zero-`r.err` exclusion count.
   Confirm that the fixed `D > 0.5 * Dmax` threshold and unweighted basis are
   visible, while `Dmax`, minimum, maximum, standard deviation, whole-mesh
   statistics, and PDD values are absent.
5. Confirm that the display includes the exact required non-clinical statement
   and that its deterministic scalar-summary JSON contains no raw arrays,
   patient identifiers, or `ROIName`.
6. Confirm that the action uses the accepted combined dose/error pair and
   frozen CT/RTPLAN/RTSTRUCT evidence, does not alter independent RTDOSE state,
   and does not substitute the live Isocenter-voxel value.
7. Leave the completed result displayed for at least one normal polling
   interval and record GUI, CPU, memory, and disk-I/O samples. Do not mutate a
   retained source merely to demonstrate stale-result rejection.

### 7. Optional GPR comparison

Run this stage only after a separate approval that identifies the frozen
non-patient reference RT Dose, generated coordinate-corrected evaluation RT
Dose, and exact external tool. Before requesting approval, freeze the
ordinary-file/no-link paths and full-file SHA-256 values of both RT Dose files.
Immediately before launch, recheck those two complete files plus the approved
paths and SHA-256 values for the GPR entry point and every frozen executable or
script that the reviewed command will run. Reproduction of the historical
research condition must explicitly select global `3% / 3 mm` with a `10%`
cutoff rather than relying on CLI defaults. Require matching Frame of Reference,
`GY` units, zero process exit, and a fresh result record. Report the observed
pass rate and settings without treating 95% or another value as a clinical
acceptance threshold.

## Acceptance criteria

### Functional acceptance

The core run passes only when all of the following are true:

- every pre-execution gate passed with unchanged frozen inputs;
- every core stage completed in order without an unauthorized retry,
  overwrite, concurrent launch, or manual artifact repair;
- all required summaries are readable, successful, current, mutually bound,
  and use known schemas;
- all active PHITS segments have clean geometry diagnostics and accepted
  output evidence;
- Sumtally records the documented all-active-segment, totalfield,
  active-treatment-MU-sum normalization in `GY`;
- the final coordinate-corrected RTDOSE passes plan-reference, fraction,
  units, dose-preservation, and placement validation;
- the selected Structure result is available only after valid combined
  dose/error evidence, is labeled non-clinical, and leaves RTDOSE state
  independent;
- source inputs and previously accepted upstream outputs retain their frozen
  hashes wherever the public contract requires immutability; and
- no protected material is added to the repository.

Any failed, incomplete, stopped, stale, mutated, ambiguous, unknown-schema, or
unbound state fails the affected gate and blocks downstream acceptance. A tool
exit code of zero alone is insufficient.

### Performance acceptance

The performance portion passes only when:

- every required metric was captured without exceeding the approved collector
  limit;
- observed workspace growth remained within the frozen storage budget;
- every approved warning threshold and response is reported;
- preflight evidence confirms that only the selected executable and bounded
  workspace inputs were inspected, not the full PHITS installation tree;
- retained Structure-result polling did not acquire the workspace execution
  lease, reconstruct CT pixels, or repeatedly parse full dose/error grids; and
- each measured value is compared with the frozen host- and case-specific
  budget without extrapolating to other machines or cases.

If numerical budgets were not approved before launch, report measurements but
mark performance acceptance **inconclusive**. Do not invent thresholds after
observing the result.

### Optional GPR outcome

GPR completion is reported separately from core functional acceptance. Record
the exact comparison settings, tool identity, grid metadata, and result. A low,
high, or unavailable pass rate must not silently change PHITS physics, the dose
factor, geometry, normalization, or the acceptance of earlier evidence gates.

## Stop conditions

Stop before the next external stage and preserve evidence when any of the
following occurs:

- patient or identifying data is discovered;
- a selected path, digest, setting, tool identity, or destination differs from
  the approved frozen record;
- an approved destination already exists or a path/link boundary is unclear;
- the case is outside the documented fixed-field 3D-CRT, 6 MV, orientation,
  geometry, or effective-aperture scope;
- a stage fails, current evidence cannot be proven, or downstream eligibility
  remains disabled;
- a required input, output, summary, geometry diagnostic, dose/error companion,
  or Structure mapping is missing or ambiguous;
- the resource collector interferes with the calculation or loses required
  samples;
- a resource warning threshold is crossed and the approved response does not
  authorize continuation; or
- completing the run would require an unapproved retry, overwrite, cleanup,
  physics change, data transfer, external write, or scope decision.

Do not troubleshoot a real-tool failure by weakening a guard, changing the
case, increasing histories, installing dependencies, searching other storage,
or reusing a failed workspace. Report the observation, current evidence,
remaining uncertainty, and the smallest next decision.

## Evidence and reporting

The private run record must contain exact paths, DICOM identifiers, input and
tool hashes, calculation settings, timestamps, process records, summaries,
resource samples, output hashes, deviations, and operator decisions. It remains
outside Git and is not uploaded or attached to a public issue or pull request.

A sanitized repository-facing report may contain only:

- the repository commit and public model/workflow identity;
- an abstract non-patient case description;
- tool versions without installation paths or distribution contents;
- calculation settings already safe for public disclosure;
- stage outcomes and schema versions;
- aggregated wall-time, CPU, peak-memory, I/O, and workspace-size results;
- sanitized structural conclusions from the Structure and optional GPR stages;
- every skipped, failed, inconclusive, or unverified item; and
- an explicit statement that the result is non-clinical and bounded to one
  approved case and host.

Before publishing such a report, scan it for personal paths, UIDs, patient or
facility identifiers, machine-specific configuration, raw PHITS or DICOM
content, official distribution content, and credentials. Publication and any
release use require separate approval.

## Expected stage evidence

Review at least these workspace records privately after their producing stage:

- `analysis/public_preparation_workspace_summary.json`
- `analysis/phits_generation_summary.json`
- `analysis/segment_execution_summary.json`
- `analysis/sumtally_generation_summary.json`
- `analysis/sumtally_execution_summary.json`
- `analysis/rtdose_conversion_prepare_summary.json`
- `analysis/rtdose_conversion_execution_summary.json`
- the current preflight/progress receipt and post-completion Structure result
  evidence selected by the GUI
- `gpr/gpr_handoff_summary.json` only when the optional GPR stage is approved

The exact schema fields remain governed by the current specifications and
runtime validators; this checklist does not replace them.

## Required approvals for a later execution session

Use separate approval gates so that consent for one external action is not
treated as consent for another:

1. Approval for one bounded read-only identifier review and freeze operation
   on an exact human-identified candidate DICOM file set, including any optional
   reference RT Dose or external RTDOSE template.
2. Approval for one bounded read-only CT2PHITS tool-role review and freeze on
   the exact human-identified `RTphits_win.bat`, resolved CT2PHITS executable,
   and HU-table files.
3. Approval for one bounded read-only PHITS review and freeze on the exact
   human-identified installation-root metadata and executable.
4. Approval for one bounded read-only phits2dicom review and freeze on the exact
   human-identified executable.
5. Approval for one bounded read-only GPR review and freeze on the exact
   human-identified checkout-root metadata and finite entry point, executable,
   script, and dependency file set, if GPR is requested.
6. Approval for one bounded read-only review and freeze of the exact
   human-identified external calculation-configuration file, if one is used.
7. Approval of the final frozen non-patient dataset, tool identities,
   destinations, settings, collector, resource budgets, and stop policy.
8. Approval for one exact GUI launch from the reviewed package commit, without
   authority to launch CT2PHITS or any later external tool.
9. Approval for one exact CT2PHITS frontend invocation using the frozen DICOM,
   batch, resolved CT2PHITS executable, and HU table.
10. Approval for one exact workspace-preparation invocation using the frozen
    DICOM and handoff.
11. Approval for one exact all-active-segment controller invocation, with the
    reviewed manifest fixing the maximum PHITS child-launch count.
12. Approval for one exact Sumtally invocation.
13. Approval for one exact RTDOSE-preparation invocation using the frozen
    DICOM, accepted Sumtally evidence, and template.
14. Approval for one exact phits2dicom invocation.
15. Approval for one exact post-completion Structure evaluation using the
    frozen RT Structure Set.
16. Approval for one exact GPR invocation using the frozen reference and
    evaluation RT Dose files, if requested.
17. Approval for one exact cleanup operation, including its targets and
    recoverability.
18. Approval for publishing one exact sanitized report or evidence set.
19. Approval for one exact release operation.
20. Approval for each exact rerun under a newly frozen launch record.

An approval is consumed by the specified launch. Failure or inconclusive
evidence does not authorize another attempt.

## References

- [Manual Smoke Workflow](manual_smoke_workflow.md)
- [Workflow Stages](workflow_stages.md)
- [Public Feasibility Demonstration](public-feasibility-demonstration.md)
- [Calculation Configuration](calculation-configuration.md)
- [Repository safety rules](../AI_AGENT_RULES.md)
- [Guided GUI Workflow specification](../openspec/specs/guided-gui-workflow/spec.md)
- [PHITS Segment Runtime specification](../openspec/specs/phits-segment-runtime/spec.md)
- [PHITS Preflight Control specification](../openspec/specs/phits-preflight-control/spec.md)
- [PHITS Live Observation specification](../openspec/specs/phits-live-observation/spec.md)
- [Post-Completion Structure Relative Error specification](../openspec/specs/post-completion-structure-relative-error/spec.md)
- [RTDOSE DICOM Semantics specification](../openspec/specs/rtdose-dicom-semantics/spec.md)
- [Workspace Output Security specification](../openspec/specs/workspace-output-security/spec.md)
