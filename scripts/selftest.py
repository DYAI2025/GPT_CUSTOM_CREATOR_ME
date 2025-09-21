from pathlib import Path
from enginelib.runtime import EngineRuntime, selftest as rt_selftest
root=Path(__file__).resolve().parents[1]
ok, code = rt_selftest(root)
print(f"Selbsttest: {code}")
exit(0 if ok else 1)