# Tasks

## 1. Contract and provenance

- [x] 1.1 Confirm that `-I -S` retains the installed standard-library paths
  and that Python source files do not provide an acceptable Authenticode trust
  anchor.
- [x] 1.2 Confirm official application-local CPython 3.12.10, Tcl/Tk, and
  package-signature verification sources.
- [x] 1.3 Obtain human approval for the authenticated application-local
  runtime contract.
- [x] 1.4 Validate this OpenSpec change strictly.

## 2. Producer changes

- [x] 2.1 Download pinned NuGet verifier, CPython NuGet package, and Tcl/Tk MSI
  over HTTPS.
- [x] 2.2 Validate expected Authenticode and NuGet repository signatures before
  staging.
- [x] 2.3 Record exact runtime-source provenance and include all artifacts in
  the bundle inventory.
- [x] 2.4 Replace the full-installer bundle layout without changing the locked
  wheelhouse or indexed-source boundary.

## 3. Consumer changes

- [x] 3.1 Validate and lock the runtime source artifacts before executing the
  verifier or Windows Installer.
- [x] 3.2 Safely extract the application-local CPython and Tcl/Tk runtime into
  new bounded staging directories.
- [x] 3.3 Reject unsafe, unexpected, changed, missing, linked, or non-regular
  runtime content before Python execution.
- [x] 3.4 Read-lock the complete runtime through installation and use no host
  Python candidate.
- [x] 3.5 Preserve isolated base launches, repository-local venv behavior,
  offline pip, import checks, and optional GUI launch.

## 4. Tests and documentation

- [x] 4.1 Add red-to-green regressions proving a malicious existing standard
  library is never executed.
- [x] 4.2 Add synthetic provenance, extraction, runtime inventory, and lock
  lifetime tests.
- [x] 4.3 Confirm a clean application-local CPython 3.12 x64 runtime with pip
  and Tkinter remains accepted.
- [x] 4.4 Update English and Japanese offline documentation and handoff notes.

## 5. Completion

- [x] 5.1 Run focused tests and all required public checks with a fresh
  `C:\tmp` pytest basetemp.
- [x] 5.2 Commit and push one reviewable implementation commit, reply to the
  P1 thread, and resolve it only with supporting validation.
- [x] 5.3 Confirm exact-head CI and continue `@codex review` until clean.
- [x] 5.4 Promote the accepted specification, archive this change, and run
  strict OpenSpec validation.
- [x] 5.5 Confirm merge authorization and prerequisites; merge PR #33 and
  delete its remote source branch only after the archive commit also passes
  exact-head review and CI gates.
