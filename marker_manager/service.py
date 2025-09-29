"""High-level service orchestration for the marker manager toolkit."""
from __future__ import annotations

import os
import shutil
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import yaml

from .enginelib.marker_catalog import MarkerCatalog, MarkerCatalogResult
from .enginelib.focus_schema import FocusSchemaRegistry
from .enginelib.model_config import ModelConfigRegistry


@dataclass
class ManagerConfig:
    source_dir: Path
    canonical_json: Path
    backup_dir: Path
    schema_file: Path
    focus_schemata_file: Path
    models_dir: Path
    watch: bool = False
    atomic_writes: bool = True
    sort_key: str = "id"
    id_required: bool = True
    unknown_field_policy: str = "preserve_in.extras"
    mirror_targets: List[Path] = field(default_factory=list)

    @staticmethod
    def from_mapping(
        mapping: Dict[str, Any],
        base_dir: Optional[Path] = None,
    ) -> "ManagerConfig":
        def resolve(value: str) -> Path:
            path = Path(value)
            if not path.is_absolute() and base_dir is not None:
                if path.parts and path.parts[0] == base_dir.name:
                    path = base_dir.parent / path
                else:
                    path = base_dir / path
            return path

        return ManagerConfig(
            source_dir=resolve(mapping["source_dir"]),
            canonical_json=resolve(mapping["canonical_json"]),
            backup_dir=resolve(mapping["backup_dir"]),
            schema_file=resolve(mapping["schema_file"]),
            focus_schemata_file=resolve(mapping["focus_schemata_file"]),
            models_dir=resolve(mapping["models_dir"]),
            watch=bool(mapping.get("watch", False)),
            atomic_writes=bool(mapping.get("atomic_writes", True)),
            sort_key=str(mapping.get("sort_key", "id")),
            id_required=bool(mapping.get("id_required", True)),
            unknown_field_policy=str(
                mapping.get("unknown_field_policy", "preserve_in.extras")
            ),
            mirror_targets=[
                resolve(target) for target in mapping.get("mirror_targets", [])
            ],
        )


@dataclass
class ManagerStatus:
    last_build: Optional[float] = None
    last_result: Optional[MarkerCatalogResult] = None
    active_focus: Optional[str] = None
    active_model: Optional[str] = None
    recent_events: List[Dict[str, Any]] = field(default_factory=list)


