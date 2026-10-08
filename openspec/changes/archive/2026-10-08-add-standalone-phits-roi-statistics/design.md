# Standalone PHITS ROI statistics design

## Scope and decisions

The analysis is a separate script, not another entry point into the GUI's
Structure evaluator. It reads completed snapshots, has no external runner,
and never repairs workspace evidence. Review the existing parser in
`src/dicomxphits/phits_observation_format.py` as a format reference; do not
change its current callers or import the GUI evaluation/recovery machinery.
Implement the bounded parser needed by the standalone script with synthetic
parity tests for the supported pair format.

The user approved radius 0.25 cm with sampling volume 0.081 cm3 and separate
analytic sphere volume, then approved the full implementation proposal on
2026-10-08. The script remains independent of GUI authority and does not
change existing runtime or public specifications.

## Explicit inputs and provenance

A command-line invocation selects a directory or ZIP, the relative dose
and error paths (ZIP member paths for archives), and the saved normalization
evidence. A JSON batch manifest represents these same explicit selections
for multiple cases; it contains no executable commands. Relative source
locations are resolved from the manifest location. Member paths are always
relative to the selected source container.

The evidence consists of the selected generation/execution summaries and
canonical segment manifest. Validate their supported schemas, shared
manifest digest, successful execution, recorded dose digest, and matching
normalization records. The manifest's dose semantics must establish the
approved per-MU normalization, and the weighted Sumtally output must match
the recorded one-fraction Gy state, active segment weights, and sumfactor.
Do not infer absolute Gy from the printed `Gy/source` header alone.
Saved absolute paths are historical labels, never automatic read targets;
explicit current selectors and content digests identify relocated artifacts.

The combined pair must have matching mesh, tally semantics, source weights,
sumfactor, slice identities, and complete finite non-negative arrays. Check
the error role from its supported content as well as its selected name.
Record digests of all consumed bytes. A retained error is usable only with
an explicitly selected dose from the same retained directory and an
explicitly selected official dose: the doses must be byte-identical and
match the terminal execution digest. No staging-directory search, recovery
receipt creation, or workspace modification is performed.

Read only explicitly named ordinary files or archive members. Reject path
traversal, absolute member paths, duplicate selected member names, linked or
reparse-backed paths, and unsupported ZIP entries. Read ZIP members in memory
with bounded sizes; do not extract a case or deserialize pickles. Fail on
changing inputs or ambiguous pairing. A missing error is not an instruction
to rerun Sumtally or combine per-beam errors.

## Coordinates and region selection

All analysis coordinates are PHITS xyz in cm, anchored to the isocenter.
Parse native bin boundaries and derive cell centres. Decode x-ascending,
y-descending xy pages and z slice identifiers into a single documented array
order `(x, y, z)`, with each coordinate axis ascending. No DICOM transform is
used, and the origin is not assumed to be a native cell centre.

For a sphere, accept exactly one positive finite radius in cm or analytic
volume in cm3, plus a finite centre. Convert volume input using
`r = (3 V / (4 pi))**(1/3)`. The default example uses centre `(0, 0, 0)` and
radius `0.25 cm`. Use squared Euclidean distance `<= r**2` for inclusion;
do not introduce a physical inclusion tolerance. Reject a sphere extending
outside the mesh, rather than silently report a clipped sphere.

Use two independently counted populations:

- Sampling points lie on a sphere-centred Cartesian lattice with explicit
  spacing `h`, default `0.1 cm` (1 mm). Positions are `centre + h*(i,j,k)`
  for integer indices within the sphere. Points is their count; sampling
  volume is `Points*h**3`. This is a discretization estimate, not an exact
  geometric volume, an interpolation population, or extra Monte Carlo data.
- Native Grid Points is the number of PHITS cell centres within the sphere.
  Grid volume is the sum of those cells' volumes. Only these cells contribute
  to dose and error statistics. Different native offsets can change this
  count even when radius and spacing are unchanged.

A Structure input is an NPZ with Boolean `mask` of shape `(nx, ny, nz)` and
finite ascending `x_edges_cm`, `y_edges_cm`, `z_edges_cm`, plus an explicit
PHITS coordinate-system marker. Loading uses `allow_pickle=False`. Edges,
shape, axis order, and coordinate convention must match the dose mesh;
there is no implicit resampling, contour inference, or frame conversion.
The user supplies the display label, which is not a DICOM identity. Each
true cell is included in full. Structure volume means selected native-cell
volume. Radius, analytic sphere volume, sampling Points, and sampling volume
are null for an arbitrary mask because those geometric quantities are not
defined by this input. A sphere labelled `Chamber` still has region type
`sphere` and must not be reported as an imported Structure.

## Statistics and units

