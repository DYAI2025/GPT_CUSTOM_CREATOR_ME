"""Compatibility layer that forwards legacy imports to the canonical engine."""

from marker_manager import enginelib as _canonical_enginelib  # type: ignore
from marker_manager.enginelib import *  # noqa: F401,F403

__all__ = getattr(_canonical_enginelib, "__all__", [])  # type: ignore
