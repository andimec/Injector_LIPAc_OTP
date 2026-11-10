"""Isolated LIPAc VAC01/VAC02/GV/MFC CA bridge.

Read-only by default; a monitored, allowlisted and bounded full-vacuum
publisher is opt-in. Neither this module nor the physics models actuate real
LIPAc equipment. Only connect to the training IOC at 10.0.3.16 / internal.

Keep the older ca_bridge.py pilot untouched for rollback.
"""
from __future__ import annotations

import argparse
from collections import OrderedDict
from dataclasses import dataclass, field
import ipaddress
import logging
import math
import os
import queue
import signal
import time
from typing import Any

LOG = logging.getLogger("vacuum_full_ca_bridge")
SUBNET = ipaddress.ip_network("10.0.3.0/24")
STATIONS = ("LEBT:VAC01", "LEBT:VAC02")
GAS_VALVES = ("SRC:SVL:H2", "SRC:SVL:D2")
MFCS = ("SRC:MFCH", "SRC:MFCD", "LEBT:MFC")


def _command_names() -> tuple[str, ...]:
    names = []
    for station in STATIONS:
        for item in ("PPOnCmd", "PPOffCmd", "TPOnCmd", "TPOffCmd"):
            names.append(station + ":" + item)
        for valve in ("PV", "SV", "AIV") + (("NIV",) if station.endswith("01") else ()):
            names += [f"{station}:{valve}OpenCmd", f"{station}:{valve}CloseCmd"]
    names += ["LEBT:GV:OpenCmd", "LEBT:GV:CloseCmd"]
    for prefix in GAS_VALVES:
        names += [prefix + "OpenCmd", prefix + "CloseCmd"]
    for prefix in MFCS:
        names += [prefix + ":OpenCmd", prefix + ":Debit"]
    return tuple(names)


COMMAND_INPUTS = _command_names()  # Eight pump actions, valve actions, MFC commands.
# MFC OpenCmd is a level, not an edge-triggered pulse.
LEVEL_INPUTS = tuple(n for prefix in MFCS for n in (prefix + ":OpenCmd", prefix + ":Debit"))
EDGE_INPUTS = tuple(n for n in COMMAND_INPUTS if n not in LEVEL_INPUTS)
EXTERNAL_INPUTS = (
    "PPS:GV:OpenPermStat", "PPS:SVL:H2PermStat", "PPS:SVL:D2PermStat",
    "LEBT:VAC01:LTVOpenStat", "LEBT:VAC02:LTVOpenStat",
    "LEBT:VAC:SVForcing",
)
# IOC's calc records own the OPI formulas. Python calculates these internally
# but DOES NOT publish the same PVs, because that would create two writers.
EXCLUDED_IOC_CALCULATIONS = tuple(
    f"{station}:{kind}OpenPrecond" for station in STATIONS
    for kind in ("PV", "SV")
)


def scalar(response: Any) -> object:
    data = response.data
    if len(data) != 1:
        raise ValueError("This bridge accepts scalar CA PVs only")
    value = data[0]
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8")
    return value


def binary(value: object) -> int:
    if isinstance(value, (bool, int, float)) and value in (0, 1):
        return int(value)
    raise ValueError(f"Boolean PV must have a native 0/1 value, got {value!r}")


def numeric(value: object) -> float:
    if isinstance(value, bool):
        raise ValueError("Analog PV cannot be boolean")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Analog PV cannot be NaN or infinite")
    return result


def isolated_target(host: str) -> None:
    try:
        ip = ipaddress.ip_address(host)
    except ValueError as exc:
        raise ValueError("IOC target must be a literal IP address") from exc
    if ip not in SUBNET or ip in (SUBNET.network_address, SUBNET.broadcast_address):
        raise ValueError(f"Refusing IOC outside training subnet {SUBNET}: {host}")


def approve_publish(mode: str) -> None:
    if mode == "publish" and (
        os.environ.get("BRIDGE_ALLOW_WRITES") != "YES"
        or os.environ.get("BRIDGE_ISOLATED_ACK") != "YES"
        or os.environ.get("BRIDGE_SCOPE_ACK") != "FULL_VACUUM"
    ):
        raise PermissionError(
            "Publish requires BRIDGE_ALLOW_WRITES=YES, "
            "BRIDGE_ISOLATED_ACK=YES and BRIDGE_SCOPE_ACK=FULL_VACUUM"
        )


