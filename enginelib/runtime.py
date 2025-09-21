from dataclasses import dataclass, field
from typing import List, Dict, Any, Tuple
from pathlib import Path
import importlib.util, yaml, time, json, hashlib

# --- Selftest und Gates ---
REQUIRED = [
    "resources/markers_canonical.json",
    "resources/templates/OUTPUT_TEMPLATE_V3.yaml",
    "enginelib/runtime.py",
]
def selftest(root: Path) -> tuple[bool, str]:
    try:
        for rel in REQUIRED:
            if not (root/rel).exists():
                return (False, "E_NO_CANON" if "markers_canonical" in rel else "E_RUNTIME_UNAVAILABLE")
        return (True, "OK")
    except Exception:
        return (False, "E_ENGINE_FAIL")

def enforce_gates(hits, segments, gates: dict) -> None:
    if len(segments) < int(gates.get("min_segments", 2)): raise RuntimeError("E_GATE_BLOCKED")
    if len(hits)     < int(gates.get("min_total_markers", 5)): raise RuntimeError("E_GATE_BLOCKED")

# --- Datenklassen ---
@dataclass
class MarkerHit:
    name: str
    family: str
    span: Tuple[int,int]
    score: float
    meta: Dict[str, Any] = field(default_factory=dict)

@dataclass
class AnalysisResult:
    segments: List[str]
    hits_ato: List[MarkerHit]
    hits_sem: List[MarkerHit]
    hits_clu: List[MarkerHit]
    hits_mema: List[MarkerHit]
    drift: Dict[str, Any]
    telemetry: Dict[str, Any]