Initial supported meshes are uniform rectilinear grids. The report's dose
basis is the validated one-fraction combined Gy tally multiplied by 100 to
obtain cGy. Already-applied normalization is never reapplied, and planned
fraction count is not a multiplier for this report. It is therefore not a
promise to reproduce a multi-fraction RTDOSE course dose.

For N selected native cells with doses D_i in cGy:

- `voxel_dose_sum_cgy = sum(D_i)`, displayed as
  `Total Dose / voxel-dose sum (cGy)`. This is grid-dependent and is not a
  physical energy integral or an ROI mean dose.
- `mean_dose_cgy = sum(D_i)/N`.
- `min_dose_cgy` and `max_dose_cgy` are the extrema of all selected doses.
- `spatial_stddev_cgy = sqrt(sum((D_i-mean)**2)/N)` (population definition,
  `ddof=0`). Zero-dose cells remain in every dose statistic.

The statistical-error population is the subset with `D_i > 0` and `r_i > 0`.
Report unweighted mean, median, P95, and maximum of `100*r_i`. For median and
P95 use linear interpolation at sorted position `q*(n-1)`. The report states
that no low-dose threshold is applied. Zero relative-error entries are
unavailable statistical observations, not evidence of exact zero uncertainty.
Record the total eligible count and separate counts for zero-dose cells,
positive-dose cells with zero r.err, and the union of exclusions.

A single eligible cell has its own voxel statistics, explicitly count 1;
an empty eligible set produces null error statistics and a diagnostic while
valid dose statistics remain available. An empty region produces no dose
statistics and a diagnostic. Negative, non-finite, malformed, or missing
array values invalidate the pair, not just the affected region.

For eligible cells, absolute voxel standard error is `D_i*r_i` in cGy;
report its mean and maximum as voxel-standard-error summaries. These are not
an ROI-mean standard error. Do not report the exact r.err of the ROI mean or
propagate errors as if different voxels were independent: the input lacks
their covariance. Sampling points never increase the uncertainty sample
count. No per-voxel raw-array export is part of this initial scope.

## Reports and failure behavior

Console and CSV show one scalar row per requested case/region with its
status, label, region type, centre, geometry fields, native spacing, counts,
dose basis, dose summaries, and voxel-error summaries. JSON records the
versioned definitions and provenance as well as these values. Missing
quantities are JSON null/empty CSV fields with reasons, never numeric zero.
No automatic DICOM identifiers, absolute source paths, or raw arrays are
exported. Source paths in reports are container-relative; case and region
labels are explicit user input. External CSV strings use the existing
spreadsheet-neutralization contract.

Reports are created only in an explicitly selected separate analysis output
directory, outside source case trees and the repository for real-data use.
Use guarded, atomic new-only writes; never overwrite an existing report,
modify an input, or emit GUI authority records. If a report publication fails,
report the failure and any files already published instead of implying an
all-or-nothing success. In a batch, retain clearly marked per-case failures
and return a nonzero overall exit status when any case is invalid or empty.
Missing r.err eligibility with otherwise valid nonempty dose selection is a
reported partial result. New-only output conflicts are failures.

## Acceptance examples and implementation sequence

Synthetic geometry examples:

- Radius 0.25 cm, centre-anchored 1 mm sampling: Points 81, sampling volume
  0.081 cm3, analytic volume approximately 0.06544985 cm3.
- The same sphere on a centre-aligned 2 mm native lattice: Grid Points 7,
  grid volume 0.056 cm3.
- A synthetic 3 mm native lattice with x/y centres at zero and nearest z
  centres at -0.1 and 0.2 cm: Grid Points 2, grid volume 0.054 cm3.
- Analytic volume input 0.25 cm3 gives radius approximately 0.39079632 cm;
  it must not be interpreted as the radius-0.25-cm example.

Implement explicit input/pair validation first, geometry second, scalar
statistics third, and reports/batch support last. Test each observable
contract with synthetic files before the full public checks. Version-format
fixtures model v1.0.3 retained-pair selection and v1.1.1 saved-pair selection;
they contain no copied local calculation outputs. Read-only checks on
explicitly selected local phantom outputs are separate evidence and must be
recorded as unverified when input identity, permissions, or masks are missing.

## Sources for the existing boundaries

- `openspec/specs/post-completion-structure-relative-error/spec.md`:
  existing GUI-only evidence, population, and export restrictions.
- `openspec/specs/rtdose-dicom-semantics/spec.md`: active-treatment-MU
  normalization and separate planned-fraction course-dose conversion.
- `openspec/specs/sumtally-relative-error-recovery/spec.md`: existing
  recovery authority, which this script does not invoke or extend.
- `openspec/specs/csv-export-security/spec.md` and
  `openspec/specs/workspace-output-security/spec.md`: output boundaries.
