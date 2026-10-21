"""Graph execution and shared runtime support.

Graph loading, execution and provider bridges live in ``system.core``; start
with ``system/core/loader.py`` and ``system/core/engine.py``. Shared helpers
live in ``system.lib``. In particular, ``system/lib/openrouter_free_runtime.py``
also supplies provider transport for the current research studies.

This package marker imports no components and defines no runtime behaviour.
"""
