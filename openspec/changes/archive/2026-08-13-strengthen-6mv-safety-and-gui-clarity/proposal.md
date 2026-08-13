# Strengthen 6 MV Safety and GUI Clarity

## Why

The public rectangular 3D-CRT workflow always renders the bundled Elekta
Precise nominal 6 MV research spectrum, but the GUI does not identify that
fixed beam model and workspace preparation does not currently prove that each
included treatment beam in the source RT Plan is a 6 MV photon beam. A plan
using another nominal energy could therefore reach PHITS input generation with
the fixed 6 MV spectrum.

The shared Activity log is also too short to reliably show two complete lines
in the supported Windows layout, and the GUI does not expose the public
repository address or package author. These small visibility defects make the
research model and support provenance harder to identify.

## What Changes

- Define one runtime source of truth for the approved public research model:
  Elekta Precise, photon, nominal 6 MV, fixed (not an energy selector).
- Display the fixed model identity in a shared read-only GUI area visible on
  every workflow page, without presenting 10 MV or another selectable energy.
- Add core, GUI-independent RT Plan validation for every treatment beam
  included in public workspace generation. Require `RadiationType` `PHOTON`
  and an effective finite, positive `NominalBeamEnergy` of exactly 6 MV at
  every control point, applying DICOM control-point inheritance only after an
  explicit valid value at the first control point.
- Reject missing, malformed, non-finite, non-positive, non-photon, mixed, or
  changing beam energy before any PHITS input is written. Controlled errors
  identify the beam, the observed energy when available, the fixed 6 MV model,
  and that no PHITS input was generated.
- Add backward-compatible beam-model and per-beam nominal-energy evidence to
  the segment manifest and public workspace-preparation summary.
- Increase only the shared Activity log text area enough to keep at least two
  log lines visible at the documented normal and minimum window sizes while
  preserving scrolling and automatic latest-entry scrolling.
- Show the public repository URL and author `Hiroki Inata` in a shared,
  read-only GUI area without adding browser-launch or network behavior.
- Add synthetic RT Plan and GUI regressions. Do not use private fixtures,
  patient data, or real external tools.

## Impact

- Affected runtime: public workspace preparation and the shared Tk GUI.
- Affected capabilities: new `fixed-6mv-beam-model-safety`; existing
  `guided-gui-workflow`.
- Existing valid 6 MV workspaces retain the same spectrum, geometry, source,
  MLC and jaw handling, scaling, materials, transport and cutoff settings,
  tallies, `totfact_per_MU`, Sumtally normalization, RTDOSE conversion, DICOM
  meaning, and coordinate behavior.
- The change intentionally does not add a 10 MV model, an energy selector,
  FFF support, progress or remaining-time reporting, interruption or restart
  behavior, unfinished-segment recovery, convergence logic, variable tallies,
  or distributed execution.
- Version metadata, GUI/CLI version displays, changelog, release notes,
  historical validation records, and public version wording remain unchanged.
- Runtime documentation outside OpenSpec is deferred by the requested scope;
  any later documentation recommendation will be reported without editing it.
- The completed RT Dose recovery work remains a separate change and is not
  modified by this proposal.

## Approval Status

The primary user approved grouping these four requested items into this single
new OpenSpec change on 2026-08-13, then explicitly approved this proposal and
its delta specifications before runtime implementation.
