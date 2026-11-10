import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('restore', Path(__file__).parents[1] / 'scripts' / 'restore_vacuum_calc_links.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def generated_sample():
    return ''.join('record(calc, "%s")\n{\n    field(DESC, "Test")\n    field(SCAN, "1 second")\n    field(CALC, "%s")\n}\n\n' % (name, expr) for name, (expr, _) in module.ORIGINAL.items())


class Tests(unittest.TestCase):
    def test_restoration_exact(self):
        before = generated_sample()
        after = module.repair(before)
        for name,(expr, links) in module.ORIGINAL.items():
            for k,value in links.items():
                self.assertIn('field(INP%s, "%s")' % (k,value), after)
        self.assertEqual(4, after.count('record(calc'))
    def test_idempotent(self):
        after = module.repair(generated_sample())
        self.assertEqual(after, module.repair(after))
    def test_wrong_formula_fails(self):
        before = generated_sample().replace('(A&B)|C', '(A&B)&C',1)
        with self.assertRaises(ValueError):
            module.repair(before)
    def test_conflicting_link_fails(self):
        before = generated_sample().replace('    field(CALC, "(A&B)|C")', '    field(CALC, "(A&B)|C")\n    field(INPA, "WRONG:PV")',1)
        with self.assertRaises(ValueError):
            module.repair(before)
    def test_partial_present_link(self):
        before=generated_sample().replace('    field(CALC, "(A&B)|C")', '    field(CALC, "(A&B)|C")\n    field(INPA, "LEBT:VAC01:TPDefStat")',1)
        after=module.repair(before)
        self.assertEqual(1, after.count('field(INPA, "LEBT:VAC01:TPDefStat")'))
    def test_missing_record_fails(self):
        with self.assertRaises(ValueError):
            module.repair(generated_sample().replace('LEBT:VAC02:SVOpenPrecond', 'MISSING:NAME'))
    def test_no_change_unrelated(self):
        sample=generated_sample()+'record(ai, "TEST:ABC")\n{\n field(SCAN,"Passive")\n}\n'
        self.assertTrue(module.repair(sample).endswith('record(ai, "TEST:ABC")\n{\n field(SCAN,"Passive")\n}\n'))

if __name__ == '__main__':
    unittest.main()
