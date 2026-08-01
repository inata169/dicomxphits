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
`1.0e-6 mm`.

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

### Requirement: Isolated CT2PHITS Workspace and Input

The frontend SHALL create a new workspace below the supplied RT-PHITS root and
outside the `dicomxphits` repository. It SHALL refuse an existing workspace,
copy selected CT slices without modifying their sources, write a manifest, and
generate `ct2phits.inp` using the reviewed CT2PHITS procedure. The input SHALL
use the selected slice count and Rows and Columns, coarse graining `8 8 2`, and
DICOM coordinate mode `1`. The frontend SHALL record the source RT Plan SHA-256,
copy it into the isolated workspace without modification, verify the snapshot
hash, and use only that stable snapshot for the downstream handoff.

#### Scenario: New workspace preparation

- **WHEN** the supplied RT-PHITS root contains `RTphits_win.bat` and
  `data/HumanVoxelTable.data`, and the workspace path is new and in bounds
- **THEN** the frontend copies the selected slices and writes the manifest and
  CT2PHITS input with paths relative to the RT-PHITS root

#### Scenario: Existing output protection

- **WHEN** the requested workspace already exists
- **THEN** the frontend refuses to overwrite or reuse it

#### Scenario: Missing distribution component

- **WHEN** the required batch file or HU conversion table is missing
- **THEN** the frontend rejects execution before workspace creation

### Requirement: Verified Windows Batch Adapter

The frontend SHALL invoke `RTphits_win.bat` through the Windows command
processor and MUST NOT invoke `ct2phits_win.exe` directly. It SHALL enforce a
positive finite timeout and capture return code, stdout, stderr, timing, and a
failure reason in workspace logs and summary JSON.

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
  and marks the stage failed

### Requirement: Nine-File Generated Output Inventory

The frontend SHALL require the nine CT2PHITS-generated files
`CTusrparam.dat`, `CTcell.dat`, `CTmaterial.dat`, `CTuniverse.dat`,
`CTsurf.dat`, `CTmatnamecolor.dat`, `CTvoxel.dat`, `phantominfo.dat`, and
`CTtrans.dat`. Every required file MUST be a fresh, non-empty regular file for
the current execution, and the inventory SHALL record its size, modification
time, and SHA-256 digest.

#### Scenario: Complete fresh output

- **WHEN** all nine required files were produced after the current execution
  started and are non-empty regular files
- **THEN** the frontend records all nine files in the generated inventory

#### Scenario: Missing, empty, symbolic, or stale output

- **WHEN** any required generated file is missing, empty, a symbolic link, or
  older than the current execution
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
