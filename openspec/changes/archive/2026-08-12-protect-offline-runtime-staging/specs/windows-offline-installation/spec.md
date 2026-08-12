# Windows Offline Installation Delta

## MODIFIED Requirements

### Requirement: One-Entry Offline Python Setup

The extracted bundle SHALL provide `install_offline.cmd` as the normal entry
point. It SHALL complete bundle verification and payload read locking before
requesting elevation. The elevated stage MUST perform only runtime-source
verification and protected runtime construction; Python, the helper, venv, and
pip MUST run in the original non-elevated stage after it validates the
protected receipt and runtime. It SHALL construct and use only the authenticated
installation-specific CPython 3.12.10 x64 runtime derived from the bundled
Python package and Tcl/Tk component. It MUST NOT discover, probe, repair,
install, or execute an existing host Python interpreter, registry candidate,
`py.exe`, or bare `python.exe`.

The runtime MUST be created below a protected Windows Common Application Data
root that is owned by built-in Administrators, grants mutation only to `SYSTEM`
and elevated Administrators, grants the installing user read/execute access,
and uses an inheritable `OWNER RIGHTS` rule that does not grant `WRITE_DAC`.
Before its first Python launch, the stage MUST validate the complete runtime
tree as regular non-reparse content with the exact protected owner and access
rules, compare every runtime file to its authenticated source-derived digest
while acquiring its read lock, reject any missing or additional entry, and
repeat the complete inventory while all file handles are held. Every file
handle MUST remain held through the end of installation.

#### Scenario: Elevation is denied or unavailable

- **WHEN** the verified stage cannot obtain and confirm administrator authority
- **THEN** setup stops before executing the NuGet verifier, Windows Installer,
  Python, helper, or pip and makes no runtime or dependency change

#### Scenario: Non-elevated process attempts runtime injection

- **WHEN** another process running as the installing user without elevation
  attempts to add `python312._pth`, a shadow module, or another entry after the
  authenticated runtime inventory
- **THEN** protected storage denies the addition, the final inventory remains
  complete, and no unauthenticated startup code executes

#### Scenario: Protected runtime boundary is not exact

- **WHEN** a protected parent or runtime path is existing, linked, incorrectly
  owned, has additional or writable access rules,
  or otherwise cannot prove the required protected state
- **THEN** setup stops before Python execution and does not repair, reuse,
  delete, or weaken that path

#### Scenario: Application-specific runtime is complete

- **WHEN** authenticated extraction produces the required CPython, standard
  library, venv, pip, and Tcl/Tk files under the exact protected boundary and
  every file and directory passes the final protected inventory
- **THEN** the absolute protected interpreter is probed as CPython 3.12 x64 and
  may run the verified helper

#### Scenario: Host Python is malicious

- **WHEN** an existing host installation contains signed Python binaries but a
  modified standard library or additional shadow module
- **THEN** the bootstrap does not inspect or execute that installation and uses
  only the authenticated protected runtime

#### Scenario: Current-directory Python lookalikes

- **WHEN** the extraction or current directory contains `python.exe` or
  `py.exe`
- **THEN** neither file executes during runtime construction or installation

### Requirement: Documented Safety and Transfer Boundary

English and Japanese documentation SHALL reduce offline operation to copying
and extracting the ZIP on a local disk, running `install_offline.cmd`, and
approving its administrator prompt. It SHALL explain why protected runtime
storage and administrator approval are required, how a denied prompt fails
without starting Python, that the protected runtime persists as the `.venv`
base, and that removal is a separate explicit administrator action. It SHALL
explain that PHITS, RT-PHITS, phits2dicom, and GPR-comparing remain separately
obtained external tools and SHALL preserve the education/research, non-patient
phantom, and fixed-field 3D-CRT boundaries. It MUST NOT instruct users to run
the editable environment from USB or imply clinical suitability.

#### Scenario: Offline user follows the primary instructions

- **WHEN** a user reads either language's primary offline procedure
- **THEN** the required steps are local-disk ZIP extraction, execution of
  `install_offline.cmd`, and approval of the verified administrator stage

#### Scenario: User denies administrator approval

- **WHEN** the user declines or cannot satisfy the administrator prompt
- **THEN** documentation states that installation stops before Python and does
  not advise weakening access controls or substituting a host interpreter

#### Scenario: External workflow tools are absent

- **WHEN** Python package installation completes without PHITS-related tools
- **THEN** documentation presents package setup as successful while explaining
  that separately and legitimately obtained external tools are still required
  for their explicit stages
