from pathlib import Path
from orchestrator import ProjectGPT, E_NO_CANON, E_ENGINE_FAIL, E_SCHEMA_VIOLATION, E_GATE_BLOCKED, E_RUNTIME_UNAVAILABLE

def test_no_canon(tmp_path):
    root=Path(__file__).resolve().parents[1]
    canon=root/"resources/markers_canonical.json"
    backup=canon.read_text(encoding="utf-8")
    canon.unlink()
    try:
        code,_=ProjectGPT(root).start_routine("x")
        assert code in {E_NO_CANON}
    finally:
        canon.write_text(backup, encoding="utf-8")

def test_schema_violation():
    root=Path(__file__).resolve().parents[1]
    pg=ProjectGPT(root)
    code,_=pg._run_with("x", "default", schema={"name":"SCH_TEXT","chunk_size":0})
    assert code==E_SCHEMA_VIOLATION

def test_engine_fail(monkeypatch):
    root=Path(__file__).resolve().parents[1]
    pg=ProjectGPT(root)
    def boom(*a,**k): raise RuntimeError("boom")
    monkeypatch.setattr(pg.engine, "analyse", boom)
    code,_=pg._run_with("x","default")
    assert code==E_ENGINE_FAIL