# Design: Authenticated Application-Local Python Runtime

## Trust gap

`-I -S` prevents environment, user-site, and `sitecustomize` influence, but it
does not remove the selected interpreter's `python312.zip`, `DLLs`, `Lib`, or
installation root from `sys.path`. Python source files do not carry usable
Authenticode signatures. Authenticating only the executable and DLLs therefore
cannot authenticate the code loaded during interpreter startup or by the
verified helper.

The offline bootstrap must not infer that a host installation is trustworthy
from its path, registry registration, file ownership, or executable signature.
It also must not repair, remove, or overwrite a host Python installation.

## Authenticated runtime sources

The producer downloads these exact public artifacts over HTTPS:

- the official CPython `python` NuGet package at version 3.12.10;
- the official CPython 3.12.10 x64 `tcltk.msi` component; and
- a pinned NuGet CLI executable used only for signature verification.

The pinned NuGet CLI is accepted only with a valid Microsoft Authenticode
signature. It verifies the Python package's NuGet repository signature and
must report the expected package identity and version. The Tcl/Tk MSI is
accepted only with a valid Python Software Foundation Authenticode signature.
Hashes, sizes, URLs, signer evidence, and package identity are recorded in the
bundle manifest. The downloaded runtime sources and NuGet verifier remain in
the bundle integrity inventory.

The NuGet package is the CPython-supported application-local distribution for
build and script execution. It contains the CPython 3.12.10 x64 executable,
runtime DLLs, standard library, `venv`, and `ensurepip`. The Tcl/Tk MSI supplies
`tkinter`, `_tkinter.pyd`, Tcl/Tk DLLs, and Tcl/Tk library data required by the
existing GUI.

## Offline extraction boundary

The trusted absolute Windows PowerShell process performs all pre-Python work.
It first revalidates and read-locks the bundled NuGet verifier, Python package,
and Tcl/Tk MSI. The NuGet verifier checks the package signature without a
network source. The trusted absolute Windows Installer executable creates an
administrative image of the signed Tcl/Tk MSI; it does not install or register
a host Python product.

The Python package is read as a ZIP only after signature verification. The
extractor accepts regular file entries below `tools/`, normalizes separators,
rejects absolute, drive-relative, escaping, duplicate, link-like, and empty
file paths, and writes them below a newly created staging directory. Tcl/Tk is
extracted into a separate new staging directory. Only the documented Tcl/Tk
runtime paths are copied into the Python runtime; installer metadata is not.

The final runtime directory must not exist before installation. A collision or
reparse component stops the bootstrap and instructs the user to use a fresh
bundle extraction. Staging is promoted only after all extraction processes
succeed and required files are present.

## Validation and lock lifetime

Before the first `python.exe` launch, the bootstrap recursively walks the
application-local runtime without following reparse points. It requires every
entry to be a regular file or ordinary directory and holds each file open for
read sharing only. Required executable and DLL files receive Authenticode
signer checks. The read locks remain held until the offline installation stage
exits.

The first probe imports only built-in `sys` and runs with `-I -S -B`. The same
base-interpreter flags are used for the verified helper and `venv` creation.
Pip and final import validation run only in the repository-local `.venv`, where
normal site-package discovery is required.

No host Python path, Python registry entry, `py.exe`, bare `python.exe`, or
caller-controlled executable search is used. A malicious or valid existing
Python installation is not inspected or executed.

## Failure and repeat-run behavior

The generated application-local runtime remains below the extracted bundle
because the repository-local `.venv` records it as its base interpreter. The
normal entry point is intentionally run once. If `.python-runtime` already
exists, a repeat run fails closed and directs the user to a fresh verified ZIP
extraction; the bootstrap does not infer provenance from existing bytes and
does not repair, reuse, or delete runtime content.

An incompatible existing `.venv` remains a controlled manual-remediation case.
The bootstrap does not delete or rename either `.venv` or runtime content.

## Validation boundary

Automated tests use synthetic packages, fake verifier/Windows Installer
processes, temporary directories, and copied signed test binaries. They do not
install a host Python product or run PHITS-related tools. A producer-side
manual validation may download the public artifacts, verify their signatures,
assemble a temporary application-local runtime, create a temporary venv, and
import Tkinter. Generated artifacts remain ignored and uncommitted.
