"""Regression contract for the training IOC DB that was validated in the VM.

No EPICS/network dependency. Never run this as evidence of physical protection.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1] / "db"
RECORD = re.compile(r'(?ms)^record\((\w+),\s*"([^"]+)"\)\s*\{(.*?)^\}')
FIELD = re.compile(r'field\(\s*(\w+)\s*,\s*"([^"]*)"\s*\)')


def target_binary_names():
    names = set()
    for station in ("LEBT:VAC01", "LEBT:VAC02"):
        for name in ("PPOnStat", "TPOnStat", "TPSpeedStat", "TPDefStat",
                     "PGVCDefStat", "SGVCDefStat", "PGTPDefStat", "SGTPDefStat"):
            names.add(station + ":" + name)
        valves = ("PV", "SV", "AIV", "NIV") if station.endswith("VAC01") else ("PV", "SV", "AIV")
        for valve in valves:
            for name in ("OpenStat", "CloseStat"):
                names.add(station + ":" + valve + name)
    for name in ("OpenStat", "CloseStat"):
        names.add("LEBT:GV:" + name)
        for valve in ("SRC:SVL:H2", "SRC:SVL:D2"):
            names.add(valve + name)
    for mfc in ("SRC:MFCH", "SRC:MFCD", "LEBT:MFC"):
        names.add(mfc + ":StsVanne")
    assert len(names) == 39
    return names


def records():
    found = {}
    for path in ROOT.rglob("*.db"):
        text = path.read_text(encoding="utf-8")
        for match in RECORD.finditer(text):
            name = match.group(2)
            if name in found and (
                name in target_binary_names()
                or name.endswith(("PVOpenPrecond", "SVOpenPrecond"))
            ):
                raise AssertionError(f"Duplicate target record: {name} at {path}")
            found[name] = (match.group(1), dict(FIELD.findall(match.group(3))), path)
    return found


class TrainingVacuumDBContract(unittest.TestCase):
    def test_39_binary_model_outputs_are_passive_soft_channel(self):
        all_records = records()
        for name in sorted(target_binary_names()):
            with self.subTest(pv=name):
                self.assertIn(name, all_records)
                kind, fields, _ = all_records[name]
                self.assertEqual(kind, "bi")
                self.assertEqual(fields.get("DTYP"), "Soft Channel")
                self.assertEqual(fields.get("SCAN"), "Passive")
                self.assertEqual(fields.get("INP"), "0")

    def test_four_opi_preconditions_have_all_source_links(self):
        all_records = records()
        expected = {
            "LEBT:VAC01:PVOpenPrecond": (
                "(A&B)|C",
                {"A": "LEBT:VAC01:TPDefStat",
                 "B": "LEBT:VAC01:PPOnStat",
                 "C": "LEBT:VAC01:AIVOpenStat"}),
            "LEBT:VAC01:SVOpenPrecond": (
                "((((A&B)|D)|(E&F&G))&C)|H",
                {"A": "LEBT:VAC01:AIVOpenStat",
                 "B": "LEBT:VAC01:NIVOpenStat",
                 "C": "LEBT:VAC01:TPDefStat",
                 "D": "LEBT:VAC01:SVOpenStat",
                 "E": "LEBT:VAC01:PGTPDefStat",
                 "F": "LEBT:VAC01:SGTPDefStat",
                 "G": "LEBT:VAC01:PGVCDefStat",
                 "H": "LEBT:VAC:SVForcing"}),
            "LEBT:VAC02:PVOpenPrecond": (
                "(A&B)|C",
                {"A": "LEBT:VAC02:TPDefStat",
                 "B": "LEBT:VAC02:PPOnStat",
                 "C": "LEBT:VAC02:AIVOpenStat"}),
            "LEBT:VAC02:SVOpenPrecond": (
                "(A&B&C&D)|E",
                {"A": "LEBT:VAC02:PGTPDefStat",
                 "B": "LEBT:VAC02:SGTPDefStat",
                 "C": "LEBT:VAC02:PGVCDefStat",
                 "D": "LEBT:VAC02:TPSpeedStat",
                 "E": "LEBT:VAC:SVForcing"}),
        }
        for name, (formula, links) in expected.items():
            with self.subTest(pv=name):
                self.assertIn(name, all_records)
                kind, fields, _ = all_records[name]
                self.assertEqual(kind, "calc")
                self.assertEqual(fields.get("CALC"), formula)
                self.assertEqual(fields.get("SCAN"), "1 second")
                for letter, link in links.items():
                    self.assertEqual(fields.get("INP" + letter), link)

    def test_training_binary_fields_do_not_point_to_hardware(self):
        all_records = records()
        for name in target_binary_names():
            fields = all_records[name][1]
            self.assertNotIn("S7plc", fields.get("DTYP", ""))
            self.assertEqual(fields.get("INP"), "0")
            self.assertNotIn("OUT", fields)
            self.assertNotIn("DOL", fields)


if __name__ == "__main__":
    unittest.main()
