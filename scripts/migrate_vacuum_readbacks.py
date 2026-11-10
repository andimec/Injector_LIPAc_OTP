#!/usr/bin/env python3
"""Conservative migration of the 50 known Python-owned vacuum readbacks.

Only for the isolated simulation IOC, never for the original LIPAc databases.
No EPICS CA writes. Dry-run by default, atomic writes with per-file backups.
Use --scope bi, pilot-ai, ai, or all. Never alters commands, PPS, or calc records.
"""
from __future__ import annotations

import argparse
import difflib
import os
from pathlib import Path
import re
import shutil
import tempfile
from datetime import datetime

RECORD = re.compile(r'(?ms)^record\((?P<type>\w+),\s*"(?P<name>[^"]+)"\)\s*\{(?P<body>.*?)^\}', re.MULTILINE)
FIELDS = re.compile(r'^\s*field\(\s*(?P<name>[A-Z0-9]+)\s*,\s*"(?P<value>[^"]*)"\s*\)\s*$', re.MULTILINE)

PILOT_AI = 'LEBT:VAC01:VacSGVC'


def manifest():
    outputs = {}
    for region in ('LEBT:VAC01', 'LEBT:VAC02'):
        for s in ('PPOnStat', 'TPOnStat', 'TPSpeedStat', 'TPDefStat',
                  'PGVCDefStat', 'SGVCDefStat', 'PGTPDefStat', 'SGTPDefStat'):
            outputs[f'{region}:{s}'] = 'bi'
        for s in ('VacPGVC', 'VacSGVC', 'VacPGTP', 'VacSGTP'):
            outputs[f'{region}:{s}'] = 'ai'
        valves = ('PV', 'SV', 'AIV', 'NIV') if region.endswith('VAC01') else ('PV', 'SV', 'AIV')
        for v in valves:
            for stat in ('OpenStat', 'CloseStat'):
                outputs[f'{region}:{v}{stat}'] = 'bi'
    for s in ('OpenStat', 'CloseStat'):
        outputs['LEBT:GV:' + s] = 'bi'
        for gas in ('SRC:SVL:H2', 'SRC:SVL:D2'):
            outputs[gas + s] = 'bi'
    for controller, measure in (('SRC:MFCH', 'Deb2Mes'),
                                ('SRC:MFCD', 'Deb1Mes'),
                                ('LEBT:MFC', 'Deb1Mes')):
        outputs[controller + ':StsVanne'] = 'bi'
        outputs[controller + ':' + measure] = 'ai'
    assert len(outputs) == 50
    assert list(outputs.values()).count('bi') == 39
    assert list(outputs.values()).count('ai') == 11
    return outputs


def expected_names(scope):
    m = manifest()
    if scope == 'pilot-ai':
        return {PILOT_AI: 'ai'}
    if scope in ('bi', 'ai'):
        return {k: v for k, v in m.items() if v == scope}
    return m


def transform_record(record_text, name, typ):
    match = RECORD.fullmatch(record_text)
    if not match or match.group('name') != name or match.group('type') != typ:
        raise ValueError(f'{name}: unexpected record name/type')
    fields = {}
    for field in FIELDS.finditer(match.group('body')):
        key = field.group('name')
        if key in fields:
            raise ValueError(f'{name}: duplicate field {key}')
        fields[key] = field.group('value')
    if fields.get('DTYP') not in ('Injector Soft Channel', 'Soft Channel'):
        raise ValueError(f'{name}: unexpected DTYP {fields.get("DTYP")!r}')
    if fields.get('SCAN') not in ('I/O Intr', 'Passive', '1 second', '2 second'):
        raise ValueError(f'{name}: unexpected SCAN {fields.get("SCAN")!r}')
    if fields.get('PINI') not in (None, 'NO'):
        raise ValueError(f'{name}: PINI non-default; refusing')
    if fields.get('INP') not in (None, '', '0'):
        raise ValueError(f'{name}: nonconstant INP; refusing')
    if fields.get('FLNK') not in (None, '', '0'):
        raise ValueError(f'{name}: forward link present; refusing')
    if fields.get('UDF') not in (None, '1'):
        raise ValueError(f'{name}: unexpected UDF override; refusing')
    if any(key in fields for key in ('OUT', 'DOL')):
        raise ValueError(f'{name}: unexpected output/control link; refusing')
    result = record_text
    def sub_field(key, value):
        nonlocal result
        pattern = re.compile(r'(?m)^(\s*)field\(\s*' + key + r'\s*,\s*"[^"]*"\s*\)')
        updated, n = pattern.subn(lambda m: f'{m.group(1)}field({key}, "{value}")', result)
        if n != 1:
            raise ValueError(f'{name}: field {key} missing or repeated')
        result = updated
    sub_field('DTYP', 'Soft Channel')
    sub_field('SCAN', 'Passive')
    if fields.get('INP') == '0':
        pass
    elif 'INP' in fields:
        sub_field('INP', '0')
    else:
        result = result[:-1].rstrip() + '\n    field(INP, "0")\n}'
    return result


