"""Top-level composition of all Injector equipment model families.

Every V2.0 interface belongs to a named subsystem. Equipment for which we do
not yet have a validated behavioural law receives an explicit interface-only
model rather than fabricated physics or readbacks.
"""
from __future__ import annotations

from .base import SubsystemModel
from .catalog import DeviceCatalog
from .control_devices import (
    BeamTransportModel, InterfaceOnlyModel,
    PositionerModel, RFSystemModel, TimingSystemModel,
)
from .plant import CoolingSkidModel, GasFlowController, ValveDevice
from .vacuum_network import VacuumNetworkModel
from .vacuum_opi import VacuumOPIPreconditions
from .chopper_cim import ChopperCIMModel
from .hv_auto_ramp import HVAutoRampModel, HVRampSettings
from .calorimetry import LegacyCalorimetryModel
from .emu_hardware import EmuMotorSupervisor, EmuMotorModel, EmuPlatePSModel, EmuAcquisitionModel
from .emu_sequencer import EmuScanSequencer, EmuSequenceSettings
from .power_supplies import POWER_SUPPLY_PREFIXES, PowerSupplyDevice


class InjectorModel(SubsystemModel):
    """Aggregate model with explicit subsystem coverage and maturity."""

    name = "injector"

    def __init__(
        self,
        catalog: DeviceCatalog | None = None,
        parameters: dict | None = None,
    ) -> None:
        super().__init__()
        self.catalog = catalog
        self.parameters = parameters or {}
        self.components: list[SubsystemModel] = []
        self.maturity: dict[str, str] = {}
        self.beam_current_mA = 0.0
        self.hv_kV = 0.0
        self.rf_forward_W = 0.0
        self.vacuum_mbar = 1.0
        if catalog is not None:
            self._compose(catalog)

    def _add(self, model: SubsystemModel, maturity: str = "reduced_order") -> None:
        self.components.append(model)
        self.maturity[model.name] = maturity

    def _compose(self, catalog: DeviceCatalog) -> None:
        # The sequence follows causal dependencies, not EPICS scan periods.
        self._add(CoolingSkidModel(catalog), "interface_with_fault_response")

        for prefix, permit in (
            ("SRC:SVL:D2", "PPS:SVL:D2PermStat"),
            ("SRC:SVL:H2", "PPS:SVL:H2PermStat"),
            ("LEBT:GV", "PPS:GV:OpenPermStat"),
        ):
            if catalog.has(prefix + "OpenCmd") or catalog.pv(prefix, "OpenCmd"):
                self._add(ValveDevice(prefix, catalog, permit_pv=permit))

        for prefix, valve in (("SRC:MFCD", "SRC:SVL:D2"),
                              ("SRC:MFCH", "SRC:SVL:H2")):
            if catalog.contains_prefix(prefix):
                self._add(GasFlowController(prefix, valve, catalog, self.parameters))

        # The 2026 LCS user manual documents a separate PR4000B for
        # auxiliary LEBT gas, distinct from H2/D2 on the HV platform.
        if catalog.contains_prefix("LEBT:MFC"):
            self._add(GasFlowController("LEBT:MFC", None, catalog, self.parameters))

        for region in ("LEBT:VAC01", "LEBT:VAC02"):
            if not catalog.contains_prefix(region):
                continue
            for valve in ("PV", "SV", "AIV", "NIV", "LTV"):
                if region == "LEBT:VAC02" and valve == "NIV":
                    # No physical NIV on VAC02; legacy DB command is inert.
                    continue
                subprefix = f"{region}:{valve}"
                if catalog.has(subprefix + "OpenCmd"):
                    self._add(ValveDevice(subprefix, catalog))
        # One network writer, not two independent pressure models. MFC and
        # valve models run first so the network receives fresh flow/position.
        self._add(VacuumNetworkModel(catalog, self.parameters),
                  "configurable_unvalidated_network")
        self._add(VacuumOPIPreconditions(catalog), "exact_opi_formula_only")

        # Automation requests operator-setpoint inputs via the engine ACL.
        # It runs ahead of PS dynamics so its requests are consumed in-cycle.
        ramp_settings = HVRampSettings(**self.parameters.get("auto_hv", {}))
        self._add(HVAutoRampModel(catalog, ramp_settings), "procedure_based_2026")

        for prefix in POWER_SUPPLY_PREFIXES:
            if catalog.contains_prefix(prefix):
                self._add(PowerSupplyDevice(prefix, catalog, self.parameters))

        if catalog.contains_prefix("SRC:TIM"):
            self._add(TimingSystemModel(catalog))

        for prefix in ("LEBT:CHOP", "LEBT:FC", "LEBT:BS", "LEBT:EMIT"):
            if catalog.pv(prefix, "InCmd") or catalog.pv(prefix, "OutCmd"):
                self._add(PositionerModel(prefix, catalog))

        if catalog.contains_prefix("LEBT:CHOP_IM"):
            self._add(ChopperCIMModel(catalog), "operational_state_and_injected_snapshot")

        if catalog.contains_prefix("SRC:RF_GENE"):
            self._add(RFSystemModel(catalog, self.parameters))

        self._add(BeamTransportModel(catalog, self.parameters), "qualitative_only")
        self._add(LegacyCalorimetryModel(catalog), "exact_legacy_equations")

        # EMU is a coupled motor/plates/FACQ process. The controller must
        # observe the freshly computed actuator feedback and acquisition event.
        emu = self.parameters.get("emu", {})
        self._add(EmuMotorSupervisor(catalog, float(emu.get("enable_stage_delay_s", 1.0))),
                  "source_snl_2012_with_explicit_external_guard")
        self._add(EmuMotorModel(catalog, emu.get("motor", {})), "reduced_order_unvalidated_speed")
        self._add(EmuPlatePSModel(catalog, emu.get("plates", {})), "source_links_with_training_dynamics")
        self._add(EmuAcquisitionModel(catalog, emu.get("facq", {})), "synthetic_facq_trigger_only")
        self._add(EmuScanSequencer(catalog, EmuSequenceSettings(**emu.get("scan", {}))),
                  "reconstructed_2026_snl_sequence")

        # All remaining equipment families are represented as explicit
        # uncalibrated interfaces. They will not invent PV values.
        covered = {model.name for model in self.components}
        for subsystem in catalog.subsystems():
            key = f"interface:{subsystem}"
            if key not in covered:
                self._add(InterfaceOnlyModel(key), "interface_only")

    def update(self, dt: float, context) -> None:
        super().update(dt)
        if not self.state.enabled or self.state.fault or self.in_fault(context):
            return
        for model in self.components:
            model.update(dt, context)
        self.beam_current_mA = context.metrics.get("beam.current_mA", 0.0)
        self.hv_kV = context.metrics.get("LEBT:HV_PS.voltage", 0.0)
        self.rf_forward_W = context.metrics.get("rf.forward_W", 0.0)
        self.vacuum_mbar = context.metrics.get("LEBT:VAC01.pressure_mbar", 1.0)

    def model_coverage(self) -> dict[str, str]:
        return dict(sorted(self.maturity.items()))
