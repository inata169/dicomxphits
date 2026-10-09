# CT2PHITS Frontend Specification

## Purpose

Define the safe, auditable Windows stage that converts one validated DICOM CT
series through the external RT-PHITS batch adapter and hands verified CT2PHITS
assets to existing workspace preparation.

## Requirements

### Requirement: Explicit External Execution Gate

The CT2PHITS frontend SHALL run only on Windows and SHALL require explicit
confirmation that the input is a non-patient phantom before it creates an
execution workspace. It MUST NOT discover external installations or datasets
on its own.

#### Scenario: Confirmed Windows execution

- **WHEN** a user supplies all required paths on Windows and explicitly
  confirms a non-patient phantom
- **THEN** the frontend may prepare the external execution workspace

#### Scenario: Unsupported platform

- **WHEN** the frontend is invoked on a non-Windows platform
- **THEN** it rejects execution before creating the workspace

#### Scenario: Missing phantom confirmation

- **WHEN** explicit non-patient phantom confirmation is absent
- **THEN** it rejects execution before creating the workspace

### Requirement: CT Series Selection and Inspection

The frontend SHALL select exactly one CT DICOM series from the supplied
directory. It SHALL require explicit Series Instance UID selection when more
than one series is present and SHALL reject unreadable or inconsistent geometry
needed by the existing axial HFS coordinate contract. The selected CT series
and RT Plan MUST share a Frame of Reference UID. Adjacent DICOM Z positions
MUST have uniform spacing using relative tolerance zero and absolute tolerance
`1.0e-6 mm`. Every slice MUST provide the same two finite, positive
`PixelSpacing` values. RT Plan `BeamNumber` and `ReferencedBeamNumber` values
used to select treatment beams MUST be valid integers.

#### Scenario: Single valid CT series

- **WHEN** the supplied directory contains one internally consistent axial HFS
  CT series and the RT Plan uses the same Frame of Reference UID
- **THEN** the frontend selects the series and orders slices by DICOM Z position

#### Scenario: Ambiguous CT directory

- **WHEN** more than one CT series is present and no Series Instance UID is
  specified
- **THEN** the frontend rejects the input as ambiguous

#### Scenario: Geometry or frame mismatch

- **WHEN** CT orientation, dimensions, slice positions, or Frame of Reference
  metadata violate the supported contract
- **THEN** the frontend rejects the input before external execution

#### Scenario: Invalid RT Plan beam identifier

- **WHEN** a treatment beam or referenced beam has a non-integer beam number
- **THEN** the frontend reports a controlled input failure before workspace
  creation

### Requirement: Isolated CT2PHITS Workspace and Input

The frontend SHALL create a new workspace below the supplied RT-PHITS root and
outside the `dicomxphits` repository. It SHALL refuse an existing workspace,
copy the complete validated CT series without modifying sources, write a
manifest, and generate `ct2phits.inp` using the reviewed CT2PHITS procedure.
The input SHALL default to the full source slice count and Rows and Columns.
It MAY use explicitly supplied, validated one-based inclusive pixel and slice
ranges under the `ct-pixel-clipping` contract. It SHALL use coarse graining
`8 8 2` by default, accept an explicit factor triple with equal positive
integer X/Y values and a Z value from `1` through `4`,
and retain DICOM coordinate mode `1`. Requested ranges and factors SHALL be
recorded in `ct2phits_input.clipping`, `ct2phits_input.slice_range`, and
`ct2phits_input.coarse_graining` without changing the
original snapshot numbering, source dimensions, slice count, or origin.
For clipped conversion, the manifest SHALL also record retained source
bounds, discarded high-end source counts, expected voxel counts, and the frozen
placement reference slice. The frontend SHALL reject zero-voxel selections,
check the raw tool's DICOM origin against that slice, and check the generated
voxel counts against complete coarse groups before accepting the handoff.
For every clipped or non-default-factor conversion, the frontend SHALL verify
the generated lattice parameters, surfaces, fill dimensions, conversion-table
material definitions, and every voxel material against the frozen source CT.
It MUST reject differences and preserve the original and accepted voxel
hashes in the execution evidence. It SHALL preserve the default full-volume
`8 8 2` output bytes when no clipping is requested.
The execution summary SHALL record the placement origin separately from the
full-series source origin.
The frontend SHALL record the source RT Plan SHA-256,
copy it into the isolated workspace without modification, verify the snapshot
hash, and use only that stable snapshot for the downstream handoff. It SHALL
also verify each CT slice hash before and after copying, record the snapshot
hashes, re-enumerate the source series membership, recheck every source hash,
and revalidate the copied CT series before external execution. After external
execution and again after downstream preparation, it SHALL recheck the RT Plan
and every CT snapshot hash, the exact CT directory contents, and the DICOM
geometry of both snapshots before accepting the handoff.

