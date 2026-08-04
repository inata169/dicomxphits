# rtdose-dicom-semantics Delta

## ADDED Requirements

### Requirement: Final RT Dose Placement Shall Be Bound to Frozen-Plan and Tally Geometry

The public RTDOSE adapter SHALL derive the final dose-voxel patient-coordinate
affine from the hash-bound frozen RT Plan isocenter, the reviewed
PHITS/IEC-to-DICOM transform, and the exact tally mesh bounds, bin counts, and
bin-centre semantics that produced the accepted Sumtally dose. It MUST NOT use
the selected CT reference slice's `ImagePositionPatient` as authoritative final
dose-grid placement.

Each finite tally minimum and maximum SHALL be interpreted as bin edges. For
axis `a` in centimetres, bin count `n_a`, and index `i`, the adapter SHALL use
`delta_a = (a_max - a_min) / n_a` and bin centre
`a_i = a_min + (i + 0.5) * delta_a`. Given frozen-plan DICOM isocenter
`I = (I_x, I_y, I_z)` in millimetres and PHITS/IEC bin centre
`p = (x, y, z)` in centimetres, the patient-coordinate mapping SHALL be
`P_DICOM_mm(p) = I + 10 * (-x, z, y)`.

For output index `(frame, row, column) = (f, r, c)`, the adapter SHALL map
`x = x_(n_x - 1 - c)`, `y = y_f`, and `z = z_r`. The supported axial output
SHALL therefore use shape `(n_y, n_z, n_x)`,
`ImageOrientationPatient = [1, 0, 0, 0, 1, 0]`,
`PixelSpacing = [10 * delta_z, 10 * delta_x]`, relative
`GridFrameOffsetVector[f] = 10 * f * delta_y`, and
`ImagePositionPatient = P_DICOM_mm(x_(n_x - 1), y_0, z_0)`.

Any CT position required by `phits2dicom` SHALL be recorded as
converter-compatibility input. The adapter SHALL independently derive and
validate the corrected output's `ImagePositionPatient`,
`ImageOrientationPatient`, `PixelSpacing`, and `GridFrameOffsetVector` from the
bound plan-and-tally geometry.

#### Scenario: CT slice origin differs from the PHITS dose-grid origin

- **GIVEN** a supported frozen RT Plan and tally mesh are bound to one reviewed
  coordinate transform
- **AND** the converter CT reference identifies a voxel position that is not
  the mapped first dose-bin centre
- **WHEN** RTDOSE coordinate correction runs
- **THEN** final dose placement is derived from the frozen-plan and tally
  geometry
- **AND** the CT slice position is not preserved as the final dose-grid origin

#### Scenario: Required placement evidence is incomplete

- **GIVEN** the frozen-plan isocenter, tally bin geometry, transform version,
  or binding digest is missing, stale, ambiguous, or inconsistent
- **WHEN** RTDOSE preparation or execution validates coordinate placement
- **THEN** the stage fails before accepting the corrected RT Dose
- **AND** it does not infer placement from the CT reference or array dimensions

#### Scenario: Asymmetric tally geometry is mapped from bin centres

- **GIVEN** a supported tally has finite asymmetric bounds and positive bin
  counts on all three axes
- **WHEN** the final output affine is derived
- **THEN** the bounds are treated as bin edges rather than voxel centres
- **AND** output frame, row, and column voxel centres follow the approved
  `(y, z, reversed x)` association and `I + 10 * (-x, z, y)` mapping

### Requirement: RTDOSE Preparation Shall Not Mutate Accepted Upstream Results

RTDOSE Prepare SHALL preserve the accepted Sumtally dose output and companion
PHITS output byte-for-byte. Any converter-compatibility title patch SHALL be
applied only to hash-recorded RTDOSE-private copies. Prepare and Run SHALL
revalidate the upstream and staged input digests and SHALL record whether the
upstream files remained unchanged.

A workspace modified by the historical in-place
"ImagePositionPatient" title patch MAY be reused without rerunning Sumtally
only when a deterministic inverse replacement using the hash-bound segment
T-Deposit titles reconstructs bytes whose SHA-256 exactly equals the
Sumtally Run digest. The recovery SHALL account only for the known title
replacement and its historical LF/CRLF normalization, SHALL leave the
external workspace source file unchanged, and SHALL fail closed for every
other difference.

#### Scenario: RTDOSE Prepare stages converter inputs

- **GIVEN** accepted Sumtally and companion PHITS outputs
- **WHEN** RTDOSE Prepare supplies converter-compatibility metadata
- **THEN** it copies those inputs into an RTDOSE-private staging directory
- **AND** patches only the staged copies
- **AND** proves the upstream input digests are unchanged after preparation

#### Scenario: A historical in-place title patch is exactly reversible

- **GIVEN** the current Sumtally output digest differs from its Run evidence
- **AND** reversing only the known IPP title replacement and newline
  normalization reconstructs the exact recorded SHA-256
