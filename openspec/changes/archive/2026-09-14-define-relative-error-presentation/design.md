# Design: separated live and post-completion relative-error presentation

## Accepted starting boundary

The live PHITS observer remains read-only and non-authoritative. During an
owned invocation it may report only the finite positive `r.err` value paired
with finite positive dose in the unique primary 3D mesh voxel whose open
interior contains Isocenter. It does not interpolate, choose a nearest voxel,
read PDD as a fallback, aggregate the whole mesh, inspect RT Structure data, or
change any execution or downstream decision.

Any future RT Structure statistics belong to a separate post-completion
evaluation. They must not replace or augment the live Isocenter detail and must
not become convergence, completion, automatic-stopping, clinical-uncertainty,
or downstream-eligibility evidence.

## Evidence and current implementation gap

The [PHITS 3.35 manual](https://phits.jaea.go.jp/manual/manualE-phits.pdf)
defines `r.err` as a statistical relative error derived from the standard error
and tally mean. This is not, by itself, a clinical dose error statement. The
repository currently parses and presents the current segment's separate primary
3D dose/error pair for live Isocenter observation.

The completed downstream path instead validates a Sumtally combined 3D dose
output and its mesh geometry. It does not yet provide a repository contract and
parser proving which completed statistical-error values are authoritative for
Structure evaluation, how they remain bound to the combined dose, or how
historical outputs are handled. PHITS documentation about sum-over error output
does not replace repository evidence validation.

[DICOM PS3.3 Structure Set Module](https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_C.8.8.5.html)
identifies ROIs and their referenced Frame of Reference, images, and contours.
The standard does not select this application's voxel-inclusion or resampling
policy. The existing repository RT Structure rasterization is specific to
CT-based phantom derivation. Reusing its CT-slice mapping for an RTDOSE or PHITS
error grid would be a new decision, not an established contract.

## Approved decisions

1. **Authoritative completed source (approved 2026-09-14).** Post-completion
   Structure evaluation SHALL use only the validated all-active-segments
   Sumtally combined 3D result. Its dose and statistical-error values SHALL be
   bound to terminal success, the current workspace, manifest, mesh geometry,
   and immutable digest evidence. The evaluator SHALL remain unavailable unless
   the combined `r.err` semantics and its pairing with the combined dose are
   implemented and verified; it MUST NOT fall back to per-segment, live, PDD,
   historical, or unverified values.
2. **Target Structure (approved 2026-09-14).** Each evaluation SHALL require
   the user to explicitly select exactly one ROI by its unique `ROINumber`
   within one validated RT Structure Set. `ROIName` SHALL be shown only as a
   display label and MUST NOT be an implicit selection key. The evaluator SHALL
   fail closed for a missing or duplicate ROI number, a missing or duplicate
   matching ROI Contour item, or an empty ROI, and MUST NOT automatically match
   names or evaluate multiple ROIs as one request.
3. **Grid and contour mapping (approved 2026-09-14).** The evaluator SHALL map
   the validated Sumtally mesh into DICOM patient coordinates through the
   existing accepted RTDOSE affine and SHALL accept only `CLOSED_PLANAR`
   contours bound to the same validated Frame of Reference and frozen CT
   series. It SHALL define Structure membership on the frozen CT voxel-centre
   mask and include a dose voxel only through the mask value of the unique CT
   voxel whose cell contains that dose-voxel centre. It MUST NOT interpolate
   contours, calculate partial-volume weights, add a new coordinate tolerance,
   or infer membership for a centre on a boundary or without a unique mapping.
   Ambiguous mapping or no mapped Structure voxel SHALL make evaluation
   unavailable.
4. **Low-dose exclusion (approved 2026-09-14).** The evaluator SHALL derive one
   finite positive `Dmax` from the entire validated all-active-segments
   Sumtally combined 3D dose grid and use it only as a non-displayed threshold
   reference. Within the selected Structure, only voxels satisfying
   `D > 0.5 * Dmax` SHALL enter relative-error statistics. Version 1 SHALL keep
   this threshold fixed rather than expose a user control. An unavailable or
   invalid `Dmax`, or a Structure with no voxel above the threshold, SHALL make
   evaluation unavailable. This volume-based threshold follows the reporting
   example in [AAPM TG-105](https://physics.carleton.ca/~drogers/pubs/papers/tg105.pdf)
   without presenting `Dmax` as a whole-mesh relative-error statistic or a
   clinical acceptance limit.
5. **Numeric admissibility (approved 2026-09-14).** The completed dose/error
   grids SHALL have matching supported metadata, shape, and cell count. Every
   required value SHALL parse as a finite non-negative number; any malformed,
   non-finite, or negative value or any grid mismatch SHALL make the entire
   evaluation unavailable rather than be silently dropped. After the approved
   low-dose threshold, only cells with `D > 0` and `r.err > 0` SHALL be
   statistically eligible. An `r.err` value of zero SHALL be excluded and
   counted, not presented as zero-percent uncertainty. Fewer than two eligible
   voxels SHALL make evaluation unavailable so that the feature cannot reduce
   to another single-voxel statistic.
6. **Reported statistics (approved 2026-09-14).** For the eligible unweighted
   voxel population, the evaluator SHALL convert each `r.err` to percent and
   report its arithmetic mean, median, and P95. For an even population the
   median SHALL be the arithmetic mean of the two central sorted values. P95
   SHALL use linear interpolation at zero-based sorted position
   `0.95 * (n - 1)`. The result SHALL also report the mapped Structure voxel
   count, the count satisfying `D > 0.5 * Dmax`, the final eligible count, and
   the zero-`r.err` exclusion count. It MUST NOT report relative-error minimum,
   maximum, or standard deviation.
7. **Presentation and persistence (approved 2026-09-14).** The evaluator SHALL
   appear only in a distinct `Post-completion Structure r.err` section on the
   Sumtally page after verified all-active-segment Sumtally success. Evaluation
   SHALL require an explicit user action and explicit RT Structure Set and
   unique `ROINumber` selection; it MUST NOT start automatically. The GUI SHALL
   use `ROIName` only as an in-memory display label and SHALL display the exact
   statement `Monte Carlo statistical relative error within the selected
   Structure; not clinical dose error, convergence, patient QA, or an acceptance
   criterion.` Results SHALL be versioned derived scalar-summary JSON at
   `analysis/structure_relative_error/<evaluation_sha256>.json`, where the
   deterministic evaluation identity binds the current manifest, validated
   Sumtally combined dose/error outputs and semantics, RT Structure Set digest,
   `ROINumber`, frozen CT/Frame of Reference/accepted RTDOSE-affine evidence,
   and evaluation-contract version including the threshold. Publication SHALL
   be atomic and new-only. The record MUST NOT contain raw grid arrays, RT
   Structure content, patient identifiers, or `ROIName`. The GUI SHALL
   recompute the exact identity and consider only that exact safe record; it
   MUST NOT search the result directory for alternatives. Changed or invalid
   evidence therefore makes the previous result stale and undisplayable.
   Version 1 SHALL provide no CSV, DICOM, or other export. Failure, staleness,
   or mismatch SHALL leave the evaluation unavailable and MUST NOT create
   downstream authority.

## Invariants

- `deposit-pdd.out` relative error remains PDD-specific and is not used as a
  patient 3D representative value.
- Whole-3D-mesh simple aggregates remain out of scope.
- Live observation remains Isocenter-only and provisional.
- Post-completion evaluation cannot make an incomplete, stopped, failed,
  cancelled, stale, mutated, or unverified result eligible.
- Fixed 6 MV and fixed-field 3D-CRT physics, geometry, DICOM meaning, MU,
  normalization, dose factors, histories, and tally settings remain unchanged.
- Automated development uses synthetic data and fake or mock external tools.
  Any real-tool or real-DICOM run requires a separate exact approval.

## Staged delivery

1. Strictly validate the complete proposal and obtain human approval before
   implementation.
2. Implement only the approved bounded evaluator and presentation using
   synthetic fixtures and fail-closed evidence checks.
3. Run focused and full public validation.
4. If all approved acceptance criteria pass, promote the deltas and archive
   this change. Real-tool acceptance and release remain separately gated.
