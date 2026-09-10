# Supported observation grammar: PHITS 3.35 Windows OpenMP

## Evidence and limits

Two separately approved synthetic probes were assessed on 2026-09-10. The first
provided final structure and examples of torn and generation-mismatched reads.
The second supplied nine distinct generations, each with two stable consecutive
complete matching pairs. Both identified 3.350 and two OpenMP workers, exited
naturally with geometry-clean diagnostics and preserved input/final digests.
Exact private paths, runtime hashes, raw numeric output and seed/time records
are not part of this public document. No distributed output fixture is copied.

The [versioned official manual](https://phits.jaea.go.jp/manual/manualE-phits335.pdf),
sections 3.1-3.2, 4.9 and 5.2.20, independently explains restart fields, remaining
batches, separate error files, page boundaries, array order and batch-end writes.
Its older T-Track example is not used to assert target-version support.

The observed variant is fresh transport with default history variance (istdev=2),
xyz linear mesh, axis=xy, output=dose, unit=0, part=all, material=all and epsout=1.
Unsupported syntax or another variance/restart mode remains unavailable; support
must not be guessed from a filename. Read-only observations remain provisional.
Collector overhead was not independently timed; no performance-equivalence or
desktop-responsiveness claim follows from these probes.

## Identity

Require the owned summary's unambiguous version marker with value 3.350 and the
bound standard Windows OpenMP executable/runtime and input identity. Actual
OpenMP stdout identifies worker ordinals/total and IP(MPI)=0. The tally page
caption identifies PHITS 3.35. A basename, isolated numeric substring or reused
output cannot establish version/mode. Keep identity reads bounded.

## Batch records

The initial record contains the prepared remaining count followed by
the initial remaining-batch label, blank line, separator, start-calculation
line, separator, blank line, date/time and blank line. Its time ends at seconds
without the suffix used in updated records. Updated records use a different label and
contain, in order: remaining count, blank line, separator, bracketed batch
ordinal and cumulative ncas, a binary seed, batch CPU duration, blank line,
date/time, separator, next-seed heading and binary seed. Newlines are CRLF in
the observed files. Require the complete selected record, bounded numeric
fields and a remaining count within the prepared budget. Retain independent
batch timestamps and reject regressions. Neither the ordinal, ncas, seed nor
remaining zero is successful-segment evidence.

## Dose/error pair

1. An input echo begins with T-Deposit and records title, mesh type, axis bounds,
   cell counts, coordinate lists, unit, material, output, 2D-type=3, axis, output
   filename, particle and other fixed tally options. Both roles echo the dose
   filename; role identification must also check the later Dose/Relative Error
   label rather than infer role solely from the header filename.
2. The first page uses a commented newpage marker; subsequent pages use the
   active marker. Each page has matching page ordinal, iz, particle and z bounds,
   a quoted page title, PHITS version caption, graph directives and mesh counts.
3. The explicit array-order comment precedes the mesh hc coordinate record and
   exactly nx*ny numeric values. x varies fastest ascending; y descends. Pages
   cover z slices in ascending order. Require every slice and no duplicate.
4. Plot-legend hc data (the separate 1..100 scale), graph directives, role label,
   z annotations and final plot reset follow each mesh block. They are not dose
   cells and must not enter statistics. Reject missing structural endings;
   never execute ANGEL commands or follow paths found in text.
5. A single trailing restart block states newly started calculation, istdev,
   resc2, resc3, maxcas and next bitrseed, ending at the binary-seed comment.
   Both roles must agree on all these fields as well as actual mesh, particle,
   output mode and tally identity. No partial or extra numeric cells are filled.

The fields have the meanings stated in the manual; history/seed metadata is
used only to reject inconsistent observations, never to unlock downstream work.
Mesh values use exponent notation and may wrap across lines. Numeric tokens
and total cells must be limited before allocation. Require finite nonnegative
values, exclude zero dose/error once, and compute positive-cell coverage and
median/maximum percent under the approved observation specification.

## Concurrent sampling

Both complete files must pass unchanged identity/size/time checks around their
reads and agree as a pair, then agree across two successive samples. The first
probe demonstrates why individually stable metadata alone is insufficient.
An unstable or mismatched sample resets candidate confirmation. Accepted values
keep their original timestamp while unchanged. No final snapshot replaces
missing live confirmation. Diagnostic polling was 100 ms; production remains
at most once per second with a cooperative two-second sample deadline.
