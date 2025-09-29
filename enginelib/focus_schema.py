"""Proxy module forwarding to the canonical focus schema helpers."""

from marker_manager.enginelib import (  # type: ignore
    focus_schema as _canonical_focus_schema,
)

__all__ = getattr(_canonical_focus_schema, "__all__", [])  # type: ignore
globals().update(
    {name: getattr(_canonical_focus_schema, name) for name in __all__}
)
