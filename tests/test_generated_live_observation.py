"""Generated-input compatibility; all output fixtures are project-authored."""
from __future__ import annotations

import json
import time

import pytest

from dicomxphits.phits_observation import Observer, Presentation, RELATIVE_PATH
from dicomxphits.phits_observation_format import ObservationError, prepared_contract, paired_tally_values, LIVE_PARSER
from test_phits_live_observation import deck, observer_fixture, tally, MESH
from test_prepare_3dcrt_workspace import (
    ExternalToolPaths, install_manifest_export, manifest_with,
    prepare_public_3dcrt_workspace, rectangular_segment,
)


def test_public_generated_segment_can_construct_observer_without_input_edits(tmp_path, monkeypatch):
    segment = rectangular_segment(resolved_mlc_positions_mm={
        'bank_a': [-20.0] * 80, 'bank_b': [20.0] * 80})
    install_manifest_export(monkeypatch, manifest_with(segment))
    plan = tmp_path / 'authored-placeholder.dcm'
    plan.write_text('synthetic placeholder; DICOM reader is mocked', encoding='utf-8')
    root = tmp_path / 'workspace'
    prepared = prepare_public_3dcrt_workspace(
        rtplan_path=plan, workspace_root=root,
        paths=ExternalToolPaths(str(tmp_path / 'synthetic-tools'), ''),
        ct_datfiles_root=tmp_path / 'DATfiles', ct_reference_dicom=tmp_path / 'CT.dcm',
        confirmed_non_patient_phantom=True, maxcas=1000, maxbch=10, omp_threads=1)
    generation = prepared['phits_generation']
    source = root / generation['generated_phits_inputs'][0]
    dose = root / generation['expected_output_paths'][0]
    before = source.read_bytes()
    assert ' istdev = -1' in before.decode('utf-8')
    observer = Observer(root, root, source, dose, {})
    assert observer.runtime == {'maxcas': 1000, 'maxbch': 10, 'threads': 1}
    assert observer.mesh.file == dose.relative_to(root).as_posix()
    assert observer.mesh.counts == tuple(generation['calculation_config']['dose_tally_3d']['counts'])
    assert source.read_bytes() == before
    assert not (root / RELATIVE_PATH).exists()


@pytest.mark.parametrize('variance', [1, 2])
@pytest.mark.parametrize('directive', [' istdev = -1', ' ISTDEV = -1 # generated default'])
def test_generated_variance_directive_keeps_live_sampling_and_reset(tmp_path, directive, variance):
    old, summary = observer_fixture(tmp_path)
    source = old.staging / 'input.inp'
    source.write_text(deck().replace('[ Parameters ]', '[ Parameters ]\n' + directive))
    for path, role in ((old.dose_path, "dose"), (old.error_path, "error")):
        path.write_bytes(tally(role).replace(b"# istdev = 2", f"# istdev = {variance}".encode()))
    before = {p.name: p.read_bytes() for p in old.staging.iterdir()}
    observer = Observer(old.root, old.staging, source, old.dose_path, old.binding)
    observer.feed_stdout(bytes(old.stdout))
    first = observer.sample()
    assert first['batch']['value'] is None and first['error']['value'] is None
    record = {**observer.sample(), 'sequence': 1}
    assert record['parser'] == LIVE_PARSER
    assert record['batch']['value'] == {'remaining': 9, 'prepared_total': 10}
    assert record['error']['value'] == {'relative_error_percent': 10.0}
    target = tmp_path / RELATIVE_PATH
    target.parent.mkdir()
    target.write_text(json.dumps(record))
    presentation = Presentation()
    now = time.monotonic()
    display = presentation.refresh(tmp_path, summary, active=True, now=now)
    assert 'Observed remaining batches 9' in display
    assert 'Isocenter voxel r.err 10%' in display
    assert 'provisional' in display and 'single reference voxel' in display
    assert 'stale' in presentation.refresh(tmp_path, summary, active=True, now=now + 6)
    assert 'no owned active' in presentation.refresh(tmp_path, summary, active=False)
    assert presentation.record is None
    assert {p.name: p.read_bytes() for p in old.staging.iterdir()} == before


@pytest.mark.parametrize('directive', [
    'istdev = 1', 'istdev = 2', 'istdev = 0', 'istdev = -2',
    'istdev = -1.0', 'istdev = -1 extra', 'istdev =', 'istdev',
    'istdev = -1\nistdev = -1', 'istdev = -1\nistdev = 2',
    'istdev = -1\nistdev = nonsense', 'itall = 1', '$MPI = 2',
])
def test_unsupported_or_ambiguous_prepared_variance_remains_rejected(directive):
    with pytest.raises(ObservationError):
        prepared_contract(deck().replace('[ Parameters ]', '[ Parameters ]\n' + directive), 'dose.out')


@pytest.mark.parametrize('variance', [0, 3])
def test_default_input_does_not_authorize_unsupported_output_variance(tmp_path, variance):
    old, _ = observer_fixture(tmp_path)
    source = old.staging / 'input.inp'
    source.write_text(deck().replace('[ Parameters ]', '[ Parameters ]\n istdev = -1'))
    for path, role in ((old.dose_path, 'dose'), (old.error_path, 'error')):
        path.write_bytes(tally(role).replace(b'# istdev = 2', f'# istdev = {variance}'.encode()))
    observer = Observer(old.root, old.staging, source, old.dose_path, old.binding)
    observer.feed_stdout(bytes(old.stdout))
    observer.sample()
    record = observer.sample()
    assert record['batch']['state'] == 'available'
    assert record['error']['state'] == 'unsupported-format'
    assert record['error']['value'] is None


def batch_tally(role="dose", batches=10):
    return tally(role, histories=batches).replace(b"# istdev = 2", b"# istdev = 1")


@pytest.mark.parametrize("batches", [1, 10])
def test_live_batch_budget_boundaries_and_shared_default(batches):
    dose, error = batch_tally(batches=batches), batch_tally("error", batches)
    with pytest.raises(ObservationError, match="unsupported-variance"):
        paired_tally_values(dose, error, MESH, 10, time.monotonic()+2)
    _, _, metadata = paired_tally_values(
        dose, error, MESH, 10, time.monotonic()+2, live_maxbch=10)
    assert metadata["resc3"] == batches


@pytest.mark.parametrize("old,new", [
    (b"# istdev = 1", b"# istdev = 2"),
    (b"# resc2 = 1.00000000000000000E+01", b"# resc2 = 9"),
    (b"# resc3 = 1.00000000000000000E+01", b"# resc3 = 9"),
    (b"# maxcas = 10", b"# maxcas = 11"),
    (b"# bitrseed = " + b"0"*64, b"# bitrseed = " + b"1"*64),
])
def test_live_batch_pair_rejects_metadata_disagreement(old, new):
    error = batch_tally("error")
    assert old in error
    with pytest.raises(ObservationError):
        paired_tally_values(batch_tally(), error.replace(old, new), MESH, 10,
                            time.monotonic()+2, live_maxbch=10)


@pytest.mark.parametrize("count", [b"0", b"-1", b"1.5", b"11", b"nan", b"inf"])
def test_live_batch_pair_rejects_invalid_or_excess_counts(count):
    def altered(role):
        return batch_tally(role).replace(b"# resc3 = 1.00000000000000000E+01", b"# resc3 = " + count)
    with pytest.raises(ObservationError):
        paired_tally_values(altered("dose"), altered("error"), MESH, 10,
                            time.monotonic()+2, live_maxbch=10)
