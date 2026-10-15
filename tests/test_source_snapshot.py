"""A custody extraction must preserve members, bytes and public import paths."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile

import pytest

from zenith import source_snapshot as snapshot

ROOT = Path(__file__).resolve().parents[1]


def legacy_hashes(root):
    paths = []
    for folder in ("zenith", "system/core", "system/lib", "tools", "variants"):
        paths.extend((root / folder).rglob("*.py"))
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(paths) if path.is_file()}


def test_implementation_hashes_preserve_legacy_member_policy():
    assert snapshot.implementation_hashes() == legacy_hashes(ROOT)


def test_snapshot_exact_members_bytes_and_exclusive_creation(tmp_path):
    expected = set(legacy_hashes(ROOT))
    expected.update(str(p.relative_to(ROOT)) for p in (ROOT / "research").rglob("*.py"))
    expected.update(str(p.relative_to(ROOT)) for p in (ROOT / "codex").rglob("*.json"))
    expected.add("master_config.json")
    receipt = snapshot.archive_runtime(tmp_path)
    target = Path(receipt["path"])
    assert receipt["sha256"] == hashlib.sha256(target.read_bytes()).hexdigest()
    assert receipt["scope"] == snapshot.ARCHIVE_SCOPE
    with ZipFile(target) as archive:
        assert archive.namelist() == sorted(expected)
        assert all(archive.read(name) == (ROOT / name).read_bytes() for name in expected)
        assert not any(name.startswith(("examples/", "work/")) or "/.env" in name
                       for name in archive.namelist())
    with pytest.raises(FileExistsError):
        snapshot.archive_runtime(tmp_path)


def test_old_import_paths_remain_compatible():
    from research.investigator_study import archive_runtime
    from zenith.runtime import implementation_hashes
    assert archive_runtime is snapshot.archive_runtime
    assert implementation_hashes() == snapshot.implementation_hashes()


@pytest.mark.parametrize("runner", (
    "research.decomposition_study", "research.investigation_learning_study",
))
def test_current_runner_import_does_not_load_historical_engine(runner):
    code = '''import sys, json, importlib
sys.path.insert(0, sys.argv[1])
before = set(sys.modules)
runner = importlib.import_module(sys.argv[2])
assert runner.archive_runtime is importlib.import_module("zenith.source_snapshot").archive_runtime
forbidden = ("research.investigator_study", "zenith.runtime", "zenith.basket_panel",
             "zenith.investigator", "zenith.market_graph", "zenith.market_data",
             "system.core.engine", "numpy", "pandas")
print(json.dumps([name for name in forbidden if name in sys.modules and name not in before]))
'''
    result = subprocess.run([sys.executable, "-I", "-c", code, str(ROOT), runner],
                            cwd=ROOT, env={}, check=True, capture_output=True, text=True)
    assert json.loads(result.stdout) == []
