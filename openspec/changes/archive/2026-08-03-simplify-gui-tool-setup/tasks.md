# Tasks

## 1. Tool Profile Model

- [x] 1.1 Record the versioned bounded Windows relative candidate table from
  public documentation and maintainer-confirmed relative layout, and obtain
  human approval before runtime implementation.
- [x] 1.2 Implement a pure filesystem tool-profile resolver with structured
  missing and ambiguous results and no external execution.
- [x] 1.3 Implement identical prerequisite validation for standard and explicit
  custom layouts.

## 2. Settings and Migration

- [x] 2.1 Extend ignored GUI settings compatibly with profile mode and selected
  installation folder.
- [x] 2.2 Migrate valid existing flat paths to standard mode and preserve other
  existing paths as explicit custom-layout settings.
- [x] 2.3 Revalidate restored settings on launch without persisting safety
  confirmation, overwrite permission, or case inputs.

## 3. Guided GUI

- [x] 3.1 Replace the primary independent tool fields with one PHITS
  installation-folder control, readiness summary, and validate/save action.
- [x] 3.2 Move individual tool paths and the CT2PHITS workspace override into an
  explicitly selected advanced custom-layout section.
- [x] 3.3 Keep effective paths visible and show role-specific missing or
  ambiguous setup errors.
- [x] 3.4 Disable relevant external stages until the effective tool profile
  passes validation.

## 4. Derived Case Workspace

- [x] 4.1 Derive the normal CT2PHITS workspace from the effective RT-PHITS root
  and sanitized RT Plan stem.
- [x] 4.2 Recompute the derived workspace whenever the RT Plan or effective
  RT-PHITS root changes, including when a previous derived value is non-empty.
- [x] 4.3 Preserve the existing new-directory, RT-PHITS containment, repository
  exclusion, and command-path safety validation.

## 5. Documentation

- [x] 5.1 Document the one-folder standard Windows setup and advanced custom
  fallback in README.md.
- [x] 5.2 Explain installation settings versus per-case output and the readiness
  checks in the guided workflow documentation.
- [x] 5.3 Keep tracked configuration examples empty of personal absolute paths.

## 6. Synthetic Validation

- [x] 6.1 Add focused synthetic tests for resolver, validation, migration,
  persistence, GUI state, and stale-workspace replacement.
- [x] 6.2 Run focused GUI tests with fake/mock external runners.
- [x] 6.3 Run compileall, the full public pytest suite, public-tree verification,
  and Git diff/status checks.
- [x] 6.4 Record real external-tool execution as not run unless separately and
  explicitly authorized by the human maintainer.

## 7. Completion

- [x] 7.1 Confirm all approved acceptance criteria and required checks.
- [x] 7.2 Promote the accepted requirement deltas into the current guided GUI
  specification.
- [x] 7.3 Archive this change and validate the resulting OpenSpec tree before
  completion handoff.