- **WHEN** RTDOSE Prepare stages the dose
- **THEN** it uses the reconstructed bytes only in the private staged copy
- **AND** records the recovery rule and both current and recovered digests

#### Scenario: Legacy recovery cannot reproduce the recorded digest

- **GIVEN** any additional, ambiguous, or unsupported Sumtally output change
- **WHEN** legacy recovery is evaluated
- **THEN** RTDOSE Prepare fails before conversion
- **AND** it does not silently bless, rewrite, or replace the upstream result

### Requirement: Coordinate Translation Shall Be Explicit and Auditable

Coordinate correction SHALL record its source voxel affine, rule-derived
target affine, applied translation, frozen-plan isocenter, tally mesh geometry,
axis-mapping version, input digests, output affine, and maximum independently
calculated patient-coordinate residual.

The normal public path SHALL use the approved plan-and-tally mapping rule. A
case-specific target override MUST contain three finite patient-coordinate
values and a non-empty reason, and the provenance SHALL distinguish the
rule-derived target from the requested target. The implementation MUST NOT
silently apply a phantom-specific or comparison-optimized target as a universal
default.

#### Scenario: Normal plan-derived placement is applied

- **GIVEN** complete frozen-plan, tally, and transform evidence
- **WHEN** coordinate correction runs without an override
- **THEN** it records plan-and-tally-derived placement mode
- **AND** the output voxel affine matches independently calculated mapped
  tally-bin centres within the approved tolerance

#### Scenario: A bounded reproduction supplies an explicit target

- **GIVEN** a separately approved non-patient research reproduction requires a
  finite target placement
- **WHEN** the caller supplies the target with a non-empty case-specific reason
- **THEN** the coordinate summary records both the rule-derived and requested
  targets, the reason, and the applied translation
- **AND** the target is not persisted as a package or GUI default

### Requirement: RTDOSE Completion Shall Require Patient-Coordinate Placement Validation

RTDOSE Run SHALL reopen the final coordinate-corrected output and independently
reconstruct its first, centre, edge, and final voxel patient coordinates. It
SHALL report success only when those coordinates match the expected mapped
tally geometry with zero relative tolerance and no DICOM Cartesian component
exceeding `1e-6` millimetres absolute residual, and all bound geometry digests
remain current. The execution summary SHALL record the maximum absolute
component residual across those validated voxels.

A coordinate-placement failure SHALL be a failed RTDOSE stage, not a warning.
The guided GUI MUST NOT show RTDOSE as Completed solely because conversion,
metadata synchronization, or file creation succeeded.

#### Scenario: Converter succeeds with a wrong translation

- **GIVEN** `phits2dicom` returns success and creates an RT Dose
- **BUT** the corrected output affine does not match the bound plan-and-tally
  geometry
- **WHEN** final RTDOSE validation runs
- **THEN** RTDOSE Run reports failure with coordinate evidence
- **AND** the GUI does not present the stage as Completed

#### Scenario: Final coordinate placement is proven

- **GIVEN** conversion and coordinate correction create a fresh output
- **AND** the final voxel affine, frozen-plan binding, tally geometry, and
  transform evidence all validate
- **WHEN** final RTDOSE validation completes
- **THEN** the execution summary records the placement rule, coordinate
  residual, and successful geometry validation
- **AND** the GUI may present RTDOSE as Completed

### Requirement: Coordinate Repair Shall Preserve Dose and Physics Semantics

The isocenter-translation change SHALL preserve stored dose values,
`DoseGridScaling`, `DoseUnits`, MU and Sumtally normalization, the approved
PHITS2DICOM dose factor, frozen-plan references, `FrameOfReferenceUID`, PHITS
segment outputs, and all source and accelerator physics. It SHALL NOT tune
coordinates against GPR or change external comparison criteria.

#### Scenario: A translated output is compared with its source dose

- **GIVEN** a supported RT Dose requires an approved coordinate translation
- **WHEN** coordinate correction completes
- **THEN** every mapped voxel retains its source stored value and physical dose
- **AND** dose, MU, normalization, identity, and physics semantics remain
  unchanged

### Requirement: Coordinate Validation Shall Use Synthetic Repository Evidence

Automated coordinate validation SHALL use synthetic DICOM, synthetic nonzero
isocenters, asymmetric tally bounds, unequal dimensions, anisotropic spacing,
and fake or mock converter runners. It MUST NOT add or run real DICOM, PHITS,
Sumtally, `phits2dicom`, GPR-comparing, or calculation outputs in repository
tests.

#### Scenario: Translation regression is tested

- **WHEN** the plan-and-tally affine and fail-closed RTDOSE behavior are tested
- **THEN** only synthetic identifiers and temporary generated artifacts are
  used
- **AND** no external scientific executable or real workflow data is required
