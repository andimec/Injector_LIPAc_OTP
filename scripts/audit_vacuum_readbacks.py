#!/usr/bin/env python3
"""Read-only audit of the model-owned EPICS readback values and quality."""
from __future__ import annotations
import argparse
import os
import subprocess
from migrate_vacuum_readbacks import expected_names


def read(pv: str, field: str) -> str:
    cmd = ['caget', '-w', '2', '-t', f'{pv}.{field}']
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
    if proc.returncode:
        raise RuntimeError(f'{pv}.{field}: {proc.stderr.strip()}')
    return proc.stdout.strip()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--scope', choices=('pilot-ai','bi','ai','all'), default='all')
    args=p.parse_args()
    if os.environ.get('EPICS_CA_AUTO_ADDR_LIST') != 'NO' or not os.environ.get('EPICS_CA_ADDR_LIST'):
        p.error('Set EPICS_CA_AUTO_ADDR_LIST=NO and EPICS_CA_ADDR_LIST to the isolated training IOC')
    failure=0
    for pv in sorted(expected_names(args.scope)):
        try:
            val=read(pv,'VAL')
            udf=read(pv,'UDF')
            stat=read(pv,'STAT')
            sevr=read(pv,'SEVR')
            bad=udf != '0' or stat.upper() == 'UDF' or sevr.upper() == 'INVALID'
            if bad: failure+=1
            print(f'{"BAD" if bad else "OK "} {pv:38} VAL={val:>12} UDF={udf:>1} STAT={stat:>12} SEVR={sevr}')
        except Exception as exc:
            failure+=1
            print(f'ERR {pv}: {exc}')
    print(f'UNHEALTHY={failure} of {len(expected_names(args.scope))}')
    return 1 if failure else 0


if __name__ == '__main__':
    raise SystemExit(main())
