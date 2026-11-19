# Design

## Establish the saved tally budget

Use the prepared input to establish the intended batch count and histories
per batch. Use invocation-bound progress and the recorded exit to identify
the supported failure. Use restart metadata in the retained tally pair to
establish the saved count. The reported completion of a batch is insufficient
to establish that its results were written. The narrowly scoped first policy
requires a recorded last planned batch and a complete paired snapshot of
the preceding batch. The pair and any other required retained tally must
belong to the same saved batch and have compatible restart metadata.

Use the existing bounded readers where they cover the required format.
Cross-check tally identity, grid coverage, and restart metadata against the
prepared input and the invocation evidence. Verify every consumed tally
byte-for-byte against the prospective retained-staging record. Incidental
outputs such as plot images are outside the consumed tally set. A mutable
batch progress file by itself grants no authority. An absent end-of-run
geometry summary stays explicitly unavailable. Known positive or
contradictory geometry diagnostics disqualify the snapshot.

## Keep research export authority separate

Preview one explicitly selected retained staging directory from the failed
case. Confirmation binds the preview to the current input, output, execution,
and destination evidence. The export owns its writes and uses private
intermediates. Its authority applies only to this export and cannot enable
ordinary actions or act as an existing geometry-recovery receipt. The failed
source execution stays visible and the original records and staging retain
their bytes.

Reuse existing validation and calculation code for the confirmed input set.
The saved tally covers the one active delivery segment, with fewer Monte
Carlo batches than requested. Batches determine the sampling budget. They
do not change the treatment-beam set, prescribed fraction count, or MU.
Carry the saved tally's own normalization into Sumtally and apply the
approved treatment normalization once. The batch ratio is provenance and
does not enter the dose arithmetic. The export uses tally aggregation and
DICOM conversion only. A PHITS executable used by Sumtally must operate in
aggregation mode.

## Keep the label with the result

Publish the research RT Dose with a versioned JSON receipt. The receipt
contains the failure and completeness details and binds the final DICOM by
SHA-256. The RT Dose itself carries a bounded ASCII `DoseComment` containing
`RESEARCH ONLY`, `PARTIAL PHITS`, and the saved/planned batch counts. The comment
is descriptive. Preserve the existing plan reference, frame of reference,
dose values, units, scaling, and coordinate semantics. Verify the label and
the ordinary semantic checks on the final file before publication. The
receipt remains the complete provenance record even when a viewer omits the
comment from its display.

See [DICOM PS3.3 RT Dose Module](https://dicom.nema.org/Medical/dicom/current/output/chtml/part03/sect_C.8.8.3.html)
for `DoseComment` and [PHITS 3.35 §3](https://phits.jaea.go.jp/manual/manualE-phits335.pdf)
for saved tally restart metadata.
