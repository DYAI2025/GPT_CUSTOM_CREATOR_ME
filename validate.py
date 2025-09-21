import json, sys
from pathlib import Path
import yaml
from jsonschema import validate, Draft7Validator

ROOT=Path(__file__).parent
SCHEMAS=ROOT/"schemas"; RES=ROOT/"resources"

# Schemata
def _j(p): return json.loads(Path(p).read_text(encoding="utf-8"))
def _y(p): return yaml.safe_load(Path(p).read_text(encoding="utf-8"))

def validate_profiles():
    schem=_j(SCHEMAS/"profile.schema.json"); ok=True
    for p in (RES/"profiles").glob("*.yaml"):
        data=_y(p); errs=sorted(Draft7Validator(schem).iter_errors(data), key=lambda e:e.path)
        if errs: ok=False; print(f"[FAIL] profile {p.name}:"); [print("  -",e.message) for e in errs]
        else: print(f"[OK]   profile {p.name}")
    return ok

def validate_schemata():
    ok=True; st=_j(SCHEMAS/"schema_text.schema.json"); sv=_j(SCHEMAS/"schema_voice.schema.json")
    for p in (RES/"schemata").glob("*.yaml"):
        data=_y(p); schema=sv if "VOICE" in p.stem else st
        errs=sorted(Draft7Validator(schema).iter_errors(data), key=lambda e:e.path)
        if errs: ok=False; print(f"[FAIL] schema {p.name}:"); [print("  -",e.message) for e in errs]
        else: print(f"[OK]   schema {p.name}")
    return ok

def validate_configs():
    ok=True
    # Model-registry und switch minimal prüfen
    try:
        reg=_j(RES/"config/Model-registry.json"); assert "models" in reg
        mids={m.get("id") for m in reg["models"]}
        print("[OK]   config Model-registry.json")
        sw=_j(RES/"config/model_switch_config.json")
        base=sw.get("dynamic_selection",{}).get("base"); assert base in mids or base is None
        for r in sw.get("dynamic_selection",{}).get("selection_criteria",[]): assert "model" in r
        print("[OK]   config model_switch_config.json")
    except Exception as e:
        ok=False; print(f"[FAIL] config registry/switch: {e}")
    
    # NEW: axes_map validation
    try: 
        _y(RES/"config/axes_map.yaml"); print("[OK]   axes_map.yaml")
    except Exception as e: 
        ok=False; print(f"[FAIL] axes_map.yaml: {e}")
    
    # scorings und lenses_map
    try: _y(RES/"scorings/scorings.yaml"); print("[OK]   scorings.yaml")
    except Exception as e: ok=False; print(f"[FAIL] scorings.yaml: {e}")
    try: _y(RES/"mappings/lenses_map.yaml"); _y(RES/"mappings/frame_mapping.yaml"); print("[OK]   mappings")
    except Exception as e: ok=False; print(f"[FAIL] mappings: {e}")
    return ok

def validate_required_files():
    req = [
      "resources/templates/OUTPUT_TEMPLATE_V3.yaml",
      "resources/templates/CHUNK_ANALYSE_V2.yaml",
      "resources/schemata/SCH_TEXT.yaml",
      "resources/profiles/default.yaml",
      "resources/config/Model-registry.json",
      "resources/config/model_switch_config.json",
      "resources/config/PROF_marker_axes.json",
      "resources/config/axes_map.yaml",
      "resources/mappings/lenses_map.yaml",
      "resources/scorings/scorings.yaml",
      "resources/manifest/MANIFEST.yaml",
      "resources/gates/gates.yaml",
      "resources/html/analyse.HTML"
    ]
    ok=True
    for r in req:
        if not (ROOT/r).exists(): ok=False; print(f"[FAIL] missing {r}")
        else: print(f"[OK]   found  {r}")
    return ok

def check_template_section_order():
    try:
        tpl=_y(RES/"templates/OUTPUT_TEMPLATE_V3.yaml")
        # Minimal: Abschnittsreihenfolge-Liste, falls vorhanden
        order = tpl.get("sections_order") or []
        if order and not isinstance(order, list): print("[FAIL] template order type"); return False
        print("[OK]   template sections order check")
        return True
    except Exception as e:
        print(f"[FAIL] template order: {e}"); return False

if __name__=="__main__":
    ok = all([ validate_profiles(), validate_schemata(), validate_configs(), validate_required_files(), check_template_section_order() ])
    print("[SUMMARY]", "OK" if ok else "FAIL"); sys.exit(0 if ok else 1)