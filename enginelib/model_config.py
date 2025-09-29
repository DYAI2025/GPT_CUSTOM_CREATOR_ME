"""Proxy module forwarding to the canonical model config helpers."""

from marker_manager.enginelib import (  # type: ignore
    model_config as _canonical_model_config,
)

__all__ = getattr(_canonical_model_config, "__all__", [])  # type: ignore
globals().update(
    {name: getattr(_canonical_model_config, name) for name in __all__}
)
