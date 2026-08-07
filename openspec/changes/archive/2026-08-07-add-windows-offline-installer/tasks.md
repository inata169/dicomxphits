# Tasks

## 1. Approval and contracts

- [x] 1.1 Obtain explicit human approval of this proposal before
  implementation or network downloads.
- [x] 1.2 Define the tracked-source boundary, generated-artifact layout,
  checksum self-reference exception, and external-tool exclusions.
- [x] 1.3 Define the Python, wheel-tag, virtual-environment, no-network, log,
  and optional-GUI contracts.

## 2. Online bundle preparation

- [x] 2.1 Add `tools/prepare_offline_bundle.ps1` and a standard-library helper
  that read project metadata and enumerate only Git-indexed public source.
- [x] 2.2 Download Python 3.12.10 x64 and validate its Authenticode signature,
  signer identity, and SHA-256.
- [x] 2.3 Download binary-only CPython 3.12 Windows x64 dependency wheels from
  runtime metadata plus `setuptools` and `wheel`.
- [x] 2.4 Reject missing direct requirements, source archives, and NumPy wheels
  without exact `cp312-cp312-win_amd64` compatibility.
- [x] 2.5 Generate the deterministic relative-path manifest, checksum file,
  and versioned ZIP below `dist/` without tracking generated binaries.

## 3. Offline installation

- [x] 3.1 Add root `install_offline.cmd` and a standard-library-only helper
  that verify the full checksum inventory before installation.
- [x] 3.2 Detect an existing Python 3.12 x64 or install the verified bundled
  Python 3.12.10 for the current user with pip, Launcher, and Tcl/Tk.
- [x] 3.3 Create or safely reuse only a Python 3.12 x64 repository-local
  `.venv`, rejecting an incompatible or malformed existing environment
  without deleting it.
- [x] 3.4 Install build tools, runtime requirements, and the editable project
  using the bundled wheelhouse and all three required offline pip flags.
- [x] 3.5 Verify imports, record versions and results in
  `offline-install.log`, print the existing GUI launch command, and launch it
  only after an explicit user choice.

## 4. Documentation

- [x] 4.1 Add English and Japanese instructions for online ZIP creation and
  the two-step offline local-disk installation workflow.
- [x] 4.2 Document checksums, external prerequisites, excluded/protected
  material, troubleshooting, existing `.venv` recovery, Unicode/space paths,
  and offline guarantees.
- [x] 4.3 Link the offline documents from `README.md` without changing public
  physics or clinical claims.

## 5. Synthetic validation

- [x] 5.1 Test runtime dependency extraction, correct wheel recognition,
  exact NumPy platform tags, missing wheels, and source-archive rejection.
- [x] 5.2 Test manifest/checksum generation and rejection of mismatch,
  duplicate, absolute, or escaping paths.
- [x] 5.3 Test offline pip command/environment construction and prove no
  network-capable fallback is invoked.
- [x] 5.4 Test incompatible existing `.venv` rejection without deletion and
  successful handling of temporary paths containing spaces and Japanese text.
- [x] 5.5 Test that successful installation presents and optionally invokes
  the existing GUI launcher while no PHITS-related process is started.

## 6. Completion

- [x] 6.1 Run focused tests, compilation, the full public pytest suite,
  public-tree verification, Git whitespace/stat/status checks, and strict
  OpenSpec validation.
- [x] 6.2 On the current Windows environment, attempt the real public bundle
  preparation when network and Authenticode validation are safely available;
  verify the ZIP inventory and record the exact result without committing
  generated binaries.
- [ ] 6.3 Record actual Python installation and fully offline target-computer
  execution as human-required verification rather than running them in CI or
  changing a host Python installation automatically.
- [x] 6.4 Promote the accepted delta, archive the completed change, and
  validate the resulting OpenSpec tree before the completion report.

Task 6.3 is explicitly deferred as a non-blocking human verification item. The
generated ZIP, installer Authenticode signature, wheel inventory, checksums,
and synthetic installer behavior were validated on the producer environment;
the automated work did not change a host Python installation or claim an
air-gapped target-PC observation.
