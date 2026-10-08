# Independent PHITS ROI statistics

## Display language

In the standalone GUI, choose **表示言語 / Language → English** or **日本語**.
Each launch starts in Japanese. Switching updates interface text without
clearing paths, the selected ROI, queued cases, or results, and without running
analysis again. Switching during analysis preserves the busy guards; completion
messages use the language selected at completion.

File names, DICOM ROI names, result values, units, status codes, CSV/JSON keys,
and original analysis diagnostics remain unchanged. Native file-dialog controls
follow the operating system language. This setting is not persisted.

`tools/phits_roi_stats.py` reads an explicitly selected, completed PHITS 3.35
T-Deposit xyz/xy `isumtally=2` combined dose and `_err.out` pair. It uses
Python 3.12, NumPy, and the bounded format parser in this checkout's `src/`
tree. The optional independent GUI is `tools/phits_roi_stats_gui.py`; RT
Structure evaluation additionally uses pydicom. No DICOM conversion or PHITS
execution is needed. The tools only read inputs unless a report is explicitly
published. They neither grant workflow authority nor establish clinical
suitability. A [Japanese usage guide](phits-roi-statistics-ja.md) is also
available.

## Explicit inputs

Select a case directory or ZIP with `--source`. Linked or reparse-backed
input paths are rejected. The `--dose`, `--error`,
`--generation`, `--execution`, and `--manifest` values are **relative paths
within that source**. They must name the official combined dose, its paired
combined relative-error file, `sumtally_generation_summary.json`,
`sumtally_execution_summary.json`, and `segment_manifest.json`. If the error
is preserved in a saved Sumtally run directory, select its co-located dose
with `--retained-dose` as well. The script requires that retained dose to be
byte-identical to the official dose and terminal digest. Historical absolute
paths recorded in the summaries are labels, never implicit input selectors.

An example using entirely synthetic files:

```powershell
python tools/phits_roi_stats.py `
  --source synthetic-case.zip `
  --dose case/sumtally/dose.out `
  --error case/saved/dose_err.out `
  --retained-dose case/saved/dose.out `
  --generation case/analysis/sumtally_generation_summary.json `
  --execution case/analysis/sumtally_execution_summary.json `
  --manifest case/segments/segment_manifest.json `
  --case-label Synthetic --region-label CentralSphere `
  --radius-cm 0.25 --center-cm 0 0 0
