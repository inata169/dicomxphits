# Simplified Guided GUI Tool Setup Design

## Context

The GUI currently remembers stable local paths but displays four independent
tool settings and a manually editable CT2PHITS workspace on the first workflow
page. The existing safe suggestion logic changes only empty values. As a
result, changing the RT Plan or RT-PHITS root can leave a stale workspace path
that fails the required containment check.

PHITS installation, external-tool execution, and case output are different
concepts:

- the PHITS installation folder is stable local configuration;
- the RT-PHITS folder and executables are tool-profile members;
- the CT2PHITS workspace is a new per-case output and is not an installation
  root.

The interface should preserve those distinctions internally while asking a
normal user for as little configuration as possible.

## Goals and Non-Goals

### Goals

- Make standard Windows setup possible from one explicitly selected PHITS
  installation folder.
- Validate the complete tool profile before enabling an external stage.
- Remove normal manual entry of the CT2PHITS workspace.
- Recompute case output from current inputs instead of retaining stale derived
  values.
- Preserve an advanced escape hatch for a valid nonstandard layout.
- Keep all current execution, non-patient, overwrite, repository-boundary, and
  audit gates fail-closed.

### Non-Goals

- Search drives, environment variables, registries, or unrelated directories
  for PHITS installations.
- Read or redistribute official PHITS or RT-PHITS file contents.
- Launch an external tool while validating setup.
- Choose among multiple executable variants without a documented deterministic
  rule.
- Change CT2PHITS input, geometry, physics, DICOM meaning, or downstream dose
  behavior.
- Combine CT2PHITS and 3D-CRT workspaces or run the complete workflow with one
  click.
- Support a workspace outside the RT-PHITS root in this change; that remains a
  separate CT2PHITS frontend contract decision.

## Decisions

### One Explicit Installation Selection

The primary setup control is `PHITS installation folder`. After the user
selects it, the GUI checks a versioned, bounded list of relative candidate
paths for each required role. It does not recurse beyond those candidates and
does not inspect file contents.

The initial approved profile is the PHITS 3.35-style Windows layout:

- PHITS root: the explicitly selected installation folder;
- PHITS executable: `bin/phits_win.exe`;
- RT-PHITS root: `utility/RTphits`;
- RT-PHITS execution markers: `RTphits_win.bat` and
  `data/HumanVoxelTable.data`; and
- phits2dicom executable: the single regular file matching
  `phits2dicom*.exe` directly below `utility/RTphits/bin`.

The resolver does not infer the installed PHITS version from this match and
does not inspect distribution file contents. This candidate table was confirmed
by the maintainer as the current PHITS 3.35 relative layout. A future layout
that does not match is treated as unsupported and falls back to custom-layout
mode until another bounded profile is explicitly added.

The resolver returns a structured result for the PHITS root, RT-PHITS root,
PHITS executable, phits2dicom executable, and every required marker. A role is
ready only when its supported candidate is uniquely resolved and is the
expected file or directory type. Missing and ambiguous roles are reported
without silently guessing.

### Explicit Advanced Custom Layout

Standard layout is the default mode. Advanced custom-layout mode exposes the
four effective paths and requires explicit user selection before edits are
used. Custom paths receive the same existence, file-type, RT-PHITS batch, and
HU-table checks as derived paths. Switching the selected installation folder
refreshes standard derived state and does not silently overwrite stored custom
values.

### Validate and Save Without Execution

The GUI provides one `Validate and save setup` action. It performs filesystem
checks only, saves successful stable settings to the ignored local JSON, and
shows a role-by-role readiness result. Restored settings are revalidated on
launch because an installation may have moved or changed. An invalid profile
does not enable an external stage and does not imply that an external tool was
executed successfully.

### Automatic CT2PHITS Case Workspace

In standard mode the GUI derives the workspace from the effective RT-PHITS
root, the existing `work` child, a sanitized RT Plan filename stem, and the
`ct2phits` suffix. This preserves the currently accepted CT2PHITS frontend
layout. The path is visible but read-only in the primary flow.

Derived state is owned by the GUI: changing the RT Plan or effective RT-PHITS
root recomputes it even when the previous derived value was non-empty. The GUI
still refuses an existing workspace and a path inside the dicomxphits
repository. Advanced custom-layout mode may expose an explicit workspace
override, but it must satisfy the unchanged CT2PHITS frontend validation.

### Backward-Compatible Local Settings

Existing flat path settings continue to load. When they form a valid supported
standard layout, the GUI migrates them into the standard profile. Otherwise it
retains them as an advanced custom layout rather than discarding them. The
ignored settings file may contain local absolute paths; tracked examples remain
empty and no case DICOM path, non-patient confirmation, or overwrite permission
is persisted.

## Risks and Mitigations

- Distribution layouts can change. Keep candidate paths versioned and bounded,
  fail clearly when no unique supported match exists, and preserve custom mode.
- Automatic values can look authoritative. Display effective paths and a
  readiness checklist, and validate again before every relevant stage.
- A stale workspace can target the wrong installation. Treat it as derived
  state and recompute it whenever either source input changes.
- Simplification could weaken execution gates. Keep external-stage confirmation
  and the accepted CLI validation unchanged.
- Personal paths could be committed. Store populated settings only in the
  existing ignored local file and keep public examples empty.

## Validation Strategy

- Test standard-layout resolution with synthetic temporary directory trees.
- Test missing, duplicate, wrong-type, moved, and nonstandard candidates.
- Test backward-compatible migration and ignored local persistence.
- Test that RT Plan or RT-PHITS changes replace stale derived workspace state.
- Test that custom mode remains explicit and receives identical prerequisite
  validation.
- Test that no resolver or setup action launches an external process.
- Run focused GUI tests and the complete public validation suite with
  synthetic/mock runners only.
- Treat any real non-patient PHITS or RT-PHITS smoke execution as a separate,
  explicitly authorized optional validation step.

## Migration Plan

Existing settings load without data loss. The GUI initially derives a standard
profile only when the stored paths match one supported layout; otherwise it
selects advanced custom-layout mode and explains why. After implementation and
accepted validation, promote the modified guided GUI requirements and archive
this change before completion.
