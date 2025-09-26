import time
from pathlib import Path
from types import MethodType

import time
from pathlib import Path
from types import MethodType

import yaml

from marker_manager.enginelib.marker_catalog import MarkerCatalogResult
from marker_manager.service import MarkerManagerService


class FakeObserver:
    def __init__(self):
        self.handler = None

    def schedule(self, handler, path, recursive):
        self.handler = handler

    def start(self):
        return None

    def stop(self):
        return None

    def join(self):
        return None


class FakeTimer:
    def __init__(self, interval, callback):
        self.interval = interval
        self.callback = callback
        self.cancelled = False

    def start(self):
        return None

    def cancel(self):
        self.cancelled = True

    def fire(self):
        if not self.cancelled:
            self.callback()


def create_config(tmp_path: Path) -> Path:
    source_dir = tmp_path / "yaml"
    canonical = tmp_path / "canonical" / "markers_canonical.json"
    backup_dir = tmp_path / "canonical" / "backups"
    source_dir.mkdir()
    schema_file = Path(__file__).resolve().parents[1] / "schemas" / "schema.markers.json"
    focus_file = Path(__file__).resolve().parents[1] / "schemas" / "focus_schemata.json"
    models_dir = Path(__file__).resolve().parents[1] / "resources" / "models"
    config_path = tmp_path / "config.yaml"
    payload = {
        "source_dir": str(source_dir),
        "canonical_json": str(canonical),
        "backup_dir": str(backup_dir),
        "schema_file": str(schema_file),
        "focus_schemata_file": str(focus_file),
        "models_dir": str(models_dir),
        "watch": False,
        "atomic_writes": True,
        "sort_key": "id",
        "id_required": True,
        "unknown_field_policy": "preserve_in.extras",
    }
    with open(config_path, "w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle)
    return config_path


def test_watch_debounces_multiple_events(tmp_path):
    config_path = create_config(tmp_path)
    service = MarkerManagerService(config_path)
    observer = FakeObserver()
    timers = []

    def timer_factory(interval, callback):
        timer = FakeTimer(interval, callback)
        timers.append(timer)
        return timer

    calls = []

    def fake_sync(self):
        calls.append("sync")
        return MarkerCatalogResult(ok=True, count=0, errors=[])

    service.sync = MethodType(fake_sync, service)

    service.start_watcher(debounce_seconds=0.01, observer_factory=lambda: observer, timer_factory=timer_factory)
    time.sleep(0.05)
    assert observer.handler is not None

    event = type("Evt", (), {"is_directory": False})
    observer.handler.on_any_event(event)
    observer.handler.on_any_event(event)

    assert timers, "expected timer creation"
    timers[-1].fire()

    service.stop_watcher()

    assert calls.count("sync") == 1
