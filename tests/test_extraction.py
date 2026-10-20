"""Custody regressions for reviewed source refreshes and frozen evidence."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


@pytest.fixture
def custody_repo(tmp_path):
    """Exercise the real CLI against a small independent source checkout."""
    (tmp_path / 'scripts').mkdir()
    shutil.copyfile(ROOT / 'scripts/check_extraction.py', tmp_path / 'scripts/check_extraction.py')
    records = [('zenith/live.py', 'original source\n'),
               ('research/other.py', 'other maintained source\n'),
               ('examples/study/attempt.json', '{"result": "failed"}\n')]
    rows = []
    for name, value in records:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(value)
        rows.append({'path': name, 'source_path': 'upstream/' + name,
                     'source_sha256': digest(value), 'export_sha256': digest(value),
                     'disposition': 'exact_source', 'role': 'Existing provenance.'})
    (tmp_path / 'docs').mkdir()
    manifest = tmp_path / 'docs/extraction-manifest.json'
    manifest.write_text(json.dumps({
        'source_revision': 'original-revision', 'files': rows,
        'asset_audit': {'reviewed': True},
        'retired_files': [{'path': 'codex/retired.md', 'source_sha256': 'original-digest',
                           'retirement': {'replacement_path': 'codex/current.md'}}],
    }, indent=2) + '\n')

    def run(*args):
        return subprocess.run([sys.executable, str(tmp_path / 'scripts/check_extraction.py'), *args],
                              cwd=tmp_path, text=True, capture_output=True, check=False)

    return tmp_path, manifest, run


def test_read_only_and_explicit_noop_preserve_manifest_bytes(custody_repo):
    root, manifest, run = custody_repo
    before = manifest.read_bytes()
    assert run().returncode == 0
    assert run('--refresh', 'zenith/live.py').returncode == 0
    assert manifest.read_bytes() == before


def test_refresh_requires_named_reviewed_paths(custody_repo):
    unused, manifest, run = custody_repo
    before = manifest.read_bytes()
    assert run('--refresh').returncode == 2
    assert manifest.read_bytes() == before


def test_reviewed_change_preserves_original_custody_and_other_rows(custody_repo):
    root, manifest, run = custody_repo
    before = json.loads(manifest.read_text())
    (root / 'zenith/live.py').write_text('reviewed source\n')
    result = run('--refresh', 'zenith/live.py')
    assert result.returncode == 0, result.stdout
    after = json.loads(manifest.read_text())
    assert after['source_revision'] == before['source_revision']
    assert after['asset_audit'] == before['asset_audit']
    assert after['retired_files'] == before['retired_files']
    assert after['files'][1:] == before['files'][1:]
    original, updated = before['files'][0], after['files'][0]
    for key in ('path', 'source_path', 'source_sha256', 'role'):
        assert updated[key] == original[key]
    assert updated['export_sha256'] == digest('reviewed source\n')
    assert updated['disposition'] == 'standalone_adaptation'
    assert run().returncode == 0


@pytest.mark.parametrize('other,remove', [
    ('examples/study/attempt.json', False),
    ('examples/study/attempt.json', True),
    ('research/other.py', False),
    ('research/other.py', True),
])
def test_unreviewed_change_or_missing_member_aborts_refresh_without_write(custody_repo, other, remove):
    root, manifest, run = custody_repo
    before = manifest.read_bytes()
    (root / 'zenith/live.py').write_text('reviewed source\n')
    if remove:
        (root / other).unlink()
    else:
        (root / other).write_text('unreviewed replacement\n')
    result = run('--refresh', 'zenith/live.py')
    assert result.returncode == 1
    assert json.loads(result.stdout)['changed_or_missing'] == [other]
    assert manifest.read_bytes() == before


def test_frozen_evidence_cannot_be_explicitly_refreshed(custody_repo):
    root, manifest, run = custody_repo
    before = manifest.read_bytes()
    (root / 'examples/study/attempt.json').write_text('{"result": "passed"}\n')
    result = run('--refresh', 'examples/study/attempt.json')
    assert result.returncode == 1
    assert 'Frozen evidence' in result.stdout
    assert manifest.read_bytes() == before


def test_new_source_is_added_only_when_explicitly_selected(custody_repo):
    root, manifest, run = custody_repo
    before = json.loads(manifest.read_text())
    (root / 'research/new.py').write_text('new reviewed source\n')
    (root / 'research/unreviewed.py').write_text('unreviewed source\n')
    assert run('--refresh', 'zenith/live.py').returncode == 0
    assert json.loads(manifest.read_text()) == before
    assert run('--refresh', 'research/new.py').returncode == 0
    after = json.loads(manifest.read_text())
    assert after['files'][:-1] == before['files']
    assert after['files'][-1]['path'] == 'research/new.py'
    assert 'source_sha256' not in after['files'][-1]


@pytest.mark.parametrize('target', ['../outside.py', '/tmp/outside.py', 'zenith/../zenith/live.py',
                                    './zenith/live.py', 'zenith//live.py', 'zenith', 'README.md'])
def test_invalid_or_unowned_refresh_targets_leave_manifest_untouched(custody_repo, target):
    root, manifest, run = custody_repo
    (root / 'README.md').write_text('Not a recorded extraction member.\n')
    before = manifest.read_bytes()
    assert run('--refresh', 'zenith/live.py', target).returncode == 1
    assert manifest.read_bytes() == before


def test_symlink_and_duplicate_members_cannot_hide_custody_changes(custody_repo):
    root, manifest, run = custody_repo
    before = manifest.read_bytes()
    (root / 'zenith/link.py').symlink_to(root / 'zenith/live.py')
    assert run('--refresh', 'zenith/link.py').returncode == 1
    assert manifest.read_bytes() == before
    value = json.loads(manifest.read_text())
    value['files'].append(dict(value['files'][0]))
    manifest.write_text(json.dumps(value))
    duplicated = manifest.read_bytes()
    result = run('--refresh', 'zenith/live.py')
    assert result.returncode == 1
    assert 'Duplicate manifest member' in result.stdout
    assert manifest.read_bytes() == duplicated


@pytest.mark.parametrize('restored_kind', ['file', 'directory', 'broken_symlink'])
def test_retired_path_must_stay_absent_and_aborts_source_refresh(custody_repo, restored_kind):
    root, manifest, run = custody_repo
    before = manifest.read_bytes()
    retired = root / 'codex/retired.md'
    retired.parent.mkdir()
    if restored_kind == 'file':
        retired.write_text('Accidentally restored duplicate.\n')
    elif restored_kind == 'directory':
        retired.mkdir()
    else:
        retired.symlink_to(root / 'missing.md')
    assert run().returncode == 1
    (root / 'zenith/live.py').write_text('reviewed source\n')
    assert run('--refresh', 'zenith/live.py').returncode == 1
    assert manifest.read_bytes() == before


def test_active_and_retired_manifest_members_must_be_disjoint(custody_repo):
    root, manifest, run = custody_repo
    value = json.loads(manifest.read_text())
    value['retired_files'].append(dict(value['files'][0]))
    manifest.write_text(json.dumps(value))
    before = manifest.read_bytes()
    result = run()
    assert result.returncode == 1
    assert 'both active and retired' in result.stdout
    assert run('--refresh', 'research/other.py').returncode == 1
    assert manifest.read_bytes() == before


def test_explicit_refresh_cannot_resurrect_retired_source(custody_repo):
    root, manifest, run = custody_repo
    before = manifest.read_bytes()
    result = run('--refresh', 'codex/retired.md')
    assert result.returncode == 1
    assert 'Retired source cannot be refreshed' in result.stdout
    (root / 'codex').mkdir()
    (root / 'codex/retired.md').write_text('Restored duplicate.\n')
    result = run('--refresh', 'codex/retired.md')
    assert result.returncode == 1
    assert 'Retired source cannot be refreshed' in result.stdout
    assert manifest.read_bytes() == before


@pytest.mark.parametrize('unsafe', ['../outside.md', '/tmp/outside.md', './codex/old.md',
                                   'codex/../old.md', None])
def test_malformed_retirement_path_cannot_be_accepted_by_refresh(custody_repo, unsafe):
    root, manifest, run = custody_repo
    value = json.loads(manifest.read_text())
    value['retired_files'][0]['path'] = unsafe
    manifest.write_text(json.dumps(value))
    before = manifest.read_bytes()
    (root / 'zenith/live.py').write_text('reviewed source\n')
    assert run().returncode == 1
    assert run('--refresh', 'zenith/live.py').returncode == 1
    assert manifest.read_bytes() == before
