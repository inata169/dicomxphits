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

## Create the USB bundle on an online computer

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
2. reads the version and runtime requirements from `pyproject.toml`;
3. downloads the exact official Python 3.12.10 x64 installer over HTTPS;
4. requires a valid Windows Authenticode signature from the Python Software
   Foundation and records the signer and installer SHA-256;
5. asks pip for CPython 3.12 `win_amd64` wheels with binary-only resolution;
6. verifies `numpy`, `pydicom`, `setuptools`, and `wheel`, including exact
   `cp312-cp312-win_amd64` compatibility for NumPy;
7. copies only the audited regular-file blobs already present in the Git index
   (untracked and unstaged bytes are not copied); and
8. writes `bundle-manifest.json`, `SHA256SUMS.txt`, and the final ZIP.

The output is:

```text
dist/dicomxphits-offline-win64-<version>.zip
```

If that file already exists, the script stops. Use `-Force` only after
confirming that the existing generated ZIP may be replaced. `dist/`, downloaded
installers, wheels, and staging files are ignored and must not be committed.

Copy the completed ZIP to the USB storage. Keep the ZIP SHA-256 printed by the
preparation script as transfer evidence if your organization has a controlled
media process.

## Install on the offline computer: two steps

1. Copy the ZIP from USB to a writable folder on a local disk and extract it
   completely. Do not open files inside the ZIP and do not use the USB folder
   as the editable project location.
2. In the extracted folder, run `install_offline.cmd` once.

In PowerShell, run the file with the following command. Do not use
`cd install_offline.cmd`; `cd` changes directories and does not execute files.

```powershell
.\install_offline.cmd
```

The command verifies all protected bundle files before executing the bundled
Python installer. It then:

- uses an existing CPython 3.12 x64 when available;
- otherwise installs the bundled Python 3.12.10 for the current user with pip,
  the Python Launcher, and Tcl/Tk enabled, without changing PATH, creating
  Python file associations, or creating shortcuts;
- creates the extracted project's `.venv`;
- installs only from `wheelhouse/` with `--no-index`, `--find-links`, and
  `--no-build-isolation` on every pip install command;
- installs dicomxphits in editable mode;
- imports `tkinter`, `numpy`, `pydicom`, and `dicomxphits`;
- records the Python, NumPy, and pydicom versions in `offline-install.log`; and
- displays the existing `launchers\run_gui_venv.cmd` command.

The GUI starts only if you answer `y` or `yes` to the final prompt. Declining
the prompt still leaves a successful installation. Start it later with:

```cmd
launchers\run_gui_venv.cmd
```

## Integrity files

`bundle-manifest.json` records the source HEAD commit, a SHA-256 fingerprint of
the exact Git index entries, target, runtime requirements, wheel tags, Python
installer URL and Authenticode signer evidence, and the role, size, and
SHA-256 of every payload.

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

### Python installation fails

Review `offline-install.log` and `python-installer.log` in the extracted root.
The Python installation is current-user only and does not require changing
machine-wide PATH. Organization policy may still control software installation.

### `Python 3.12 not found!` is treated as the Python executable

This was possible in a pre-correction bundle when the Python Launcher existed
but CPython 3.12 did not. The launcher message was captured as though it were an
executable path. The current installer accepts captured output only when it
names an existing executable. Do not replace only the CMD file in an extracted
bundle. Rebuild or obtain the corrected complete ZIP and extract it into a
separate folder.

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
failed or superseded installation. Do not delete, move, or rename the active
successful folder.

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
