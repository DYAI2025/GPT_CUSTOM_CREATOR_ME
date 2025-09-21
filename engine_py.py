# engine_py.py  — CARL marker engine (Python) for ADA runtime
# Deterministic: patterns from carl/markers_canonical.json → events → features → indices → output
# No external deps (stdlib only). Compatible with JSON schemas you provided.

import json, re, hashlib, time, math, os
from typing import List, Dict, Any, Optional

ENGINE_VERSION = "CARL-PY-0.9"

# ---------- FS helpers ----------
def _read(path: str) -> str:
    for p in (path, f"./{path}", f"/mnt/data/{path}"):
        try:
            with open(p, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            continue
    raise FileNotFoundError(path)

def _load_json(path: str) -> dict:
    return json.loads(_read(path))

def _exists(path: str) -> bool:
    for p in (path, f"./{path}", f"/mnt/data/{path}"):
        if os.path.exists(p):
            return True
    return False

def _sha256_str(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

# ---------- Segmentation ----------
def segment_dialog(text: str) -> List[Dict[str, str]]:
    segs = []
    for line in (text or "").splitlines():
        if not line.strip():
            continue
        if ":" in line[:80]:
            lab, rest = line.split(":", 1)
            tag = lab.strip().lower()
            who = "A" if tag in ("a", "person a") else ("B" if tag in ("b", "person b") else "other")
            segs.append({"who": who, "text": rest.lstrip()})
        else:
            segs.append({"who": "other", "text": line.strip()})
    return segs

# ---------- Detection ----------
def _compile_patterns(markers: List[dict]):
    compiled = []
    flags = re.I | re.M | re.U
    for m in markers:
        pats = m.get("pattern") or []
        regs = [re.compile(p, flags) for p in pats]
        compiled.append((m, regs))
    return compiled

def _span_to_segment(pos: int, text_len: int, segments: List[dict]) -> int:
    if not segments or text_len <= 0:
        return 0
    ratio = pos / max(1, text_len)
    return min(len(segments) - 1, int(ratio * len(segments)))

def detect_events(text: str, segments: List[dict], canon: dict) -> List[dict]:
    events = []
    text_len = len(text or "")
    markers = canon.get("markers", [])
    # Backward compatibility: support both `pattern` and `regex`
    patt = []
    for m in markers:
        pats = list(m.get("pattern") or ([] if m.get("regex") is None else [m.get("regex")]))
        patt.append((m, pats))
    flags_default = re.I | re.M | re.U
    for m, patterns in patt:
        mtype = m.get("type")
        if mtype not in ("ATO", "SEM", "CLU", "MEMA", "DETECT"):
            continue
        flags = flags_default
        # allow marker-specific flags (e.g. "g", "i"): ignore "g", map "i" to re.I
        if isinstance(m.get("flags"), str):
            fl = m["flags"].lower()
            if "i" in fl:
                flags |= re.I
        for p in patterns:
            try:
                r = re.compile(p, flags)
            except Exception:
                continue
            for match in r.finditer(text):
                start, end = match.start(), match.end()
                seg_idx = _span_to_segment(start, text_len, segments)
                who = segments[seg_idx]["who"] if seg_idx is not None else "other"
                events.append({
                    "id": m["id"],
                    "type": mtype,
                    "span": {"start": start, "end": end},
                    "segment_idx": seg_idx or 0,
                    "who": who,
                    "evidence": (text[start:end])[:120]
                })
    events.sort(key=lambda e: e["span"]["start"])
    return events

# ---------- Promotion (ATO → SEM etc.) ----------
def promote_sem(events: List[dict], promo_map: dict):
    out = list(events)
    by_seg: Dict[int, List[dict]] = {}
    for ev in events:
        if ev["type"] == "ATO":
            by_seg.setdefault(ev["segment_idx"], []).append(ev)

    for rule in (promo_map.get("map") or []):
        promote_id = rule.get("promote")
        cond = rule.get("when", {})
        min_ATO = ((cond.get("segment_co_occurs") or {}).get("min_ATO")) or 2
        allowed = set(rule.get("from_ATO_ids") or [])
        for seg_idx, atos in by_seg.items():
            hits = [a for a in atos if (not allowed or a["id"] in allowed)]
            if len(hits) >= min_ATO:
                out.append({
                    "id": promote_id,
                    "type": "SEM",
                    "span": {"start": hits[0]["span"]["start"], "end": hits[-1]["span"]["end"]},
                    "segment_idx": seg_idx, "who": hits[-1]["who"],
                    "promotion_of": [h["id"] for h in hits]
                })
    out.sort(key=lambda e: e["span"]["start"])
    return out, []  # optional explicit promotion list

# ---------- Counts / Features ----------
def _build_counts(events: List[dict]) -> dict:
    total = {"ATO": 0, "SEM": 0, "CLU": 0, "MEMA": 0}
    by_speaker = {"A": {}, "B": {}}
    for ev in events:
        if ev["type"] in total:
            total[ev["type"]] += 1
        bs = by_speaker.setdefault(ev["who"], {})
        bs[ev["type"]] = bs.get(ev["type"], 0) + 1
    return {"total": total, "by_speaker": by_speaker}

def _features_from_counts(counts: dict, text_len: int) -> dict:
    perk = {k: (counts["total"].get(k, 0) / max(1, text_len / 1000.0)) for k in ("ATO", "SEM", "CLU", "MEMA")}
    caps = {"ATO": 10.0, "SEM": 6.0, "CLU": 4.0, "MEMA": 3.0}  # clip caps → [0..1]
    return {k: min(1.0, perk[k] / caps[k]) for k in perk}

# ---------- Indices ----------
def _normal_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2)))

