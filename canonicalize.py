import os,json,sys,argparse
try:
    import yaml
except ImportError:
    sys.exit("PyYAML fehlt. pip install pyyaml")
ap=argparse.ArgumentParser()
ap.add_argument("--in",dest="src",required=True)
ap.add_argument("--out",dest="dst",default="./carl/markers_canonical.json")
a=ap.parse_args()
src=os.path.abspath(a.src); dst=os.path.abspath(a.dst)
items=[]
for dp,_,files in os.walk(src):
    for fn in files:
        if not fn.lower().endswith((".yaml",".yml")): continue
        p=os.path.join(dp,fn)
        try:
            data=yaml.safe_load(open(p,"r",encoding="utf-8")) or {}
        except Exception as e:
            print(f"SKIP {p}: {e}", file=sys.stderr); continue
        recs=data if isinstance(data,list) else [data]
        mt=os.path.getmtime(p)
        for r in recs:
            if isinstance(r,dict):
                r["_src"]=p; r["_mt"]=mt; items.append(r)
by_id={}
for r in items:
    i=r.get("id")
    if not i: continue
    if i not in by_id or r["_mt"]>by_id[i]["_mt"]:
        by_id[i]=r
canon=[{k:v for k,v in r.items() if k not in ("_src","_mt")}
       for _,r in sorted(by_id.items(), key=lambda kv: kv[0])]
os.makedirs(os.path.dirname(dst), exist_ok=True)
json.dump(canon, open(dst,"w",encoding="utf-8"), ensure_ascii=False, indent=2, default=str)
print("markers:", len(canon))
