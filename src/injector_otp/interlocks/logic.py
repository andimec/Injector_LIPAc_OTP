from __future__ import annotations

"""Injector interlock logic for the LIPAc OTP simulation.

This module intentionally contains authorization logic, not physical models.

Design rules
------------
1. Physical/reduced-order models publish equipment state through PVs.
2. This module reads those states and evaluates authorization chains.
3. The normalized result is written to SimulationControlPlane using the
   convention True = authorized / allowed and False = blocked.
4. Device faults remain independent. A fault may be injected externally
   through SimulationControlPlane.device_faults and this logic consumes
   that information without owning the fault injection mechanism.
5. The documentation is treated as complementary. Current LCS manual signals
   and legacy PLC relationships are both represented where the available
   source material supports the relationship. Ambiguous or undocumented
   conditions are deliberately not invented here.

PV names in this file are source Injector names. The simulation backend exposes
them as OTP:<name>; _pv() accepts both forms so the logic remains independent
of the EPICS namespace adapter.
"""

from dataclasses import dataclass
from typing import Any

from ..core.control import SimulationControlPlane


@dataclass(frozen=True)
class InterlockResult:
    """A named authorization result and the individual conditions that formed it."""

    name: str
    allowed: bool
    conditions: dict[str, bool]


class InjectorInterlockLogic:
    """Evaluate the documented Injector authorization chains.

    The class is deliberately stateless. Every evaluation recomputes all
    derived interlock signals from the current simulation snapshot. This makes
    the result deterministic and suitable for training, replay and unit tests.
    """

    def evaluate(self, context: Any, controls: SimulationControlPlane) -> None:
        """Evaluate all currently supported Injector interlock chains.

        No operator command is accepted as an authorization signal here.
        Commands may change equipment PVs through the models, but the
        authorization result is always calculated from observed conditions.
        """
        hv = self._evaluate_hv(context, controls)
        ie = self._evaluate_ie(context, controls)
        plasma = self._evaluate_rf_plasma(context, controls)
        beam = self._evaluate_rf_beam(context, controls)

        controls.set_interlock(
            "VACUUM:READY",
            self._healthy_pv(context, "LEBT:VAC01:SGVCDefStat"),
        )
        controls.set_interlock(
            "COOLING:READY",
            self._healthy_pv(context, "INJ:WS:ResPCDefStat"),
        )
        controls.set_interlock(
            "COILS:READY",
            self._all_healthy(
                context,
                ("SRC:COIL01:FSDefStat", "SRC:COIL02:FSDefStat"),
                controls,
                devices=("coil1", "coil2"),
            ),
        )
        controls.set_interlock("GAS:READY", self._gas_ready(context, controls))
        controls.set_interlock("MAGNETS:READY", self._magnets_ready(context, controls))
        controls.set_interlock("CHOPPER:READY", self._chopper_ready(context, controls))

        controls.set_interlock("HV:ENABLE", hv.allowed)
        controls.set_interlock("IE:ENABLE", ie.allowed)
        controls.set_interlock("RF:PLASMA:ENABLE", plasma.allowed)
        controls.set_interlock("RF:BEAM:ENABLE", beam.allowed)

        # The normalized beam authorization remains distinct from the raw PPS
        # inhibit PV. The latter is an external protection signal.
        controls.set_interlock(
            "BEAM:ENABLE",
            beam.allowed and not self._fbi_active(context),
        )

        # Legacy PLC relationships are retained as complementary diagnostic
        # signals. They are not used to silently replace current chains.
        self._evaluate_legacy_relationships(context, controls)

    def _evaluate_hv(self, context: Any, controls: SimulationControlPlane) -> InterlockResult:
        """Implement the current LCS HVPS authorization chain."""
        conditions = {
            "control_room_key": self._bool(context, "LEBT:HV:RoomKeyA1"),
            "relay_remote": self._bool(context, "LEBT:HV:RlyRmtStat"),
            "relay_closed": self._bool(context, "LEBT:HV:RlyCloseStat"),
            "vacuum": self._healthy_pv(context, "LEBT:VAC01:SGVCDefStat"),
            "ieps_available": self._bool(context, "SRC:IE_PS:OnStat"),
            "cooling": self._healthy_pv(context, "INJ:WS:ResPCDefStat"),
            "coil1_healthy": self._healthy_pv(context, "SRC:COIL01:FSDefStat"),
            "coil2_healthy": self._healthy_pv(context, "SRC:COIL02:FSDefStat"),
            "rf_healthy": self._healthy_pv(context, "SRC:RF:FSDefStat") and not controls.device_in_fault("rf"),
            "pps_hv_permit": self._bool(context, "PPS:HV:PermStat"),
            "external_hv_safety": self._bool(context, "LEBT:HV_PS:ExtSec") and not controls.device_in_fault("hv"),
        }
        return InterlockResult("HV:ENABLE", all(conditions.values()), conditions)

    def _evaluate_ie(self, context: Any, controls: SimulationControlPlane) -> InterlockResult:
        """Implement the dedicated IEPS authorization chain."""
        conditions = {
            "control_room_key": self._bool(context, "LEBT:HV:RoomKeyA1"),
            "relay_remote": self._bool(context, "LEBT:HV:RlyRmtStat"),
            "relay_defensive_open": self._bool(context, "LEBT:HV:RlyDefOpen"),
            "relay_closed": self._bool(context, "LEBT:HV:RlyCloseStat"),
            "vacuum": self._healthy_pv(context, "LEBT:VAC01:SGVCDefStat"),
            "cooling": self._healthy_pv(context, "INJ:WS:ResPCDefStat"),
            "coil1_healthy": self._healthy_pv(context, "SRC:COIL01:FSDefStat"),
            "coil2_healthy": self._healthy_pv(context, "SRC:COIL02:FSDefStat"),
            "rf_healthy": self._healthy_pv(context, "SRC:RF:FSDefStat"),
            "pps_hv_permit": self._bool(context, "PPS:HV:PermStat"),
            "external_ie_safety": self._bool(context, "SRC:IE_PS:ExtSec") and not controls.device_in_fault("ie"),
        }
        return InterlockResult("IE:ENABLE", all(conditions.values()), conditions)

    def _evaluate_rf_plasma(
        self,
        context: Any,
        controls: SimulationControlPlane,
    ) -> InterlockResult:
        """Implement the RF-for-Plasma authorization path."""
        conditions = {
            "coil1_on": self._healthy_pv(context, "SRC:COIL01_PS:OnStat"),
            "coil2_on": self._healthy_pv(context, "SRC:COIL02_PS:OnStat"),
            "ie_on": self._healthy_pv(context, "SRC:IE_PS:OnStat") and not controls.device_in_fault("ie"),
            "repeller_on": self._healthy_pv(context, "LEBT:R_PS:OnStat") and not controls.device_in_fault("repeller"),
            "gas_ready": self._gas_ready(context, controls),
            "rf_healthy": self._healthy_pv(context, "SRC:RF:FSDefStat") and not controls.device_in_fault("rf"),
            "vacuum": self._healthy_pv(context, "LEBT:VAC01:SGVCDefStat") and not controls.device_in_fault("vacuum"),
            "pps_plasma_permit": self._bool(context, "PPS:PLSM:PermStat"),
        }
        return InterlockResult("RF:PLASMA:ENABLE", all(conditions.values()), conditions)

    def _evaluate_rf_beam(
        self,
        context: Any,
        controls: SimulationControlPlane,
    ) -> InterlockResult:
        """Implement the RF-for-Beam authorization path."""
        conditions = {
            "chopper_healthy": self._healthy_pv(context, "LEBT:CHOP:FSDefStat") and not controls.device_in_fault("chopper"),
            "emittance_healthy": self._healthy_pv(context, "LEBT:EMIT:FSDefStat"),
            "faraday_cup_healthy": self._healthy_pv(context, "LEBT:FC:FSDefStat"),
            "acct_healthy": self._healthy_pv(context, "LEBT:IC:FSDefStat"),
            "solenoid1_cooling": self._healthy_pv(context, "LEBT:SOL01:VCFlowStat") and not controls.device_in_fault("solenoids"),
            "solenoid2_cooling": self._healthy_pv(context, "LEBT:SOL02:VCFlowStat") and not controls.device_in_fault("solenoids"),
            "solenoid1_on": self._healthy_pv(context, "LEBT:SOL01_PS:OnStat") and not controls.device_in_fault("solenoids"),
            "solenoid2_on": self._healthy_pv(context, "LEBT:SOL02_PS:OnStat") and not controls.device_in_fault("solenoids"),
            "rf_healthy": self._healthy_pv(context, "SRC:RF:FSDefStat") and not controls.device_in_fault("rf"),
            "gate_valve_open": self._bool(context, "LEBT:GV:OpenStat"),
            "chopper_inserted": self._bool(context, "LEBT:CHOP:InStat"),
            "gas_ready": self._gas_ready(context, controls),
            "hv_on": self._healthy_pv(context, "LEBT:HV_PS:OnStat") and not controls.device_in_fault("hv"),
            "ie_on": self._healthy_pv(context, "SRC:IE_PS:OnStat") and not controls.device_in_fault("ie"),
            "repeller_on": self._healthy_pv(context, "LEBT:R_PS:OnStat") and not controls.device_in_fault("repeller"),
            "chopper_pps_permit": self._bool(context, "PPS:CHOP:PermStat"),
            "acceleration_pps_permit": self._bool(context, "PPS:ACCL:PermStat"),
            "beam_not_inhibited": not self._bool(context, "PPS:BEAM:InhibitStat"),
        }
        return InterlockResult("RF:BEAM:ENABLE", all(conditions.values()), conditions)

    def _evaluate_legacy_relationships(
        self,
        context: Any,
        controls: SimulationControlPlane,
    ) -> None:
        """Expose documented legacy PLC relationships as diagnostics.

        The 2012 PLC maintenance document gives explicit Boolean relationships
        for focalization, vacuum, GV/FC protection and chopper status. The
        current LCS manual states that PPS/MPS interfaces are evolving, so these
        relationships are deliberately complementary rather than replacements
        for the current authorization chains.
        """
        repeller_fault = not self._healthy_pv(context, "LEBT:R_PS:OnStat")
        sol1_fault = not self._healthy_pv(context, "LEBT:SOL01:FSDefStat")
        sol2_fault = not self._healthy_pv(context, "LEBT:SOL02:FSDefStat")
        focalization_fault = repeller_fault or sol1_fault or sol2_fault

        vacuum_fault = (
            not self._healthy_pv(context, "LEBT:VAC01:SGVCDefStat")
            or not self._healthy_pv(context, "LEBT:VAC02:SGVCDefStat")
        )

        gv_protection = (
            self._bool(context, "LEBT:FC:InStat")
            and self._bool(context, "LEBT:GV:CloseStat")
        )

        chopper_status = (
            self._bool(context, "LEBT:CHOP:InStat")
            and self._healthy_pv(context, "LEBT:CHOP_PS:OnStat")
        )

        controls.set_interlock("LEGACY:MPS:FOCALIZATION:OK", not focalization_fault)
        controls.set_interlock("LEGACY:MPS:VACUUM:OK", not vacuum_fault)
        controls.set_interlock("LEGACY:MPS:GV_PROTECTION", gv_protection)
        controls.set_interlock("LEGACY:MPS:CHOPPER:STATUS", chopper_status)

    def _pv(self, context: Any, name: str, default: Any = False) -> Any:
        pv = getattr(context, "pv", {})
        if name in pv:
            return pv[name]
        otp_name = f"OTP:{name}"
        return pv.get(otp_name, default)

    def _bool(self, context: Any, name: str, default: bool = False) -> bool:
        return bool(self._pv(context, name, default))

    def _healthy_pv(self, context: Any, name: str, default: bool = False) -> bool:
        """Interpret the agreed status convention: True means healthy."""
        return bool(self._pv(context, name, default))

    def _all_healthy(
        self,
        context: Any,
        names: tuple[str, ...],
        controls: SimulationControlPlane,
        devices: tuple[str, ...] = (),
    ) -> bool:
        healthy = all(self._healthy_pv(context, name) for name in names)
        return healthy and not any(controls.device_in_fault(device) for device in devices)

    def _gas_ready(self, context: Any, controls: SimulationControlPlane) -> bool:
        """Model the current D2 gas-availability path."""
        return (
            self._bool(context, "SRC:SVL:D2OpenStat")
            and self._healthy_pv(context, "LEBT:GE:FSFlowStat")
            and self._healthy_pv(context, "LEBT:GE:TSDefStat")
            and not controls.device_in_fault("gas")
        )

    def _magnets_ready(self, context: Any, controls: SimulationControlPlane) -> bool:
        return (
            self._healthy_pv(context, "LEBT:SOL01_PS:OnStat")
            and self._healthy_pv(context, "LEBT:SOL02_PS:OnStat")
            and self._healthy_pv(context, "LEBT:SOL01:VCFlowStat")
            and self._healthy_pv(context, "LEBT:SOL02:VCFlowStat")
            and not controls.device_in_fault("solenoids")
        )

    def _chopper_ready(self, context: Any, controls: SimulationControlPlane) -> bool:
        return (
            self._healthy_pv(context, "LEBT:CHOP:FSDefStat")
            and self._healthy_pv(context, "LEBT:CHOP_PS:OnStat")
            and self._bool(context, "LEBT:CHOP:InStat")
            and self._bool(context, "PPS:CHOP:PermStat")
            and not controls.device_in_fault("chopper")
        )

    def _fbi_active(self, context: Any) -> bool:
        """Consume CIM/FBI status without inventing its trigger equation."""
        return self._bool(context, "LEBT:CHOP_IM:Fbi")


__all__ = ["InjectorInterlockLogic", "InterlockResult"]