def _compute_indices(features: dict, weights: dict) -> dict:
    idx = {}
    calib = weights.get("calib", {"mu": {}, "sigma": {}})
    for key in ("trust", "deesc", "conflict", "sync"):
        conf = (weights.get("indices") or {}).get(key) or {"w": {"ATO": 0, "SEM": 0, "CLU": 0, "MEMA": 0}, "bias": 0.0}
        w, bias = conf["w"], conf.get("bias", 0.0)
        raw = sum(w.get(t, 0.0) * features.get(t, 0.0) for t in ("ATO", "SEM", "CLU", "MEMA")) + bias
        mu = calib.get("mu", {}).get(key, 0.0)
        sigma = max(1e-9, calib.get("sigma", {}).get(key, 1.0))
        z = (raw - mu) / sigma
        p = _normal_cdf(z)
        idx[key] = {"raw": raw, "z": z, "p": p}
    return idx

# ---------- Packaging ----------
def _density(events: List[dict], text_len: int) -> dict:
    per = {k: 0.0 for k in ("ATO", "SEM", "CLU", "MEMA")}
    totals = _build_counts(events)["total"]
    for k in per.keys():
        per[k] = totals.get(k, 0) / max(1, text_len / 1000.0)
    return {"text_len": text_len, "per_1k_chars": per}

def _package_output(text: str, segments: List[dict], events: List[dict], indices: dict,
                    canon_hash: str, engine_hash: str, elapsed_ms: float) -> dict:
    text_len = len(text or "")
    counts = _build_counts(events)
    feats = _features_from_counts(counts, text_len)
    out = {
        "meta": {
            "input_hash": _sha256_str((text or "") + json.dumps(segments, ensure_ascii=False)),
            "canon_hash": canon_hash,
            "engine_hash": engine_hash,
            "elapsed_ms": int(elapsed_ms),
            "gated": False
        },
        "segments": segments,
        "markers": events,
        "promotion": [],
        "counts": counts,
        "density": _density(events, text_len),
        "features": feats,
        "indices": indices,
        "top_contributors": {"A": [], "B": []}
    }
    total_hits = sum(out["counts"]["total"].values())
    if total_hits < 5 or len(segments) < 2:
        out["meta"]["gated"] = True
        for v in out["indices"].values():
            v.pop("p", None)
    return out

# ---------- Public API ----------
def run(text: Optional[str] = None,
        segments: Optional[List[dict]] = None,
        canon_path: str = "carl/markers_canonical.json",
        promotion_path: str = "carl/promotion_mapping.json",
        weights_path: str = "carl/weights.json") -> dict:
    t0 = time.time()
    if segments is None:
        if text is None:
            raise ValueError("E_EMPTY_INPUT: provide text or segments")
        segments = segment_dialog(text)
    if text is None:
        text = "\n".join(s["text"] for s in segments)

    canon = _load_json(canon_path)
    promo = _load_json(promotion_path) if _exists(promotion_path) else {"map": []}
    weights = _load_json(weights_path)

    events = detect_events(text, segments, canon)
    events, promo_list = promote_sem(events, promo)

    canon_hash = _sha256_str(json.dumps(canon, ensure_ascii=False))
    engine_hash = _sha256_str(ENGINE_VERSION)

    indices = _compute_indices(_features_from_counts(_build_counts(events), len(text)), weights)
    out = _package_output(text, segments, events, indices, canon_hash, engine_hash, elapsed_ms=(time.time() - t0) * 1000)
    out["promotion"] = promo_list
    return out


