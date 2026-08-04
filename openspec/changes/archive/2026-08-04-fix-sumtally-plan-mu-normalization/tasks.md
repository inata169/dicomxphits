# Correct Sumtally Plan-MU Normalization Tasks

## 1. Approval and Contract

- [x] 1.1 Obtain human approval to create this proposal without changing
  runtime behavior or executing external tools.
- [x] 1.2 Obtain explicit human approval of the active-treatment-MU equation,
  skipped SETUP behavior, fail-closed legacy behavior, and implementation
  scope before changing runtime or tests.
- [x] 1.3 Keep this change on a dedicated feature branch/worktree independent
  from the active RTDOSE coordinate and portable-workspace recovery changes.

## 2. Synthetic Algebra and Evidence

- [x] 2.1 Add synthetic unequal-active-segment-MU cases whose expected
  absolute treatment dose is calculated independently from maintained
  implementation output.
- [x] 2.2 Prove `isumtally = 2` uses active segment MU as weights and their sum
  as `sumfactor`.
- [x] 2.3 Prove validated skipped SETUP beam evidence, with positive or zero
  BeamMeterset and zero segment MU, does not change the factor and reconciles
  complete MU totals.
- [x] 2.4 Reject missing, non-finite, non-positive active MU, nonzero skipped
  segment MU, or unexplained complete-MU differences.

## 3. Sumtally and RTDOSE Implementation

- [x] 3.1 Generate and record the validated active treatment-segment MU sum as
  `sumfactor` for the absolute treatment-dose contract.
- [x] 3.2 Bind the exact normalization equation, units, active/skipped MU
  reconciliation, dose state, manifest, and generated inputs across Sumtally
  Generate and Run.
- [x] 3.3 Reject legacy incorrect-factor Sumtally evidence before RTDOSE
  conversion while permitting unchanged active-segment PHITS outputs to be
  reused.
- [x] 3.4 Keep phits2dicom `factor = 1.0` and prove that no downstream stage
  applies MU again.
- [x] 3.5 Keep `maxcas`, `maxbch`, OpenMP, coordinate placement, DICOM identity,
  and approved public calibration unchanged.

## 4. GUI and Documentation

- [x] 4.1 Make stale-normalization guidance direct the user to rerun Sumtally
  Generate, Sumtally Run, RTDOSE Prepare, and RTDOSE Run without rerunning
  PHITS.
- [x] 4.2 Update public Sumtally and RTDOSE documentation with the exact
  external-tool equation, SETUP exclusion, and single-application rule.
- [x] 4.3 Preserve education-and-research-only and no-clinical-claim language.
- [x] 4.4 Derive RTDOSE `Not run`, `Prepared`, and `Completed` from the current
  Sumtally-to-Prepare-to-Run digest chain, refresh GUI state after successful
  stages, and permit explicit overwrite to re-Prepare from `Completed`.

## 5. Validation and External Boundary

- [x] 5.1 Run focused synthetic Sumtally, RTDOSE, GUI, and manual-smoke tests.
- [x] 5.2 Run source compilation, the full public pytest suite, public-tree
  verification, and Git diff/status checks.
- [x] 5.3 Run strict OpenSpec validation and inspect the complete change diff.
- [x] 5.4 Obtain separate explicit approval before running real Sumtally,
  RTDOSE, GPR, or additional PHITS histories with designated non-patient data.
- [x] 5.5 If separately approved, reuse existing validated active-segment
  PHITS outputs for Sumtally and downstream unscaled research comparison
  before considering a higher-history PHITS rerun.
- [x] 5.6 After all approved acceptance criteria pass, promote the delta,
  archive the change, and validate the resulting specification tree.
