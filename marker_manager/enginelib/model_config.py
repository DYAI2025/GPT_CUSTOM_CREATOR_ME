"""Model profile registry for the marker manager."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


@dataclass
class ModelProfile:
    name: str
    payload: Dict[str, object]


class ModelConfigRegistry:
    """Manage model profile selection from a directory of JSON files."""

    STATE_FILE = ".model_state.json"

    def __init__(self, models_dir: Path):
        self.models_dir = Path(models_dir)
        self._profiles: Dict[str, ModelProfile] = {}
        self.active_name: Optional[str] = None
        self._load()

    def _load(self):
        if not self.models_dir.exists():
            self.models_dir.mkdir(parents=True, exist_ok=True)
        for path in self.models_dir.glob("*.json"):
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            profile = ModelProfile(name=path.stem, payload=data)
            self._profiles[profile.name] = profile
        self.active_name = self._load_state()
        if self.active_name not in self._profiles:
            self.active_name = None

    def _state_file(self) -> Path:
        return self.models_dir / self.STATE_FILE

    def _load_state(self) -> Optional[str]:
        path = self._state_file()
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            return data.get("active")
        except json.JSONDecodeError:
            return None

    def _store_state(self, name: Optional[str]):
        path = self._state_file()
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"active": name}, handle, indent=2)

    def set_active(self, name: str) -> Dict[str, Optional[str]]:
        if name not in self._profiles:
            raise ValueError(f"Unknown model profile: {name}")
        self.active_name = name
        self._store_state(name)
        return self.status()

    def status(self) -> Dict[str, Optional[str]]:
        return {
            "active": self.active_name,
            "available": list(self._profiles.keys()),
        }

    def payload(self) -> Optional[Dict[str, object]]:
        if not self.active_name:
            return None
        return self._profiles[self.active_name].payload