class MarkerManagerService:
    """Coordinate marker catalog operations, focus schemas, and watcher."""

    def __init__(self, config_path: Path):
        self.config_path = Path(config_path)
        with open(self.config_path, "r", encoding="utf-8") as handle:
            config_data = yaml.safe_load(handle) or {}
        base_dir = self.config_path.parent
        self.config = ManagerConfig.from_mapping(config_data, base_dir)
        self.catalog = MarkerCatalog(
            cfg={
                "source_dir": str(self.config.source_dir),
                "canonical_json": str(self.config.canonical_json),
                "backup_dir": str(self.config.backup_dir),
                "schema_file": str(self.config.schema_file),
                "sort_key": self.config.sort_key,
                "id_required": self.config.id_required,
                "unknown_field_policy": self.config.unknown_field_policy,
                "atomic_writes": self.config.atomic_writes,
            }
        )
        self.focus_registry = FocusSchemaRegistry(
            self.config.focus_schemata_file
        )
        self.model_registry = ModelConfigRegistry(self.config.models_dir)
        self.status = ManagerStatus(
            active_focus=self.focus_registry.active_name,
            active_model=self.model_registry.active_name,
        )
        self._watch_thread: Optional[threading.Thread] = None
        self._watch_stop = threading.Event()
        self._lock = threading.Lock()

    # ----------------------- core catalog ops -----------------------
    def sync(self) -> MarkerCatalogResult:
        """Build the canonical JSON output from the YAML tree."""
        with self._lock:
            result = self.catalog.sync()
            self.status.last_build = time.time()
            self.status.last_result = result
            self._record_event("sync", result.summary())
            if result.ok:
                mirror_errors = _mirror_targets(
                    self.config.canonical_json,
                    self.config.mirror_targets,
                )
                if mirror_errors:
                    self._record_event("mirror_warning", {"errors": mirror_errors})
        return result

    def validate(self) -> MarkerCatalogResult:
        with self._lock:
            result = self.catalog.validate_only()
            self.status.last_result = result
            self._record_event("validate", result.summary())
        return result

    def diff_last(self) -> Dict[str, Any]:
        return self.catalog.diff_last()

    # ----------------------- focus and models -----------------------
    def set_focus_schema(self, name: str) -> Dict[str, Any]:
        info = self.focus_registry.set_active(name)
        self.status.active_focus = self.focus_registry.active_name
        self._record_event("focus", {"active_focus": self.status.active_focus})
        return info

    def set_model_profile(self, name: str) -> Dict[str, Any]:
        info = self.model_registry.set_active(name)
        self.status.active_model = self.model_registry.active_name
        self._record_event("model", {"active_model": self.status.active_model})
        return info

    # ----------------------- status & logs -----------------------
    def status_payload(self) -> Dict[str, Any]:
        metrics = self.catalog.metrics()
        fallback_result = (
            self.status.last_result.summary()
            if self.status.last_result
            else None
        )
        last_ts = metrics.get("last_build_ts")
        iso_ts: Optional[str] = None
        if isinstance(last_ts, (int, float)):
            iso_ts = datetime.fromtimestamp(
                float(last_ts),
                tz=timezone.utc,
            ).isoformat()

        conflicts_list: List[str] = []
        conflicts_raw = metrics.get("conflicts")
        if isinstance(conflicts_raw, list):
            conflicts_list = [str(item) for item in conflicts_raw]

        ok_value: Optional[bool]
        ok_raw = metrics.get("ok")
        if isinstance(ok_raw, bool):
            ok_value = ok_raw
        elif ok_raw is None:
            if fallback_result and fallback_result.get("ok") is not None:
                ok_value = bool(fallback_result.get("ok"))
            else:
                ok_value = None
        else:
            ok_value = bool(ok_raw)

        count_value = 0
        count_raw = metrics.get("count")
        if isinstance(count_raw, (int, float)):
            count_value = int(count_raw)
        elif fallback_result:
            fallback_count = fallback_result.get("count")
            if isinstance(fallback_count, (int, float)):
                count_value = int(fallback_count)

        dedupe_hits_int = 0
        dedupe_raw = metrics.get("dedupe_hits")
        if isinstance(dedupe_raw, (int, float)):
            dedupe_hits_int = int(dedupe_raw)

        input_files: List[str] = []
        input_raw = metrics.get("input_files")
        if isinstance(input_raw, list):
            input_files = [str(item) for item in input_raw]

        last_backup_raw = metrics.get("last_backup")
        last_backup = (
            str(last_backup_raw)
            if last_backup_raw is not None
            else None
        )

        return {
            "ok": ok_value,
            "count": count_value,
            "dedupe_hits": dedupe_hits_int,
            "conflicts": len(conflicts_list),
            "hash_canonical": metrics.get("hash_canonical"),
            "last_build_ts": iso_ts,
            "input_files": input_files,
            "last_backup": last_backup,
            "active_focus_schema": self.status.active_focus,
            "active_model_profile": self.status.active_model,
        }

    def recent_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        return list(self.status.recent_events[-limit:])

    def _record_event(self, event_type: str, payload: Dict[str, Any]):
        event = {"type": event_type, "timestamp": time.time(), "payload": payload}
        self.status.recent_events.append(event)

    # ----------------------- uploads -----------------------
    def write_yaml_blob(self, filename: str, content: str) -> Path:
        target_dir = self.config.source_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        sanitized = filename.replace("..", "_").replace(os.sep, "_")
        target_path = target_dir / sanitized
        with open(target_path, "w", encoding="utf-8") as handle:
            handle.write(content)
        self._record_event("write_yaml", {"file": str(target_path)})
        return target_path

    def rebuild_after_write(self) -> MarkerCatalogResult:
        return self.sync()

    # ----------------------- watcher -----------------------
    def start_watcher(
        self,
        debounce_seconds: float = 0.5,
        observer_factory=None,
        timer_factory=None,
    ):
        if self._watch_thread and self._watch_thread.is_alive():
            return

        self._watch_stop.clear()

        def loop():
            try:
                from watchdog.observers import Observer
                from watchdog.events import FileSystemEventHandler
            except ImportError as exc:  # pragma: no cover - handled in tests
                raise RuntimeError("watchdog package is required for watch command") from exc

            class Handler(FileSystemEventHandler):
                def __init__(self, service: "MarkerManagerService"):
                    self.service = service
                    self._timer: Optional[threading.Timer] = None

                def on_any_event(self, event):  # type: ignore[override]
                    if event.is_directory:
                        return
                    if self._timer:
                        self._timer.cancel()
                    factory = timer_factory or threading.Timer
                    self._timer = factory(debounce_seconds, self._run)
                    self._timer.start()

                def _run(self):
                    try:
                        self.service.sync()
                    except Exception as error:  # pragma: no cover - logged for troubleshooting
                        self.service._record_event("watch_error", {"error": str(error)})

            observer_cls = observer_factory or Observer
            observer = observer_cls()
            handler = Handler(self)
            self.config.source_dir.mkdir(parents=True, exist_ok=True)
            observer.schedule(handler, str(self.config.source_dir), recursive=True)
            observer.start()
            try:
                while not self._watch_stop.is_set():
                    time.sleep(0.1)
            finally:
                observer.stop()
                observer.join()

        self._watch_thread = threading.Thread(target=loop, daemon=True)
        self._watch_thread.start()
        self._record_event("watch_start", {})

    def stop_watcher(self):
        if not self._watch_thread:
            return
        self._watch_stop.set()
        self._watch_thread.join(timeout=2)
        self._record_event("watch_stop", {})


def load_config(path: Path) -> ManagerConfig:
    with open(path, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return ManagerConfig.from_mapping(data, path.parent)


def _mirror_targets(canon_path: Path, targets: Iterable[Path]) -> List[str]:
    errors: List[str] = []
    if not targets:
        return errors
    for target in targets:
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(canon_path, target)
        except FileNotFoundError as exc:
            errors.append(f"Missing canonical source: {exc}")
        except OSError as exc:  # pragma: no cover - logged via status
            errors.append(f"Mirror failure for {target}: {exc}")
    return errors
