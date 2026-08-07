# Public Feasibility Demonstration

## Purpose

This document states the research and engineering value demonstrated by
dicomxphits and the limits of that demonstration. It distinguishes a working
public implementation from a proposal that the relevant interfaces might be
connected, while avoiding clinical, vendor, and general-compatibility claims.

## Research Question

Can an openly inspectable workflow connect non-patient phantom DICOM CT and RT
Plan inputs to PHITS calculations, DICOM RT Dose output, coordinate correction,
and an external gamma comparison without embedding confidential machine data,
licensed tool distributions, or generated research artifacts in the public
repository?

The repository answers this question constructively for a limited fixed-field
3D-CRT research scope: it provides the public implementation, explicit stage
contracts, and a human-confirmed end-to-end demonstration under bounded
non-patient phantom conditions.

## What Was Implemented

The public implementation provides adapters and validation gates for:

1. selecting and freezing non-patient phantom DICOM CT and RT Plan inputs;
2. invoking the user-supplied Windows CT2PHITS batch frontend and validating
   its handoff;
3. generating fixed-field 3D-CRT PHITS inputs from the RT Plan and validated
   CT2PHITS assets;
4. explicitly executing all active PHITS segments;
5. generating and executing a Sumtally job that combines the active segment
   doses with the documented MU normalization;
6. preparing and executing conversion to DICOM RT Dose;
7. applying and independently validating the documented RTDOSE coordinate
   correction;
8. preparing or executing a handoff to the external GPR-comparing project; and
9. comparing the coordinate-corrected result with a TPS-derived RT Dose.

These stages are not represented by one opaque command. Each stage records
its inputs, outputs, status, and relevant provenance or integrity evidence, and
the downstream stages fail closed when required evidence is missing or stale.
The public automated tests exercise these contracts with synthetic data and
mock external runners; they do not replace the separately reported real-tool
phantom demonstration.

## Public Research Model

The built-in model is a deliberately simplified public research model. It
uses:

- an author-generated 59-bin photon spectrum derived from part 1 of the IAEA
  `ELEKTA_PRECISE` 6 MV phase-space dataset, identified by
  `ELEKTA_PRECISE_6mv_part1.IAEAphsp` and its matching `.IAEAheader`;
- a uniform `3 × 3 mm` rectangular photon source centered in a beam-aligned
  source plane located `100 cm` upstream of isocenter;
- rectangular MLC and Y-Diaphragm geometry; and
- materials, transport controls, and other research settings selected by the
  authors and collaborators after reviewing public literature and available
  manufacturer information.

The model does not reproduce a specific clinical Elekta treatment unit or a
proprietary Monaco beam-model configuration. It carries no vendor
certification and is not a commercial treatment machine digital twin. The
original IAEA phase-space and header files, official PHITS or RT-PHITS
distributions, vendor-confidential drawings, NDA-protected information,
facility-specific commissioning data, and proprietary Monaco beam-model data
are not included.

This distinction is central to the contribution. Simplification makes the
model more openly inspectable and modifiable and permits public discussion of
the complete engineering workflow. It trades machine-specific fidelity for
public availability, explainability, and a basis that other researchers can
replace or refine.

## End-to-End Workflow Demonstrated

The author has confirmed completion of the following chain under limited
non-patient phantom research conditions:

```text
DICOM CT + RT Plan
  -> CT2PHITS handoff
  -> fixed-field 3D-CRT PHITS inputs
  -> PHITS segment calculations
  -> Sumtally dose aggregation
  -> DICOM RT Dose conversion
  -> coordinate correction and placement validation
  -> external GPR-comparing handoff
  -> gamma comparison with TPS-derived RT Dose
```

The significance is not merely that each interface appears possible in
principle. A public implementation exists and the full chain was made to run
for the bounded cases below. In this sense, dicomxphits is a working
end-to-end demonstration and an engineering constructive proof of feasibility.

## Tested Non-Patient Phantom Cases

The human-confirmed demonstrations and their mapped comparison outcomes were:

- a non-patient water phantom with a centered `20 × 20 cm²` fixed field, with
  two comparison records around 95%, slightly below 95% in both records; and
- a non-patient phantom case using the PHITSgeoTest plan, with a Gamma Passing
  Rate of at least 95%.

Both cases completed the chain from DICOM input through PHITS, Sumtally,
coordinate-corrected RTDOSE, and external GPR-comparing under limited research
conditions. A separate non-patient phantom report also recorded a Gamma
Passing Rate of at least 95%. The retained evidence for that record establishes
the comparison outcome, but not the human-confirmed completion of the full
chain used to define the two demonstrated cases, so it is not counted as a
third end-to-end demonstration.

Only these bounded results are asserted. Exact individual pass rates and the
external result artifacts are not published. No values should be inferred
from the implementation, tests, or historical release evidence.

## Gamma Comparison Conditions

The demonstrated comparisons used the TPS-derived RT Dose as the reference and
the coordinate-corrected PHITS-derived RTDOSE as the evaluation.
GPR-comparing remained an external research tool. The current dicomxphits
documentation gives a reproduction example that explicitly selects global
`3% / 3 mm` gamma with a `10%` dose cutoff. The command-line defaults differ:
they are global `3% / 2 mm` with a `10%` cutoff, so the documented example
passes `--dd 3 --dta 3 --cutoff 10` explicitly.

A read-only review of four locally retained comparison reports found consistent
recorded comparison settings: global `3% / 3 mm` gamma, a `10%` dose cutoff,
global-maximum normalization, linear interpolation, and an interpolation
fraction of 3. The accompanying run logs map one report to the PHITSgeoTest
case, two reports to the same centered water-phantom case, and one report to a
separate non-patient phantom.

