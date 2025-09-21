from pathlib import Path
from enginelib.runtime import EngineRuntime
import json

def test_payload_shape():
    root=Path(__file__).resolve().parents[1]
    eng=EngineRuntime(root)
    data={"model":"x","axes":[],"result":{"summary":{"top_clusters":[["SUPPORT",1.0]],"drift":{}},"details":{"sem":[],"clu":[]}},"telemetry":{}}
    data["engine_result"]={"indices":{},"drift_axes":{"values":{},"trend":{}},"heatmap":[],"balance":{},"gaps_silence":{},"needs_attachment":{},"change_points":[],"validity":{},"meta":{}}
    html = eng.render_html(root/"resources/html/analyse.HTML", data)
    assert "ANALYSIS_DATA" in html