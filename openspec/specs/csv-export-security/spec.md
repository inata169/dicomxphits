# csv-export-security Specification

## Purpose

Define spreadsheet-safe serialization of DICOM-derived external strings while
preserving ordinary CSV values, numeric fields, and the published table
structures.

## Requirements
### Requirement: External String Spreadsheet Neutralization

CSV writers SHALL pass externally derived string cells through one common
neutralization boundary. A string beginning with `=`, `+`, `-`, or `@`, or a
leading C0/C1 control character including tab, carriage return, or line feed,
MUST be made non-active for spreadsheet interpretation by prefixing an
apostrophe. Ordinary strings and empty strings SHALL remain unchanged, numeric
values MUST remain numeric, and CSV quoting SHALL remain responsible for commas,
quotes, and embedded record characters rather than being treated as formula
protection.

#### Scenario: Ordinary DICOM BeamName

- **WHEN** BeamName contains an ordinary Unicode or Japanese value that does
  not begin with a spreadsheet-active or control character
- **THEN** the CSV cell contains the original value unchanged

#### Scenario: Formula-leading external string

- **WHEN** an external CSV string begins with `=`, `+`, `-`, or `@`
- **THEN** the stored cell begins with an apostrophe followed by the complete
  original value

#### Scenario: Control-leading external string

- **WHEN** an external CSV string begins with tab, carriage return, line feed,
  or another C0/C1 control character
- **THEN** the stored cell is prefixed so the control character is not the
  spreadsheet-visible first character

#### Scenario: CSV structural characters

- **WHEN** an external string is empty or contains Unicode, Japanese text,
  commas, quotes, or embedded newlines
- **THEN** a standards-compliant CSV read returns the expected neutralized cell
  and the original number and order of columns
