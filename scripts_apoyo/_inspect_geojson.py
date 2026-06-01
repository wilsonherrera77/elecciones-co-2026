"""Inspecciona el geojson unificado para identificar las llaves de join."""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
d = json.load((ROOT / "data" / "processed" / "colombia_municipios.geojson").open(encoding="utf-8"))
feats = d["features"]
print(f"features totales: {len(feats)}")
print(f"feature[0] keys: {list(feats[0].keys())}")
print(f"feature[0] geometry.type: {feats[0]['geometry']['type']}")
print(f"feature[0] properties: {feats[0]['properties']}")
print()
print(f"features por depto: {dict(sorted(Counter(f['properties'].get('_depto_codigo','?') for f in feats).items()))}")
print()
print("Sample 5 deptos distintos:")
seen = set()
for f in feats:
    dep = f["properties"].get("_depto_codigo")
    if dep not in seen and len(seen) < 5:
        seen.add(dep)
        print(f"  depto {dep}: {f['properties']}")