def collect_changes(files: list[Path], scope: str):
    selected = expected_names(scope)
    seen = {}
    data = {}
    for p in files:
        s = p.read_text(encoding='utf-8')
        data[p] = s
        for match in RECORD.finditer(s):
            n = match.group('name')
            if n not in selected:
                continue
            if n in seen:
                raise ValueError(f'Duplicate PV {n} in {seen[n][0]} and {p}')
            seen[n] = (p, match)
    missing = selected.keys() - seen.keys()
    if missing:
        raise ValueError(f'Missing {len(missing)} expected records: ' + ', '.join(sorted(missing)))
    updates = {}
    for p, original in data.items():
        matches = sorted((m for pp, m in seen.values() if pp == p), key=lambda m: m.start())
        output = original
        for m in reversed(matches):
            n = m.group('name')
            new_record = transform_record(m.group(0), n, selected[n])
            output = output[:m.start()] + new_record + output[m.end():]
        if output != original:
            updates[p] = (original, output)
    return selected, updates


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True,
                        help='Absolute path to .../IOCs/example_ioc_mounts/db')
    parser.add_argument('--scope', required=True, choices=('pilot-ai', 'bi', 'ai', 'all'))
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--confirm-offline-training-ioc', action='store_true')
    args = parser.parse_args(argv)
    root = args.root.expanduser().resolve(strict=True)
    if not root.is_dir() or root.name != 'db' or root.parent.name != 'example_ioc_mounts' or root.parent.parent.name != 'IOCs':
        parser.error('Refusing path outside .../IOCs/example_ioc_mounts/db')
    files = sorted(root.rglob('*.db'))
    if not files:
        parser.error('No .db files under root')
    selected, updates = collect_changes(files, args.scope)
    print(f'SCOPE={args.scope} expected={len(selected)} files_to_update={len(updates)}')
    for p, (original, new) in updates.items():
        print(''.join(difflib.unified_diff(original.splitlines(True), new.splitlines(True),
                                           fromfile=str(p), tofile=str(p)+' (proposed)')))
    if not updates:
        print('Already normalized: nothing to change')
        return 0
    if not args.apply:
        print('DRY RUN: no files modified')
        return 0
    if not args.confirm_offline_training_ioc:
        parser.error('Apply requires --confirm-offline-training-ioc')
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backups = []
    for p, (original, new) in updates.items():
        if p.read_text(encoding='utf-8') != original:
            raise RuntimeError(f'File changed since inspection: {p}')
        backup = p.with_name(f'{p.name}.bak_readbacks_{stamp}')
        shutil.copy2(p, backup)
        backups.append(backup)
        fd, tmp = tempfile.mkstemp(dir=p.parent, prefix='.readback_')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(new)
            os.chmod(tmp, p.stat().st_mode & 0o777)
            os.replace(tmp, p)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        print('PATCHED', p)
    for backup in backups:
        print('BACKUP', backup)
    print('IOC not restarted. Stop bridge and restart IOC only when ready.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
