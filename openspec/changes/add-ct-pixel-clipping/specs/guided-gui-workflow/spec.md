## ADDED Requirements

### Requirement: Linked Orthogonal CT Clipping Preview

The GUI SHALL provide Axial, Coronal, and Sagittal previews of the explicitly
selected validated axial HFS source series after non-patient confirmation.
It SHALL provide plane navigation, contrast, direction labels, source-index
pointer readout, and synchronized overlays for one shared box. Display SHALL
preserve physical aspect ratio and map clicks independently of scaling,
letterboxing, and display-axis reversal. It MUST NOT rewrite source DICOM,
display demographics, or launch an external tool from preview actions.
The GUI SHALL let the human visually choose any valid axis-aligned source box,
independently of whether excluded content is a couch or other material. It
MUST NOT infer an automatic material or anatomy boundary. Browse mode SHALL
leave bounds unchanged; explicit corner-selection mode SHALL change only the
selected view's two axes. Plane enlargement and one-index stepping SHALL
preserve the shared bounds and pointer mapping.

#### Scenario: Edit two axes in one view

- **WHEN** two opposite corners are selected within one view in either order
- **THEN** Axial updates X/Y, Coronal updates X/Z, or Sagittal updates Y/Z,
  preserves the third pair, and synchronizes all six fields and all views

#### Scenario: Numeric editing

- **WHEN** valid pixel/slice bounds are entered numerically
- **THEN** the shared box and all three overlays reflect those bounds

#### Scenario: Independent navigation

- **WHEN** viewing position, crosshairs, or contrast changes
- **THEN** clipping bounds remain unchanged and a plane outside the selected
  volume is identified as outside

#### Scenario: Human reviews an unwanted object

- **WHEN** the user inspects planes, enlarges one view, and manually adjusts
  bounds to place unwanted material outside the chosen box
- **THEN** the GUI shows retained and excluded source regions without claiming
  to classify the material or removing any voxel inside the box

#### Scenario: Outside click or interrupted pair

- **WHEN** a click is outside the image or the user changes views mid-pair
- **THEN** the GUI does not construct a crop from outside coordinates or points
  belonging to different planes

### Requirement: Bounded Read-Only Preview Loading

The GUI SHALL load preview pixels responsively within a documented memory
bound, validate decoded dimensions and supported representation, and apply
rescale/contrast for display only. It MUST discard stale load results after
case changes or dialog closure and MUST NOT install codecs or persist pixels
automatically. Unsupported preview MUST NOT disable the existing unpreviewed
full-volume workflow.

#### Scenario: Failed or oversize load

- **WHEN** decoding fails or the preview exceeds its memory bound
- **THEN** the GUI reports the condition without claiming a valid visual crop

#### Scenario: Single source slice

- **WHEN** adjacent Z spacing cannot be established for a single-slice source
- **THEN** Axial and numeric controls remain usable and Coronal/Sagittal are
  identified as unavailable without inventing physical thickness

### Requirement: Case-Bound Clipping Apply and Invalidation

The GUI SHALL distinguish draft and applied bounds, provide Apply, Cancel,
and Reset to full volume, and display applied bounds before conversion.
It SHALL show three numeric coarse-graining fields for X, Y, and Z with
defaults `8 8 2`, validate equal positive X/Y factors and Z from `1` through
`4`, and treat them as case-local settings rather than global preferences.
Apply MUST reject invalid or incomplete selection. Applied bounds SHALL use
the accepted shell-free CLI and frontend revalidation. They MUST NOT persist
as global preferences, carry silently into another series, or mutate an
active execution's request.

#### Scenario: Cancel or reset

- **WHEN** draft edits are canceled
- **THEN** prior applied bounds remain unchanged
- **AND WHEN** Reset to full volume is applied
- **THEN** all six bounds cover the original complete volume

#### Scenario: Changed source

- **WHEN** directory, selected series, or inspected source identity changes
- **THEN** stale bounds cannot authorize conversion and the current source
  must be revalidated before a new selection is applied

#### Scenario: Confirmed execution

- **WHEN** valid applied bounds and all existing plus clipping-specific gates pass
- **THEN** the GUI passes exactly those pixel/slice ranges to the existing
  frontend with the effective X/Y/Z coarse-graining factors, without
  duplicating tool invocation

#### Scenario: Numeric coarse-graining edit

- **WHEN** the user enters equal positive X/Y factors and a Z factor from
  `1` through `4`
- **THEN** the GUI passes those factors through the existing CLI path only
  when the supported-tool geometry contract permits conversion

#### Scenario: Clipped default coarse conversion with remainders

- **WHEN** a valid selected box under positive factors has incomplete high-end groups
- **THEN** the GUI shows the lost source counts and retained source bounds as a
  warning in a child window using the main GUI palette before starting the
  frontend; Continue proceeds with the requested box and Cancel leaves it idle

#### Scenario: Visible actions and consistent child windows

- **WHEN** the CT preview opens at its initial size or is resized within its minimum
- **THEN** Apply, Cancel, and Reset remain visible while the image row resizes
- **AND** application message and confirmation windows use the main GUI palette,
  with closure and Escape returning the negative confirmation result
