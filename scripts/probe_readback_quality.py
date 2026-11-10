#!/usr/bin/env python3
"""Safely diagnose one model-owned EPICS readback in the isolated training IOC.

Without --process: strictly READ ONLY. With --process: ONLY PV.PROC gets a
put. No DB modifications, no VAL puts, no STAT/SEVR/UDF manipulation.
"""
from __future__ import annotations

import argparse
import ipaddress
import os
import re
import subprocess
import sys

SUBNET = ipaddress.ip_network('10.0.3.0/24')
PV_RE = re.compile(r'^LEBT:VAC0[12]:(PPOnStat|TPOnStat|TPSpeedStat|TPDefStat|PV(Open|Close)Stat|SV(Open|Close)Stat|AIV(Open|Close)Stat|Vac(PGVC|SGVC|PGTP|SGTP))$')


def run(cmd: list[str], timeout: float = 12) -> str:
    res = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=timeout)
    if res.returncode:
        raise RuntimeError(f"Command failed ({res.returncode}): {' '.join(cmd)}\n{res.stderr}")
    return res.stdout.strip()


def ca_field(name: str, *, number: bool = False) -> str:
    cmd = ['caget', '-w', '4', '-t']
    if number:
        cmd.insert(1, '-n')
    return run(cmd + [name])


def snapshot(pv: str) -> dict[str, str]:
    return {field: ca_field(f'{pv}.{field}', number=(field in {'VAL', 'UDF'}))
            for field in ('VAL', 'UDF', 'STAT', 'SEVR')}


def check_safe_target(pv: str, ioc: str) -> None:
    if not PV_RE.fullmatch(pv):
        raise ValueError(f"PV is not in the training readback allowlist: {pv}")
    try:
        ip = ipaddress.ip_address(ioc)
    except ValueError as exc:
        raise ValueError('IOC must be a literal IP address') from exc
    if ip not in SUBNET or ip in (SUBNET.network_address, SUBNET.broadcast_address):
        raise ValueError(f'IOC must be in training subnet {SUBNET}, not {ioc}')


def validate_record(metadata: dict[str,str]) -> None:
    if metadata['RTYP'] != 'bi':
        raise RuntimeError('Initial trial is limited to bi readbacks')
    if metadata['DTYP'] not in ('Soft Channel','Injector Soft Channel'):
        raise RuntimeError('Not a supported training soft input')
    if metadata['SCAN'] not in ('I/O Intr','Passive'):
        raise RuntimeError('Unexpected SCAN for trial')
    if metadata['FLNK'].strip() not in ('', '0'):
        raise RuntimeError('Record has a forward link; .PROC may cascade; aborting')
    if metadata['INP'].strip() not in ('', '0'):
        raise RuntimeError('Record reads from an input link; .PROC may overwrite value')


def check_alarm_before_processing(state: dict[str,str]) -> None:
    if state['VAL'] not in ('0', '1'):
        raise RuntimeError('Unexpected boolean readback VAL')
    if state['UDF'] != '0':
        raise RuntimeError('UDF must be 0 before .PROC trial; investigate source')
    if (state['STAT'].upper(), state['SEVR'].upper()) != ('UDF', 'INVALID'):
        raise RuntimeError('This probe only targets stale UDF INVALID alarms; no write performed')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ioc', required=True, help='actual IP of isolated training IOC')
    parser.add_argument('--pv', default='LEBT:VAC01:TPOnStat')
    parser.add_argument('--process', action='store_true', help='request ONE .PROC write after confirmation')
    parser.add_argument('--confirm-training-ioc', action='store_true')
    args = parser.parse_args()
    check_safe_target(args.pv, args.ioc)
    if args.process and not args.confirm_training_ioc:
        parser.error('--process requires --confirm-training-ioc')
    os.environ['EPICS_CA_AUTO_ADDR_LIST'] = 'NO'
    os.environ['EPICS_CA_ADDR_LIST'] = args.ioc
    os.environ.pop('EPICS_CA_NAME_SERVERS', None)
    info = run(['cainfo', args.pv])
    if not re.search(r'(?im)^\s*Host:\s*' + re.escape(args.ioc) + r':5064\s*$', info):
        raise RuntimeError('PV is NOT served by the expected isolated IOC: ' + info)
    fields = ('RTYP','DTYP','SCAN','INP','FLNK')
    metadata = {f: ca_field(args.pv + '.' + f) for f in fields}
    print('SCHEMA', metadata)
    validate_record(metadata)
    before = snapshot(args.pv)
    print('BEFORE', before)
    if not args.process:
        print('READ ONLY: no record processing requested. Use --process only if BEFORE has stale UDF INVALID.')
        return 0
    check_alarm_before_processing(before)
    print('PROCESSING', args.pv + '.PROC=1 (no other EPICS field will be written)', flush=True)
    print(run(['caput', '-w', '5', '-n', args.pv + '.PROC', '1']))
    after = snapshot(args.pv)
    print('AFTER', after)
    if after['VAL'] != before['VAL']:
        raise RuntimeError('FAILED: .PROC changed the readback VAL; do not enable auto-normalization')
    if after['UDF'] != '0' or after['SEVR'].upper() == 'INVALID' or after['STAT'].upper() == 'UDF':
        raise RuntimeError('FAILED: .PROC did not remove stale invalid alarm; inspect device support')
    print('PASS: VAL preserved and alarm quality normalized. Auto-processing may be trialed in bridge.')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        print('STOP:', exc, file=sys.stderr)
        sys.exit(2)
