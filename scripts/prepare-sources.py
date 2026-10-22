#!/usr/bin/env python3
"""Materialize or verify the pinned source trees inside macos/sources."""
import argparse
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def git(path, *args):
    return subprocess.check_output(['git', '-C', str(path), *args], text=True).strip()


def prepare(check_only):
    lock = json.loads((ROOT / 'configs/sources.lock.json').read_text())
    for name, spec in lock['sources'].items():
        path = (ROOT / 'sources' / name).resolve()
        if not path.is_relative_to(ROOT / 'sources'):
            raise ValueError('source path escapes workspace')
        if not path.exists():
            if check_only:
                raise ValueError(f'missing source: {name}')
            path.mkdir(parents=True)
            git(path, 'init')
            git(path, 'remote', 'add', 'origin', spec['url'])
            git(path, 'fetch', '--depth', '1', 'origin', spec['commit'])
            git(path, 'checkout', '--detach', spec['commit'])
        # Never reset an existing tree, including an unrelated or modified checkout.
        if git(path, 'remote', 'get-url', 'origin') != spec['url']:
            raise ValueError(f'{name}: remote differs from lock')
        if git(path, 'rev-parse', 'HEAD') != spec['commit']:
            raise ValueError(f'{name}: HEAD differs from lock; retain it and use a fresh checkout')
        if git(path, 'status', '--porcelain', '--untracked-files=normal'):
            raise ValueError(f'{name}: working tree is not clean')
        if not check_only:
            git(path, 'submodule', 'update', '--init', '--recursive', '--depth', '1', '--jobs', '4')
        actual = {}
        for line in git(path, 'submodule', 'status', '--recursive').splitlines():
            # git() strips the initial space of the first initialized entry only.
            if line[0] in '-+U':
                raise ValueError(f'{name}: uninitialized or mismatched submodule: {line}')
            sha, module, *_ = line.split()
            actual[module] = sha
        if actual != spec['submodules']:
            raise ValueError(f'{name}: submodules differ from lock')
        if git(path, 'status', '--porcelain', '--untracked-files=normal'):
            raise ValueError(f'{name}: modified submodule contents')
        print(f'{name}: {spec["commit"]}, {len(actual)} submodules verified')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='verify without fetching or modifying sources')
    prepare(parser.parse_args().check)
