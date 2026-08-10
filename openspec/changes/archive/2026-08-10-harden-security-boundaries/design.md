# Design: Harden Security Boundaries

## Patch contracts

### Offline executable selection

The attacker-controlled input is the extracted bundle directory and current
directory, including executable lookalikes and reparse points. The invariant is
that no file from that directory executes before the integrity inventory has
been checked by a trusted Windows system binary, and that Python is invoked only
by an absolute path after its identity and CPython 3.12 x64 properties are
validated.

`install_offline.cmd` will invoke the quoted absolute
`%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe` path. That trusted
PowerShell process will:

1. reject a reparse-point bundle root, checksum file, or protected payload path;
2. verify and read-lock the checksum and manifest inventory;
3. reject unmanifested top-level executable lookalikes;
4. find CPython only through bounded registry/canonical installation paths,
   never through current-directory or `PATH` lookup;
5. require a valid Python Software Foundation Authenticode signature, execute
   the locked absolute candidate only to prove CPython 3.12 x64, and keep its
   executable read-locked;
6. when no candidate is valid, execute the already verified and locked bundled
   installer, then repeat the bounded signed-interpreter selection; and
7. invoke the verified PowerShell installation stage in the same trusted
   PowerShell process with a random in-process stage token, so payload locks
   remain live without introducing another command-processor lookup.

The verified stage will not call `py.exe`, `python.exe`, `powershell.exe`, or any
other executable by bare name. All paths remain quoted, and the existing
no-index wheelhouse installation remains offline.

The bundle's checksum file is transfer-integrity evidence, not an independent
signature for a maliciously replaced whole bundle. Controlled acquisition of
the producer ZIP remains a documented trust boundary.

### CSV serialization

The attacker-controlled input is a DICOM-originated string that reaches a CSV
cell. A shared helper will leave non-string values and ordinary strings exactly
unchanged. It will prefix a string with an apostrophe when its first character
is `=`, `+`, `-`, or `@`, or is a leading C0/C1 control character such as tab,
carriage return, or line feed. Python's CSV writer remains responsible for
quoting commas, quotes, and embedded newlines; quoting alone is not treated as
formula neutralization.

The helper is applied at the shared row serialization boundary so all external
string fields receive the same treatment while numeric fields remain numeric.
JSON evidence and DICOM values in memory are not rewritten.

### Workspace output paths

The attacker-controlled input is an existing case-root tree that may contain a
symbolic link, junction, mount-like reparse point, or a path replaced between a
prior validation and mutation. The invariant is that a workspace-local stage
does not create, overwrite, or delete outside its explicitly supplied case root.

A shared output guard will:

- reject a linked/reparse-point case root and each existing component from that
  root to the output;
- combine lexical relative-path validation with resolved containment checks;
- on Windows, inspect `FILE_ATTRIBUTE_REPARSE_POINT` in addition to Python's
  symbolic-link and junction predicates;
- hold non-delete-sharing handles to existing Windows directories during a
  guarded mutation so those components cannot be replaced after inspection;
- create missing directories one component at a time and inspect them
  immediately;
- create new files exclusively and replace existing regular files through a
  same-directory temporary regular file; and
- refuse to overwrite or remove a link/reparse-point target.

Linux tests cover symbolic-link containment and common writer behavior. Windows
tests create real directory junctions and inspect real reparse attributes. A
remaining same-machine actor with stronger privileges may bypass user-process
filesystem controls; that is outside this local workspace threat boundary.

## Dependency consistency

The project metadata will keep its public Python 3.12 range. Reviewed constraint
files will pin the runtime versions used by CI, and the offline Windows lock will
pin exact wheel filenames and SHA-256 digests. Bundle preparation will use
binary-only, hash-required resolution and verify that the captured wheel set is
exactly the lock set. Installation will use the locked requirements with
`--require-hashes`; editable installation remains bound to the already verified
and read-locked source inventory.

Build tools and any transitive wheel required by them will also be explicit in
the offline lock. Dependabot will propose future Python and GitHub Actions
updates for human review rather than silently changing the bundle.

The workflow will retain the existing action major generations and pin their
current immutable commits with source-version comments:

- `actions/checkout` v4.3.0:
  `08eba0b27e820071cde6df949e0beb9ba4906955` (`# v4`)
- `actions/setup-python` v5.6.0:
  `a26af69be951a213d495a4c3e4e4022e16d87065` (`# v5`)

## Exact proposed SECURITY.md

The confirmed target is the repository root, `SECURITY.md`. No nested or tracked
security policy currently exists. The policy resolver could not traverse
several pre-existing unreadable, untracked `.pytest-*` directories, so Git index
inventory and a pruned filesystem check were also used.

```markdown
# Security Policy

## Supported Versions

Security updates are provided for the latest released `1.0.x` version and the
current `main` branch. Older releases may be asked to upgrade before a fix is
provided.

| Version | Supported |
| --- | --- |
| Latest `1.0.x` release | Yes |
| `main` | Yes |
| Older releases | No |

## Reporting a Vulnerability

Please do not include vulnerability details, exploit steps, sensitive data, or
embargoed information in a public GitHub Issue.

Report vulnerabilities privately through this repository's GitHub Private
Vulnerability Reporting form. If you are a repository maintainer, you may
instead open a draft GitHub Security Advisory for private coordination. If the
private reporting form is unavailable, open a public Issue containing only a
request for a private security contact channel and no vulnerability details.

Please include the affected version or commit, the reachable component, the
security impact, and minimal reproduction information that uses synthetic or
non-sensitive data.

## Project Security Boundary

`dicomxphits` is education and research software for the documented fixed-field
3D-CRT workflow. It is not clinical commissioning, patient QA, or vendor
certification software. Security reports must not include patient DICOM,
patient identifiers, facility configuration, credentials, licensed PHITS or
RT-PHITS material, or real external-tool results.
```

This policy introduces no email address, exclusion, accepted vulnerability, or
clinical claim.

## Validation strategy

Automated validation will include:

- static ordering tests showing trusted PowerShell starts before integrity
  verification and no bare-name PowerShell/Python command remains;
- Windows-only marker executables named `powershell.exe`, `python.exe`, and
  `py.exe` in the extraction/current directory, proving none executes;
- complete and corrupted bundle controls in paths containing spaces and
  Japanese text;
- CSV round trips for ordinary values, all four formula prefixes, empty and
  Unicode/Japanese values, quotes, commas, newlines, tabs, and controls while
  preserving column counts and numeric types;
- Linux symbolic-link escape tests and Windows real junction/reparse-point
  tests for create, replace, and delete paths; and
- focused GUI/CLI synthetic workflows plus the full repository validation.

The current agent environment is Linux under WSL2 and has no `cmd.exe` or
PowerShell executable on `PATH`. Windows-only tests must therefore remain
explicitly unverified until run on the stated Windows-native host; they will not
be inferred from Linux results.
