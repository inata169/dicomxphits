# Change: Define relative-error presentation boundaries

## Why

The accepted live-observation contract reports only the provisional relative
error of the single primary 3D dose voxel containing Isocenter. It deliberately
does not mix in PDD relative error, whole-mesh aggregates, or RT Structure
statistics. That execution-time boundary is appropriate, but the repository
does not yet define an approval-ready post-completion RT Structure evaluation
contract.

Unqualified whole-mesh minimum, maximum, mean, median, percentile, standard
deviation, or coverage values would be difficult to interpret because
low-dose and out-of-body voxels can dominate relative-error summaries. A PDD
`r.err` value describes the PDD tally and is not a representative patient 3D
dose value. Post-completion Structure statistics therefore require an explicit
source, mapping, filtering, statistic, and labeling contract before runtime
implementation.

## What Changes

- Preserve the existing execution-time display as one provisional Isocenter
  voxel from the current manifest-selected primary 3D dose/error pair.
- Make the separation permanent: live observation does not add or substitute
  PDD, whole-mesh aggregate, or RT Structure relative-error values.
- Define RT Structure relative-error statistics as a separate, explicitly
  invoked post-completion Sumtally capability, not as live progress,
  convergence, stopping, completion, or downstream evidence.
- Exclude unqualified whole-3D-mesh summary statistics and exclude
  `deposit-pdd.out` from patient 3D relative-error presentation.
- Bind the evaluation to validated combined dose/error, RT Structure, frozen
  CT and accepted RTDOSE-affine evidence; define one explicit ROI, fail-closed
  mapping and numeric checks, a fixed low-dose exclusion, exact unweighted
  summary statistics, non-clinical labeling, and evidence-bound persistence.
- Provide no v1 export, whole-mesh relative-error aggregate, PDD substitution,
  clinical acceptance claim, or automatic downstream authority.

## Impact

Proposed capabilities: `phits-live-observation` (clarified),
`guided-gui-workflow` (clarified), and
`post-completion-structure-relative-error` (new).

This proposal phase changes OpenSpec documents only. It does not change the
runtime, GUI, PHITS inputs, tally or variance settings, histories, `maxcas`,
`maxbch`, Sumtally, RTDOSE generation, DICOM coordinates, geometry, dose, MU,
normalization, dose factors, public fixed-field 3D-CRT scope, or downstream
safety gates. It does not authorize real PHITS, Sumtally, phits2dicom, GPR, or
real-DICOM execution.

## Approval and completion boundary

The human approved this complete proposal as the implementation contract on
2026-09-14. That approval fixes the bounded contract but does not by itself
authorize runtime implementation. Keep the change active while implementation,
required validation, promotion, or archive work remains.