@dataclass
class EdgeGate:
    """Arm a pulse only after observing low; never replay a stale high."""
    previous: dict[str, int] = field(default_factory=dict)
    armed: set[str] = field(default_factory=set)

    def seed(self, name: str, value: object) -> None:
        v = binary(value)
        self.previous[name] = v
        if v == 0:
            self.armed.add(name)
        else:
            self.armed.discard(name)

    def event(self, name: str, value: object) -> int | None:
        v = binary(value)
        previous = self.previous.get(name)
        self.previous[name] = v
        if v == 0:
            self.armed.add(name)
            return 0 if previous != 0 else None
        if v == 1 and previous == 0 and name in self.armed:
            return 1
        return None


def expected_owner(name: str, owner: str) -> bool:
    """Only active physical model outputs, not IOC calc or safety PVs."""
    if name in EXCLUDED_IOC_CALCULATIONS or name.startswith("PPS:"):
        return False
    if owner == "vacuum_network":
        pump_suffixes = ("PPOnStat", "TPOnStat", "TPSpeedStat", "TPDefStat")
        valid = set(pump_suffixes) | {
            "Vac" + gauge for gauge in ("PGVC", "SGVC", "PGTP", "SGTP")
        } | {
            gauge + "DefStat" for gauge in ("PGVC", "SGVC", "PGTP", "SGTP")
        }
        return any(name == station + ":" + suffix
                   for station in STATIONS for suffix in valid)
    if owner.startswith("valve:"):
        prefix = owner[6:]
        if prefix == "LEBT:GV":
            return name in ("LEBT:GV:OpenStat", "LEBT:GV:CloseStat")
        if prefix in GAS_VALVES:
            return name in (prefix + "OpenStat", prefix + "CloseStat",
                            prefix + ":OpenStat", prefix + ":CloseStat")
        for station in STATIONS:
            active = ("PV", "SV", "AIV") + (("NIV",) if station.endswith("01") else ())
            if prefix in tuple(f"{station}:{valve}" for valve in active):
                return name in (prefix + "OpenStat", prefix + "CloseStat",
                                prefix + ":OpenStat", prefix + ":CloseStat")
        return False
    if owner.startswith("mfc:"):
        prefix = owner[4:]
        return prefix in MFCS and name in (
            prefix + ":StsVanne",
            prefix + (":Deb2Mes" if prefix == "SRC:MFCH" else ":Deb1Mes"),
        )
    return False


def values_agree(a: object, b: object) -> bool:
    if isinstance(a, float) or isinstance(b, float):
        return math.isclose(float(a), float(b), rel_tol=1e-6, abs_tol=1e-12)
    return a == b


def should_publish(previous: object | None, desired: object) -> bool:
    if previous is None:
        return True
    if isinstance(desired, float):
        # Bounded gauge/MFC publications; no artificial 10 Hz IOC traffic.
        return not math.isclose(float(previous), desired, rel_tol=1e-3, abs_tol=1e-10)
    return previous != desired


def quality_action(*, udf: int, stat: str, sevr: str, mode: str) -> str:
    """Decide if a soft readback is valid without suppressing genuine alarms.

    Only stale UDF/INVALID after a successful .VAL write is eligible for
    explicit .PROC processing, and only in the opted-in mode.
    """
    if mode not in ("off", "verify", "process-stale-udf"):
        raise ValueError(f"Unknown quality mode: {mode}")
    if mode == "off":
        return "skip"
    if udf != 0:
        raise RuntimeError(f"Undefined model output: UDF={udf}")
    status, severity = stat.strip().upper(), sevr.strip().upper()
    if severity == "INVALID":
        if status == "UDF" and mode == "process-stale-udf":
            return "process"
        raise RuntimeError(f"Invalid output alarm STAT={stat!r} SEVR={sevr!r}")
    if severity not in ("NO_ALARM", "MINOR", "MAJOR"):
        raise RuntimeError(f"Unknown output alarm severity {sevr!r}")
    if status == "UDF":
        raise RuntimeError("Stale UDF status without INVALID severity")
    return "ok"