The PHITSgeoTest log records `3 mm` reference and evaluation in-plane RT Dose
grid spacing, reported through DICOM `PixelSpacing`, and initial
`GridFrameOffsetVector` values in `3 mm` increments. The two water-phantom logs
record `2 mm` reference and `3 mm` evaluation in-plane dose-grid spacing, with
corresponding initial frame-offset increments. The separate phantom log records
`3 mm` reference and evaluation in-plane dose-grid spacing and initial frame
offsets. The final logged calculations were run from August 4 through August 6,
2026. These values record the comparison grids and run dates only; they do not
establish numerical reproducibility outside the documented inputs and
environment.

The retained reports label the settings as global-maximum normalization and a
`10%` dose cutoff, but do not identify the exact GPR-comparing version or commit
used for the four runs. This document therefore does not further assert the
normalization denominator or cutoff-mask implementation for those runs.

The two water-phantom records are repeat or comparison records for the same
named case, not two additional cases. The separate phantom record is distinct
from the two named demonstrations, but it is retained as supporting evidence
rather than used to increase the demonstrated-case count.

The repository also retains a precise pass rate for separate historical
v1.0.0 evidence under global `3% / 3 mm` with a `10%` cutoff, but explicitly
marks that record as not applicable to the v1.0.1 target release. It is not
used as the value for either case reported in this document.

The reports and logs therefore establish the common comparison condition and
the case mapping. The PHITSgeoTest result is stated as at least 95%, while the
two centered water-phantom records are stated as around 95%, slightly below
95%. Exact individual pass rates remain unasserted. Here, 95% is only a concise
description of the observed research results; it is not a clinical pass/fail
threshold, a treatment QA acceptance criterion, or a commissioning decision.

## What the Result Demonstrates

The result demonstrates that, for the two stated non-patient phantom cases and
the documented fixed-field 3D-CRT boundaries:

- the public adapters and model can be assembled into an operational workflow;
- the CT2PHITS, PHITS, Sumtally, RTDOSE, coordinate, and external comparison
  handoffs can complete in sequence;
- the public implementation is more than a conceptual integration proposal;
  and
- researchers have an openly inspectable and modifiable baseline for studying
  or replacing individual model components.

This is a feasibility result. The public stage contracts make an engineering
rerun possible within the documented prerequisites and boundaries, but the
repository alone does not provide the inputs and result artifacts needed for
independent numerical reproduction. Numerical identity across tools, machines,
datasets, or environments is not claimed.

## What the Result Does Not Demonstrate

The result does not establish:

- clinical accuracy or clinical validity;
- commissioning of a treatment machine or TPS beam model;
- agreement with an arbitrary physical Elekta unit;
- approval, certification, endorsement, or affiliation by any vendor;
- compatibility with other TPS versions, accelerators, scanners, operating
  environments, field arrangements, or treatment techniques;
- suitability for treatment decisions, patient-specific QA, or patient QA;
- support for IMRT, dynamic MLC delivery, or VMAT; or
- a general or universal dose-accuracy claim.

The reported Gamma Passing Rates are bounded phantom research observations.
They cannot by themselves establish any of the claims above.

## Reproducibility Boundaries

The public repository contains the implementation, default research-model
definition, synthetic/mock tests, documentation, and a sanitized RTDOSE
template. It intentionally does not contain real DICOM inputs, external-tool
outputs, screenshots, the original IAEA phase-space data, or official PHITS
and RT-PHITS distribution files.

Reproduction therefore requires the documented Python 3.12 and Windows-host
workflow environment, separately obtained licensed PHITS and RT-PHITS tools,
an external GPR-comparing checkout when gamma comparison is requested, and
appropriately authorized non-patient phantom DICOM. Numerical comparison also
depends on the selected model, calculation controls, dose grids, comparison
criteria, interpolation behavior, and reference RT Dose.

Within those prerequisites and boundaries, the public stages and contracts can
be inspected and rerun as an engineering workflow. The two reported cases are
not independently numerically reproducible from this repository alone,
identical physics or gamma results are not guaranteed, and the locally retained
comparison artifacts are not distributed as a public numerical-reproduction
package.

## Replaceable Model Components

The research model is structured so that its source description, spectrum,
MLC, Y-Diaphragm, material, and transport settings can be inspected. The
machine-configuration interface permits research overrides, providing a basis
for investigations with more detailed source, MLC, jaw, or machine
configurations.

Replacement is not automatic validation. The approved public dose factor is
bound to the built-in model identity. A modified model fails closed as using a
stale factor unless relative-dose-only mode is explicitly selected; a new
absolute-dose model requires an independently justified calibration and
validation.

## Future Research Directions

Possible research extensions include:

- independent replication with shareable non-patient phantom inputs and a
  fully recorded comparison protocol;
- sensitivity studies for the source spectrum, focal-spot description,
  rectangular MLC and jaw geometry, materials, and transport settings;
- evaluation across additional non-patient phantoms, static field sizes,
  angles, dose grids, and comparison implementations within the documented
  fixed-field boundary;
- replacement of simplified components with more detailed public or
  independently measured research models; and
- publication of additional case-specific results and fuller comparison
  provenance when they can be shared without adding protected or licensed
  artifacts.

Any future expansion of treatment-technique scope, clinical claims, or machine
specificity requires separate evidence and review. It is not implied by the
current demonstration.
