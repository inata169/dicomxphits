"""Cross-process retry regression without invoking any external calculation tool."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from dicomxphits.gui import incomplete_plan_for_config
from dicomxphits.segment_stop import ControllerPipe


CHILD = """
import json
from pathlib import Path
import sys
sys.path.insert(0, sys.argv[1])
from test_segment_retry import partial, runner_for
from dicomxphits.prepare_3dcrt_workspace import ExternalToolPaths
from dicomxphits.run_segments import run_segments
if sys.argv[2] == 'initial':
    root, manifest, paths, summary = partial(Path(sys.argv[3]))
    print(json.dumps(dict(workspace_root=str(root),
        phits_root_folder=paths.phits_root_folder,
        phits_executable_path=paths.phits_executable_path)))
else:
    config = json.loads(sys.argv[3])
    root = Path(config['workspace_root'])
    paths = ExternalToolPaths(config['phits_root_folder'], config['phits_executable_path'])
    calls = []
    summary = run_segments(workspace_root=root, paths=paths, run_incomplete=True,
        expected_summary_sha256=sys.argv[4], runner=runner_for(root, calls=calls))
    print(json.dumps(dict(status=summary['stage_status'], calls=calls)))
"""


@pytest.mark.parametrize('cached_value', [None, 'python-environment'])
def test_controller_retry_uses_gui_environment_and_keeps_change_guard(
    tmp_path, monkeypatch, cached_value,
):
    key = 'DICOMXPHITS_TEST_CONTROLLER_ENVIRONMENT'
    # Like a native Tcl/Tk environment update: putenv changes what an implicit
    # subprocess inherits, but does not update Python's os.environ mapping.
    if cached_value is None:
        monkeypatch.delenv(key, raising=False)
    else:
        monkeypatch.setenv(key, cached_value)
    os.putenv(key, 'native-environment')
    try:
        command = [sys.executable, '-c', CHILD, str(Path(__file__).parent)]
        first = ControllerPipe().run([*command, 'initial', str(tmp_path)], cwd=tmp_path)
        assert first.returncode == 0, first.stderr
        config = json.loads(first.stdout)
        root = Path(config['workspace_root'])
        summary_path = root / 'analysis/segment_execution_summary.json'
        initial_bytes = summary_path.read_bytes()
        initial = json.loads(initial_bytes)
        retained = {
            item['path']: ((root / item['path']).read_bytes(), (root / item['path']).stat().st_mtime_ns)
            for item in initial['segments'][0]['output_evidence']
        }
        preview = incomplete_plan_for_config(SimpleNamespace(**config))
        assert preview['retained'] == ['seg_001']
        assert preview['scheduled'] == ['seg_002']
        assert summary_path.read_bytes() == initial_bytes

        retry = ControllerPipe().run(
            [*command, 'retry', json.dumps(config), preview['source_sha256']], cwd=tmp_path)
        assert retry.returncode == 0, retry.stderr
        assert json.loads(retry.stdout) == {'status': 'success', 'calls': ['seg_002']}
        assert {
            path: ((root / path).read_bytes(), (root / path).stat().st_mtime_ns)
            for path in retained
        } == retained
        complete_plan = incomplete_plan_for_config(SimpleNamespace(**config))
        assert complete_plan['scheduled'] == []

        # A genuine Python environment change must still invalidate the binding,
        # both in GUI preview and in the next controller before any fake launch.
        terminal_bytes = summary_path.read_bytes()
        monkeypatch.setenv(key, 'changed-after-preview')
        with pytest.raises(ValueError, match='runtime changed'):
            incomplete_plan_for_config(SimpleNamespace(**config))
        stale = ControllerPipe().run(
            [*command, 'retry', json.dumps(config), complete_plan['source_sha256']], cwd=tmp_path)
        assert stale.returncode != 0
        assert 'runtime changed' in stale.stderr
        assert summary_path.read_bytes() == terminal_bytes
    finally:
        # Restore the native-only divergence too; monkeypatch restores Python's
        # original mapping at teardown. No HOME or other system setting changes.
        current = os.environ.get(key)
        if current is None:
            os.unsetenv(key)
        else:
            os.putenv(key, current)
