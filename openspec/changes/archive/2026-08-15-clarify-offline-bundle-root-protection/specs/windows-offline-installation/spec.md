## MODIFIED Requirements

### Requirement: Bundle Integrity Inventory

The preparation command SHALL generate `bundle-manifest.json` and
`SHA256SUMS.txt` with normalized relative paths, byte sizes, SHA-256 values,
and artifact roles for every payload, and SHALL identify the source HEAD commit
and exact Git index-entry fingerprint. `SHA256SUMS.txt` SHALL also contain the
manifest digest and, as the unavoidable self-reference exception, MUST NOT
claim to contain its own digest. Every runtime source, verifier, and wheel MUST
be listed in both inventories. Offline bootstrap verification MUST use an
absolute PowerShell executable below the Windows system directory, MUST reject
reparse-point paths, and MUST NOT execute a bundle verifier, Windows Installer,
Python executable, helper, or pip until its required input has passed the
applicable inventory and signature checks and has been read-locked.
Before starting Windows PowerShell, the bootstrap MUST clear inherited CLR
profiling, startup-hook, and AppDomain-manager environment variables that can
load caller-selected managed or native code before the verification command.
The bootstrap MUST authenticate and rehash the manifest-listed
`install_offline.cmd`, retain a strict read handle without delete sharing on
that file to protect the bundle root from rename, and retain that protection
through the verified stage. The bootstrap MUST acquire a no-delete-sharing
handle for every required child directory below the bundle root in each
inventoried payload parent chain. Failure to acquire or retain the root-file
protection or any required child-directory handle MUST stop installation before
elevation; an access-denied child directory MUST NOT be skipped. The bootstrap
MUST reject any unmanifested file in the extracted source tree. Before helper
or pip execution, the elevated stage SHALL copy only inventoried payloads into
protected storage, and the non-elevated stage MUST use that exact protected
snapshot for bundle verification, wheel installation, and editable source
installation.

#### Scenario: Complete inventory

- **WHEN** staging finishes successfully
- **THEN** every downloaded and source payload has matching size and SHA-256
  metadata and the checksum file includes the completed manifest

#### Scenario: Unsafe inventory path

- **WHEN** an inventory entry is absolute, duplicated, escapes the bundle root,
  or traverses a symbolic link, junction, or other reparse point
- **THEN** verification rejects the bundle before executing a verifier,
  Windows Installer, Python, helper, or pip

#### Scenario: Payload changed after preparation

- **WHEN** any inventoried payload has a different size or SHA-256
- **THEN** offline installation stops before runtime extraction or dependency
  changes

#### Scenario: Unmanifested build source

- **WHEN** the extracted bundle contains `setup.py` or another file absent from
  the integrity inventories
- **THEN** bootstrap rejects it, the protected source snapshot excludes it,
  and neither helper nor pip executes it

#### Scenario: Current-directory PowerShell lookalike

- **WHEN** the extraction or current directory contains `powershell.exe`
- **THEN** bootstrap uses only the quoted absolute Windows system PowerShell
  path and the lookalike is not executed

#### Scenario: Inherited CLR startup injection

- **WHEN** the caller sets CLR profiler, startup-hook, or AppDomain-manager
  environment variables before starting the offline bootstrap
- **THEN** bootstrap clears them before its first PowerShell process and no
  caller-selected CLR startup code runs

#### Scenario: Bundle root is the caller current directory

- **WHEN** the calling PowerShell retains the extracted bundle root as its
  current directory
- **THEN** bootstrap protects the root through the authenticated, rehashed,
  strict `install_offline.cmd` read handle, protects every required child
  directory with a no-delete-sharing handle, and blocks root and child-directory
  rename through the verified stage

#### Scenario: Bundle root protection cannot be acquired

- **WHEN** the manifest-listed `install_offline.cmd` cannot be authenticated,
  rehashed, or held with the required strict read handle
- **THEN** bootstrap fails before elevation and does not execute a bundle
  verifier, Windows Installer, Python, helper, or pip

#### Scenario: Bundle directory lock is denied

- **WHEN** a required child directory can be inspected but its protective
  no-delete-sharing handle cannot be acquired
- **THEN** bootstrap fails before elevation and does not skip that directory

#### Scenario: Runtime artifact changed after preparation

- **WHEN** the verifier, Python package, Tcl/Tk component, or another payload
  differs from its inventory
- **THEN** offline installation stops before extracting or executing runtime
  content

#### Scenario: Unsafe runtime extraction path

- **WHEN** a runtime archive entry is absolute, drive-relative, duplicated,
  escaping, link-like, non-regular, or traverses a reparse point
- **THEN** extraction fails before any Python process starts
