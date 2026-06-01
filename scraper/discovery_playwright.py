"""discovery_playwright.py · descubre las URLs reales que carga el SPA.

Lanza Chromium, navega a https://resultados.registraduria.gov.co/,
intercepta todas las requests XHR/fetch, y guarda en data/raw/_discovery.json
el patrón base URL + ejemplos concretos para cada scope_code visitado.

También guarda los headers exactos que envía el browser, para que fetch_estatico.py
los replique y pase el WAF.

Uso:
    python scraper/discovery_playwright.py
    python scraper/discovery_playwright.py --headed   # ver el browser
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, PROJECT_ROOT.as_posix())

from scraper.db import connect  # noqa: E402

BASE = "https://resultados.registraduria.gov.co"
OUT = PROJECT_ROOT / "data" / "raw" / "_discovery.json"

JSON_PATH_RE = re.compile(r"/json/(ACT|INI|HIST|EST)/")


def main(headed: bool, max_seconds: int) -> int:
    captured: list[dict] = []
    last_headers: dict[str, str] = {}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not headed)
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="es-CO",
            viewport={"width": 1366, "height": 900},
        )
        page = ctx.new_page()

        def on_response(resp):
            url = resp.url
            if JSON_PATH_RE.search(url):
                try:
                    body_len = len(resp.body())
                except Exception:
                    body_len = -1
                captured.append({
                    "url": url,
                    "status": resp.status,
                    "method": resp.request.method,
                    "headers": dict(resp.request.headers),
                    "bytes": body_len,
                })
                # nos quedamos con los últimos headers de un 200
                if resp.status == 200:
                    last_headers.clear()
                    last_headers.update(dict(resp.request.headers))

        page.on("response", on_response)

        print(f"[discovery] navegando a {BASE}/ ...")
        page.goto(BASE + "/", wait_until="networkidle", timeout=30000)
        time.sleep(3)

        # intentar navegar a un departamento (Antioquia)
        target_routes = [
            "/resultados/0/01/",      # Antioquia
            "/resultados/0/01004/",   # Abejorral (municipio)
            "/resultados/0/16/",      # Bogotá
        ]
        for r in target_routes:
            url = BASE + r
            print(f"[discovery] navegando a {url}")
            try:
                page.goto(url, wait_until="networkidle", timeout=20000)
                time.sleep(2)
            except Exception as e:
                print(f"  warn: {type(e).__name__}: {e}")

        time.sleep(2)
        ctx.close()
        browser.close()

    OUT.parent.mkdir(parents=True, exist_ok=True)

    # Analiza patrón
    urls_200 = sorted({c["url"] for c in captured if c["status"] == 200})
    urls_other = sorted({(c["url"], c["status"]) for c in captured if c["status"] != 200})

    patterns: dict[str, list[str]] = {"ACT": [], "INI": [], "HIST": [], "EST": []}
    for u in urls_200:
        m = JSON_PATH_RE.search(u)
        if m:
            patterns[m.group(1)].append(u)

    out = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "base": BASE,
        "headers_sample": last_headers,
        "endpoint_patterns": {
            "ACT": "/json/ACT/{electionSiglas}/{scopeCode}",
            "INI": "/json/INI/{electionSiglas}/{scopeCode}",
            "HIST": "/json/HIST/{departmentCode}/{electionSiglas}/{advance}/{scopeCode}",
            "EST": "/json/EST/{electionSiglas}/{statCode}",
        },
        "samples_200": urls_200[:30],
        "samples_non_200": urls_other[:20],
        "total_captured": len(captured),
    }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")

    print(f"\n[discovery] guardado en {OUT.relative_to(PROJECT_ROOT)}")
    print(f"  total requests JSON capturadas: {len(captured)}")
    print(f"  URLs 200 únicas: {len(urls_200)}")
    print(f"  URLs no-200 únicas: {len(urls_other)}")
    if urls_200:
        print("\n  ejemplos 200:")
        for u in urls_200[:8]:
            print(f"    - {u}")
    if urls_other:
        print("\n  ejemplos no-200:")
        for u, s in urls_other[:5]:
            print(f"    - {s} {u}")

    # Persiste a la tabla discovery_meta
    con = connect()
    con.execute("DELETE FROM discovery_meta WHERE key LIKE 'discovery%';")
    con.execute("INSERT INTO discovery_meta (key, value) VALUES (?, ?)",
                ["discovery_json", json.dumps(out)])
    con.close()

    # Si captura algún 200 en /json/ACT exit 0, si no exit 2 (warning)
    return 0 if patterns["ACT"] or patterns["INI"] else 2


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--headed", action="store_true", help="muestra el browser")
    ap.add_argument("--max-seconds", type=int, default=30)
    args = ap.parse_args()
    sys.exit(main(args.headed, args.max_seconds))
