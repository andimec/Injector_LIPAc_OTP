"""Offline tests, no EPICS server, hardware or caproto import required."""
import os
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from injector_otp.epics.vacuum_full_bridge import (
    FullVacuumBridge, EdgeGate, EDGE_INPUTS, LEVEL_INPUTS, EXTERNAL_INPUTS,
    EXCLUDED_IOC_CALCULATIONS, STATIONS, COMMAND_INPUTS, approve_publish,
    binary, expected_owner, isolated_target, should_publish, validate_schema,
)


class FakePV:
    connected = True

    def __init__(self, value=0):
        self.value = value
        self.writes = []

    def write(self, value, **kw):
        self.value = value
        self.writes.append(value)

    def read(self, **kw):
        return SimpleNamespace(data=[self.value])


class FakeState:
    def __init__(self):
        self.values = {}
        self.puts = []
        self.published = []
    def get(self, name):
        return self.values.get(name, 0)
    def put(self, name, value, **kw):
        self.values[name] = value
        self.puts.append((name, value))
    def publish(self, name, value, **kw):
        self.values[name] = value
        self.published.append((name, value))


class FakeEngine:
    def __init__(self):
        self.context = SimpleNamespace(outputs={}, time=0.0)
        self.steps = 0
    def step(self):
        self.steps += 1
        self.context.time += .1


class TestContract(unittest.TestCase):
    def test_all_pump_commands_for_two_stations(self):
        self.assertIn("LEBT:VAC02:TPOnCmd", EDGE_INPUTS)
        self.assertIn("LEBT:VAC01:SVOpenCmd", EDGE_INPUTS)
        self.assertIn("LEBT:GV:OpenCmd", EDGE_INPUTS)
        self.assertIn("SRC:SVL:D2CloseCmd", EDGE_INPUTS)
        self.assertNotIn("LEBT:VAC02:NIVOpenCmd", COMMAND_INPUTS)
        self.assertIn("LEBT:VAC01:NIVOpenCmd", COMMAND_INPUTS)
        self.assertIn("LEBT:MFC:Debit", LEVEL_INPUTS)
        self.assertIn("PPS:GV:OpenPermStat", EXTERNAL_INPUTS)
        self.assertEqual(len(COMMAND_INPUTS), len(set(COMMAND_INPUTS)))
        self.assertEqual(len(COMMAND_INPUTS), len(EDGE_INPUTS) + len(LEVEL_INPUTS))

    def test_strict_isolation(self):
        isolated_target("10.0.3.2")
        for host in ("127.0.0.1", "8.8.8.8", "10.0.4.3", "example.com", "10.0.3.255"):
            with self.assertRaises(ValueError, msg=host):
                isolated_target(host)

    def test_strict_write_ack(self):
        with patch.dict(os.environ, {}, clear=True):
            approve_publish("observe")
            approve_publish("validate")
            with self.assertRaises(PermissionError):
                approve_publish("publish")
        with patch.dict(os.environ, {
            "BRIDGE_ALLOW_WRITES":"YES", "BRIDGE_ISOLATED_ACK":"YES",
            "BRIDGE_SCOPE_ACK":"FULL_VACUUM"}, clear=True):
            approve_publish("publish")

    def test_pulse_gate_stale_high(self):
        gate = EdgeGate()
        gate.seed("a", 1)
        self.assertIsNone(gate.event("a", 1))
        self.assertEqual(gate.event("a", 0), 0)
        self.assertEqual(gate.event("a", 1), 1)
        self.assertIsNone(gate.event("a", 1))
        self.assertEqual(gate.event("a", 0), 0)
        with self.assertRaises(ValueError):
            gate.event("a", 8)

    def test_schema_rejects_hardware_or_calc(self):
        validate_schema("bi", "I/O Intr", "Injector Soft Channel", "")
        validate_schema("ai", "2 second", "Soft Channel", "")
        for arguments in (
            ("calc", "1 second", "", ""),
            ("bi", "I/O Intr", "asyn", ""),
            ("ai", ".01 second", "Soft Channel", ""),
            ("ai", "Passive", "Soft Channel", "OTHER:PV CP"),
        ):
            with self.assertRaises(RuntimeError, msg=str(arguments)):
                validate_schema(*arguments)

    def test_only_physical_model_outputs(self):
        self.assertTrue(expected_owner("LEBT:VAC01:VacPGVC", "vacuum_network"))
        self.assertTrue(expected_owner("LEBT:VAC02:TPOnStat", "vacuum_network"))
        self.assertTrue(expected_owner("LEBT:VAC02:SVOpenStat", "valve:LEBT:VAC02:SV"))
        self.assertTrue(expected_owner("LEBT:GV:OpenStat", "valve:LEBT:GV"))
        self.assertTrue(expected_owner("SRC:SVL:H2OpenStat", "valve:SRC:SVL:H2"))
        self.assertTrue(expected_owner("SRC:MFCH:Deb2Mes", "mfc:SRC:MFCH"))
        self.assertTrue(expected_owner("LEBT:MFC:Deb1Mes", "mfc:LEBT:MFC"))
        self.assertFalse(expected_owner("LEBT:VAC02:NIVOpenStat", "valve:LEBT:VAC02:NIV"))
        self.assertFalse(expected_owner("PPS:GV:OpenPermStat", "vacuum_network"))
        self.assertFalse(expected_owner("LEBT:VAC01:SVOpenPrecond", "plc_opi_formula"))
        self.assertFalse(expected_owner("LEBT:VAC01:LTVOpenStat", "vacuum_network"))
        self.assertEqual(len(EXCLUDED_IOC_CALCULATIONS), 4)

    def test_change_tolerance(self):
        self.assertTrue(should_publish(None, 0))
        self.assertFalse(should_publish(1, 1))
        self.assertTrue(should_publish(1, 0))
        self.assertFalse(should_publish(1e-6, 1.0001e-6))
        self.assertTrue(should_publish(1e-6, 2e-6))


