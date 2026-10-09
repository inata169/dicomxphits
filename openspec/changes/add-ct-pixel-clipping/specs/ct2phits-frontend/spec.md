## MODIFIED Requirements

### Requirement: Isolated CT2PHITS Workspace and Input

The frontend SHALL create a new workspace below the supplied RT-PHITS root and
outside the `dicomxphits` repository. It SHALL refuse an existing workspace,
copy the complete selected CT series without modifying sources, write a
manifest, and generate `ct2phits.inp` using the reviewed CT2PHITS procedure.
The input SHALL default to the full source slice count and Rows and Columns.
It MAY use explicitly supplied, validated one-based inclusive pixel and slice
ranges under the `ct-pixel-clipping` contract. It SHALL retain coarse graining
`8 8 2` and DICOM coordinate mode `1`. Effective ranges SHALL be recorded in
`ct2phits_input.clipping` and `ct2phits_input.slice_range` without changing the
original snapshot numbering, source dimensions, slice count, or origin.
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
- **THEN** the frontend copies the selected slices and writes the manifest and
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