#### Scenario: New workspace preparation

- **WHEN** the supplied RT-PHITS root contains `RTphits_win.bat` and
  `data/HumanVoxelTable.data`, and the workspace path is new and in bounds
- **THEN** the frontend copies all validated CT slices and writes the manifest and
  CT2PHITS input with paths relative to the RT-PHITS root

#### Scenario: Existing output protection

- **WHEN** the requested workspace already exists
- **THEN** the frontend refuses to overwrite or reuse it

#### Scenario: Missing distribution component

- **WHEN** the required batch file or HU conversion table is missing
- **THEN** the frontend rejects execution before workspace creation

#### Scenario: RT Plan snapshot copy failure

- **WHEN** copying or hashing the RT Plan snapshot fails before external execution
- **THEN** the frontend reports a controlled failure and removes the newly
  created workspace when cleanup succeeds

#### Scenario: Other workspace preparation failure

- **WHEN** CT snapshot copying, copied-series revalidation, input generation,
  or initial manifest writing fails before external execution
- **THEN** the frontend reports a controlled failure and removes the newly
  created workspace when cleanup succeeds

#### Scenario: Source series changes during snapshot creation

- **WHEN** the selected source series gains, loses, or changes a slice while
  workspace snapshots are being created
- **THEN** the frontend rejects the snapshot before external execution and
  removes the new workspace when cleanup succeeds

#### Scenario: Workspace input changes during external execution

- **WHEN** the RT Plan snapshot, any CT snapshot, or the CT directory contents
  change while the external batch runs
- **THEN** the frontend rejects the generated output before downstream handoff

#### Scenario: Unsafe command-processor path

- **WHEN** the workspace-relative input path contains a `cmd.exe` metacharacter
- **THEN** the frontend rejects execution before workspace creation

#### Scenario: Explicit clipped conversion

- **WHEN** supplied pixel/slice ranges pass source validation and the established
  supported-tool clipping and coordinate contract
- **THEN** the frontend writes those ranges to the CT2PHITS input and manifest
  while retaining all source snapshots and existing integrity checks

#### Scenario: Invalid or unsupported selection

- **WHEN** a requested range is malformed, outside the selected source, or cannot
  satisfy the established clipping contract
- **THEN** the frontend rejects it before workspace creation or external execution

#### Scenario: Numeric coarse-graining factors

- **WHEN** the user supplies equal positive X/Y factors and a Z factor from
  `1` through `4` under the established supported-tool geometry contract
- **THEN** the frontend writes the same factors to the CT2PHITS input and
  manifest while leaving source CT geometry unchanged

#### Scenario: Invalid or output-free factors

- **WHEN** X and Y differ, Z is outside `1` through `4`, a factor is not a
  positive integer, or no complete coarse voxel fits on an axis
- **THEN** the frontend rejects it before workspace creation or external execution

#### Scenario: Other output discrepancy

- **WHEN** the generated geometry, material definitions, or voxel materials
  differ for any other reason
- **THEN** downstream preparation stops with a recorded failure

### Requirement: Verified Windows Batch Adapter

