## ADDED Requirements

### Requirement: Explicit adoption of preserved staging evidence

A preserved staging tree SHALL remain non-authoritative and MUST NOT be reused
as an external-tool execution directory. A recovery capability MAY read exactly
one explicitly selected preserved tree only while holding the normal guarded
workspace and staging path identities and only after rejecting symbolic links,
Windows junctions, reparse points, out-of-root resolution, unsafe file types,
and path replacement.

Recovery MUST NOT scan for preserved trees, mutate or delete the selected tree,
or weaken the requirement that every later external execution use a fresh
exclusively created staging directory. Any adopted output and receipt SHALL use
the existing atomic and new-only output rules.

#### Scenario: Explicit guarded recovery reads preserved evidence

- **WHEN** one preserved staging tree is explicitly selected and every source
  and ancestor retains its validated ordinary path identity
- **THEN** recovery may read it as evidence without making it execution staging
  or changing any retained file

#### Scenario: Later execution follows recovery inspection

- **WHEN** a later external execution is separately requested after preserved
  evidence was inspected or adopted
- **THEN** that execution creates a different fresh staging directory and does
  not reuse the preserved tree

#### Scenario: Preserved path is unsafe or replaced

- **WHEN** the selected tree or any required source or ancestor is linked,
  reparse-backed, outside the workspace, replaced, or no longer the validated
  identity
- **THEN** recovery fails without reading through the unsafe path or creating,
  replacing, moving, or deleting an output
