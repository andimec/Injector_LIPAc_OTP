import importlib.util
from pathlib import Path
import tempfile
import unittest

PATH = Path(__file__).resolve().parents[1] / 'scripts' / 'migrate_vacuum_readbacks.py'
spec = importlib.util.spec_from_file_location('migrate', PATH)
migrate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migrate)


def record(name, typ, dtyp='Injector Soft Channel', scan='I/O Intr', inp=None):
    contents = '\n'.join(['    field(DTYP, "'+dtyp+'")',
                           '    field(SCAN, "'+scan+'")',
                           '    field(PINI, "NO")',
                           *([f'    field(INP, "{inp}")'] if inp is not None else []),
                           '    field(DESC, "keep me")'])
    return f'record({typ}, "{name}")\n{{\n{contents}\n}}'


class MigrationTests(unittest.TestCase):
    def test_manifest(self):
        m = migrate.manifest()
        self.assertEqual(50, len(m))
        self.assertEqual(39, sum(x == 'bi' for x in m.values()))
        self.assertEqual(11, sum(x == 'ai' for x in m.values()))

    def test_transform_bi(self):
        name = 'LEBT:VAC01:TPSpeedStat'
        updated = migrate.transform_record(record(name, 'bi'), name, 'bi')
        self.assertIn('field(SCAN, "Passive")', updated)
        self.assertIn('field(DTYP, "Soft Channel")', updated)
        self.assertIn('field(INP, "0")', updated)
        self.assertIn('field(DESC, "keep me")', updated)
        self.assertEqual(updated, migrate.transform_record(updated, name, 'bi'))

    def test_transform_ai(self):
        name = 'LEBT:VAC01:VacSGVC'
        updated = migrate.transform_record(record(name,'ai','Soft Channel','2 second'),name,'ai')
        self.assertIn('field(INP, "0")', updated)
        self.assertIn('field(SCAN, "Passive")', updated)

    def test_reject_hardware(self):
        name = 'LEBT:VAC01:TPOnStat'
        with self.assertRaisesRegex(ValueError, 'DTYP'):
            migrate.transform_record(record(name, 'bi', 'S7plc'), name, 'bi')

    def test_reject_nonconstant_inp(self):
        name = 'LEBT:VAC01:TPOnStat'
        with self.assertRaisesRegex(ValueError, 'INP'):
            migrate.transform_record(record(name, 'bi', inp='@plcInjector/7'), name, 'bi')

    def test_reject_mismatch(self):
        name = 'LEBT:VAC01:TPOnStat'
        with self.assertRaisesRegex(ValueError,'type'):
            migrate.transform_record(record(name,'ai'),name,'bi')

    def test_collect_all_and_idempotence(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'plcInjector_Input.db'
            m = migrate.manifest()
            p.write_text('\n\n'.join(record(n,t) for n,t in m.items()))
            selected, updates = migrate.collect_changes([p],'all')
            self.assertEqual(50,len(selected))
            self.assertEqual(1,len(updates))
            p.write_text(updates[p][1])
            _, again = migrate.collect_changes([p],'all')
            self.assertEqual({},again)

    def test_no_missing_allowed(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'foo.db'
            p.write_text(record('LEBT:VAC01:TPOnStat','bi'))
            with self.assertRaisesRegex(ValueError, 'Missing'):
                migrate.collect_changes([p], 'bi')

    def test_duplicate_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)/'one.db'; q=Path(td)/'two.db'
            m=migrate.manifest()
            content='\n'.join(record(n,t) for n,t in m.items())
            p.write_text(content); q.write_text(record('LEBT:VAC01:TPOnStat','bi'))
            with self.assertRaisesRegex(ValueError,'Duplicate'):
                migrate.collect_changes([p,q], 'all')

if __name__ == '__main__': unittest.main()
