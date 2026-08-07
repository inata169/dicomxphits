# Design: Windows Offline Installer

## Two-computer workflow

The producer is an internet-connected 64-bit Windows computer with Git,
PowerShell, and a usable Python capable of running the repository preparation
helper. The consumer is an offline Windows 10 or 11 x64 computer.

The producer writes one versioned ZIP below `dist/`. The consumer copies that
ZIP from removable storage to a local writable directory, extracts it, and
runs the root `install_offline.cmd`. The installer does not run from inside the
ZIP and the documentation does not recommend an editable installation on the
USB device.

## Bundle layout and source boundary

The extracted ZIP root is also the editable project root. It contains the
public source tree, `pyproject.toml`, the existing launchers, the offline entry
point and helpers, documentation, `python/`, `wheelhouse/`,
`SHA256SUMS.txt`, and `bundle-manifest.json`. This avoids a second nested source
copy and makes the required `.venv` unambiguously repository-local.

The source list and source bytes come from Git's index, not recursive
filesystem discovery. The preparation step first runs
`tools/verify_public_tree.py`, then copies only the audited indexed regular-file
blobs into a new staging directory. A
required offline file that is not indexed is an error. Untracked worktree
files, unstaged modifications, ignored files, `.git`, local configuration,
existing virtual environments, build output, and tool/data directories are not
source inputs.
Generated bundle dependencies and metadata are then added only at their
explicit paths.

The manifest records the source HEAD commit, a SHA-256 fingerprint of the exact
Git index entry stream, and every bundled relative file. The preparation step
rejects path traversal, duplicate relative paths, unsupported Git entry types,
and any source path or content rejected by the public-tree audit. The reviewed
public zero-dose DICOM template may remain included as an
already allowlisted tracked source file; no other DICOM is permitted.

## Python installer provenance

The preparation script downloads the exact official 64-bit installer from the
Python 3.12.10 release path over HTTPS. It accepts the file only when Windows
reports a valid Authenticode signature whose signer identifies the Python
Software Foundation. The manifest records the source URL, SHA-256, size,
signature status, signer subject, certificate thumbprint, and certificate
validity metadata. A signature or signer mismatch stops before ZIP creation.

The offline installer validates the recorded SHA-256 before executing the
installer. Checksums provide corruption/tamper detection inside the delivered
bundle; users still obtain and transport the producer-created ZIP through
their own controlled process.

## Dependency resolution and wheel validation

A standard-library helper reads `project.dependencies` and the supported
Python range from `pyproject.toml`. The PowerShell producer invokes pip download
for CPython 3.12 on `win_amd64` with binary-only resolution and includes the
runtime requirements plus `setuptools` and `wheel`. Transitive wheels resolved
by pip remain in the wheelhouse and are inventoried.

Before packaging, the helper parses wheel filenames and verifies that direct
runtime requirements and the two editable-build tools are represented. It
specifically requires a NumPy wheel tagged exactly for
`cp312-cp312-win_amd64`; an `any`, another Python/ABI tag, a 32-bit wheel, a
source archive, or a missing wheel fails the build. Unexpected source
distributions are rejected.

## Integrity metadata

`bundle-manifest.json` uses relative slash-normalized paths and records each
payload file's role, byte size, and SHA-256, plus project, target, dependency,
Git HEAD and index-fingerprint, and Python-installer provenance.
`SHA256SUMS.txt` contains the payload
hashes and the final manifest hash. Because a checksum file cannot include its
own digest without a circular definition, it is the sole file not listed in
itself; all downloaded files are listed in both integrity inventories.

The offline verifier rejects a missing, extra-required, duplicate, absolute,
or escaping checksum path and any size or SHA-256 mismatch before Python
installation or pip execution. Metadata files are not treated as an
independent cryptographic signature.

## Python selection and installation

The command entry point first verifies the bundle with Windows built-in
facilities so verification works before Python is available. It searches only
documented Python Launcher, PATH, and current-user Python 3.12 candidates and
accepts only CPython 3.12 with a 64-bit interpreter. It does not accept a
different minor version merely because its executable is named `python`.

If no acceptable interpreter exists, the verified bundled Python 3.12.10 x64
installer runs quietly for the current user with pip, the Python Launcher, and
Tcl/Tk enabled. It does not request a machine-wide installation or change PATH,
create Python file associations, or create shortcuts. The installed
interpreter is revalidated for version, architecture, pip, and tkinter before
continuing. Installer failure stops with a logged controlled error.

## Virtual environment and offline pip contract

The repository root is derived from the command file location with quoted,
Unicode-capable path handling. If `.venv` is absent, the selected interpreter
creates it. If `.venv` exists, its interpreter must execute successfully and
report Python 3.12 x64; otherwise installation stops without deleting,
renaming, or repairing it and prints explicit manual remediation guidance.

Every pip installation command includes all of:

```text
--no-index
--find-links <bundled-wheelhouse>
--no-build-isolation
```

The process also sets pip's no-index environment guard. It installs
`setuptools` and `wheel`, the parsed runtime requirements, and finally the
project in editable mode. Missing or incompatible wheels fail locally with no
index or URL fallback. Subprocess argument lists, resolved paths, and
standard-library path operations preserve spaces, Japanese user names, and
changed USB drive letters.

## Completion, logging, and GUI startup

The installer imports `tkinter`, `numpy`, `pydicom`, and `dicomxphits` using
the repository-local environment. It appends timestamps, commands without
credentials, exit status, selected Python provenance, and Python/NumPy/pydicom
versions to `offline-install.log` in the extracted root.

After successful verification and imports, it prints the existing
`launchers/run_gui_venv.cmd` command. The GUI is launched through that existing
launcher only when the user explicitly chooses yes. Starting the installer or
creating the environment never starts PHITS, RT-PHITS, Sumtally,
phits2dicom, GPR-comparing, or any calculation.

## Safety and test boundary

The bundle and documents explicitly state the non-patient phantom,
education/research, and fixed-field 3D-CRT limits. PHITS, RT-PHITS,
phits2dicom, and GPR-comparing are separately and legitimately obtained
external tools. Official distributions, their named runtime files, real or
non-public DICOM, calculation results, local settings, private repository
material, credentials, personal information, and facility information are
excluded.

Automated tests use temporary synthetic files, fabricated wheel filenames and
content, fake subprocess runners, and placeholder Python probes. They do not
download, install, or execute real external tools. Actual bundle generation is
a separate producer-environment validation that may download only the public
Python installer and public dependency wheels explicitly required for this
task; generated binaries remain ignored and uncommitted.
