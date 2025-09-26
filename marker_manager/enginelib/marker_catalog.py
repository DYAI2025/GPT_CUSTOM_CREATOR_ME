"""Marker catalog responsible for loading, validating, and canonicalising markers."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import jsonschema
import yaml
from jsonschema.exceptions import ValidationError

from .state_store import StateStore

try:
    import jsonpatch
except ImportError:  # pragma: no cover - handled by tests when dependency missing
    jsonpatch = None


@dataclass
class MarkerCatalogResult:
    ok: bool
    count: int
    errors: List[str] = field(default_factory=list)
    dedupe_hits: int = 0
    conflicts: List[str] = field(default_factory=list)

    def summary(self) -> Dict[str, object]:
        return {
            "ok": self.ok,
            "count": self.count,
            "errors": list(self.errors),
            "dedupe_hits": self.dedupe_hits,
            "conflicts": list(self.conflicts),
        }


class MarkerCatalog:
    """Load YAML markers and manage canonical JSON builds."""

    def __init__(self, cfg: Dict[str, object]):
        self.cfg = cfg
        self.source_dir = Path(cfg["source_dir"])
        self.canonical_json = Path(cfg["canonical_json"])
        self.backup_dir = Path(cfg["backup_dir"])
        self.schema_file = Path(cfg["schema_file"])
        self.sort_key = cfg.get("sort_key", "id")
        self.id_required = bool(cfg.get("id_required", True))
        self.unknown_field_policy = cfg.get("unknown_field_policy", "preserve_in.extras")
        self.atomic_writes = bool(cfg.get("atomic_writes", True))
        with open(self.schema_file, "r", encoding="utf-8") as handle:
            self.schema = json.load(handle)
        self.item_schema = self.schema.get("items", self.schema)
        self.state_store = StateStore(self.canonical_json.with_suffix(".state.json"))

    # ----------------------- loader helpers -----------------------
    def load_yaml_tree(self) -> List[Tuple[dict, Path, float]]:
        items: List[Tuple[dict, Path, float]] = []
        if not self.source_dir.exists():
            return items
        for path in self.source_dir.rglob("*.yml"):
            items.extend(self._load_file(path))
        for path in self.source_dir.rglob("*.yaml"):
            items.extend(self._load_file(path))
        return items

    def _load_file(self, path: Path) -> List[Tuple[dict, Path, float]]:
        with open(path, "r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or []
        if isinstance(data, list):
            records = data
        elif isinstance(data, dict):
            records = [data]
        else:
            raise TypeError(f"Unsupported YAML payload in {path}")
        mtime = path.stat().st_mtime
        return [(record, path, mtime) for record in records]

    # ----------------------- validation -----------------------
    def _validate_item(self, item: dict) -> Optional[str]:
        if self.id_required and "id" not in item:
            return "Missing required field 'id'"
        try:
            jsonschema.validate(item, self.item_schema)
        except ValidationError as err:
            return str(err)
        return None

    def validate_only(self) -> MarkerCatalogResult:
        raw_items = self.load_yaml_tree()
        deduped, dedupe_hits, conflicts = self._dedupe(raw_items)
        if conflicts:
            return MarkerCatalogResult(
                ok=False,
                count=0,
                errors=list(conflicts),
                dedupe_hits=dedupe_hits,
                conflicts=list(conflicts),
            )
        canonical_items = []
        errors = []
        for idx, item in enumerate(deduped):
            canonical = self._canonicalise(item)
            error = self._validate_item(canonical)
            if error:
                errors.append(f"{idx}:{error}")
                continue
            canonical_items.append(canonical)
        return MarkerCatalogResult(ok=not errors, count=len(canonical_items), errors=errors, dedupe_hits=dedupe_hits)

    # ----------------------- canonical build -----------------------
    def sync(self) -> MarkerCatalogResult:
        raw_items = self.load_yaml_tree()
        input_files = self._collect_input_files(raw_items)
        deduped, dedupe_hits, conflicts = self._dedupe(raw_items)
        if conflicts:
            self.state_store.update(
                input_files=input_files,
                dedupe_hits=dedupe_hits,
                conflicts=conflicts,
            )
            return MarkerCatalogResult(
                ok=False,
                count=0,
                errors=list(conflicts),
                dedupe_hits=dedupe_hits,
                conflicts=list(conflicts),
            )
        canonical_items = []
        errors = []
        for idx, item in enumerate(deduped):
            canonical = self._canonicalise(item)
            error = self._validate_item(canonical)
            if error:
                errors.append(f"{idx}:{error}")
                continue
            canonical_items.append(canonical)
        canonical_items.sort(key=lambda value: value.get(self.sort_key, ""))
        ok = not errors
        result = MarkerCatalogResult(
            ok=ok,
            count=len(canonical_items),
            errors=errors,
            dedupe_hits=dedupe_hits,
            conflicts=[],
        )
        if ok:
            timestamp = time.time()
            self._write_output(canonical_items)
            self.state_store.update(
                last_build_ts=timestamp,
                input_files=input_files,
                items_total=len(canonical_items),
                dedupe_hits=dedupe_hits,
                conflicts=[],
                hash_canonical=self._hash_items(canonical_items),
            )
        else:
            self.state_store.update(
                input_files=input_files,
                dedupe_hits=dedupe_hits,
                conflicts=result.conflicts,
            )
        return result

    # ----------------------- dedupe -----------------------
    def _dedupe(self, raw_items: List[Tuple[dict, Path, float]]):
        by_id: Dict[str, List[Tuple[dict, Path, float]]] = {}
        anonymous: List[Tuple[dict, Path, float]] = []
        for record, path, mtime in raw_items:
            marker_id = record.get("id")
            if not marker_id:
                anonymous.append((record, path, mtime))
                continue
            by_id.setdefault(marker_id, []).append((record, path, mtime))

        dedupe_hits = sum(max(0, len(entries) - 1) for entries in by_id.values())
        merged: List[dict] = []
        conflicts: List[str] = []
        for marker_id, entries in by_id.items():
            entries.sort(key=lambda item: item[2], reverse=True)
            base_record, base_path, _ = entries[0]
            base = base_record.copy()
            for other_record, other_path, _ in entries[1:]:
                for key, value in other_record.items():
                    if key not in base:
                        base[key] = value
                        continue
                    if base[key] != value:
                        if isinstance(base[key], (dict, list)) or isinstance(value, (dict, list)):
                            conflicts.append(
                                f"Conflict for id {marker_id} on field '{key}' between {base_path} and {other_path}"
                            )
                        # keep the value from the newest file (base)
                        continue
            merged.append(base)
        merged.extend(record for record, _, _ in anonymous)
        return merged, dedupe_hits, conflicts

    # ----------------------- canonicalise -----------------------
    def _canonicalise(self, item: dict) -> dict:
        output: Dict[str, object] = {
            "id": item.get("id"),
            "signal": item.get("signal"),
            "concept": item.get("concept"),
            "pragmatics": item.get("pragmatics"),
            "narrative": item.get("narrative"),
        }
        for key in ("pattern", "composed_of", "detect_class", "tags", "window"):
            if key in item:
                output[key] = item[key]
        extras = {k: v for k, v in item.items() if k not in output}
        if extras and self.unknown_field_policy == "preserve_in.extras":
            output.setdefault("extras", {}).update(extras)
        return output

    def _collect_input_files(self, raw_items: List[Tuple[dict, Path, float]]) -> List[str]:
        files: Set[str] = set()
        for _, path, _ in raw_items:
            files.add(str(path))
        return sorted(files)

    def _hash_items(self, canonical_items: List[dict]) -> str:
        payload = json.dumps(canonical_items, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    # ----------------------- write output -----------------------
    def _write_output(self, canonical_items: List[dict]):
        self.canonical_json.parent.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        data = json.dumps(canonical_items, indent=2, ensure_ascii=False)
        if not self.atomic_writes:
            with open(self.canonical_json, "w", encoding="utf-8") as handle:
                handle.write(data)
            return
        tmp_path = Path(f"{self.canonical_json}.tmp")
        with open(tmp_path, "w", encoding="utf-8") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if self.canonical_json.exists():
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            backup_path = self.backup_dir / f"markers_canonical_{timestamp}.json"
            shutil.copy2(self.canonical_json, backup_path)
        os.replace(tmp_path, self.canonical_json)

    # ----------------------- diffing -----------------------
    def diff_last(self) -> Dict[str, object]:
        if not self.canonical_json.exists() or not self.backup_dir.exists():
            return {"patch": [], "has_previous": False}
        candidates = sorted(self.backup_dir.glob("markers_canonical_*.json"))
        if not candidates:
            return {"patch": [], "has_previous": False}
        last = candidates[-1]
        with open(last, "r", encoding="utf-8") as handle:
            previous = json.load(handle)
        with open(self.canonical_json, "r", encoding="utf-8") as handle:
            current = json.load(handle)
        if jsonpatch is None:
            return {"patch": [], "has_previous": True, "note": "jsonpatch dependency missing"}
        patch = jsonpatch.make_patch(previous, current)
        return {"patch": patch.to_string(), "has_previous": True}

    # ----------------------- metrics -----------------------
    def metrics(self) -> Dict[str, Any]:
        return self.state_store.load()
