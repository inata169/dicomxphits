# Windows Offline Installation

This procedure installs the public dicomxphits Python environment on an
internet-disconnected Windows 10 or 11 x64 computer. It does not install or run
PHITS, RT-PHITS, phits2dicom, Sumtally, or GPR-comparing.

For Japanese instructions, see
[Windows offline installation (Japanese)](windows-offline-installation.ja.md).

## Safety and distribution boundary

dicomxphits remains education and research software for confirmed non-patient
phantoms and the documented fixed-field 3D-CRT workflow. Installation does not
establish clinical commissioning, patient QA, vendor certification, or
clinical suitability.

PHITS, RT-PHITS, `RTphits_win.bat`, `HumanVoxelTable.data`, phits2dicom, and
GPR-comparing must be obtained legitimately and installed separately by the
user. They are not in the offline ZIP. Real or non-public DICOM, PHITS results,
local settings, private-repository material, credentials, personal
information, and facility information are also excluded. The installer never
starts a PHITS calculation.

## Public bundle withdrawal

There is no currently supported public Windows offline bundle. The custom
`dicomxphits-offline-win64-1.0.2.zip` asset from the
[v1.0.2 GitHub Release](https://github.com/inata169/dicomxphits/releases/tag/v1.0.2)
is being withdrawn after a later candidate using the same relevant installer
and uninstaller implementation exposed a behavior-based endpoint-protection
failure during verified uninstallation. Do not download, install, or continue
to distribute that custom ZIP even if it remains temporarily visible while
manual removal is pending. Do not disable endpoint protection or exclude
system PowerShell as a workaround.

The following values are retained only as the historical identity of the
withdrawn v1.0.2 asset, not as download instructions:

```text
6b957e1ff236ef787d791db0921edabd18ea459a27fbe745f7c2d98979e86217
```

The historical asset was built from manifest source HEAD
`efb0dace568fbcb12019f3d320a468dcfb446e34`. The following build procedure is
retained for maintainer evaluation and future compatibility work only. Its
output is not a public release artifact and must not be represented or
distributed as a supported replacement bundle. A future public offline asset
requires separate review and a complete successful exact-HEAD installation,
GUI-startup, and verified-uninstall lifecycle under the intended endpoint
protection environment.

## Create an evaluation bundle on an online computer (maintainers only)

Use an internet-connected Windows 10/11 x64 computer with:

- a reviewed Git checkout of this repository;
- Git available on `PATH`;
- PowerShell 5.1 or later; and
- local CPython 3.12 x64 with pip.

From the repository root in PowerShell, run:

```powershell
.\tools\prepare_offline_bundle.ps1
```

If Python 3.12 is not discoverable through `py -3.12` or `python`, specify it:

```powershell
.\tools\prepare_offline_bundle.ps1 -PythonExe "C:\path\to\Python312\python.exe"
```

The script performs these checks before producing the ZIP:

1. runs the public-tree audit;
2. reads the version from `pyproject.toml` and the exact wheel versions,
   filenames, and SHA-256 values from `requirements/offline-win64.txt`;
3. downloads the exact official CPython 3.12.10 application-local NuGet
   package, CPython x64 Tcl/Tk MSI component, and pinned NuGet CLI over HTTPS;
4. requires the expected NuGet repository signature and package identity for
   CPython, a valid Python Software Foundation Authenticode signature for the
   Tcl/Tk component, and a valid Microsoft Authenticode signature for the
   NuGet CLI, then records their provenance and SHA-256 values;
5. asks pip for CPython 3.12 `win_amd64` wheels with binary-only resolution and
   `--require-hashes`;
6. rejects any missing, additional, renamed, or hash-mismatched wheel and
   verifies exact `cp312-cp312-win_amd64` compatibility for NumPy;
7. copies only the audited regular-file blobs already present in the Git index
   (untracked and unstaged bytes are not copied); and
8. writes `bundle-manifest.json`, `SHA256SUMS.txt`, and the final ZIP.

The output is:

```text
dist/dicomxphits-offline-win64-<version>.zip
```

If that file already exists, the script stops. Use `-Force` only after
confirming that the existing generated ZIP may be replaced. `dist/`, downloaded
runtime sources, wheels, and staging files are ignored and must not be
committed.

For bounded maintainer testing, copy the completed ZIP only through the
organization's controlled-media process and retain the SHA-256 printed by the
preparation script as transfer evidence. This does not make the ZIP a public or
supported release asset.

## Maintainer evaluation on the offline computer: three steps

The remaining installation and uninstallation procedure is retained for
controlled maintainer evaluation and future revalidation. It is not an
end-user installation procedure for a currently supported public bundle.

1. Copy the ZIP from USB to a writable folder on a local disk and extract it
   completely. Do not open files inside the ZIP and do not use the USB folder
   as the editable project location.
2. In the extracted folder, run `install_offline.cmd` once.
3. Approve the Windows administrator prompt for the verified installation
   stage. If you decline it, installation stops before Python starts.

In PowerShell, run the file with the following command. Do not use
`cd install_offline.cmd`; `cd` changes directories and does not execute files.

```powershell
.\install_offline.cmd
```

Before bundle verification, the command starts only the quoted absolute
`%__APPDIR__%WindowsPowerShell\v1.0\powershell.exe`, after clearing any inherited
`__APPDIR__` override so cmd.exe supplies its own application directory. It does
not use caller-supplied `SystemRoot`, current-directory, or `PATH` lookup for
PowerShell, `py.exe`, or `python.exe`.
The bootstrap rejects reparse-point protected paths and unexpected executable
lookalikes at the extracted root, verifies and read-locks every protected
payload, locks the bundle directory path against rename, revalidates every
payload through that locked path, and only then requests administrator approval
for protected runtime construction. The elevated child uses only absolute
Windows-system executables,
creates the runtime and protected hash receipt, and exits before Python starts.
The protected runtime identity is bound to both the normalized absolute
extraction root and the verified bundle-manifest SHA-256. A later authenticated
bundle freshly extracted at the same absolute path therefore receives a
different runtime identity, while an exact repeat of the same bundle still
fails closed instead of reusing protected content.
The original non-elevated stage then:

- validates and read-locks the bundled NuGet verifier, CPython package, and
  Tcl/Tk component before using them;
- safely constructs a complete installation-specific runtime below protected
  Windows Common Application Data storage from those authenticated sources;
  only `SYSTEM` and elevated Administrators may mutate it, while the installing
  user receives read/execute access;
- validates the exact protected owner and access rules, validates every file
  against its authenticated source-derived digest while acquiring its read
  lock, repeats the complete protected inventory, and retains every file lock
  through the end of installation before the first Python launch;
- uses an exact protected snapshot containing only inventoried bundle files for
  the helper, wheelhouse, and editable source; unmanifested files such as an
  added `setup.py` are rejected and never copied or executed;
- uses the declared setuptools PEP 660 backend so editable build metadata is
  written to temporary build storage, not the read-only protected source;
- clears inherited CLR profiler, startup-hook, and AppDomain-manager settings
  before the first PowerShell process, and fails if any required bundle
  directory cannot be held against rename;
- uses only that application-local CPython 3.12.10 x64 interpreter with
  `-I -S -B`; it never discovers, probes, installs, repairs, or executes a host
  Python, registry candidate, `py.exe`, or bare `python.exe`;
- creates the extracted project's `.venv`;
- installs the exact locked dependencies only from `wheelhouse/` with
  `--require-hashes`, `--no-index`, `--find-links`, and
  `--no-build-isolation`;
- installs dicomxphits in editable mode;
- imports `tkinter`, `numpy`, `pydicom`, and `dicomxphits`;
- records the Python, NumPy, and pydicom versions in `offline-install.log`; and
- displays the existing `launchers\run_gui_venv.cmd` command.

The GUI starts only if you answer `y` or `yes` to the final prompt. Declining
the prompt still leaves a successful installation. Start it later with:

```cmd
launchers\run_gui_venv.cmd
```

The protected runtime and source snapshot remain after success because `.venv`
records the runtime as its base interpreter and the editable installation
records the protected source. The installer never deletes or repairs one
automatically. Use the verified uninstaller below when the complete extracted
installation is no longer needed.

## Uninstall one offline installation

Close its GUI and every Python or PHITS-related process first. Also close every
terminal, File Explorer window, editor, or other process whose current folder
is the extracted installation. Start the uninstaller from File Explorer, or
from a terminal whose current directory is outside that folder. For example:

```powershell
Set-Location D:\
& "D:\path\to\dicomxphits-offline-win64-<version>\uninstall_offline.cmd"
```

After the local verification succeeds, type the exact confirmation word
`UNINSTALL` and approve the Windows administrator prompt. The verified
uninstaller binds the current normalized extraction path and manifest digest
to its protected receipt, checks the receipt owner and access rules, and
refuses to discover or guess another runtime.

Before deleting anything, it verifies that authenticated bundle payloads are
unchanged, allows only the installer-created `.venv` and installation log, and
rejects unknown files, unknown directories, reparse points, associated running
processes, or any exact target that Windows cannot open for deletion while
sharing deletion with the cleanup process. This last check prevents a terminal
whose current directory is the extracted folder from causing a partial
deletion. Move any intentional additional file out of the extracted folder and
close every process using it before retrying. Do not weaken these checks.

A successful uninstall removes only that extracted bundle, its `.venv`, its
installation log, its exact protected runtime and source snapshot, its receipt,
its Windows Installer log, and bounded cleanup staging. It does not remove
another extracted installation or runtime ID, case folders, DICOM, PHITS or
other external tools, or per-user GUI settings. The latter remain at
`%LOCALAPPDATA%\dicomxphits\dicomxphits.gui.local.json`; remove that exact file
separately only if the user intentionally wants to discard settings shared with
future installations.

Deletion across the local installation disk and protected `ProgramData`
storage cannot be transactional. If Windows prevents a target from being
removed after cleanup begins, uninstallation remains failed and reports the
exact installation-owned path that remains; it never broadens the deletion
scope. Because the verified bootstrap must release its read locks before its
own folder can be removed, the command schedules the final elevated deletion
and prints the exact protected `failure.json` location. Successful cleanup
removes that staging path; while it remains, open the reported file to
distinguish the exact pending sentinel described below from a different
terminal error or indeterminate evidence.

The `Verified cleanup was scheduled` message and return to the calling prompt
mean that the authenticated parent handed work to the detached elevated
finalizer. They do not mean that removal has already finished, and they do not
mean that it failed. The extracted folder can remain briefly while the parent
exits, releases its bundle read locks, and the finalizer completes its bounded
checks and deletion. During this interval, do not run the uninstaller again or
manually delete any target.

Wait for an observable outcome. The finalizer writes a protected
`failure.json` with the exact message `Final cleanup staging removal is
pending.` after the installation targets are absent but before its child
removes cleanup staging. That exact message is a pending sentinel, not a
failure; continue to wait and do not rerun or delete anything.

Success is complete only after the extracted folder and the reported
cleanup-staging directory have disappeared; before removing that staging
directory, the finalizer verifies that every exact installation-owned target
is absent. A terminal cleanup failure retains the staging directory and
replaces the pending sentinel with a different error message whose
`remaining_paths` list identifies the exact remnants. If the report is missing,
unreadable, malformed, or remains at the pending sentinel without reaching
either outcome, the state is indeterminate rather than success or failure.
Preserve the evidence and investigate; do not rerun uninstall or manually
delete targets. The uninstaller does not publish a fixed completion deadline.
Seeing the extracted folder immediately after prompt return is only an
in-progress observation and is not, by itself, an uninstall failure.

## Integrity files

`bundle-manifest.json` records the source HEAD commit, a SHA-256 fingerprint of
the exact Git index entries, target, runtime requirements, wheel tags, runtime
source URLs, NuGet and Authenticode signer evidence, the reviewed wheel lock,
and the role, size, and SHA-256 of every payload. Normal CI uses the same pinned
NumPy and pydicom versions from `requirements/runtime.txt`.

`SHA256SUMS.txt` records every payload digest and the manifest digest. It cannot
contain its own digest because that would be circular. The checksum inventory
detects transfer corruption or changed bundle content; it is not a replacement
for your organization's controlled USB handling.

## Troubleshooting

### SHA-256 mismatch

Nothing is installed. Delete the extracted copy, copy the producer-created ZIP
again, and compare the ZIP SHA-256 with the value printed on the online
computer. Do not edit `SHA256SUMS.txt` to accept changed content.

### Existing `.venv` uses another Python

The installer stops without deleting or changing it. If the environment is no
longer needed, a human may rename or remove `.venv` after reviewing it, then
rerun `install_offline.cmd`. The installer does not make that destructive
decision automatically.

### A wheel is missing or incompatible

There is no internet fallback. Recreate the bundle on the online computer and
resolve the reported binary wheel problem there. Do not copy an unreviewed
source archive into `wheelhouse/`.

### Python runtime construction fails

Review `offline-install.log` in the extracted root. The protected Windows
Installer log is stored as `%ProgramData%\dicomxphits\offline-runtimes\*-msi.log`.
Do not substitute a locally installed Python or edit checksum-protected runtime
sources. Extract the producer-created ZIP into a fresh ordinary local folder
and retry. Organization policy may still control Windows Installer
administrative extraction even though no host Python product is installed.

### Administrator approval is declined or unavailable

The installer stops before the NuGet verifier, Windows Installer, Python,
helper, or pip starts. Rerun `install_offline.cmd` and approve the verified
Windows-system PowerShell stage. Do not weaken folder permissions, copy a host
Python into the bundle, or run a partially created runtime.

### A protected runtime already exists

The installer does not reuse, repair, or remove an exact-repeat target. If the
old installation still exists, run its `uninstall_offline.cmd` rather than
manually identifying a hashed `ProgramData` directory. A newly produced bundle
with a different verified manifest may be freshly extracted into an empty
directory at the same absolute path and receives a distinct protected runtime.
Do not copy new bundle files over a populated installation tree.

### An unexpected executable or reparse-point error is reported

Do not remove the check or edit checksum-protected files. Extract a fresh ZIP
into a new ordinary local directory. The current installer deliberately stops
if the extracted root contains executable lookalikes or if the bundle root or
a protected path crosses a symbolic link, junction, or reparse point.

### The `offline-install.log` path ends with an extra `"`

This was possible in a pre-correction bundle when the script directory's
trailing separator interacted with Windows quoted-argument parsing. The
current installer passes an absolute bundle path without a trailing separator.
Use the corrected complete ZIP rather than modifying checksum-protected files
individually.

### The final `[y/N]` prompt

Pressing `Enter` or entering `n` declines immediate GUI launch; it does not undo
the successful installation. Start the GUI later with
`launchers\run_gui_venv.cmd`.

### More than one extracted installation folder exists

The editable installation and `.venv` depend on the extracted folder's
absolute path. Confirm GUI launch from the newer folder before removing an old
superseded installation, then run the old folder's `uninstall_offline.cmd`.
Do not delete, move, or rename the active successful folder. A pre-uninstaller
or incomplete failed bundle may still require explicit administrator cleanup;
never delete the shared `offline-runtimes` parent or guess a runtime ID.

### PowerShell blocks the online preparation script

Keep the organization or machine execution policy in place. Run the script
from an approved reviewed checkout using the method authorized by the local
administrator; do not weaken policy merely to build the bundle.

### Paths contain spaces or Japanese characters

The scripts pass paths as quoted arguments and use Unicode-capable Python path
operations. If a local security product or extraction tool rejects such a
path, extract to another writable local folder and rerun; do not run the
editable environment from USB as a workaround.

### GUI opens but external tools are unavailable

Python package installation is complete. Configure the separately obtained
PHITS/RT-PHITS/phits2dicom tools in the GUI only when using confirmed
non-patient phantom data. Installation itself intentionally does not discover,
copy, or run those tools.

## Human validation record

See the bounded
[Windows offline installation validation record](windows-offline-installation-validation-2026-08-07.md)
for the 2026-08-07 Windows-host checks and corrections. It records installation
behavior only and is not clinical validation.
