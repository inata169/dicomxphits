# Design: Detached Uninstall Completion Observation

## Existing Lifecycle

The verified uninstall lifecycle intentionally crosses a process-lifetime
boundary:

1. The authenticated non-elevated parent verifies the bundle, receipt, exact
   targets, and local confirmation.
2. The direct elevated staging process revalidates the protected boundary and
   starts a detached finalizer.
3. The direct elevated process exits, the parent reports that cleanup was
   scheduled, and control can return to the calling terminal.
4. Parent and bootstrap processes exit and release the authenticated bundle
   read locks that prevented self-deletion.
5. The detached finalizer observes those exits, repeats its bounded checks,
   removes only the exact installation-owned targets, and verifies their
   absence.
6. After installation-target removal, the finalizer writes `failure.json` with
   the exact message `Final cleanup staging removal is pending.` and starts a
   child that waits for the finalizer to exit before removing bounded cleanup
   staging.
7. On success, that child removes cleanup staging. On terminal failure, the
   catch path replaces the pending sentinel with a different error message and
   retains exact remaining-path evidence.

The extracted bundle can therefore still exist between steps 3 and 5. This is
an expected in-progress state. Treating it as immediate failure encourages an
unnecessary retry or manual deletion while verified cleanup is active.

## Completion Observation

The command's `cleanup scheduled` message confirms only that the verified
parent handed work to the detached finalizer. It does not claim that exact
target removal has already completed.

Documentation will direct an operator to allow the detached finalizer to
finish and then distinguish the terminal outcomes:

- success: the exact extracted bundle and every matching installation-owned
  target have passed the final elevated absence check, and the bounded cleanup
  staging no longer exists;
- pending: bounded cleanup staging remains with the exact
  `Final cleanup staging removal is pending.` sentinel;
- failure: bounded cleanup staging remains after that sentinel is replaced by a
  different error message identifying the exact remaining paths; and
- indeterminate: the report is missing, unreadable, malformed, or does not
  progress beyond the pending sentinel. Evidence is preserved without retry or
  manual deletion.

A folder observed immediately after prompt return is neither outcome by
itself. The operator must not rerun uninstall or manually delete targets while
the detached finalizer is still reaching a terminal outcome.

## Scope Boundary

This change documents the existing lifecycle. It does not alter process
launching, waiting, privilege boundaries, receipt identity, target selection,
pre-deletion guards, retry behavior, or cleanup ordering. It also does not
change bundle version metadata or authorize tag or release publication. The
existing local ZIP remains untouched during this change, but its source HEAD
precedes these indexed documentation and specification updates. Release work
must therefore regenerate and revalidate the ZIP from the eventual merged HEAD
before any tag or publication decision.

## Validation Strategy

- Strictly validate the OpenSpec delta before implementation and the promoted
  specification and archive at completion.
- Review both language documents for the same scheduled, in-progress, success,
  and failure distinctions.
- Run the existing synthetic uninstaller regression coverage and the full
  repository checks without executing real external scientific tools or
  reading real DICOM or calculation results.
