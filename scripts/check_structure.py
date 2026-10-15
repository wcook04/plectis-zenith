#!/usr/bin/env python3
"""Enforce documented source roles using Git candidates, without walking build trees."""
from pathlib import Path, PurePosixPath
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = {'.gitattributes', 'AGENTS.md', '.gitignore', 'README.md', 'RESEARCH_NOTICE.md', 'master_config.json', 'NOTICE', 'requirements-test.lock', 'CITATION.cff', 'LICENSE', 'program.md', 'SECURITY.md', 'pyproject.toml', 'CONTRIBUTING.md', 'Makefile', '.env.example'}
ROLES = {'codex', 'benchmarks', 'scripts', 'site', 'tests', 'zenith', 'examples', 'tools', 'docs', 'feedback', 'paper', 'research', '.github', '.agents', 'variants', 'system'}
REQUIRED = {'zenith/__main__.py', 'AGENTS.md', 'docs/architecture.md', 'README.md', 'master_config.json', 'pyproject.toml', 'scripts/check_structure.py'}
TEST_AREAS = ('tests/',)


def candidate_paths(root):
    """Include staged and visible new files; Git handles ignored build directories."""
    return set(subprocess.check_output(
        ['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'],
        cwd=root).decode().split('\0')) - {''}


def check_paths(paths):
    paths = set(paths)
    failures = []
    for required in REQUIRED:
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


def main():
    paths = candidate_paths(ROOT)
    failures = check_paths(paths)
    print(json.dumps({'ok': not failures, 'candidate_files': len(paths), 'failures': failures}, indent=2))
    return int(bool(failures))


if __name__ == '__main__':
    raise SystemExit(main())
