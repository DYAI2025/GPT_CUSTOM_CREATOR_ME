"""Persistent storage for catalog build metrics."""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, Iterable


_DEFAULT_STATE: Dict[str, Any] = {
    "last_build_ts": None,
    "input_files": [],
    "items_total": 0,
    "dedupe_hits": 0,
    "conflicts": [],
    "hash_canonical": None,
}


class StateStore:
    """Manage persisted build metrics with atomic updates."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self._lock = threading.Lock()

    # ----------------------- helpers -----------------------
    def load(self) -> Dict[str, Any]:
        """Return the current persisted state or defaults."""

        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except FileNotFoundError:
            return dict(_DEFAULT_STATE)
        except (OSError, json.JSONDecodeError):
            return dict(_DEFAULT_STATE)

        state = dict(_DEFAULT_STATE)
        if isinstance(data, dict):
            state.update(data)
        return state

    # ----------------------- public api -----------------------
    def update(self, **updates: Any) -> Dict[str, Any]:
        """Merge updates into the persisted state atomically."""

        with self._lock:
            state = self.load()
            normalised = self._normalise(updates)
            state.update(normalised)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
            with open(tmp_path, "w", encoding="utf-8") as handle:
                json.dump(state, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, self.path)
            return state

    # ----------------------- normalisation -----------------------
    def _normalise(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for key, value in updates.items():
            if key == "input_files":
                result[key] = self._prepare_paths(value)
            elif key == "conflicts":
                if isinstance(value, (str, bytes)):
                    result[key] = [value]
                elif isinstance(value, Iterable):
                    result[key] = list(value)
                else:
                    result[key] = []
            else:
                result[key] = value
        return result

    @staticmethod
    def _prepare_paths(value: Any) -> list[str]:
        paths = []
        if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
            for entry in value:
                if entry is None:
                    continue
                paths.append(str(Path(entry)))
        return sorted(set(paths))
