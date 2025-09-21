# carl_runtime.py — injects ANALYSIS_DATA into analyse.HTML and displays it in ADA.
# Uses only IPython.display (works in ChatGPT ADA). Benchmarks optional.

import json, os
from IPython.display import HTML, display  # ADA can render HTML via IPython display. 

def _read(path: str) -> str:
    for p in (path, f"./{path}", f"/mnt/data/{path}"):
        try:
            with open(p, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            continue
    raise FileNotFoundError(path)

def _exists(path: str) -> bool:
    for p in (path, f"./{path}", f"/mnt/data/{path}"):
        if os.path.exists(p):
            return True
    return False

def _pct_from_score(s):
    if not isinstance(s, dict):
        return None
    if "p" in s:
        return int(round(max(0.0, min(1.0, s["p"])) * 100))
    return int(round(max(0.0, min(1.0, s.get("raw", 0.0))) * 100))

def build_dashboard_payload(engine_output: dict) -> dict:
    counts = engine_output.get("counts", {})
    features = engine_output.get("features", {})
    indices = engine_output.get("indices", {})
    # Individuals (simple top-4 per speaker)
    def top_for(sp):
        bs = counts.get("by_speaker", {}).get(sp, {})
        arr = [{"key": k, "score": v} for k, v in bs.items()]
        arr.sort(key=lambda x: -x["score"])
        return arr[:4]
    individuals = {
        "A": {"name": "Person A", "notes": "–", "top_markers": top_for("A")},
        "B": {"name": "Person B", "notes": "–", "top_markers": top_for("B")}
    }
    overview = {
        "indices": {
            "trust": _pct_from_score(indices.get("trust")),
            "deesc": _pct_from_score(indices.get("deesc")),
            "conflict": _pct_from_score(indices.get("conflict")),
            "sync": _pct_from_score(indices.get("sync"))
        },
        "summary": ""
    }
    phases = [{
        "title": "Phase 1",
        "narrative": "—",
        "cards": [{"label": k, "percent": min(100, int(v * 100)), "desc": ""} for k, v in features.items()]
    }]
    data = {
        "meta": {"title": "Emotionale Reise", "subtitle": "Markerbasierte Auswertung"},
        "phases": phases,
        "overview": overview,
        "individuals": individuals,
        "system": {"name": "Person A ↔ Person B", "drivers": [], "consequences": []},
        "change": {"A": [], "B": [], "shared": []},
        "closing": {"what": "", "attach": "", "total": ""}
    }
    return data

def render_html(engine_output: dict,
                html_path: str = "carl/analyse.HTML",
                benchmarks_path: str = "carl/benchmarks.json") -> None:
    tpl = _read(html_path)
    display(HTML(tpl))
    payload = build_dashboard_payload(engine_output)
    inj = f"<script>window.ANALYSIS_DATA = {json.dumps(payload, ensure_ascii=False)}; if(window.renderDashboard) window.renderDashboard();</script>"
    display(HTML(inj))
    if _exists(benchmarks_path):
      bench = _read(benchmarks_path)
      bs = f"<script>if(window.applyPairBenchmarks) window.applyPairBenchmarks({bench});</script>"
      display(HTML(bs))


