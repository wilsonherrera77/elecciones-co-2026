"""elecciones_doctor · health check del proyecto.

Verifica:
- Python 3.11+
- Dependencias instaladas
- Conectividad a Registraduría con headers Chrome (HTTP 200 en endpoints JSON)
- Ollama up + modelo qwen2.5:14b disponible
- Espacio en disco >= 2 GB
- Acceso de escritura a data/raw, data/processed, logs

Exit 0 si todo OK · exit 1 si alguna falla.
Uso: `python -m scripts_apoyo.elecciones_doctor`
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REGISTRADURIA_BASE = "https://resultados.registraduria.gov.co"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def _line(label: str, ok: bool, detail: str = "") -> str:
    mark = "OK " if ok else "FAIL"
    return f"[{mark}] {label:30s} {detail}"


def check_python() -> tuple[bool, str]:
    v = sys.version_info
    ok = v.major == 3 and v.minor >= 11
    return ok, f"{v.major}.{v.minor}.{v.micro}"


def check_deps() -> tuple[bool, str]:
    missing = []
    for mod in ("httpx", "duckdb", "polars", "pydantic", "tenacity"):
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        return False, f"falta(n): {', '.join(missing)} · pip install -r requirements.txt"
    return True, "httpx, duckdb, polars, pydantic, tenacity"


def check_playwright() -> tuple[bool, str]:
    try:
        import playwright  # noqa: F401
        return True, "playwright importable"
    except ImportError:
        return False, "playwright no instalado (opcional · sólo para discovery)"


def _http_get(url: str, timeout: float = 8.0) -> tuple[int, bytes]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Referer": REGISTRADURIA_BASE + "/",
            "Accept": "application/json,text/html;q=0.9",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read()


def check_registraduria() -> tuple[bool, str]:
    try:
        status, body = _http_get(f"{REGISTRADURIA_BASE}/json/web/config.json")
        if status != 200:
            return False, f"HTTP {status}"
        data = json.loads(body)
        return True, f"version={data.get('version')} fase={data.get('numeroDeFase')} polling_ms={data.get('polling', {}).get('interval_MS')}"
    except urllib.error.HTTPError as e:
        return False, f"HTTPError {e.code}"
    except (urllib.error.URLError, socket.timeout, json.JSONDecodeError) as e:
        return False, f"{type(e).__name__}: {e}"


def check_nomenclator() -> tuple[bool, str]:
    try:
        status, body = _http_get(f"{REGISTRADURIA_BASE}/json/nomenclator.json", timeout=15.0)
        if status != 200:
            return False, f"HTTP {status}"
        return True, f"{len(body)/1024:.0f} KB descargados"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def check_ollama() -> tuple[bool, str]:
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    target_model = os.environ.get("OLLAMA_MODEL_NARRATIVA", "qwen2.5:14b")
    try:
        with urllib.request.urlopen(f"{host}/api/tags", timeout=4.0) as resp:
            data = json.loads(resp.read())
        models = [m.get("name", "") for m in data.get("models", [])]
        if not models:
            return False, "Ollama up pero sin modelos · ollama pull qwen2.5:14b"
        has_target = any(m.startswith(target_model.split(":")[0]) for m in models)
        return has_target, f"{len(models)} modelos · target {target_model} {'OK' if has_target else 'AUSENTE'}"
    except (urllib.error.URLError, socket.timeout) as e:
        return False, f"no responde en {host} · ollama serve"


def check_disk() -> tuple[bool, str]:
    total, used, free = shutil.disk_usage(PROJECT_ROOT)
    free_gb = free / (1024**3)
    return free_gb >= 2.0, f"{free_gb:.1f} GB libres (mín 2 GB)"


def check_paths() -> tuple[bool, str]:
    paths = [
        PROJECT_ROOT / "data" / "raw",
        PROJECT_ROOT / "data" / "processed",
        PROJECT_ROOT / "data" / "outputs",
        PROJECT_ROOT / "logs",
    ]
    for p in paths:
        p.mkdir(parents=True, exist_ok=True)
    return True, " · ".join(p.relative_to(PROJECT_ROOT).as_posix() for p in paths)


def check_va_root() -> tuple[bool, str]:
    va = Path(os.environ.get("VA_ROOT", r"C:\Users\wilso\Desktop\Escritorio2026\Visual_Agentes"))
    routing = va / "templates" / "routing_inteligente.py"
    if not va.exists():
        return False, f"VA_ROOT inexistente: {va}"
    if not routing.exists():
        return False, f"routing_inteligente.py inexistente en {routing}"
    return True, f"{va} · routing OK"


CHECKS = [
    ("Python 3.11+", check_python),
    ("Dependencias core", check_deps),
    ("Playwright (opcional)", check_playwright),
    ("Conectividad Registraduria", check_registraduria),
    ("Nomenclator DIVIPOLA", check_nomenclator),
    ("Ollama LOCAL-FIRST", check_ollama),
    ("Espacio en disco", check_disk),
    ("Paths de escritura", check_paths),
    ("VA_ROOT (gateway)", check_va_root),
]


def main() -> int:
    print("=" * 70)
    print(f"elecciones_doctor · {PROJECT_ROOT}")
    print("=" * 70)
    results = []
    for label, fn in CHECKS:
        t0 = time.time()
        try:
            ok, detail = fn()
        except Exception as e:  # noqa: BLE001
            ok, detail = False, f"excepción: {type(e).__name__}: {e}"
        dt_ms = (time.time() - t0) * 1000
        print(_line(label, ok, f"{detail} ({dt_ms:.0f} ms)"))
        results.append((label, ok))
    print("=" * 70)
    fails = [r[0] for r in results if not r[1]]
    if fails:
        print(f"FAIL · {len(fails)} chequeos fallaron: {', '.join(fails)}")
        # Playwright se considera opcional · si es el único fallo, OK con warning
        critical_fails = [f for f in fails if f != "Playwright (opcional)"]
        if not critical_fails:
            print("(playwright es opcional · doctor pasa con warning)")
            return 0
        return 1
    print("OK · todos los chequeos pasaron")
    return 0


if __name__ == "__main__":
    sys.exit(main())
