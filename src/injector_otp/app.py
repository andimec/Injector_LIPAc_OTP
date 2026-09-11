from .core.engine import SimulationEngine
from .epics.store import PVStore
from .faults.manager import FaultManager
from .models.injector import InjectorModel


def build_application() -> tuple[SimulationEngine, PVStore, FaultManager]:
    model = InjectorModel()
    engine = SimulationEngine(models=[model], dt=0.1)
    pv = PVStore()
    faults = FaultManager()

    # Initial contract. This is intentionally small until the full V1.1 registry
    # is converted into machine-readable configuration.
    pv.define("LEBT:FC:InStat", False, writable=False)
    pv.define("PPS:BEAM:InhibitStat", False, writable=False)
    pv.define("MPS:INJ:DefStat", False, writable=False)
    pv.define("SRC:COIL01_PS:ISet", 0.0, writable=True)
    pv.define("SRC:COIL01_PS:IRdbk", 0.0, writable=False)

    return engine, pv, faults


def step_once() -> None:
    engine, _, _ = build_application()
    engine.step()


if __name__ == "__main__":
    step_once()
