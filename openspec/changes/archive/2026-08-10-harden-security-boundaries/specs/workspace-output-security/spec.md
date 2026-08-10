# Workspace Output Security Delta

## ADDED Requirements

### Requirement: Bounded Workspace Mutation

Before a workspace-local stage creates, replaces, or removes an output, it SHALL
validate every existing path component from the explicitly supplied case
root through the output parent. It MUST reject a symbolic-link, Windows
junction, or other reparse-point case root, ancestor, target, or staging path;
MUST confirm that normalized and resolved destinations remain below the case
root; and MUST fail with a controlled path-specific error before external
execution or out-of-root mutation.

#### Scenario: Normal new workspace output

- **WHEN** a new or existing case root and all output ancestors are ordinary
  local directories and the normalized output is below the root
- **THEN** the existing GUI or CLI stage creates its documented output with no
  path or content schema change

#### Scenario: Symbolic-link output ancestor

- **WHEN** any existing component between the case root and an output is a
  symbolic link to a directory inside or outside the root
- **THEN** the stage rejects the path before writing through the link

#### Scenario: Windows junction or reparse-point output ancestor

- **WHEN** any existing component between the case root and an output is a
  junction or another Windows reparse point
- **THEN** the stage rejects the path before writing through it

#### Scenario: Linked existing output

- **WHEN** an output selected for overwrite or removal is a symbolic link,
  junction-like reparse point, or resolves outside the case root
- **THEN** the stage neither follows nor removes the unsafe entry and reports a
  controlled error

### Requirement: Race-Reduced Output Creation

Workspace-local writers SHALL create new files exclusively or replace an
existing regular file atomically from a same-directory exclusively created
temporary regular file. They SHALL revalidate the guarded path immediately
before mutation and, on Windows, hold non-delete-sharing handles for validated
existing directories throughout the mutation. Cleanup MUST use the same path
guard and MUST NOT follow a linked or reparse-point target.

#### Scenario: Output appears after preflight

- **WHEN** a new-only output path becomes occupied after initial validation
- **THEN** exclusive creation fails without overwriting the new entry

#### Scenario: Ancestor replacement attempt on Windows

- **WHEN** another process attempts to rename or replace a validated output
  ancestor while the stage holds its guard
- **THEN** the replacement cannot redirect the guarded mutation outside the
  case root

#### Scenario: Failure cleanup encounters unsafe path

- **WHEN** cleanup would traverse or remove a linked/reparse-point path
- **THEN** cleanup refuses that mutation and preserves the controlled failure
  evidence without acting on the link target

### Requirement: Synthetic Path-Security Validation Boundary

Automated output-path security tests SHALL use temporary synthetic workspaces,
synthetic DICOM descriptors, and fake or mock runners. Windows coverage SHALL
create real temporary junctions/reparse points where supported. Tests MUST NOT
use patient DICOM, licensed tools, real calculation outputs, or paths outside
test-controlled temporary storage.

#### Scenario: Cross-platform symlink escape test

- **WHEN** a temporary workspace output parent links to a test-controlled
  outside directory
- **THEN** the writer fails and the outside sentinel and output set are
  unchanged

#### Scenario: Windows junction test

- **WHEN** a Windows test creates a real directory junction from a workspace
  output parent to a test-controlled outside directory
- **THEN** the writer recognizes the reparse point, fails closed, and creates,
  overwrites, or deletes nothing in the outside directory
