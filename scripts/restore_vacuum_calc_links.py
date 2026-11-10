#!/usr/bin/env python3
"""Restore missing INPA..INPH links from original topIFMIF_INJ calc records.

Dry-run by default; explicit offline training approval required for --apply.
No IOC restart, no CA writes, no changes to CALC/SCAN, no model edits.
"""
from __future__ import annotations

import argparse
import difflib
from datetime import datetime
from pathlib import Path
import re
import shutil
import sys

ORIGINAL = {
    'LEBT:VAC01:PVOpenPrecond': (
        '(A&B)|C',
        {'A': 'LEBT:VAC01:TPDefStat', 'B': 'LEBT:VAC01:PPOnStat',
         'C': 'LEBT:VAC01:AIVOpenStat'},
    ),
    'LEBT:VAC01:SVOpenPrecond': (
        '((((A&B)|D)|(E&F&G))&C)|H',
        {'A': 'LEBT:VAC01:AIVOpenStat', 'B': 'LEBT:VAC01:NIVOpenStat',
         'C': 'LEBT:VAC01:TPDefStat', 'D': 'LEBT:VAC01:SVOpenStat',
         'E': 'LEBT:VAC01:PGTPDefStat', 'F': 'LEBT:VAC01:SGTPDefStat',
         'G': 'LEBT:VAC01:PGVCDefStat', 'H': 'LEBT:VAC:SVForcing'},
    ),
    'LEBT:VAC02:PVOpenPrecond': (
        '(A&B)|C',
        {'A': 'LEBT:VAC02:TPDefStat', 'B': 'LEBT:VAC02:PPOnStat',
         'C': 'LEBT:VAC02:AIVOpenStat'},
    ),
    'LEBT:VAC02:SVOpenPrecond': (
        '(A&B&C&D)|E',
        {'A': 'LEBT:VAC02:PGTPDefStat', 'B': 'LEBT:VAC02:SGTPDefStat',
         'C': 'LEBT:VAC02:PGVCDefStat', 'D': 'LEBT:VAC02:TPSpeedStat',
         'E': 'LEBT:VAC:SVForcing'},
    ),
}

BLOCK_RE = re.compile(r'(?ms)^record\(calc,\s*"(?P<name>LEBT:VAC0[12]:(?:PV|SV)OpenPrecond)"\)\s*\{(?P<body>.*?)^\}', re.MULTILINE)
FIELD_RE = re.compile(r'field\(\s*(?P<field>INP[A-L])\s*,\s*"(?P<value>[^"]*)"\s*\)')


def repair(text: str) -> str:
    counts = {k: 0 for k in ORIGINAL}

    def replace(match: re.Match[str]) -> str:
        name, body = match.group('name'), match.group('body')
        if name not in ORIGINAL:
            return match.group()
        counts[name] += 1
        expected_calc, expected_links = ORIGINAL[name]
        calc = re.search(r'field\(\s*CALC\s*,\s*"([^"]+)"\s*\)', body)
        if not calc or calc.group(1) != expected_calc:
            raise ValueError(f'{name}: CALC differs from original, refusing modification')
        scan = re.search(r'field\(\s*SCAN\s*,\s*"([^"]+)"\s*\)', body)
        if not scan or scan.group(1) != '1 second':
            raise ValueError(f'{name}: SCAN differs from original, refusing modification')
        existing = list(FIELD_RE.finditer(body))
        if len({m.group('field') for m in existing}) != len(existing):
            raise ValueError(f'{name}: duplicate INP fields')
        links = {m.group('field'): m.group('value') for m in existing}
        expected_fields = {f'INP{key}': value for key, value in expected_links.items()}
        for k,v in links.items():
            if k not in expected_fields or v != expected_fields[k]:
                raise ValueError(f'{name}: existing {k}={v!r} differs from original; refusing')
        add = [f'    field({key}, "{value}")\n' for key, value in expected_fields.items() if key not in links]
        if not add:
            return match.group()
        return match.group()[:-1] + ''.join(add) + '}'

    updated = BLOCK_RE.sub(replace, text)
    bad = [name for name, count in counts.items() if count != 1]
    if bad:
        raise ValueError('Expected one calc record per name, missing/duplicate: '+', '.join(bad))
    return updated


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('db_file', type=Path, help='Actual mounted Soft IOC db file')
    p.add_argument('--apply', action='store_true', help='Write changes, keep timestamped backup')
    p.add_argument('--confirm-training-ioc', action='store_true', help='Confirm offline training IOC only')
    args = p.parse_args(argv)
    path = args.db_file.expanduser().resolve()
    if not path.is_file():
        p.error(f'DB file not found: {path}')
    if args.apply and (not args.confirm_training_ioc or 'example_ioc_mounts' not in path.parts):
        p.error('For --apply, require --confirm-training-ioc and path under example_ioc_mounts')
    before = path.read_text(encoding='utf-8')
    try:
        after = repair(before)
    except ValueError as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 2
    diff = ''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                  fromfile=str(path), tofile=str(path)+' (restored)'))
    if diff:
        print(diff, end='')
    else:
        print('OK: all expected original links are already present; no modification needed')
    if not args.apply:
        print('\nDRY RUN: no files modified. Use --apply --confirm-training-ioc after review.')
        return 0
    if not diff:
        return 0
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = path.with_name(f'{path.name}.bak_{stamp}')
    shutil.copy2(path, backup)
    try:
        path.write_text(after, encoding='utf-8')
    except Exception:
        shutil.copy2(backup, path)
        raise
    print(f'PATCHED: {path}\nBACKUP: {backup}\nNOTE: IOC database links change only after controlled IOC reload/restart.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
