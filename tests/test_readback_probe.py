"""Safety tests for the standalone quality probe; no EPICS tools invoked."""
from pathlib import Path
import importlib.util
import unittest

path=Path(__file__).resolve().parents[1]/'scripts'/'probe_readback_quality.py'
spec=importlib.util.spec_from_file_location('readback_probe',path)
probe=importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class ReadbackProbeSafety(unittest.TestCase):
    def test_only_allowlisted_training_readbacks(self):
        probe.check_safe_target('LEBT:VAC01:TPOnStat','10.0.3.16')
        for bad_pv in ('LEBT:VAC01:TPOnCmd','PPS:GV:OpenPermStat',
                       'LEBT:VAC01:PVOpenPrecond','LEBT:VAC01:TPOnStat.PROC'):
            with self.assertRaises(ValueError):
                probe.check_safe_target(bad_pv,'10.0.3.16')
        for bad_ip in ('192.168.1.1','10.0.4.3','10.0.3.0','10.0.3.255','host.example'):
            with self.assertRaises(ValueError):
                probe.check_safe_target('LEBT:VAC01:TPOnStat',bad_ip)

    def test_rejects_hardware_forward_links_and_source_links(self):
        metadata=dict(RTYP='bi',DTYP='Injector Soft Channel',SCAN='I/O Intr',INP='',FLNK='')
        probe.validate_record(metadata)
        for field,new in [('RTYP','calc'),('DTYP','asyn'),('SCAN','0.1 second'),
                          ('INP','ANOTHER:PV'),('FLNK','OTHER:PROC')]:
            invalid=dict(metadata, **{field:new})
            with self.assertRaises(RuntimeError):
                probe.validate_record(invalid)

    def test_only_processes_stale_udf_alarm(self):
        probe.check_alarm_before_processing(dict(VAL='1',UDF='0',STAT='UDF',SEVR='INVALID'))
        for invalid in (dict(VAL='1',UDF='1',STAT='UDF',SEVR='INVALID'),
                        dict(VAL='0',UDF='0',STAT='HIGH',SEVR='MAJOR'),
                        dict(VAL='1500',UDF='0',STAT='UDF',SEVR='INVALID')):
            with self.assertRaises(RuntimeError):
                probe.check_alarm_before_processing(invalid)


if __name__ == '__main__':
    unittest.main()
