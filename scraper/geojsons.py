"""geojsons.py · baja /maps/<codigo>.geojson para Colombia + 34 deptos + opcionalmente mpios.

Modo `nacional` (default): baja 1 geojson nacional con polígonos por DEPARTAMENTO.
Modo `departamentos`: baja los 34 geojsons departamentales con polígonos por MUNICIPIO,
                      y los unifica en `data/processed/colombia_municipios.geojson`.

Uso:
    python -m scraper.geojsons --modo nacional
    python -m scraper.geojsons --modo departamentos
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, PROJECT_ROOT.as_posix())

from scraper.db import connect  # noqa: E402

BASE = "https://resultados.registraduria.gov.co"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": BASE + "/",
    "Accept": "application/json, */*",
}

OUT_DIR = PROJECT_ROOT / "data" / "raw" / "geojsons"


async def fetch_one(client: httpx.AsyncClient, codigo: str) -> tuple[str, int, bytes]:
    url = f"{BASE}/maps/{codigo}.geojson"
    try:
        r = await client.get(url, timeout=20)
        return codigo, r.status_code, r.content
    except Exception as e:  # noqa: BLE001
        return codigo, -1, str(e).encode()


async def fetch_all(codigos: list[str]) -> list[tuple[str, int, bytes]]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(http2=True, headers=HEADERS) as client:
        sem = asyncio.Semaphore(10)

        async def w(c):
            async with sem:
                return await fetch_one(client, c)

        return await asyncio.gather(*[w(c) for c in codigos])


def main(modo: str) -> int:
    con = connect(read_only=True)
    if modo == "nacional":
        codigos = ["00"]
    elif modo == "departamentos":
        codigos = ["00"] + [r[0] for r in con.execute(
            "SELECT codigo_interno FROM divipola_2026 WHERE level=2 ORDER BY codigo_interno"
        ).fetchall()]
    else:
        print(f"modo desconocido: {modo}")
        return 1
    con.close()

    print(f"[geojsons] bajando {len(codigos)} archivos · modo={modo}")
    t0 = time.monotonic()
    results = asyncio.run(fetch_all(codigos))
    dt = time.monotonic() - t0

    ok = 0
    nodata: list[str] = []
    for c, status, body in results:
        if status == 200:
            (OUT_DIR / f"{c}.geojson").write_bytes(body)
            ok += 1
        else:
            nodata.append(f"{c}:{status}")
    print(f"[geojsons] ok={ok}/{len(codigos)} · {dt:.1f}s")
    if nodata:
        print(f"  no-200: {nodata[:8]}")

    if modo == "departamentos":
        # Unifica todos los deptos en un solo FeatureCollection nacional
        all_features = []
        for c, status, _ in results:
            if status != 200 or c == "00":
                continue
            data = json.loads((OUT_DIR / f"{c}.geojson").read_text(encoding="utf-8"))
            for feat in data.get("features", []):
                # Anota el código de depto en properties para join futuro
                feat.setdefault("properties", {})["_depto_codigo"] = c
                all_features.append(feat)
        out_unified = PROJECT_ROOT / "data" / "processed" / "colombia_municipios.geojson"
        out_unified.write_text(json.dumps({"type": "FeatureCollection", "features": all_features}),
                                encoding="utf-8")
        print(f"[geojsons] unificado: {out_unified.relative_to(PROJECT_ROOT)} · "
              f"{len(all_features)} features")

    return 0 if ok == len(codigos) else 2


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--modo", choices=["nacional", "departamentos"], default="departamentos")
    sys.exit(main(ap.parse_args().modo))
