# Design

Use explicit translation keys for application-owned interface text. Keep
language state separate from case inputs and analysis results. Update widget
text and dynamic message rendering in place rather than rebuilding the form.
Keep table column identifiers stable while translating their visible headings.

Language switching must not write input fields, clear the ROI list, re-run
analysis, publish reports, or change action availability. It is allowed during
analysis; the eventual completion message uses the current display language.

The menu caption and language names remain discoverable in either language.
Japanese is the initial language on each launch; persistent settings are outside
this change. Paths, user labels, ROIName, raw source/analysis diagnostics, numeric
values, units, and machine-readable report keys are not translated. Localized
context explains raw diagnostic text. OS-owned file-dialog controls may follow
the operating system's language.
