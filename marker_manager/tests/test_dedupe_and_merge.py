import json
import time
from pathlib import Path

import yaml

from marker_manager.enginelib.marker_catalog import MarkerCatalog


def make_cfg(tmp_path: Path) -> dict:
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
        "atomic_writes": False,
    }


def test_dedupe_prefers_newer_file(tmp_path):
    cfg = make_cfg(tmp_path)
    dir_path = Path(cfg["source_dir"])
    first = dir_path / "marker_a.yaml"
    second = dir_path / "marker_b.yaml"

    with open(first, "w", encoding="utf-8") as handle:
        yaml.safe_dump({"id": "dup", "signal": "from first", "concept": "base"}, handle)
    time.sleep(0.1)
    with open(second, "w", encoding="utf-8") as handle:
        yaml.safe_dump({"id": "dup", "signal": "from second"}, handle)

    catalog = MarkerCatalog(cfg)
    result = catalog.sync()
    assert result.ok
    canonical_path = Path(cfg["canonical_json"])
    with open(canonical_path, "r", encoding="utf-8") as handle:
        canonical = json.load(handle)
    assert canonical[0]["signal"] == "from second"
    assert canonical[0]["concept"] == "base"


def test_conflicting_duplicate_raises(tmp_path):
    cfg = make_cfg(tmp_path)
    dir_path = Path(cfg["source_dir"])
    file_one = dir_path / "marker1.yaml"
    file_two = dir_path / "marker2.yaml"

    with open(file_one, "w", encoding="utf-8") as handle:
        yaml.safe_dump({"id": "conflict", "tags": ["first"]}, handle)
    time.sleep(0.1)
    with open(file_two, "w", encoding="utf-8") as handle:
        yaml.safe_dump({"id": "conflict", "tags": ["second"]}, handle)

    catalog = MarkerCatalog(cfg)
    result = catalog.sync()
    assert not result.ok
    assert any("Conflict" in message for message in result.errors)
    assert result.conflicts
