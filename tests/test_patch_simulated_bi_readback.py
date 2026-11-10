import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from patch_simulated_bi_readback import transform, main

BASE = '''record(bi, "LEBT:VAC01:TPOnStat")\n{\n    field(DTYP, "Injector Soft Channel")\n    field(DESC, "Status TP")\n    field(SCAN, "I/O Intr")\n    field(PINI, "NO")\n    field(ZNAM, "Off")\n    field(ONAM, "On")\n}\n\nrecord(bi, "LEBT:VAC01:PPOnStat")\n{\n    field(DTYP, "Injector Soft Channel")\n    field(SCAN, "I/O Intr")\n    field(PINI, "NO")\n}\n'''

class PatchTests(unittest.TestCase):
    def test_transform_one_record(self):
        new = transform(BASE)
        self.assertIn('field(DTYP, "Soft Channel")', new)
        self.assertIn('field(SCAN, "Passive")', new)
        self.assertIn('field(INP, "0")', new)
        self.assertEqual(new.count('field(DTYP, "Injector Soft Channel")'), 1)
        self.assertIn('field(ZNAM, "Off")', new)
        self.assertIn('field(PINI, "NO")', new)
    def test_preserves_unrelated_record(self):
        new = transform(BASE)
        self.assertEqual(new.split('record(bi, "LEBT:VAC01:PPOnStat")')[1],
                         BASE.split('record(bi, "LEBT:VAC01:PPOnStat")')[1])
    def test_reject_pv(self):
        with self.assertRaises(ValueError):transform(BASE, 'LEBT:VAC02:TPOnStat')
    def test_reject_wrong_device(self):
        with self.assertRaises(ValueError):transform(BASE.replace('Injector Soft Channel', 'S7plc', 1))
    def test_reject_external_inp(self):
        with self.assertRaises(ValueError):transform(BASE.replace('field(PINI, "NO")', 'field(PINI, "NO")\n    field(INP, "@plcInjector/7 T=BYTE B=4")', 1))
    def test_dry_run_does_not_write(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'test.db';p.write_text(BASE)
            self.assertEqual(main([str(p)]),0)
            self.assertEqual(p.read_text(),BASE)
    def test_apply_creates_backup(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'test.db';p.write_text(BASE)
            self.assertEqual(main([str(p),'--apply','--confirm-offline-training-ioc']),0)
            self.assertNotEqual(p.read_text(),BASE)
            self.assertEqual(len(list(Path(d).glob('test.db.bak_quality_*'))),1)
    def test_requires_ack(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'test.db';p.write_text(BASE)
            with self.assertRaises(SystemExit):main([str(p),'--apply'])
            self.assertEqual(p.read_text(),BASE)

if __name__=='__main__':unittest.main()
