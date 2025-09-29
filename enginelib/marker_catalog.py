"""Proxy module forwarding to the canonical marker catalog implementation."""

from marker_manager.enginelib import marker_catalog as _canonical_marker_catalog  # type: ignore

__all__ = getattr(_canonical_marker_catalog, "__all__", [])  # type: ignore
globals().update(
    {name: getattr(_canonical_marker_catalog, name) for name in __all__}
)