```

The default sphere centre is `(0, 0, 0)` cm and default sampling spacing is
`0.1` cm. Supply exactly one of `--radius-cm` and `--volume-cm3`. The latter
is **analytic sphere volume**, converted to radius before selection. The
sphere must fit entirely within the PHITS mesh. PHITS cell centres at or
inside its radius define the dose population; no partial-volume weighting or
interpolation occurs.

For a Structure, use `--region-type structure --mask synthetic-mask.npz`
and provide a display label with `--region-label`. A label alone cannot
specify Structure geometry. The NPZ must contain a Boolean `mask` of shape
`(nx, ny, nz)`, `x_edges_cm`, `y_edges_cm`, `z_edges_cm`, scalar
`coordinate_system="phits_iec_fixed_cm_isocenter_anchored"`, and scalar
`axis_order="xyz"`. Its bin edges must exactly match the dose grid. It is
loaded without pickle. A sphere labelled `Chamber` remains a sphere.

For a DICOM RT Structure, use `--region-type rtstruct` with `--rtstruct`,
`--roi-number`, `--rtplan`, `--ct-reference`, and `--workspace`. The CT
reference must be one file in the frozen CT2PHITS CT snapshot, and the
workspace must contain the matching completed preparation summary and segment
manifest. Select that preparation summary as `--preparation`, a relative
member of the case directory or ZIP. The tool verifies the frozen CT series,
CT2PHITS asset digests, RT Plan and manifest binding, frame/contour references,
and PHITS mesh before making a transient mask. It rejects a missing or
ambiguous binding. A separately supplied RTSTRUCT or ROIName alone cannot
produce a Structure result. The RT Structure path leaves sphere fields null.

For several explicit cases, provide `--batch selections.json`. The JSON
object has a `cases` array; each item uses the same option names with
underscores, such as `source`, `dose`, `error`, `retained_dose`,
`generation`, `execution`, `manifest`, `case_label`, `region_label`,
`radius_cm`, and `center_cm`. RT Structure rows may use `workspace`,
`ct_reference`, `rtplan`, `rtstruct`, `preparation`, and `roi_number`.
Relative external-file paths resolve from the batch file's directory. Each
case contains exactly one region selection.
The console emits one JSON row per case. An invalid or empty case makes the
overall exit status nonzero; a valid dose selection with no eligible r.err
is reported as `partial`.

To publish CSV and JSON, first create a separate analysis directory and
specify `--output-dir` and optionally `--report-stem`. Each destination must
be absent; publication never overwrites a report. The output directory
cannot overlap a source case directory. Real calculation data and reports
must stay outside the public repository. The JSON contains definitions and
source SHA-256 values. CSV columns carry the scalar values and provenance;
external strings are neutralized for spreadsheets. Both files omit automatic
DICOM identifiers, source member names, absolute source paths, and raw grids. If a later file
cannot be published, the command reports the names already published.
Review user-supplied case labels and RT Structure ROI names before export;
these display strings are preserved and could contain identifying text.

## Independent desktop GUI

Run `.venv/Scripts/python.exe tools/phits_roi_stats_gui.py`. Choose a ZIP or
folder. A unique standard dicomxphits layout fills editable suggested
members for combined dose/error/evidence; missing or ambiguous fields remain
blank. Each member has a picker. For a directory source it opens a file dialog
limited to files inside that source; for ZIP it opens a searchable member
list. You may also type an existing relative member path. Every suggestion
is revalidated before analysis. For an error preserved in one saved Sumtally
run, the GUI suggests its co-located retained dose too. Choose sphere or RT
Structure; for the latter, select the frozen
workspace, CT reference, RT Plan, and RT Structure files, list the ROI names,
and explicitly choose the ROI number. Add each case to the table and run the
analysis. More than one case can be shown in one table.

The standalone window follows the main GUI's navy/cyan palette. Use the right
scrollbar to reach results and exports on smaller displays and the table's
horizontal scrollbar for remaining columns. See the [synthetic desktop
validation record](phits-roi-gui-validation.md) for exercised flows and limits.

The preparation summary is JSON **inside** the selected case. The RT Structure
is an **external DICOM file** chosen from the region section. Standard filename
suggestions do not infer or replace RT Plan, CT, RT Structure, or ROI identity.

The GUI starts a sphere at `(0, 0, 0)` cm, radius `0.25 cm`, and 1 mm sample
spacing. It labels the grid-dependent total as **Cell sum cGy** and shows
**Mean cGy** separately. Invalid DICOM binding is shown as an unavailable row;
it never substitutes a sphere. Optional CSV/JSON export asks for an existing
folder outside the repository and source cases, then uses new-only publication.
The current GUI is a separate analysis tool and does not alter the public
workflow GUI or completion state.

## Definitions

The validated input represents **one fraction in Gy**. The report multiplies
it by 100 once to obtain cGy. It does not reapply MU, calibration factors, or
planned fractions. `Total Dose / voxel-dose sum (cGy)` is the sum of selected
cell dose values. It is grid-dependent, not an energy integral or the mean.
The arithmetic mean, minimum, maximum, and `Standard dev` (population
`ddof=0`) include zero-dose cells. Standard dev measures spatial dose
variation; it is not PHITS statistical error.

For a sphere of radius `0.25 cm` and sampling spacing `0.1 cm`, the independent
centre-anchored lattice has 81 Points and a sampling volume of `0.081 cm³`.
The analytic geometric sphere volume is approximately `0.06544985 cm³`.
`Grid Points` counts selected native PHITS cell centres. It can be 7 on a
centre-aligned 2 mm mesh or 2 on a suitably offset 3 mm mesh. Only Grid
Points contribute to numerical statistics. Structure volume is the selected
native-cell volume; sphere-only fields are null for a Structure mask.

Voxel r.err summaries use only selected cells with positive dose and positive
r.err; there is no low-dose threshold. The unweighted mean, median, P95, and
maximum are percentages. Median and P95 use linear interpolation at sorted
position `q*(n-1)`. Absolute voxel standard error is `dose × r.err` in cGy;
its mean and maximum are also shown. Counts distinguish zero-dose cells,
positive-dose cells with zero r.err, and all excluded cells. Zero r.err means
the statistical observation is unavailable here, not exact certainty. The
input has no voxel covariance, so the report makes **no** claim about the
exact uncertainty of the ROI mean.

## Compatibility boundary

The tested formats are synthetic PHITS 3.35 T-Deposit xyz/xy combined
`isumtally=2` pairs representing saved legacy and current layouts. The
script checks the complete pair, roles, pages, geometry, finite nonnegative
arrays, source weights, sumfactor, manifest digest, successful execution,
terminal dose digest, and the accepted active-treatment MU normalization
record. A GUI version label by itself is not evidence of compatibility.
The independent result is separate from the GUI's post-completion Structure
r.err contract and from any multi-fraction RTDOSE conversion.