class TestBridge(unittest.TestCase):
    def make_bridge(self, publish=True):
        b = FullVacuumBridge(mode="observe", host="10.0.3.2")
        if publish:
            b.mode = "publish"  # bypass env for isolated unit test only
        b.state = FakeState()
        b.engine = FakeEngine()
        names = {
            "LEBT:VAC01:PPOnStat": "vacuum_network",
            "LEBT:VAC02:VacSGVC": "vacuum_network",
            "SRC:MFCD:Deb1Mes": "mfc:SRC:MFCD",
        }
        b.output_owners.update(names)
        b.channels = {n: FakePV() for n in names}
        for n, owner in names.items():
            b.engine.context.outputs[n] = (
                1.0e-6 if ":Vac" in n else 0.0 if n.endswith("Mes") else 1,
                owner,
            )
        return b

    def test_observe_never_writes(self):
        b = self.make_bridge(publish=False)
        self.assertEqual(b.publish(), 0)
        self.assertTrue(all(not pv.writes for pv in b.channels.values()))

    def test_full_publication_different_types(self):
        b = self.make_bridge()
        self.assertEqual(b.publish(), 3)
        self.assertEqual(b.channels["LEBT:VAC01:PPOnStat"].writes, [1])
        self.assertEqual(b.channels["LEBT:VAC02:VacSGVC"].writes, [1e-6])
        self.assertEqual(b.publish(), 0)

    def test_rate_limit(self):
        b = self.make_bridge()
        b.max_writes_per_cycle = 1
        self.assertEqual(b.publish(), 1)
        self.assertEqual(sum(len(p.writes) for p in b.channels.values()), 1)
        self.assertEqual(b.publish(), 1)

    def test_competing_writer_fail_closed(self):
        b = self.make_bridge()
        b.publish()
        b.channels["LEBT:VAC01:PPOnStat"].value = 0
        b.engine.context.outputs["LEBT:VAC01:PPOnStat"] = (0, "vacuum_network")
        with self.assertRaisesRegex(RuntimeError, "COMPETING WRITER"):
            b.publish()

    def test_wrong_source_fails(self):
        b = self.make_bridge()
        b.engine.context.outputs["LEBT:VAC01:PPOnStat"] = (1, "bad_owner")
        with self.assertRaisesRegex(RuntimeError, "Changed model owner"):
            b.publish()

    def test_external_permit_updates_state(self):
        b = self.make_bridge()
        self.assertTrue(b._apply_external("PPS:GV:OpenPermStat", 1))
        self.assertEqual(b.state.published[-1], ("PPS:GV:OpenPermStat", 1))
        with self.assertRaises(ValueError):
            b._apply_external("PPS:GV:OpenPermStat", "bad")

    def test_mfc_level(self):
        b = self.make_bridge()
        self.assertTrue(b._apply_level("LEBT:MFC:Debit", 2.3))
        self.assertEqual(b.state.puts[-1], ("LEBT:MFC:Debit", 2.3))
        with self.assertRaises(ValueError):
            b._apply_level("LEBT:MFC:Debit", -1)

    def test_edge_event_is_immediate(self):
        b = self.make_bridge()
        pv = "LEBT:VAC01:PPOnCmd"
        b.gate.seed(pv, 0)
        b.inbox.put((pv, 1))
        b.inbox.put((pv, 0))
        b.apply_events()
        self.assertEqual(b.engine.steps, 2)
        self.assertEqual(b.state.puts[-2:], [(pv, 1), (pv, 0)])

    def test_strong_reference_callback(self):
        b = self.make_bridge()
        cb = b._callback("LEBT:VAC01:PPOnCmd")
        self.assertIn(cb, b._callbacks)
        cb(None, SimpleNamespace(data=[1]))
        self.assertEqual(b.inbox.get_nowait(), ("LEBT:VAC01:PPOnCmd", 1))


