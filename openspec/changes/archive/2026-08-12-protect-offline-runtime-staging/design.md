# Design: Elevated Protected Offline Runtime

## Security property

From the final authenticated inventory until the verified installation stage
exits, a process running as the installing user without elevation must be
unable to add, replace, rename, delete, relink, or change permissions on any
runtime path. A process with equal or greater administrator authority remains
outside this boundary, as it can control the installer process and protected
storage itself.

File read locks prevent mutation and replacement of authenticated files but do
not prevent new sibling entries. Directory R/RH oplocks are advisory for this
case. The design therefore uses Windows access control to deny entry creation,
deletion, permission changes, and replacement to the non-elevated user.

## Elevation ordering

The normal `install_offline.cmd` entry point continues to start only the
absolute Windows-system PowerShell before bundle verification. That process
validates and read-locks the complete checksum and manifest inventory. While
those handles remain open, the verified PowerShell stage relaunches itself
through the absolute Windows-system PowerShell with `RunAs` and waits for the
elevated child.

The parent serializes the verified-stage nonce, bundle root, and installing-user
SID into the encoded elevated command instead of relying on environment
inheritance across `RunAs`. The elevated child revalidates the trusted
PowerShell identity and protected bundle paths and performs only runtime-source
verification and protected extraction. It writes a protected receipt containing
the source-derived hashes and exits. The original non-elevated stage validates
and read-locks that receipt and runtime before running Python, the helper, venv,
or pip. If elevation is refused, unavailable, or lost, none of those processes
starts.

## Protected storage

The runtime is created below a fixed protected root under the Windows Common
Application Data directory. Its installation-specific leaf is deterministically
derived from the normalized bundle path so a repeat run maps to the same leaf
and fails on pre-existing content, matching the existing one-entry behavior.
The runtime is not shared or inferred from another extracted bundle.

Every protected directory uses a non-inheriting DACL whose inheritable rules
grant:

- full control to `SYSTEM`;
- full control to built-in Administrators;
- read and execute access to the installing user; and
- read and execute access to `OWNER RIGHTS`.

The owner is built-in Administrators. The `OWNER RIGHTS` ACE suppresses the
normal implicit `READ_CONTROL` and `WRITE_DAC` grant to an object's owner, so a
non-elevated process cannot regain write access merely because a descendant
records the user as owner. The stage compares owner, inheritance protection,
and the complete canonical access-rule set on every directory and file. It
does not repair an existing protected root or accept additional access rules.

The fixed protected parent is created one component at a time with the same
security descriptor. Any pre-existing component must already have the exact
expected identity and permissions and be an ordinary non-reparse directory;
otherwise installation stops. A new runtime leaf must be absent and is created
with the protected descriptor before runtime content is written.

## Runtime validation and handles

Extraction remains limited to authenticated NuGet and signed-MSI-derived
content. New directories and files inherit only the protected runtime rules.
Before Python starts, the stage:

1. rejects reparse and non-regular entries;
2. validates the protected owner and canonical DACL for every entry;
3. hashes each file through its retained read-only, non-write-sharing handle;
4. verifies every path is represented by the authenticated expected hash or
   expected directory inventory; and
5. performs a final recursive inventory while all file handles remain held.

An additional file cannot be created because its parent does not grant the
non-elevated user `FILE_ADD_FILE` or `FILE_ADD_SUBDIRECTORY`, delete, or
permission-change rights. Authenticated file handles remain open through
Python probing, helper execution, venv and pip work, and final import
verification.

## Persistence and failure

The protected runtime remains after success because the repository-local
`.venv` records the base interpreter location. A repeat run against the same
bundle path rejects the existing runtime rather than reusing, deleting, or
repairing it. Cleanup is an explicit administrator action documented for a
confirmed abandoned installation; the installer does not perform it
automatically.

The normal installation log and `.venv` remain at the extracted project root;
the elevated Windows Installer log remains beside the protected receipt. This
change does not grant the runtime access to the network and does not execute
PHITS-related tools or real DICOM.

## Validation boundary

Automated validation uses synthetic runtime trees, controlled temporary ACLs,
copied signed test binaries when needed, and fake malicious marker processes.
It does not modify a host Python installation. A Windows regression attempts
to add `python312._pth` after the authenticated inventory and proves the write
is denied and the malicious runner marker is absent. The existing official
artifact probe must still accept CPython 3.12.10 x64, Tcl/Tk, Tkinter, venv,
and pip from the protected runtime.
