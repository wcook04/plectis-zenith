"""
[PURPOSE]
- Teleology: Preserve the stable public Polymarket tool entrypoint while the internal scanner logic lives in bounded local seams.
- Mechanism: Re-export the runtime actor and module-level run() entrypoint from the internal runtime package.

[INTERFACE]
- Exports: `StandardActor`, `run`.
- Stability: Downstream callers keep importing `tools.polymarket.polymarket:run`.
"""

from __future__ import annotations

from tools.polymarket.runtime import StandardActor, run

__all__ = ["StandardActor", "run"]