def validate_schema(rtyp: str, scan: str, dtyp: str, inp: str = "") -> None:
    if rtyp not in ("bi", "ai"):
        raise RuntimeError(f"Only bi/ai readbacks can be Python-owned, got {rtyp}")
    if dtyp not in ("Soft Channel", "Injector Soft Channel"):
        raise RuntimeError(f"Refusing hardware/non-soft device support {dtyp}")
    if scan not in ("Passive", "I/O Intr", "1 second", "2 second"):
        raise RuntimeError(f"Unexpected output SCAN {scan}")
    if inp.strip() and not inp.strip().replace(".", "", 1).replace("-", "", 1).isdigit():
        # A nonconstant input link or device INP is a strong indication of
        # another value source. Reject rather than writing into it.
        raise RuntimeError(f"Non-constant input link: {inp}")


class FullVacuumBridge:
    def __init__(self, *, mode: str, host: str, report_every: int = 50,
                 max_writes_per_cycle: int = 12, quality_mode: str = "off"):
        if quality_mode not in ("off", "verify", "process-stale-udf"):
            raise ValueError(f"Invalid quality_mode: {quality_mode}")
        if quality_mode == "process-stale-udf" and (
            mode != "publish" or os.environ.get("BRIDGE_PROCESS_READBACKS") != "YES"
        ):
            raise PermissionError(
                "Readback processing requires publish mode and "
                "BRIDGE_PROCESS_READBACKS=YES; test one .PROC first"
            )
        isolated_target(host)
        approve_publish(mode)
        self.mode = mode
        self.host = host
        self.report_every = report_every
        self.max_writes_per_cycle = max_writes_per_cycle
        self.quality_mode = quality_mode
        self.quality_channels: dict[str, dict[str, Any]] = {}
        self.stop = False
        self.context = None
        self.channels: dict[str, Any] = {}
        self.subscriptions: list[Any] = []
        self._callbacks: list[Any] = []
        self.inbox: queue.SimpleQueue[tuple[str, object]] = queue.SimpleQueue()
        self.gate = EdgeGate()
        self.output_owners: OrderedDict[str, str] = OrderedDict()
        self.last_published: dict[str, object] = {}
        self.last_validation_time = 0.0
        self._validate_cursor = 0
        self.engine = None
        self.state = None

    def initialize_model(self) -> None:
        from injector_otp.app import build_application
        self.engine, _, _ = build_application()
        self.state = self.engine.pv_state
        if self.state is None:
            raise RuntimeError("SimulationPVState is required")
        missing = [name for name in COMMAND_INPUTS if not self.state.is_operator_writable(name)]
        if missing:
            raise RuntimeError("Missing operator-input permissions: " + ", ".join(missing))
        for name in EXTERNAL_INPUTS:
            if name not in self.state.names():
                raise RuntimeError(f"Unregistered external dependency {name}")
        self.engine.step()
        for name, (_, owner) in self.engine.context.outputs.items():
            if expected_owner(name, owner):
                if name not in self.state.names() or self.state.is_operator_writable(name):
                    raise RuntimeError(f"Bad output ownership: {name}")
                self.output_owners[name] = owner
        # Prevent a successful but accidentally empty publishing configuration.
        if len(self.output_owners) < 35:
            raise RuntimeError(
                f"Only {len(self.output_owners)} physical vacuum outputs found; "
                "inspect DeviceCatalog and model emitters"
            )
        LOG.info("Vacuum manifest: %s inputs, %s external dependencies, %s model outputs; "
                 "excluded IOC calc PVs=%s", len(COMMAND_INPUTS), len(EXTERNAL_INPUTS),
                 len(self.output_owners), len(EXCLUDED_IOC_CALCULATIONS))
        for name, owner in self.output_owners.items():
            LOG.debug("MODEL OUTPUT %s owner=%s", name, owner)

    def _metadata(self, pv_name: str) -> tuple[str, str, str, str]:
        from caproto import ChannelType
        names = tuple(pv_name + "." + field for field in ("RTYP", "SCAN", "DTYP", "INP"))
        pvs = self.context.get_pvs(*names)
        fields = []
        for pv in pvs:
            pv.wait_for_connection(timeout=8)
            fields.append(str(scalar(pv.read(data_type=ChannelType.STRING, timeout=5))).strip())
        return tuple(fields)

    def connect(self) -> None:
        self.initialize_model()
        os.environ["EPICS_CA_AUTO_ADDR_LIST"] = "NO"
        os.environ["EPICS_CA_ADDR_LIST"] = self.host
        os.environ.pop("EPICS_CA_NAME_SERVERS", None)
        from caproto.threading.client import Context
        self.context = Context()
        names = tuple(dict.fromkeys(COMMAND_INPUTS + EXTERNAL_INPUTS + tuple(self.output_owners)))
        pvs = self.context.get_pvs(*names)
        self.channels = dict(zip(names, pvs, strict=True))
        for name, pv in self.channels.items():
            pv.wait_for_connection(timeout=12)
            LOG.debug("CA connected %s", name)
        for name in COMMAND_INPUTS + EXTERNAL_INPUTS:
            initial = scalar(self.channels[name].read(data_type="native", timeout=5))
            if name in EDGE_INPUTS:
                self.gate.seed(name, initial)
                # A high command at boot does NOT turn on a device.
                self.state.put(name, 0, source="ca-boot-ignored-command")
                if binary(initial) == 1:
                    LOG.warning("Stale high command ignored until low: %s", name)
            elif name in LEVEL_INPUTS:
                self._apply_level(name, initial, seed=True)
            else:
                self._apply_external(name, initial)
            subscription = self.channels[name].subscribe(data_type="native")
            callback = self._callback(name)
            subscription.add_callback(callback)
            self.subscriptions.append(subscription)
        LOG.info("CA READY: %d command/level inputs; %d external inputs; "
                 "%d physical outputs; mode=%s", len(COMMAND_INPUTS), len(EXTERNAL_INPUTS),
                 len(self.output_owners), self.mode)
        if self.mode in ("publish", "validate"):
            self.validate_outputs()
        if self.mode == "publish":
            LOG.warning("FULL VACUUM PUBLISH ENABLED. Training IOC only. "
                        "Output writes bounded to %s/cycle", self.max_writes_per_cycle)

    def _callback(self, name: str):
        def on_monitor(_sub, response):
            try:
                val = scalar(response)
                self.inbox.put((name, val))
                LOG.debug("CA MONITOR %s=%r", name, val)
            except Exception:
                LOG.exception("CA monitor decoding error: %s", name)
        self._callbacks.append(on_monitor)  # caproto holds weak refs.
        return on_monitor

    def _apply_level(self, name: str, value: object, *, seed: bool = False) -> bool:
        if name.endswith(":OpenCmd"):
            new = binary(value)
        else:
            new = numeric(value)
            if new < 0:
                raise ValueError(f"Negative gas flow setpoint {name}={new}")
        previous = self.state.get(name)
        self.state.put(name, new, source="ca-level-init" if seed else "ca-operator-level")
        return not values_agree(previous, new)

    def _apply_external(self, name: str, value: object) -> bool:
        new = binary(value)
        old = self.state.get(name)
        self.state.publish(name, new, source="ca-external")
        return not values_agree(old, new)

    def apply_events(self, *, limit: int = 500) -> None:
        processed = 0
        while processed < limit:
            try:
                name, value = self.inbox.get_nowait()
            except queue.Empty:
                return
            processed += 1
            try:
                if name in EDGE_INPUTS:
                    event = self.gate.event(name, value)
                    if event is None:
                        continue
                    self.state.put(name, event, source="ca-operator-pulse")
                    # Step immediately so a short pulse is not lost.
                    self.engine.step()
                    LOG.info("CA EVENT %s=%d state_time=%.3fs", name, event,
                             self.engine.context.time)
                elif name in LEVEL_INPUTS:
                    changed = self._apply_level(name, value)
                    if changed:
                        LOG.info("CA LEVEL %s=%s", name, value)
                elif name in EXTERNAL_INPUTS:
                    changed = self._apply_external(name, value)
                    if changed:
                        LOG.info("CA EXTERNAL %s=%s", name, value)
            except (ValueError, PermissionError, TypeError) as exc:
                # Invalid CA payload is not a valid zero / permit. Stop the
                # service instead of silently keeping obsolete conditions.
                raise RuntimeError(f"Invalid CA input {name}={value!r}: {exc}") from exc
        LOG.warning("CA monitor backlog reached %d events", limit)

    def validate_outputs(self) -> None:
        for name in self.output_owners:
            metadata = self._metadata(name)
            validate_schema(*metadata)
            LOG.info("SCHEMA OK %s rtyp=%s scan=%s dtyp=%s inp=%s", name, *metadata)
        LOG.info("PUBLISH PREFLIGHT OK: %s model-owned readbacks", len(self.output_owners))

    def _verify_competitor(self) -> None:
        """Round-robin check for accidental writes by another client."""
        if not self.last_published:
            return
        names = tuple(self.last_published)
        for _ in range(min(4, len(names))):
            name = names[self._validate_cursor % len(names)]
            self._validate_cursor += 1
            pv = self.channels[name]
            actual = self._normalize_output(name, scalar(pv.read(data_type="native", timeout=5)))
            if not values_agree(actual, self.last_published[name]):
                raise RuntimeError(f"COMPETING WRITER: {name} actual={actual!r} "
                                   f"last_written={self.last_published[name]!r}")

    def _normalize_output(self, name: str, raw: object) -> object:
        if ":Vac" in name or name.endswith("Mes"):
            return numeric(raw)
        return binary(raw)

    def _quality_channels_for(self, name: str) -> dict[str, Any]:
        if name not in self.quality_channels:
            fields = ("UDF", "STAT", "SEVR", "PROC", "FLNK")
            pvs = self.context.get_pvs(*(name + "." + f for f in fields))
            for pv in pvs:
                pv.wait_for_connection(timeout=8)
            self.quality_channels[name] = dict(zip(fields, pvs, strict=True))
        return self.quality_channels[name]

    def _quality_snapshot(self, name: str) -> tuple[int, str, str]:
        from caproto import ChannelType
        channels = self._quality_channels_for(name)
        udf = binary(scalar(channels["UDF"].read(data_type="native", timeout=5)))
        stat = str(scalar(channels["STAT"].read(
            data_type=ChannelType.STRING, timeout=5))).strip()
        sevr = str(scalar(channels["SEVR"].read(
            data_type=ChannelType.STRING, timeout=5))).strip()
        return udf, stat, sevr

    def _normalize_alarm(self, name: str, desired: object) -> None:
        """Process only stale UDF alarm on model-owned readback; fail closed.

        Record .PROC is NOT a value override. It may invoke device support
        and forward links, so this mode must be independently proven using
        the standalone one-record probe before enablement.
        """
        if self.quality_mode == "off":
            return
        snapshot = self._quality_snapshot(name)
        action = quality_action(udf=snapshot[0], stat=snapshot[1],
                                sevr=snapshot[2], mode=self.quality_mode)
        if action == "process":
            from caproto import ChannelType
            flnk = str(scalar(self._quality_channels_for(name)["FLNK"].read(
                data_type=ChannelType.STRING, timeout=5))).strip()
            if flnk not in ("", "0"):
                raise RuntimeError(
                    f"Refusing .PROC for {name}: record has forward link {flnk!r}"
                )
            LOG.warning("CA PROCESS readback %s.PROC=1 to resolve stale UDF alarm", name)
            self._quality_channels_for(name)["PROC"].write(1, wait=True, timeout=5)
            # A .PROC action can cause an input support read. Never assume
            # it preserved the previously published model value.
            after = self._normalize_output(
                name, scalar(self.channels[name].read(data_type="native", timeout=5)))
            if not values_agree(after, desired):
                raise RuntimeError(
                    f"Readback changed by .PROC {name}: expected={desired!r} got={after!r}"
                )
            snapshot = self._quality_snapshot(name)
            action = quality_action(udf=snapshot[0], stat=snapshot[1],
                                    sevr=snapshot[2], mode="verify")
            LOG.info("CA QUALITY RESTORED %s UDF=%s STAT=%s SEVR=%s",
                     name, *snapshot)
        if action != "ok":
            raise RuntimeError(f"Quality normalization failed for {name}: {snapshot}")
        if snapshot[2].strip().upper() in ("MINOR", "MAJOR"):
            LOG.warning("CA READBACK ALARM %s UDF=%s STAT=%s SEVR=%s",
                        name, *snapshot)

    def publish(self) -> int:
        if self.mode != "publish":
            return 0
        sent = 0
        outputs = self.engine.context.outputs
        for name, owner in self.output_owners.items():
            if name not in outputs:
                raise RuntimeError(f"Model stopped emitting required PV {name}")
            raw, actual_owner = outputs[name]
            if actual_owner != owner:
                raise RuntimeError(f"Changed model owner for {name}: {actual_owner}")
            desired = self._normalize_output(name, raw)
            previous = self.last_published.get(name)
            if not should_publish(previous, desired):
                continue
            pv = self.channels[name]
            if not pv.connected:
                raise ConnectionError(f"CA output disconnected {name}")
            if previous is not None:
                value = self._normalize_output(name, scalar(pv.read(data_type="native", timeout=5)))
                if not values_agree(previous, value):
                    raise RuntimeError(f"COMPETING WRITER {name}: {value!r} != {previous!r}")
            # Caproto clients support scalar native CA writes; avoid extra
            # CLI subprocesses and verify every published value.
            pv.write(desired, wait=True, timeout=5)
            confirmed = self._normalize_output(name, scalar(pv.read(data_type="native", timeout=5)))
            if not values_agree(desired, confirmed):
                raise RuntimeError(f"Write/readback mismatch {name}: {desired!r} != {confirmed!r}")
            self._normalize_alarm(name, desired)
            self.last_published[name] = desired
            sent += 1
            LOG.info("CA PUBLISHED %s=%r owner=%s", name, desired, owner)
            if sent >= self.max_writes_per_cycle:
                break
        return sent

    def run(self, max_steps: int = 0, publish_period: float = 0.5) -> None:
        self.connect()
        if self.mode == "validate":
            LOG.info("Validation complete, no CA writes performed")
            return
        dt = self.engine.dt
        next_tick = time.monotonic()
        next_publish = next_tick
        next_validate = next_tick + 5.0
        steps = 0
        while not self.stop and (max_steps == 0 or steps < max_steps):
            for name, pv in self.channels.items():
                if not pv.connected:
                    raise ConnectionError(f"CA DISCONNECTED: {name}")
            self.apply_events()
            self.engine.step()
            steps += 1
            now = time.monotonic()
            if now >= next_publish:
                sent = self.publish()
                if sent:
                    LOG.debug("Cycle published %d outputs", sent)
                next_publish = now + publish_period
            if self.mode == "publish" and now >= next_validate:
                self._verify_competitor()
                next_validate = now + 5.0
            if steps == 1 or steps % self.report_every == 0:
                ctx = self.engine.context
                LOG.info("step=%d time=%.1fs mode=%s P1=%g P2=%g "
                         "PP1=%s PP2=%s GV=%s outputs=%d",
                         steps, ctx.time, self.mode,
                         ctx.metrics.get("LEBT:VAC01.pressure_mbar", float("nan")),
                         ctx.metrics.get("LEBT:VAC02.pressure_mbar", float("nan")),
                         ctx.pv.get("LEBT:VAC01:PPOnStat"),
                         ctx.pv.get("LEBT:VAC02:PPOnStat"),
                         ctx.pv.get("LEBT:GV:OpenStat"), len(self.output_owners))
            next_tick += dt
            sleep = next_tick - time.monotonic()
            if sleep > 0:
                time.sleep(sleep)
            else:
                next_tick = time.monotonic()
        LOG.info("Bridge stopped after %s regular steps", steps)

    def close(self):
        if self.context is not None:
            self.context.disconnect()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LIPAc FULL vacuum isolated CA bridge")
    parser.add_argument("--mode", choices=("observe", "validate", "publish"), default="observe")
    parser.add_argument("--ioc", default="10.0.3.16")
    parser.add_argument("--steps", type=int, default=0, help="0 runs until stopped")
    parser.add_argument("--report-every", type=int, default=50)
    parser.add_argument("--publish-period", type=float, default=0.5)
    parser.add_argument("--max-writes-per-cycle", type=int, default=12)
    parser.add_argument("--quality-mode", choices=("off", "verify", "process-stale-udf"),
                        default="off", help="opt-in EPICS readback quality verification; "
                        "test .PROC independently before process-stale-udf")
    args = parser.parse_args(argv)
    if args.steps < 0 or args.report_every < 1 or args.publish_period < 0.2 or not 1 <= args.max_writes_per_cycle <= 25:
        parser.error("Invalid steps, report rate, publishing period or write budget")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    bridge = FullVacuumBridge(mode=args.mode, host=args.ioc,
                              report_every=args.report_every,
                              max_writes_per_cycle=args.max_writes_per_cycle,
                              quality_mode=args.quality_mode)
    def terminate(_sig, _frame):
        bridge.stop = True
    signal.signal(signal.SIGINT, terminate)
    signal.signal(signal.SIGTERM, terminate)
    try:
        bridge.run(max_steps=args.steps, publish_period=args.publish_period)
        return 0
    finally:
        bridge.close()


if __name__ == "__main__":
    raise SystemExit(main())