The frontend SHALL invoke `RTphits_win.bat` through the Windows command
processor and MUST NOT invoke `ct2phits_win.exe` directly. It SHALL enforce a
positive finite timeout and capture return code, stdout, stderr, timing, and a
failure reason in workspace logs and summary JSON. Process output SHALL be
captured as bytes and decoded using the Windows locale encoding with replacement
for undecodable byte sequences. A process-log write failure SHALL be recorded
separately in the summary and MUST NOT replace earlier execution-failure
evidence or prevent the other process log from being written.

#### Scenario: Successful batch execution

- **WHEN** the batch adapter finishes within the timeout with return code zero
- **THEN** the frontend records the execution evidence and validates generated
  outputs

#### Scenario: Non-zero return code

- **WHEN** the batch adapter returns a non-zero code
- **THEN** the frontend records the code and logs and marks the stage failed

#### Scenario: Timeout

- **WHEN** the batch adapter exceeds the configured timeout
- **THEN** the frontend records available output, marks the execution timed out,
  records any separate process-tree termination failure, and marks the stage failed

#### Scenario: Process-log write failure

- **WHEN** stdout or stderr cannot be written to its workspace log
- **THEN** the frontend preserves any earlier execution failure, records the
  log-write error in the summary, attempts the other log, and marks the stage
  failed

### Requirement: Nine-File Generated Output Inventory

The frontend SHALL require the nine CT2PHITS-generated files
`CTusrparam.dat`, `CTcell.dat`, `CTmaterial.dat`, `CTuniverse.dat`,
`CTsurf.dat`, `CTmatnamecolor.dat`, `CTvoxel.dat`, `phantominfo.dat`, and
`CTtrans.dat`. Every required file MUST be absent immediately before execution
and MUST be a non-empty regular file afterward. The inventory SHALL record each
file's size, modification time, and SHA-256 digest without relying on filesystem
timestamp precision to establish freshness. The execution summary SHALL record
whether the pre-run absence check passed.

#### Scenario: Complete fresh output

- **WHEN** all nine required files were absent immediately before execution and
  are non-empty regular files afterward
- **THEN** the frontend records all nine files in the generated inventory

#### Scenario: Pre-existing, missing, empty, or symbolic output

- **WHEN** any required generated file exists before execution or is missing,
  empty, or a symbolic link afterward
- **THEN** the frontend marks the stage failed and does not accept the handoff

### Requirement: Existing DATfiles and Coordinate Handoff

The frontend SHALL pass the eight raw downstream DATfiles to
`validate_raw_ct2phits_datfiles()` and SHALL call
`prepare_ct2phits_assets()` without reimplementing HU conversion, coordinate
conversion, or physics. It SHALL verify that raw hashes do not change during
handoff. Generated `CTtrans.dat` is inventory-only; the existing preparation
path SHALL create the downstream `CTtrans.inp` together with the other five
prepared assets.

#### Scenario: Valid downstream handoff

- **WHEN** all generated outputs and DICOM frame relationships pass validation
- **THEN** the frontend records hashes for the eight raw DATfiles and six
  prepared assets and marks the stage completed

#### Scenario: Raw files change during handoff

- **WHEN** any raw DATfile hash changes between validation and asset preparation
- **THEN** the frontend rejects the handoff and marks the stage failed

### Requirement: Synthetic Automated Test Boundary

Automated tests SHALL use synthetic DICOM and fake or mock external-tool
runners. CI and ordinary development MUST NOT run real PHITS, RT-PHITS,
Sumtally, phits2dicom, or GPR-comparing tools.

#### Scenario: Automated success test

- **WHEN** the frontend success path is tested automatically
- **THEN** a fake runner creates synthetic output files in a temporary
  workspace

#### Scenario: Real smoke validation

- **WHEN** a real RT-PHITS smoke test is desired
- **THEN** it runs only after explicit human authorization with a designated
  non-patient phantom outside the repository and remains optional local
  evidence rather than a CI requirement