class EngineRuntime:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.plugins_dir = self.root / "plugins"
        self.resources = self.root / "resources"
        self.telemetry: Dict[str,Any] = {}
        # Weights/Promotion laden
        cfg_dir = self.root/"resources/config"
        self.cfg = {
            "weights": self._safe_yaml(cfg_dir/"weights.yaml") or {},
            "promotion": self._safe_yaml(cfg_dir/"promotion_mapping.yaml") or {},
            "gates": self._safe_yaml(self.root/"resources/gates/gates.yaml") or {}
        }
        
        # NEW: Additional config loading
        self.cfg.update({
            "axes_map": self._safe_yaml(cfg_dir/"axes_map.yaml") or {},
            "scorings": self._safe_yaml(self.root/"resources/scorings/scorings.yaml") or {},
            "lenses_map": self._safe_yaml(self.root/"resources/mappings/lenses_map.yaml") or {},
        })
        
        # Drift-Adapter optional
        try:
            from extensions.drift.ewma_adapter import ewma_update
            self.ewma_update = ewma_update
        except Exception:
            self.ewma_update = lambda key,v: v
        try:
            from extensions.drift.drift_metrics_adapter import calc_drift_metrics
            self.calc_drift_metrics = calc_drift_metrics
        except Exception:
            self.calc_drift_metrics = lambda vectors: {}

    def _safe_yaml(self, p: Path):
        try:
            if p.exists(): return yaml.safe_load(p.read_text(encoding="utf-8"))
        except Exception: pass
        return None

    # Segmentierung
    def segment(self, text: str, schema: Dict) -> List[str]:
        size = int(schema.get("chunk_size", 1400))
        return [text[i:i+size] for i in range(0, len(text), size)] or [text]

    # Plugins
    def _plugins(self):
        mods = []
        for p in sorted(self.plugins_dir.glob("detect_*.py")):
            spec = importlib.util.spec_from_file_location(p.stem, p)
            mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)  # type: ignore
            if hasattr(mod, "detect"): mods.append(mod)
        return mods

    # Detect ATO
    def detect_markers(self, segments: List[str]) -> List[MarkerHit]:
        hits=[]
        for i, seg in enumerate(segments):
            for mod in self._plugins():
                for h in mod.detect(seg) or []:
                    h.meta["segment"]=i; hits.append(h)
        return hits

    # SEM (≥2 ATO je Familie)
    def compose_sem(self, hits_ato: List[MarkerHit], window: int = 2) -> List[MarkerHit]:
        sem, buckets = [], {}
        for h in hits_ato: buckets.setdefault((h.family, h.meta.get("segment",0)), []).append(h)
        fam_w = (self.cfg["weights"] or {}).get("families", {})
        for (fam,_), hs in buckets.items():
            if len(hs) >= window:
                s = sum(x.score for x in hs)/len(hs)
                s *= float(fam_w.get(fam, 1.0))
                sem.append(MarkerHit(name=f"SEM_{fam}_EVIDENCE", family=fam, span=(0,0), score=min(1.0,s)))
        return sem

    # CLU (X-of-Y)
    def cluster_clu(self, sem_hits: List[MarkerHit], x=2, y=3) -> List[MarkerHit]:
        by_fam, clu = {}, []
        fam_w = (self.cfg["weights"] or {}).get("families", {})
        for h in sem_hits: by_fam.setdefault(h.family, []).append(h)
        for fam, hs in by_fam.items():
            if len(hs) >= x:
                score=min(1.0, len(hs)/max(1,y)) * float(fam_w.get(fam,1.0))
                name = self.cfg["promotion"].get(fam, {}).get("clu_name", f"CLU_{fam}")
                clu.append(MarkerHit(name=name, family=fam, span=(0,0), score=score))
        return clu

    # MEMA
    def mema(self, clu_hits: List[MarkerHit]) -> List[MarkerHit]:
        return [MarkerHit(name=f"MEMA_{h.family}", family=h.family, span=h.span, score=h.score, meta=h.meta) for h in clu_hits]

    # Intuition/Telemetry
    def intuition(self, hits: List[MarkerHit], profile: Dict) -> List[MarkerHit]:
        cw = int(profile.get("intuition", {}).get("confirm_window", 6))
        mult = float(profile.get("intuition", {}).get("multiplier_on_confirm", 1.25))
        now = time.time(); out=[]
        for h in hits:
            key=f"{h.family}.counter_confirmed"
            self.telemetry[key]=self.telemetry.get(key,0)+1
            self.telemetry[f"{h.family}.confirm_window"]=cw
            self.telemetry[f"{h.family}.last_ts"]=now
            self.telemetry[f"{h.family}.ewma_precision"]=self.ewma_update(f"{h.family}.ewma_precision", h.score)
            h.score=min(1.0, h.score*mult); out.append(h)
        return out

    # Drift
    def compute_drift(self, hits: List[MarkerHit]) -> Dict[str,Any]:
        vectors=[{"dimensions":[h.score,1-h.score,0.0],"timestamp":time.time(),"magnitude":h.score,"marker_weights":{h.name:h.score}} for h in hits]
        return self.calc_drift_metrics(vectors)

    # ---- NEW: helpers for indices, lenses, heatmap, drift-axes, validity ----
    def _norm(self, x, lo=-1.0, hi=1.0):
        return max(lo, min(hi, x))

    def _pick_quotes(self, text_segments, hits, k=2):
        out=[]
        for h in hits[:k]:
            seg=text_segments[h.meta.get("segment",0)]
            out.append(seg[:160])
        return out

    def _bucket_heatmap(self, text, hits, bucket=500):
        buckets=[{"start":i,"end":min(i+bucket,len(text)),"dens":{"SEM":0,"CLU":0,"MEMA":0}} for i in range(0,len(text),bucket)]
        for h in hits:
            b=min(len(buckets)-1, (h.span[0]*bucket)//max(bucket,1)) if isinstance(h.span,(tuple,list)) else 0
            t=("SEM" if h.name.startswith("SEM_") else "CLU" if h.name.startswith("CLU_") else "MEMA")
            buckets[b]["dens"][t]+=1
        return buckets

    def _aggregate_lenses(self, hits, lenses_map):
        lens_score={}
        for h in hits:
            for ln in lenses_map.get(h.family, []):
                lens_score[ln]=lens_score.get(ln,0.0)+h.score
        return [{"lens":k,"score":v} for k,v in sorted(lens_score.items(), key=lambda x:-x[1])]

    def _indices_with_contrib(self, hits, scorings):
        # CAND_* nicht zählen
        core=[h for h in hits if not h.name.startswith("CAND_")]
        fam_sum={}
        for h in core: fam_sum[h.family]=fam_sum.get(h.family,0.0)+h.score
        out={}
        contrib={}
        for idx, spec in scorings.items():
            s=0.0; parts=[]
            for fam,w in spec.get("families",{}).items():
                v=fam_sum.get(fam,0.0)*float(w); s+=v
                if v!=0: parts.append({"family":fam,"weighted":v})
            out[idx]=self._norm(s)
            contrib[idx]=sorted(parts, key=lambda x:-abs(x["weighted"]))[:5]
        return out, contrib

    def _drift_axes(self, hits, axes_map):
        fam_sum={}
        for h in hits: fam_sum[h.family]=fam_sum.get(h.family,0.0)+h.score
        axes={}
        for axis, weights in axes_map.items():
            val=sum(fam_sum.get(f,0.0)*w for f,w in weights.items())
            axes[axis]=self._norm(val)
        # naive Trend: sign der Summe
        trend={a: ("steigt" if v>0.2 else "fällt" if v<-0.2 else "stabil") for a,v in axes.items()}
        return axes, trend

    def _balance(self, hits):
        # nutzt speaker-Meta, wenn vorhanden
        sp={}
        for h in hits:
            s=h.meta.get("speaker")
            if s: sp[s]=sp.get(s,0)+1
        if not sp: return {}
        total=sum(sp.values())
        ratios={k: v/total for k,v in sp.items()}
        return {"initiative_vs_support": ratios, "talk_time_ratio": ratios}

    def _gaps_silence(self):
        return {"unanswered_turns":0,"latency_peaks":0,"reassurance_flags":0}

    def _needs_attachment(self, hits):
        u=sum(h.score for h in hits if h.family=="UNCERTAINTY")
        s=sum(h.score for h in hits if h.family=="SUPPORT")
        idx=self._norm(u - 0.3*s)
        return {"unsaid_need_index": idx, "attachment_vector": {"seek": self._norm(s), "avoid": self._norm(u)}}

    def _change_points(self, hits):
        # Platzhalter: nimm Beginn/Ende der ersten 2 CLU
        cps=[]
        for h in [x for x in hits if x.name.startswith("CLU_")][:2]:
            cps.append({"timestamp_or_seq": h.meta.get("segment",0), "involved_markers":[h.name], "micro_narrative_1liner":"Übergang erkannt"})
        return cps

    def _validity(self, hits, segments, gates):
        counts=sum(1 for _ in hits)
        note="ok" if counts>=gates.get("min_total_markers",5) and len(segments)>=gates.get("min_segments",2) else "gate_blocked"
        return {"counts_vs_rawlog": counts, "sliding_window_confirm": True, "gate_note": note}

    # HTML-Hook
    def render_html(self, template_path: Path, analysis_data: dict) -> str:
        html = template_path.read_text(encoding="utf-8")
        payload = f"<script>window.ANALYSIS_DATA={json.dumps(analysis_data, ensure_ascii=False)};</script>"
        return html.replace("<!--__INJECT_ANALYSIS_DATA__-->", payload)

    # Render Dict with lenses
    def render(self, result: AnalysisResult, template: Dict, profile: Dict) -> Dict:
        top = sorted({h.family: h.score for h in result.hits_clu}.items(), key=lambda x: -x[1])[:5]
        lens = self._aggregate_lenses(result.hits_clu, self.cfg.get("lenses_map",{}))
        return {"summary":{"top_clusters": top, "drift": result.drift, "lenses": lens},
                "details":{"sem":[h.__dict__ for h in result.hits_sem],
                           "clu":[h.__dict__ for h in result.hits_clu],
                           "mema":[h.__dict__ for h in result.hits_mema]}}

    # Pipeline
    def analyse(self, text: str, profile: Dict, schema: Dict, axes: list) -> AnalysisResult:
        ok, code = selftest(self.root)
        if not ok: raise RuntimeError(code)
        segs=self.segment(text, schema)
        a=self.detect_markers(segs)
        s=self.compose_sem(a, profile.get("gates",{}).get("sem_compose_window",2))
        c=self.cluster_clu(s, profile.get("gates",{}).get("clu_x",2), profile.get("gates",{}).get("clu_y",3))
        enforce_gates(c, segs, self.cfg.get("gates", {}))
        m=self.mema(c); f=self.intuition(m, profile); d=self.compute_drift(f)
        
        # ENGINE_RESULT erweitern
        indices, contributors = self._indices_with_contrib(f, self.cfg.get("scorings",{}))
        axes, trend = self._drift_axes(f, self.cfg.get("axes_map", {}))
        heatmap = self._bucket_heatmap("".join(segs), f, 500)
        balance = self._balance(f)
        gaps = self._gaps_silence()
        needs = self._needs_attachment(f)
        cpoints = self._change_points(f)
        valid = self._validity(f, segs, self.cfg.get("gates", {}))
        # packe Extras in telemetry, damit orchestrator sie hat
        self.telemetry.update({
          "_indices": indices,
          "_contributors": contributors,
          "_drift_axes": {"values": axes, "trend": trend},
          "_balance": balance,
          "_heatmap": heatmap,
          "_gaps_silence": gaps,
          "_needs_attachment": needs,
          "_change_points": cpoints,
          "_validity": valid
        })
        
        return AnalysisResult(segs, a, s, f, m, d, telemetry=self.telemetry)