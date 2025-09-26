from pathlib import Path

import yaml

from marker_manager.gui import create_app
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
    config_payload = {
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
        yaml.safe_dump(config_payload, handle)
    return config_path


def test_gui_upload_and_status(tmp_path):
    config_path = write_config(tmp_path)
    service = MarkerManagerService(config_path)
    app = create_app(service)
    client = app.test_client()

    payload = {
        "filename": "upload.yaml",
        "content": "- id: gui\n  signal: via gui\n"
    }
    response = client.post("/api/paste", json=payload)
    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"]

    status = client.get("/api/status").get_json()
    assert status["result"]["count"] == 1
    metrics = status["metrics"]
    assert metrics["items_total"] == 1
    assert metrics["dedupe_hits"] == 0
    assert metrics["hash_canonical"]
    assert metrics["input_files"]
    assert Path(metrics["input_files"][0]).name == "upload.yaml"
    assert metrics["last_build_ts"] is not None

    diff = client.get("/api/diff").get_json()
    assert "patch" in diff
