# Bundle Authenticated Python Runtime

## Why

The offline bootstrap currently authenticates and locks the installed
`python.exe` and its adjacent runtime DLLs before execution. Even with isolated
mode and site initialization disabled, CPython still loads the installation's
unsigned standard library, including `Lib\encodings`, before the verified
bundle helper can run. An allowed existing installation can therefore execute
modified standard-library code without violating the executable and DLL
checks.

File read locks cannot establish the provenance of pre-existing Python source
files, and the full CPython installer cannot reliably create a separate target
when the same product is already in maintenance mode. The bootstrap needs an
application-local runtime whose complete executable input is derived from
authenticated immutable bundle artifacts.

## What Changes

- Replace existing-interpreter discovery and the bundled full installer with
  an authenticated CPython 3.12.10 application-local runtime.
- Bundle the official signed `python` NuGet package, the official signed
  CPython Tcl/Tk MSI component, and a pinned signed NuGet verification CLI.
- Verify the NuGet repository signature and Tcl/Tk Authenticode signature
  before extracting either runtime source.
- Build the runtime only in a previously absent bundle-local directory, reject
  links, reparse points, unsafe archive paths, duplicates, and unexpected
  pre-existing runtime content, and read-lock every resulting runtime file
  before the first Python launch.
- Use only the application-local interpreter for the version probe, helper,
  virtual-environment creation, pip, and Tkinter validation. Never execute an
  existing host Python candidate.
- Preserve the repository-local `.venv`, binary-only wheelhouse, no-network
  pip, optional GUI launch, and external-tool boundaries.

## Impact

- Affected capability: `windows-offline-installation`
- Affected producer: `tools/prepare_offline_bundle.ps1` and bundle assembly
- Affected consumer: `install_offline.cmd` and
  `tools/install_offline_verified.ps1`
- Affected tests: offline artifact provenance, bootstrap ordering, archive
  extraction, runtime locking, malicious host-Python rejection, and synthetic
  application-local runtime validation
- Affected documentation: English and Japanese Windows offline instructions
- Unchanged: public physics, DICOM meaning, coordinates, dose, MU,
  normalization, machine model, field-size guard, supported treatment
  techniques, and all external-tool execution contracts

## Approval Status

Approved by the primary user on 2026-08-12 before runtime implementation. The
approval specifically replaces reuse of existing Python installations with a
fully authenticated and read-locked application-local CPython runtime in the
same pull request.
