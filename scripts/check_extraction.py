#!/usr/bin/env python3
"""Check recorded exports; refresh only explicitly reviewed maintained source."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
MAINTAINED_AREAS = {'zenith', 'system', 'tools', 'feedback', 'research',
                    'variants', 'codex', 'tests'}
SOURCE_SUFFIXES = {'.py', '.json', '.md', '.jsonl'}


def member_path(root, label):
    """Resolve a canonical relative member without following symlink components."""
    path = PurePosixPath(label)
    if (not label or path.is_absolute() or '..' in path.parts or
            str(path) != label or '\\' in label):
        raise ValueError(f'Invalid relative source path: {label}')
    target = root
    for part in path.parts:
        target = target / part
        if target.is_symlink():
            raise ValueError(f'Symlink is not a regular source member: {label}')
    return target


def regular_file(root, label):
    target = member_path(root, label)
    if not target.is_file():
        raise ValueError(f'Missing or non-regular source member: {label}')
    return target


def recorded_rows(manifest, key='files'):
    rows = {}
    for row in manifest[key]:
        if row['path'] in rows:
            raise ValueError(f'Duplicate manifest member: {row["path"]}')
        rows[row['path']] = row
    return rows


def check_manifest(root, manifest):
    failures = []
    rows = recorded_rows(manifest)
    retired = recorded_rows(manifest, 'retired_files') if 'retired_files' in manifest else {}
    for label in retired:
        target = member_path(root, label)
        if label in rows:
            raise ValueError(f'Manifest member is both active and retired: {label}')
        if target.exists():
            raise ValueError(f'Retired source path still exists: {label}')
    for label, row in rows.items():
        try:
            checksum = hashlib.sha256(regular_file(root, label).read_bytes()).hexdigest()
            if checksum != row['export_sha256']:
                failures.append(label)
        except (OSError, ValueError):
            failures.append(label)
    return failures


def refresh_manifest(root, manifest, labels):
    """Build a candidate without scanning, dropping rows or erasing source custody."""
    result = dict(manifest, files=[dict(row) for row in manifest['files']])
    rows = recorded_rows(result)
    retired = recorded_rows(manifest, 'retired_files') if 'retired_files' in manifest else {}
    for label in dict.fromkeys(labels):
        path = PurePosixPath(label)
        if label in retired:
            raise ValueError(f'Retired source cannot be refreshed: {label}')
        target = regular_file(root, label)
        if path.parts[0] == 'examples':
            raise ValueError(f'Frozen evidence cannot be refreshed: {label}')
        if label not in rows and (path.parts[0] not in MAINTAINED_AREAS or
                                  path.suffix not in SOURCE_SUFFIXES or
                                  '__pycache__' in path.parts):
            raise ValueError(f'New member needs a maintained source owner: {label}')
        checksum = hashlib.sha256(target.read_bytes()).hexdigest()
        row = rows.get(label)
        if row is None:
            row = {'path': label}
            result['files'].append(row)
            rows[label] = row
        if row.get('export_sha256') != checksum:
            row['export_sha256'] = checksum
            row['disposition'] = 'standalone_adaptation'
            row.setdefault('adaptation', 'Maintained source updated after review; '
                           'original custody fields are retained where available.')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh', nargs='+', metavar='PATH',
                        help='refresh these reviewed source paths only; preserve '
                             'all other rows and reject frozen or missing evidence')
    args = parser.parse_args(argv)
    try:
        path = ROOT / 'docs/extraction-manifest.json'
        manifest = json.loads(path.read_text())
        candidate = refresh_manifest(ROOT, manifest, args.refresh) if args.refresh else manifest
        failures = check_manifest(ROOT, candidate)
        # Validate the entire candidate before writing: an unrelated changed or
        # missing experiment must never be hidden by a source refresh.
        if args.refresh and not failures and candidate != manifest:
            path.write_text(json.dumps(candidate, indent=2) + '\n')
        print(json.dumps({'ok': not failures, 'checked_files': len(candidate['files']),
                          'checked_retired_files': len(candidate.get('retired_files', [])),
                          'changed_or_missing': failures}))
        return int(bool(failures))
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({'ok': False, 'error': str(error)}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
