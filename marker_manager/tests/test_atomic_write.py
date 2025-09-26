import json
from pathlib import Path
import time

import yaml

from marker_manager.enginelib.marker_catalog import MarkerCatalog


def config(tmp_path: Path) -> dict:
    source_dir = tmp_path / "src"
    canonical = tmp_path / "out" / "markers_canonical.json"
    backup_dir = tmp_path / "out" / "backups"
    source_dir.mkdir()
    schema_file = Path(__file__).resolve().parents[1] / "schemas" / "schema.markers.json"
    return {
        "source_dir": str(source_dir),
        "canonical_json": str(canonical),
        "backup_dir": str(backup_dir),
        "schema_file": str(schema_file),
        "sort_key": "id",
        "id_required": True,
        "unknown_field_policy": "preserve_in.extras",
        "atomic_writes": True,
    }


def write_yaml(path: Path, payload):
    with open(path, "w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle)


def test_atomic_write_creates_backup(tmp_path):
    cfg = config(tmp_path)
    yaml_path = Path(cfg["source_dir"]) / "markers.yaml"

    write_yaml(yaml_path, [{"id": "one", "signal": "first"}])
    catalog = MarkerCatalog(cfg)
    result = catalog.sync()
    assert result.ok

    write_yaml(yaml_path, [{"id": "one", "signal": "updated"}])
    time.sleep(0.1)
    result = catalog.sync()
    assert result.ok

    backup_files = list(Path(cfg["backup_dir"]).glob("markers_canonical_*.json"))
    assert backup_files, "backup snapshot expected"

    with open(Path(cfg["canonical_json"]), "r", encoding="utf-8") as handle:
        data = json.load(handle)
    assert data[0]["signal"] == "updated"
