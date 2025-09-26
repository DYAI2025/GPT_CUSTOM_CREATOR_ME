"""Focus schema registry to manage active focus configurations."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


@dataclass
class FocusSchema:
    name: str
    description: str
    weights: Dict[str, float]


class FocusSchemaRegistry:
    """Load and manage focus schemata from a JSON file."""

    STATE_FILE = ".focus_state.json"

    def __init__(self, schemata_path: Path):
        self.schemata_path = Path(schemata_path)
        self._schemata: Dict[str, FocusSchema] = {}
        self.active_name: Optional[str] = None
        self._load()

    # ----------------------- loading -----------------------
    def _load(self):
        if not self.schemata_path.exists():
            self._schemata = {}
            self.active_name = None
            return
        with open(self.schemata_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        schemata = {}
        for entry in data.get("schemata", []):
            schema = FocusSchema(
                name=entry["name"],
                description=entry.get("description", ""),
                weights=entry.get("weights", {}),
            )
            schemata[schema.name] = schema
        self._schemata = schemata
        self.active_name = self._load_state()
        if self.active_name not in self._schemata:
            self.active_name = None

    def _state_file(self) -> Path:
        return self.schemata_path.parent / self.STATE_FILE

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

    # ----------------------- operations -----------------------
    def set_active(self, name: str) -> Dict[str, Optional[str]]:
        if name not in self._schemata:
            raise ValueError(f"Unknown focus schema: {name}")
        self.active_name = name
        self._store_state(name)
        return self.status()

    def status(self) -> Dict[str, Optional[str]]:
        return {
            "active": self.active_name,
            "available": list(self._schemata.keys()),
        }
