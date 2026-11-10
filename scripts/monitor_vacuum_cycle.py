#!/usr/bin/env python3
"""READ-ONLY PV monitor for the PP -> PV -> TP -> speed -> SV cycle.

Never sends commands. Operators use Phoebus for the isolated training IOC.
VAC01 SVOpenPrecond is a different formula from VAC02. In particular,
VAC01 does NOT require TPSpeedStat=1 for its displayed SV permission.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import ipaddress
import os
import subprocess
import sys
import time

SUBNET=ipaddress.ip_network('10.0.3.0/24')
SUFFIXES = ("PPOnStat", "PVOpenStat", "TPOnStat", "TPSpeedStat", "TPDefStat",
            "SVOpenPrecond", "SVOpenStat")


def query(name: str, *, numeric: bool = True) -> str:
    command=['caget','-w','3','-t']
    if numeric:
        command.append('-n')
    command.append(name)
    p=subprocess.run(command,capture_output=True,text=True,timeout=7)
    if p.returncode:
        raise RuntimeError(f"Unable to read {name}: {p.stderr.strip()}")
    return p.stdout.strip()


def bit(raw: str) -> int:
    try:
        value=float(raw)
    except ValueError as e:
        raise RuntimeError(f"Not numeric boolean: {raw!r}") from e
    if value not in (0.0,1.0):
        raise RuntimeError(f"Not 0/1: {raw!r}")
    return int(value)


def sample(prefix: str) -> dict[str,int]:
    return {suffix: bit(query(prefix+":"+suffix)) for suffix in SUFFIXES}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ioc',required=True)
    p.add_argument('--station',choices=('VAC01','VAC02'),default='VAC01')
    p.add_argument('--minutes',type=float,default=13)
    p.add_argument('--interval',type=float,default=2.0)
    p.add_argument('--once',action='store_true')
    args=p.parse_args()
    ip=ipaddress.ip_address(args.ioc)
    if ip not in SUBNET or ip in (SUBNET.network_address,SUBNET.broadcast_address):
        p.error('Refusing address outside isolated training network 10.0.3.0/24')
    if not (0<args.minutes<=30) or args.interval < 1:
        p.error('Choose a duration <=30 minutes and polling >=1 s')
    os.environ['EPICS_CA_ADDR_LIST']=args.ioc
    os.environ['EPICS_CA_AUTO_ADDR_LIST']='NO'
    os.environ.pop('EPICS_CA_NAME_SERVERS',None)
    prefix='LEBT:'+args.station
    # Check server before trusting channel values.
    probe=subprocess.run(['cainfo',prefix+':TPOnStat'],capture_output=True,text=True,timeout=8)
    if probe.returncode or f'Host:            {args.ioc}:5064' not in probe.stdout:
        # Accept varying whitespace but not another server address.
        import re
        if not re.search(r'(?m)^\s*Host:\s*'+re.escape(args.ioc)+r':5064\s*$',probe.stdout):
            raise RuntimeError('TPOnStat is not connected to requested isolated IOC: '+probe.stdout)
    print('READ ONLY:', prefix, 'at', args.ioc, flush=True)
    print('NOTE: VAC01 SVOpenPrecond does NOT use TPSpeedStat. VAC02 does.',flush=True)
    prev=None
    started=time.monotonic()
    tp_started=None
    last_quality=0.0
    while True:
        now=time.monotonic()
        state=sample(prefix)
        if prev is None or state!=prev:
            changed={k: v for k,v in state.items() if prev is None or prev[k]!=v}
            print(datetime.now().isoformat(timespec='seconds'),changed,flush=True)
        if prev is not None and prev['TPOnStat']==0 and state['TPOnStat']==1:
            tp_started=now
            if not (state['PPOnStat'] and state['PVOpenStat'] and state['TPDefStat']):
                print('WARNING: TP started without expected training-model conditions',flush=True)
        if prev is not None and prev['TPSpeedStat']==0 and state['TPSpeedStat']==1:
            if tp_started is None:
                print('NOTICE: speed nominal detected but TP start predates monitor',flush=True)
            else:
                print(f'TP acceleration measured: {now-tp_started:.1f}s (model target 600s)',flush=True)
        if prev is not None and prev['SVOpenStat']==0 and state['SVOpenStat']==1 and not state['SVOpenPrecond']:
            print('FAIL: SV opened while OPI precondition=0. ValveDevice not interlocked.',flush=True)
        # Quality readings are required, not just numeric values.
        if now-last_quality>=10 or prev is None:
            for suffix in SUFFIXES:
                pv=prefix+':'+suffix
                udf=bit(query(pv+'.UDF'))
                status=query(pv+'.STAT', numeric=False).upper()
                severity=query(pv+'.SEVR', numeric=False).upper()
                if udf or severity=='INVALID' or status=='UDF':
                    print('FAIL: invalid alarm quality', pv,
                          f'UDF={udf} STAT={status} SEVR={severity}',flush=True)
                    return 2
            last_quality=now
        prev=state
        if args.once or now-started>=args.minutes*60:
            print('Cycle monitor finished (read-only).')
            return 0
        time.sleep(max(0.0,args.interval-(time.monotonic()-now)))


if __name__=='__main__':
    try:
        sys.exit(main())
    except (ValueError,RuntimeError,subprocess.TimeoutExpired) as e:
        print('STOP:',e,file=sys.stderr)
        sys.exit(2)
