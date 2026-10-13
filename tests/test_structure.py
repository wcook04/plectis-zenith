"""Negative controls for source roles and Git's staged/ignored boundary."""
import importlib.util
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('structure_check', ROOT / 'scripts/check_structure.py')
structure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(structure)


def test_repository_layout():
    assert not structure.check_paths(structure.candidate_paths(ROOT))


def test_misplaced_program_test_and_new_owner_are_rejected():
    for misplaced in ['adhoc.py', 'docs/rebuild.py', 'scripts/test_runtime.py', 'unowned/data.json']:
        failures = structure.check_paths(set(structure.REQUIRED) | {misplaced})
        assert any(misplaced in failure for failure in failures), failures


def test_required_source_anchor_cannot_disappear():
    removed = next(iter(structure.REQUIRED))
    assert f'Missing source anchor: {removed}' in structure.check_paths(set(structure.REQUIRED) - {removed})


def test_ignored_build_tree_and_force_staged_artifacts(tmp_path):
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=tmp_path)
    git('init', '-q')
    (tmp_path / '.gitignore').write_text('node_modules/\nignored-build/\n')
    (tmp_path / 'node_modules').mkdir()
    (tmp_path / 'node_modules/dependency.py').write_text('')
    (tmp_path / 'ignored-build').mkdir()
    (tmp_path / 'ignored-build/test_generated.py').write_text('')
    (tmp_path / 'README.md').write_text('read me')
    git('add', 'README.md', '.gitignore')
    assert structure.candidate_paths(tmp_path) == {'README.md', '.gitignore'}
    git('add', '-f', 'node_modules/dependency.py')
    candidates = structure.candidate_paths(tmp_path)
    assert 'node_modules/dependency.py' in candidates
    assert any('Dependency/cache' in item for item in structure.check_paths(set(structure.REQUIRED) | candidates))
    git('rm', '--cached', '-f', 'node_modules/dependency.py')
    assert 'node_modules/dependency.py' not in structure.candidate_paths(tmp_path)
    (tmp_path / 'adhoc.py').write_text('')
    assert 'adhoc.py' in structure.candidate_paths(tmp_path)
