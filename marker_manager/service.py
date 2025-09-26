"""High-level service orchestration for the marker manager toolkit."""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

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

    @staticmethod
    def from_mapping(mapping: Dict[str, Any], base_dir: Optional[Path] = None) -> "ManagerConfig":
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
            unknown_field_policy=str(mapping.get("unknown_field_policy", "preserve_in.extras")),
        )


@dataclass
class ManagerStatus:
    last_build: Optional[float] = None
    last_result: Optional[MarkerCatalogResult] = None
    active_focus: Optional[str] = None
    active_model: Optional[str] = None
    recent_events: List[Dict[str, Any]] = field(default_factory=list)


class MarkerManagerService:
    """Facade to coordinate catalog operations, focus schemas, models, and watchers."""

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
        self.focus_registry = FocusSchemaRegistry(self.config.focus_schemata_file)
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
        result_summary = self.status.last_result.summary() if self.status.last_result else None
        return {
            "config": {
                "source_dir": str(self.config.source_dir),
                "canonical_json": str(self.config.canonical_json),
                "backup_dir": str(self.config.backup_dir),
            },
            "last_build": self.status.last_build,
            "focus": self.focus_registry.status(),
            "model": self.model_registry.status(),
            "result": result_summary,
            "metrics": self.catalog.metrics(),
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