# The bridge's optional quality mode is deliberately isolated from any IOC
# for these unit tests. The real .PROC behaviour must be verified by probe.
from injector_otp.epics.vacuum_full_bridge import quality_action


class FakeContextForQuality:
    def __init__(self, channels):
        self.channels = channels
    def get_pvs(self, *names):
        return [self.channels[name] for name in names]


class FakeQualityField(FakePV):
    def wait_for_connection(self, **kwargs):
        pass


class FakeProc(FakeQualityField):
    def __init__(self, callback):
        super().__init__(0)
        self.callback = callback
    def write(self, value, **kwargs):
        super().write(value, **kwargs)
        self.callback()


class TestQualityGate(unittest.TestCase):
    def test_policy_skips_or_rejects_real_alarms(self):
        self.assertEqual(quality_action(udf=0, stat="UDF", sevr="INVALID", mode="off"), "skip")
        self.assertEqual(quality_action(udf=0, stat="UDF", sevr="INVALID", mode="process-stale-udf"), "process")
        self.assertEqual(quality_action(udf=0, stat="NO_ALARM", sevr="NO_ALARM", mode="verify"), "ok")
        self.assertEqual(quality_action(udf=0, stat="HIGH", sevr="MAJOR", mode="verify"), "ok")
        for udf,stat,sevr,mode in (
            (0,"UDF","INVALID","verify"),
            (1,"UDF","INVALID","process-stale-udf"),
            (0,"READ","INVALID","process-stale-udf"),
            (0,"UDF","NO_ALARM","process-stale-udf"),
            (0,"NO_ALARM","FANTASY","process-stale-udf"),
        ):
            with self.subTest(udf=udf,stat=stat,sevr=sevr,mode=mode):
                with self.assertRaises(RuntimeError):
                    quality_action(udf=udf, stat=stat, sevr=sevr, mode=mode)

    def make_quality_bridge(self, *, change_value=False, change_alarm=True):
        b = FullVacuumBridge(mode="observe", host="10.0.3.16")
        b.mode = "publish"
        b.quality_mode = "process-stale-udf"
        name = "LEBT:VAC01:TPOnStat"
        b.channels[name] = FakePV(1)
        udf = FakeQualityField(0)
        stat = FakeQualityField("UDF")
        sevr = FakeQualityField("INVALID")
        def apply_proc():
            if change_alarm:
                stat.value = "NO_ALARM"
                sevr.value = "NO_ALARM"
            if change_value:
                b.channels[name].value = 0
        proc = FakeProc(apply_proc)
        flnk = FakeQualityField("")
        q = {name+"."+k: v for k,v in {"UDF":udf,"STAT":stat,"SEVR":sevr,"PROC":proc,"FLNK":flnk}.items()}
        b.context = FakeContextForQuality(q)
        return b, proc, name

    def test_normalize_stale_udf_processes_only_one_record(self):
        # .PROC resets the stale alarm but keeps .VAL unchanged.
        with patch.dict(sys.modules, {"caproto":SimpleNamespace(ChannelType=SimpleNamespace(STRING="STRING"))}):
            b,proc,name = self.make_quality_bridge()
            b._normalize_alarm(name, 1)
            self.assertEqual(proc.writes, [1])
            self.assertEqual(b.channels[name].value, 1)
            # Calling again is idempotent once the alarm is normalized.
            b._normalize_alarm(name, 1)
            self.assertEqual(proc.writes, [1])

    def test_normalize_rejects_process_value_change(self):
        with patch.dict(sys.modules, {"caproto":SimpleNamespace(ChannelType=SimpleNamespace(STRING="STRING"))}):
            b,proc,name = self.make_quality_bridge(change_value=True)
            with self.assertRaisesRegex(RuntimeError, "Readback changed by .PROC"):
                b._normalize_alarm(name, 1)

    def test_normalize_rejects_unsuccessful_process(self):
        with patch.dict(sys.modules, {"caproto":SimpleNamespace(ChannelType=SimpleNamespace(STRING="STRING"))}):
            b,proc,name = self.make_quality_bridge(change_alarm=False)
            with self.assertRaisesRegex(RuntimeError, "Invalid output alarm"):
                b._normalize_alarm(name, 1)

    def test_mode_requires_explicit_ack(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(PermissionError, "BRIDGE_PROCESS_READBACKS"):
                FullVacuumBridge(mode="observe", host="10.0.3.16", quality_mode="process-stale-udf")


    def test_rejects_forward_link_before_processing(self):
        with patch.dict(sys.modules, {"caproto":SimpleNamespace(ChannelType=SimpleNamespace(STRING="STRING"))}):
            b,proc,name=self.make_quality_bridge()
            b.context.channels[name+".FLNK"].value = "OTHER:RECORD PP"
            with self.assertRaisesRegex(RuntimeError,"forward link"):
                b._normalize_alarm(name, 1)
            self.assertEqual(proc.writes, [])


if __name__ == "__main__":
    unittest.main()
