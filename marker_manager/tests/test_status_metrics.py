import json
import time
from pathlib import Path

import yaml

from marker_manager.service import MarkerManagerService


def write_config(tmp_path: Path) -> Path:
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


def test_state_store_records_metrics(tmp_path):
    config_path = write_config(tmp_path)
    service = MarkerManagerService(config_path)
    src_dir = service.config.source_dir
    file_one = src_dir / "marker_one.yaml"
    file_two = src_dir / "marker_two.yaml"

    with open(file_one, "w", encoding="utf-8") as handle:
        yaml.safe_dump({"id": "dup", "signal": "one"}, handle)
    time.sleep(0.01)
    with open(file_two, "w", encoding="utf-8") as handle:
        yaml.safe_dump({"id": "dup", "concept": "extra"}, handle)

    result = service.sync()
    assert result.ok
    status = service.status_payload()
    metrics = status["metrics"]

    assert metrics["items_total"] == 1
    assert metrics["dedupe_hits"] == 1
    assert metrics["conflicts"] == []
    assert len(metrics["input_files"]) == 2
    assert metrics["last_build_ts"]
    assert len(metrics["hash_canonical"]) == 64

    state_file = Path(service.config.canonical_json).with_suffix(".state.json")
    assert state_file.exists()
    with open(state_file, "r", encoding="utf-8") as handle:
        persisted = json.load(handle)
    assert persisted["items_total"] == 1
