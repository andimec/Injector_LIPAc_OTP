from .core.engine import SimulationEngine
from .epics.store import PVStore
from .faults.manager import FaultDefinition, FaultManager
from .models.injector import InjectorModel


def build_application() -> tuple[SimulationEngine, PVStore, FaultManager]:
    pv = PVStore()
    faults = FaultManager()

    # Initial contract. This is intentionally small until the full V1.1 registry
    # is converted into machine-readable configuration.
    pv.define("LEBT:FC:InStat", False, writable=False)
    pv.define("PPS:BEAM:InhibitStat", False, writable=False)
    pv.define("MPS:INJ:DefStat", False, writable=False)
    pv.define("SRC:COIL01_PS:ISet", 0.0, writable=True)
    pv.define("SRC:COIL01_PS:IRdbk", 0.0, writable=False)
    pv.define("OTP:STATE", "OFF", writable=False)
    pv.define("OTP:SIM_TIME", 0.0, writable=False)

    faults.register(FaultDefinition(
        "VACUUM_LOSS",
        severity="trip",
        description="Synthetic vacuum degradation/loss scenario.",
        state_impact="fault",
    ))
    faults.register(FaultDefinition(
        "RF_FAILURE",
        severity="trip",
        description="Synthetic RF availability failure.",
        state_impact="inhibit",
    ))
    faults.register(FaultDefinition(
        "MAGNET_DRIFT",
        severity="warning",
        description="Synthetic magnet setpoint-to-feedback drift.",
        state_impact="none",
    ))

    model = InjectorModel()
    engine = SimulationEngine(models=[model], dt=0.1, pv_backend=pv)
    return engine, pv, faults


def step_once() -> None:
    engine, _, _ = build_application()
    engine.step()


if __name__ == "__main__":
    step_once()
