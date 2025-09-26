import json
from pathlib import Path

import jsonschema
import yaml

from marker_manager.enginelib.marker_catalog import MarkerCatalog


def create_config(tmp_path: Path) -> dict:
    source_dir = tmp_path / "yaml"
    canonical = tmp_path / "canonical" / "markers_canonical.json"
    backup_dir = tmp_path / "canonical" / "backups"
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


def test_yaml_to_canonical_roundtrip(tmp_path):
    cfg = create_config(tmp_path)
    yaml_path = Path(cfg["source_dir"]) / "markers.yaml"
    yaml_payload = [
        {
            "id": "alpha",
            "signal": "Alpha signal",
            "concept": "Core concept",
            "pragmatics": "Pragmatic note",
            "narrative": "Narrative detail",
            "tags": ["focus", "alpha"],
            "custom_field": "will land in extras",
        }
    ]
    with open(yaml_path, "w", encoding="utf-8") as handle:
        yaml.safe_dump(yaml_payload, handle)

    catalog = MarkerCatalog(cfg)
    result = catalog.sync()
    assert result.ok
    assert result.count == 1

    canonical_path = Path(cfg["canonical_json"])
    with open(canonical_path, "r", encoding="utf-8") as handle:
        canonical = json.load(handle)

    schema_path = Path(cfg["schema_file"])
    with open(schema_path, "r", encoding="utf-8") as handle:
        schema = json.load(handle)
    jsonschema.validate(canonical, schema)

    entry = canonical[0]
    assert entry["extras"]["custom_field"] == "will land in extras"
    assert entry["tags"] == ["alpha", "focus"] or entry["tags"] == ["focus", "alpha"]
