#!/usr/bin/env python3
"""Stage a conservative, simulator-only EPICS bi readback migration.

Dry-run by default. It changes only one explicitly named bi record after
verifying that it has the expected old mapping. Never use on a real IOC DB.
"""
from __future__ import annotations

import argparse
import difflib
import os
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

RECORD_RE = re.compile(
    r'(?m)^record\(bi,\s*"(?P<name>[^"]+)"\)\s*\{(?P<body>.*?)^\}',
    re.DOTALL | re.MULTILINE,
)
FIELD_RE = re.compile(r'^\s*field\(\s*(?P<key>[A-Z0-9]+)\s*,\s*"(?P<value>[^"]*)"\s*\)\s*$', re.MULTILINE)
EXPECTED_PV = 'LEBT:VAC01:TPOnStat'


def transform(text: str, pv: str = EXPECTED_PV) -> str:
    if pv != EXPECTED_PV:
        raise ValueError(f'Only the approved first test PV {EXPECTED_PV} is supported')
    hits = [match for match in RECORD_RE.finditer(text) if match.group('name') == pv]
    if len(hits) != 1:
        raise ValueError(f'Expected exactly one bi record {pv}, found {len(hits)}')
    hit = hits[0]
    body = hit.group('body')
    fields = {m.group('key'): m.group('value') for m in FIELD_RE.finditer(body)}
    if (fields.get('DTYP'), fields.get('SCAN'), fields.get('PINI')) != (
        'Injector Soft Channel', 'I/O Intr', 'NO'
    ):
        raise ValueError('Schema not the expected simulated S7 replacement; refusing to modify')
    if fields.get('INP') not in (None, '') or fields.get('FLNK') not in (None, ''):
        raise ValueError('INP/FLNK are present and nonempty; refusing to modify')
    if fields.get('UDF') not in (None, '1'):
        raise ValueError('Unexpected UDF override; refusing to modify')
    block = hit.group(0)
    block, n_d = re.subn(r'field\(DTYP,\s*"Injector Soft Channel"\)',
                        'field(DTYP, "Soft Channel")', block, count=1)
    block, n_s = re.subn(r'field\(SCAN,\s*"I/O Intr"\)',
                        'field(SCAN, "Passive")', block, count=1)
    if (n_d, n_s) != (1, 1):
        raise ValueError('Unexpected field syntax; refusing to modify')
    if 'field(INP,' not in block:
        block = block[:-1].rstrip() + '\n    field(INP, "0")\n}'
    else:
        block = re.sub(r'field\(INP,\s*""\)', 'field(INP, "0")', block, count=1)
    return text[:hit.start()] + block + text[hit.end():]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('db_file', type=Path)
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--confirm-offline-training-ioc', action='store_true')
    args = ap.parse_args(argv)
    path = args.db_file.expanduser().resolve(strict=True)
    if not path.is_file():
        ap.error('Input is not a regular file')
    old = path.read_text(encoding='utf-8')
    new = transform(old)
    print(''.join(difflib.unified_diff(old.splitlines(True), new.splitlines(True),
                                      fromfile=str(path), tofile=str(path)+' (proposed)')))
    if not args.apply:
        print('DRY RUN: no files modified')
        return 0
    if not args.confirm_offline_training_ioc:
        ap.error('--apply requires --confirm-offline-training-ioc')
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = path.with_name(f'{path.name}.bak_quality_{stamp}')
    shutil.copy2(path, backup)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix='.db_quality_')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(new)
        os.chmod(tmp, path.stat().st_mode & 0o777)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    print('PATCHED:', path)
    print('BACKUP:', backup)
    print('Only the isolated training IOC database was modified; restart is required')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
