# Design: Repair RTDOSE GUI Reprepare Recovery

## State source

The GUI continues to derive RTDOSE display state from successful Prepare and
Run summaries. A successful Run takes precedence over Prepare, an unreadable or
unsuccessful summary does not claim success, and the state remains presentation
and action-gating logic rather than a replacement for adapter validation.

## Explicit recovery

The GUI cannot cheaply duplicate every RTDOSE provenance validation while it
refreshes controls. The accepted downstream-summary overwrite checkbox already
bypasses the GUI's existing-summary guard and is deliberately non-persistent.
When the current state is Prepared, selecting that checkbox therefore
re-enables Prepare. The adapter remains authoritative and either writes fresh
preparation evidence or fails closed. Run remains available from Prepared, so
the user can either use still-valid evidence or explicitly regenerate it.

## Safety boundary

This change does not infer that preparation is valid, delete evidence, or
weaken any adapter gate. It changes only which already-supported GUI action is
reachable after explicit overwrite permission. Automated validation uses
synthetic summaries and no external tool or real DICOM.
