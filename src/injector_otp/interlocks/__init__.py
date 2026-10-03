"""Injector interlock and protection-logic package.

The package contains deterministic external authorization logic. It is kept
separate from subsystem physical models and from the fault-injection manager.
"""

from .logic import InterlockResult, InjectorInterlockLogic

__all__ = ["InjectorInterlockLogic", "InterlockResult"]
