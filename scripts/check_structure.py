#!/usr/bin/env python3
"""Check top-level placement, required anchors and entry-document file routes."""
from pathlib import Path, PurePosixPath
import argparse
import json
import posixpath
import re
import subprocess
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = {'.gitattributes', 'AGENTS.md', '.gitignore', 'README.md', 'RESEARCH_NOTICE.md', 'master_config.json', 'NOTICE', 'requirements-test.lock', 'CITATION.cff', 'LICENSE', 'program.md', 'SECURITY.md', 'pyproject.toml', 'CONTRIBUTING.md', 'Makefile', '.env.example'}
ROLES = {'codex', 'scripts', 'site', 'tests', 'zenith', 'examples', 'tools', 'docs', 'feedback', 'paper', 'research', '.github', '.agents', 'variants', 'system'}
ENTRY_DOCS = ('README.md', 'program.md', 'CONTRIBUTING.md', 'paper/README.md',
              'docs/architecture.md', 'docs/history/architecture.md', 'RESEARCH_NOTICE.md',
              'SECURITY.md', 'AGENTS.md', 'site/README.md')
REQUIRED = {'zenith/__main__.py', 'AGENTS.md', 'docs/architecture.md',
            'docs/history/architecture.md', 'paper/README.md', 'README.md',
            'master_config.json', 'pyproject.toml', 'scripts/check_structure.py'}
TEST_AREAS = ('tests/',)
REGULAR_MODES = {'100644', '100755'}


def candidate_paths(root, *, index=False):
    """Git supplies staged paths, optionally including visible new working files."""
    command = ['git', 'ls-files', '--cached']
    if not index:
        command.extend(('--others', '--exclude-standard'))
    command.append('-z')
    return set(subprocess.check_output(command, cwd=root).decode().split('\0')) - {''}


def check_paths(paths):
    """Pure placement checks retained for callers and negative fixtures."""
    paths = set(paths)
    failures = []
    for required in sorted(REQUIRED):
        if required not in paths:
            failures.append(f'Missing source anchor: {required}')
    for name in sorted(paths):
        path = PurePosixPath(name)
        if len(path.parts) == 1 and name not in ROOT_FILES:
            failures.append(f'Unassigned root file (choose a documented owner): {name}')
        elif len(path.parts) > 1 and path.parts[0] not in ROLES:
            failures.append(f'Unassigned source area (document its role): {name}')
        if path.parts[0] in {'docs', 'paper'} and path.suffix in {'.py', '.sh', '.js', '.mjs', '.ts', '.tsx'}:
            failures.append(f'Executable belongs with source or scripts, not narrative: {name}')
        if path.name.startswith('test_') and path.suffix == '.py' and not any(name.startswith(area) for area in TEST_AREAS):
            failures.append(f'Python regression belongs in a test owner: {name}')
        if set(path.parts) & {'.venv', '.venvs', 'node_modules', '__pycache__', '.pytest_cache'}:
            failures.append(f'Dependency/cache artifact in source candidates: {name}')
    return failures


def markdown_destinations(source):
    """Read inline/image and reference destinations without interpreting code."""
    lines = []
    fence = None
    for line in source.splitlines():
        marker = re.match(r'^ {0,3}(`{3,}|~{3,})', line)
        if marker:
            token = marker.group(1)
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            continue
        if fence is None:
            lines.append(line)
    text = '\n'.join(lines)
    text = re.sub(r'(`+)([^`]*?)\1', '', text)
    inline = re.compile(r'!?\[[^\]\n]*\]\(\s*(<[^>\n]+>|[^\s)]+)(?:\s+[^\n)]*)?\s*\)')
    reference = re.compile(r'^ {0,3}\[[^\]\n]+\]:\s*(<[^>\n]+>|\S+)', re.M)
    for pattern in (inline, reference):
        for match in pattern.finditer(text):
            yield match.group(1).removeprefix('<').removesuffix('>')


def local_target(document, destination):
    """Resolve a local destination; fragments and external URLs need no file."""
    if destination.startswith(('#', '//')) or re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:', destination):
        return None
    parsed = urlsplit(destination)
    if parsed.scheme or parsed.netloc:
        return None
    target = unquote(parsed.path)
    if not target:
        return None
    if target.startswith('/') or '\\' in target:
        raise ValueError('local route must be relative to its document')
    resolved = posixpath.normpath(str(PurePosixPath(document).parent / target))
    if resolved == '..' or resolved.startswith('../'):
        raise ValueError('local route escapes the repository')
    return resolved


def _index_entries(root):
    entries = {}
    conflicts = set()
    raw = subprocess.check_output(['git', 'ls-files', '--stage', '-z'], cwd=root).decode()
    for record in raw.split('\0'):
        if not record:
            continue
        metadata, name = record.split('\t', 1)
        mode, _, stage = metadata.split()
        if stage != '0':
            conflicts.add(name)
        else:
            entries[name] = mode
    return entries, conflicts


def _regular_working_file(root, name):
    path = root
    for part in PurePosixPath(name).parts:
        path = path / part
        if path.is_symlink():
            return False
    return path.is_file()


def check_repository(root, *, index=False):
    """Check the selected Git view, including actual required files and links."""
    root = Path(root)
    paths = candidate_paths(root, index=index)
    failures = check_paths(paths)
    modes, conflicts = _index_entries(root) if index else ({}, set())
    failures.extend(f'Unmerged index entry: {name}' for name in sorted(conflicts))

    def regular(name):
        return modes.get(name) in REGULAR_MODES if index else _regular_working_file(root, name)

    for name in sorted(REQUIRED & paths):
        if not regular(name):
            failures.append(f'Missing or non-regular {"staged" if index else "working"} source anchor: {name}')
    for document in ENTRY_DOCS:
        if document not in paths:
            failures.append(f'Missing entry document: {document}')
            continue
        if not regular(document):
            failures.append(f'Missing or non-regular entry document: {document}')
            continue
        source = (subprocess.check_output(['git', 'show', ':' + document], cwd=root).decode()
                  if index else (root / document).read_text())
        for destination in markdown_destinations(source):
            try:
                target = local_target(document, destination)
            except ValueError as error:
                failures.append(f'Invalid local route in {document}: {destination} ({error})')
                continue
            if target is None:
                continue
            # Directory links are valid when the selected Git view contains files there.
            directory = target == '.' or any(name.startswith(target.rstrip('/') + '/') for name in paths)
            exists = (target in paths and regular(target)) or directory
            if not index and directory:
                exists = (root / target).is_dir() and not (root / target).is_symlink()
            if not exists:
                failures.append(f'Stale local route in {document}: {destination} -> {target}')
    return paths, failures


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index', action='store_true', help='check staged paths and document contents only')
    args = parser.parse_args(argv)
    try:
        paths, failures = check_repository(ROOT, index=args.index)
    except (OSError, UnicodeError, subprocess.CalledProcessError) as error:
        print(json.dumps({'ok': False, 'error': str(error)}))
        return 1
    print(json.dumps({'ok': not failures, 'view': 'index' if args.index else 'working',
                      'candidate_files': len(paths), 'failures': failures}, indent=2))
    return int(bool(failures))


if __name__ == '__main__':
    raise SystemExit(main())
