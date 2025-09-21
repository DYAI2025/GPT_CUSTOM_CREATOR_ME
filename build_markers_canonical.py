# build_markers_canonical.py  — LeanDeep 3.4 → carl/markers_canonical.json
# Fixes: handles YAML/JSON, skips __MACOSX & ._ AppleDouble, infers missing types.

import json, zipfile, os, sys
from pathlib import Path

try:
    import yaml  # PyYAML
    _HAS_YAML = True
except Exception:
    _HAS_YAML = False

SRC_ZIP = "Marker_LeanDeep3.4.zip"
OUT_PATH = Path("carl/markers_canonical.json")
LD_SPEC = "LeanDeep 3.4"
VALID_TYPES = {"ATO","SEM","CLU","MEMA"}

def _skip(name: str) -> bool:
    base = os.path.basename(name)
    return (
        name.startswith("__MACOSX/")    # macOS metadata tree
        or base.startswith("._")         # AppleDouble sidecar
        or base == ".DS_Store"
        or base.lower().endswith(".md")  # docs
    )

def _infer_type_from_path(name: str):
    # Examples: SEM_SCENE_DESCRIPTION.yaml, SEM_semantic/xyz.yaml, ATO_x.json
    base = os.path.basename(name)
    head = base.split(".",1)[0]
    cand = head.split("_",1)[0].upper()
    if cand in VALID_TYPES: return cand
    # fallback: check parent folder
    parts = [p.upper() for p in name.split("/")]
    for p in parts:
        if p in VALID_TYPES:
            return p
        if p.startswith("SEM_"): return "SEM"
        if p.startswith("ATO_"): return "ATO"
        if p.startswith("CLU_"): return "CLU"
        if p.startswith("MEMA_"): return "MEMA"
    return None

def _normalize_marker(m: dict, src_name: str):
    mid = m.get("id") or m.get("name")
    mtype = m.get("type") or _infer_type_from_path(src_name)
    if not mid or mtype not in VALID_TYPES:
        return None
    return {
        "id": mid,
        "type": mtype,
        "activation": m.get("activation") or {"rule": "ANY", "params": {"window": 0}},
        "pattern": list(m.get("pattern") or m.get("patterns") or []),
        "tags": list(m.get("tags") or []),
        "composed_of": list(m.get("composed_of") or []),
        "examples": list(m.get("examples") or [])
    }

def _load_one_member(zf: zipfile.ZipFile, name: str):
    data = zf.read(name)
    if name.lower().endswith((".json",".ldjson")):
        try:
            return json.loads(data.decode("utf-8"))
        except Exception:
            return None
    if name.lower().endswith((".yaml",".yml")) and _HAS_YAML:
        try:
            obj = yaml.safe_load(data.decode("utf-8", errors="ignore"))
            return obj
        except Exception:
            return None
    return None

def main():
    if not Path(SRC_ZIP).exists():
        print(f"[ERR] {SRC_ZIP} nicht gefunden (ins Arbeitsverzeichnis legen).")
        sys.exit(2)
    if not _HAS_YAML:
        print("[INFO] PyYAML nicht gefunden — YAML wird übersprungen. Installiere mit:")
        print("       python3 -m pip install pyyaml")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    seen, out = set(), []
    counts = {"ATO":0,"SEM":0,"CLU":0,"MEMA":0}
    total_raw = 0

    with zipfile.ZipFile(SRC_ZIP, "r") as z:
        for name in z.namelist():
            if _skip(name): 
                continue
            if not name.lower().endswith((".json",".ldjson",".yaml",".yml")):
                continue
            payload = _load_one_member(z, name)
            if payload is None:
                continue
            items = payload if isinstance(payload, list) else [payload]
            for m in items:
                total_raw += 1
                nm = _normalize_marker(m or {}, name)
                if not nm:
                    # silently skip invalid
                    continue
                if nm["id"] in seen:
                    continue
                seen.add(nm["id"]); out.append(nm)
                if nm["type"] in counts: counts[nm["type"]] += 1

    out.sort(key=lambda x: (x["type"], x["id"]))
    doc = {"ld_spec": LD_SPEC, "version": "0.9", "markers": out}
    OUT_PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")

    total = len(out)
    print(f"[OK] geschrieben: {OUT_PATH} | Marker gesamt: {total} "
          f"(ATO={counts['ATO']}, SEM={counts['SEM']}, CLU={counts['CLU']}, MEMA={counts['MEMA']}; Roh={total_raw})")

if __name__ == "__main__":
    main()
