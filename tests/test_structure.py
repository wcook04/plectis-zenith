"""Negative controls for source roles and Git's staged/ignored boundary."""
import importlib.util
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('structure_check', ROOT / 'scripts/check_structure.py')
structure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(structure)


def test_repository_layout():
    unused, failures = structure.check_repository(ROOT)
    assert not failures, failures


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


@pytest.fixture
def source_repo(tmp_path):
    """A small real index: tests can disagree with the working tree deliberately."""
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=tmp_path)
    git('init', '-q')
    for name in structure.REQUIRED | set(structure.ENTRY_DOCS) | {"research/__init__.py"}:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('Source anchor.\n')
    git('add', '--all')
    return tmp_path, git


def test_required_tracked_file_missing_from_disk_cannot_pass_working_view(source_repo):
    root, unused = source_repo
    (root / 'paper/README.md').unlink()
    assert 'paper/README.md' in structure.candidate_paths(root)
    unused, failures = structure.check_repository(root)
    assert any('working source anchor: paper/README.md' in failure for failure in failures)
    assert not structure.check_repository(root, index=True)[1]


@pytest.mark.parametrize('document,destination', [
    ('README.md', 'docs/removed.md'),
    ('docs/architecture.md', '../research/removed.py'),
    ('paper/README.md', './missing.pdf#page=1'),
    ('CONTRIBUTING.md', 'docs/removed.md?raw=1'),
    ('RESEARCH_NOTICE.md', 'docs/retired-data.md'),
])
def test_stale_local_entry_routes_fail(source_repo, document, destination):
    root, unused = source_repo
    (root / document).write_text(f'[Missing source]({destination})\n')
    unused, failures = structure.check_repository(root)
    assert any('Stale local route in ' + document in failure for failure in failures), failures


def test_local_reference_links_and_encoded_file_names_are_checked(source_repo):
    root, unused = source_repo
    (root / 'docs/space guide.md').write_text('Guide.\n')
    (root / 'README.md').write_text(
        '[Guide](docs/space%20guide.md#section)\n'
        '[Readable path](<docs/space guide.md> "Guide title")\n'
        '[Missing reference][missing]\n\n[missing]: docs/deleted.md\n')
    unused, failures = structure.check_repository(root)
    assert len(failures) == 1 and 'docs/deleted.md' in failures[0], failures


def test_external_links_fragments_and_code_examples_do_not_require_files(source_repo):
    root, unused = source_repo
    (root / 'README.md').write_text(
        '[Web](https://example.org/elsewhere.md) [Mail](mailto:reader@example.org)\n'
        '[Network](//example.org/path.md) [Here](#an-anchor)\n'
        '`[Example](not-a-file.md)`\n'
        '```md\n[Example](not-a-file.md)\n```\n'
        '[Real local anchor](docs/architecture.md#not-checked)\n'
        '[Source directory](research/)\n')
    assert not structure.check_repository(root)[1]


def test_index_uses_staged_bad_content_even_when_working_content_is_repaired(source_repo, monkeypatch):
    root, git = source_repo
    (root / 'README.md').write_text('[Stale](docs/removed.md)\n')
    git('add', 'README.md')
    (root / 'README.md').write_text('[Good](docs/architecture.md)\n')
    assert not structure.check_repository(root)[1]
    unused, failures = structure.check_repository(root, index=True)
    assert any('docs/removed.md' in failure for failure in failures), failures
    monkeypatch.setattr(structure, 'ROOT', root)
    assert structure.main([]) == 0
    assert structure.main(['--index']) == 1


def test_index_accepts_staged_addition_despite_conflicting_working_files(source_repo):
    root, git = source_repo
    (root / 'docs/new-guide.md').write_text('New guide.\n')
    (root / 'README.md').write_text('[New route](docs/new-guide.md)\n')
    git('add', 'README.md', 'docs/new-guide.md')
    (root / 'docs/new-guide.md').unlink()
    (root / 'README.md').write_text('[Bad working route](docs/missing.md)\n')
    assert 'docs/new-guide.md' in structure.candidate_paths(root, index=True)
    assert not structure.check_repository(root, index=True)[1]
    assert structure.check_repository(root)[1]


def test_index_rejects_staged_deleted_required_file_despite_surviving_working_file(source_repo):
    root, git = source_repo
    git('rm', '--cached', 'paper/README.md')
    assert (root / 'paper/README.md').is_file()
    assert 'paper/README.md' not in structure.candidate_paths(root, index=True)
    assert not structure.check_repository(root)[1]
    unused, failures = structure.check_repository(root, index=True)
    assert 'Missing source anchor: paper/README.md' in failures


def test_index_rejects_staged_deleted_link_target_even_when_untracked_copy_survives(source_repo):
    root, git = source_repo
    (root / 'docs/guide.md').write_text('Guide.\n')
    (root / 'README.md').write_text('[Guide](docs/guide.md)\n')
    git('add', 'README.md', 'docs/guide.md')
    git('rm', '--cached', 'docs/guide.md')
    assert not structure.check_repository(root)[1]
    unused, failures = structure.check_repository(root, index=True)
    assert any('docs/guide.md' in failure for failure in failures), failures


def test_index_does_not_admit_an_unstaged_route_target(source_repo):
    root, git = source_repo
    (root / 'docs/untracked.md').write_text('Not in the index.\n')
    (root / 'README.md').write_text('[Guide](docs/untracked.md)\n')
    git('add', 'README.md')
    assert not structure.check_repository(root)[1]
    unused, failures = structure.check_repository(root, index=True)
    assert any('docs/untracked.md' in failure for failure in failures), failures
