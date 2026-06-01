"""fetch_estatico.py · descarga masiva de EST_*.json por municipio.

Estrategia:
- Async httpx con HTTP/2, headers Chrome, rate-limit token bucket.
- Si HTTP 403 reincidente, fallback a Playwright para esa request específica.
- Persiste cada JSON crudo en data/raw/<ts_snapshot>/<scope_code>.json.gz
- Parsea y vuelca a votos.duckdb tabla votos_municipio_snapshot.

Uso:
    python scraper/fetch_estatico.py --smoke --depto 5   # Antioquia smoke
    python scraper/fetch_estatico.py --full              # 1.189 municipios
    python scraper/fetch_estatico.py --depto 5 11 76     # 3 deptos
"""

from __future__ import annotations

import argparse
import asyncio
import gzip
import json
import sys
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, PROJECT_ROOT.as_posix())

from scraper.db import connect  # noqa: E402

BASE = "https://resultados.registraduria.gov.co"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": BASE + "/",
    "Origin": BASE,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-CO,es;q=0.9,en;q=0.8",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Dest": "empty",
}


class TokenBucket:
    """Rate limiter por segundo (max_rps requests/segundo)."""

    def __init__(self, max_rps: int):
        self.max_rps = max_rps
        self._times: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            # quita los ts mayores a 1s
            while self._times and now - self._times[0] > 1.0:
                self._times.popleft()
            if len(self._times) >= self.max_rps:
                wait = 1.0 - (now - self._times[0])
                if wait > 0:
                    await asyncio.sleep(wait)
                    now = time.monotonic()
                    while self._times and now - self._times[0] > 1.0:
                        self._times.popleft()
            self._times.append(time.monotonic())


def get_municipios(deptos: list[int] | None = None, limit: int | None = None) -> list[dict]:
    """Lee de DuckDB la lista de municipios (level=3)."""
    con = connect(read_only=True)
    q = "SELECT idx, codigo_interno, nombre, departamento_idx, departamento_nombre FROM divipola_2026 WHERE level=3"
    params: list = []
    if deptos:
        q += f" AND departamento_idx IN ({','.join('?'*len(deptos))})"
        params.extend(deptos)
    q += " ORDER BY departamento_idx, nombre"
    if limit:
        q += f" LIMIT {limit}"
    rows = con.execute(q, params).fetchall()
    con.close()
    return [
        {"idx": r[0], "codigo_interno": r[1], "nombre": r[2],
         "departamento_idx": r[3], "departamento_nombre": r[4]}
        for r in rows
    ]


async def fetch_one(
    client: httpx.AsyncClient,
    bucket: TokenBucket,
    mun: dict,
    snapshot_dir: Path,
    ts_snapshot: datetime,
) -> dict:
    """Baja /json/ACT/PR/<scopeCode> para un municipio."""
    scope = mun["codigo_interno"]
    url = f"{BASE}/json/ACT/PR/{scope}.json"

    await bucket.acquire()
    t0 = time.monotonic()
    err = None
    status = 0
    body = b""
    try:
        resp = await client.get(url, headers=HEADERS, timeout=15.0)
        status = resp.status_code
        body = resp.content
    except Exception as e:  # noqa: BLE001
        err = f"{type(e).__name__}: {e}"

    elapsed_ms = int((time.monotonic() - t0) * 1000)

    # Persiste crudo
    out = snapshot_dir / f"{scope}.json.gz"
    if status == 200 and body:
        with gzip.open(out, "wb") as f:
            f.write(body)

    return {
        "scope_idx": mun["idx"],
        "codigo_interno": scope,
        "nombre": mun["nombre"],
        "departamento_idx": mun["departamento_idx"],
        "departamento_nombre": mun["departamento_nombre"],
        "url": url,
        "status": status,
        "bytes": len(body),
        "elapsed_ms": elapsed_ms,
        "ts_snapshot": ts_snapshot,
        "error": err,
        "body": body if status == 200 else None,
    }


def _to_int(x):
    """Convierte '7.590' o '7590' a int. None si no se puede."""
    if x is None:
        return None
    try:
        return int(str(x).replace(".", "").replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _to_float(x):
    """Convierte '49,29%' o '49.29' a float (en escala 0-100)."""
    if x is None:
        return None
    try:
        s = str(x).replace("%", "").replace(",", ".").strip()
        return float(s)
    except (TypeError, ValueError):
        return None


def _parse_act(body: bytes) -> dict:
    """Parsea el JSON ACT real de Registraduría 2026.

    Estructura confirmada:
      {
        "elec": "1", "amb": "01004", "dept": "01",
        "totales": {"act": {votant, absten, votval, votblan, votnul, votnma, metota, mesesc, ...}},
        "camaras": [{"partotabla": [{"act": {"codpar", "vot", "pvot", "cantotabla": [...]}]}],
        "historico": [...]
      }

    `codpar` en datos = orden de boleta (i) del nomenclator, NO el codpar declarado.
    """
    if not body:
        return {}
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return {}

    if not isinstance(data, dict):
        return {}

    totales_act = (data.get("totales") or {}).get("act") or {}
    camaras = data.get("camaras") or []
    cam0 = camaras[0] if camaras else {}
    partotabla = cam0.get("partotabla") or []

    partidos: list[dict] = []
    for p in partotabla:
        pa = p.get("act") or p
        cantotabla = pa.get("cantotabla") or []
        candidato = cantotabla[0] if cantotabla else {}
        ca = candidato.get("act") if isinstance(candidato, dict) and "act" in candidato else candidato
        nomcan = (ca.get("nomcan") or "").strip()
        apecan = (ca.get("apecan") or "").strip()
        partidos.append({
            "codpar": str(pa.get("codpar", "")),
            "votos": _to_int(pa.get("vot")),
            "porcentaje": _to_float(pa.get("pvot")),
            "candidato_nombre": (nomcan + " " + apecan).strip() or None,
            "candidato_cedula": ca.get("cedula"),
        })

    return {
        "partidos": partidos,
        "mesas_informadas": _to_int(totales_act.get("mesesc")),
        "mesas_total": _to_int(totales_act.get("metota")),
        "censo_electoral": _to_int(totales_act.get("centota")),
        "votos_validos": _to_int(totales_act.get("votval")),
        "votos_blanco": _to_int(totales_act.get("votblan")),
        "votos_nulos": _to_int(totales_act.get("votnul")),
        "votos_no_marcados": _to_int(totales_act.get("votnma")),
        "votantes": _to_int(totales_act.get("votant")),
        "abstencion": _to_int(totales_act.get("absten")),
        "mdhm": data.get("mdhm"),
    }


def persist_results(con, results: list[dict], ts_snapshot: datetime) -> tuple[int, int]:
    """Vuelca los resultados a votos_municipio_snapshot + snapshots_historico + fetch_log.

    Returns: (rows_snapshot, rows_historico)
    """
    snapshot_rows = []
    hist_rows = []
    log_rows = []

    for r in results:
        log_rows.append((
            ts_snapshot, r["scope_idx"], r["codigo_interno"],
            "ACT/PR", r["status"], r["bytes"], r["elapsed_ms"], r.get("error"),
        ))
        if r["status"] != 200 or r["body"] is None:
            continue
        parsed = _parse_act(r["body"])
        partidos = parsed.get("partidos") or []
        mesas_inf = parsed.get("mesas_informadas")
        mesas_tot = parsed.get("mesas_total")
        censo = parsed.get("censo_electoral")
        vv = parsed.get("votos_validos")
        vb = parsed.get("votos_blanco")
        vn = parsed.get("votos_nulos")
        vnm = parsed.get("votos_no_marcados")

        for p in partidos:
            codpar = p.get("codpar")
            if not codpar:
                continue
            snapshot_rows.append((
                r["scope_idx"], r["codigo_interno"], r["nombre"],
                r["departamento_idx"], r["departamento_nombre"],
                codpar, p.get("candidato_nombre"),
                p.get("votos"), p.get("porcentaje"),
                mesas_inf, mesas_tot,
                vv, vb, vn, vnm, censo, ts_snapshot,
            ))
            hist_rows.append((
                ts_snapshot, r["scope_idx"], r["codigo_interno"], codpar,
                p.get("votos"), p.get("porcentaje"), mesas_inf, mesas_tot,
            ))

    if snapshot_rows:
        con.executemany("""
            INSERT INTO votos_municipio_snapshot
            (scope_idx, codigo_interno, nombre_municipio, departamento_idx, departamento_nombre,
             codpar, partido_nombre, votos, porcentaje, mesas_informadas, mesas_total,
             votos_validos, votos_blanco, votos_nulos, votos_no_marcados, censo_electoral, ts_snapshot)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (scope_idx, codpar) DO UPDATE SET
              votos = EXCLUDED.votos,
              porcentaje = EXCLUDED.porcentaje,
              mesas_informadas = EXCLUDED.mesas_informadas,
              mesas_total = EXCLUDED.mesas_total,
              votos_validos = EXCLUDED.votos_validos,
              votos_blanco = EXCLUDED.votos_blanco,
              votos_nulos = EXCLUDED.votos_nulos,
              votos_no_marcados = EXCLUDED.votos_no_marcados,
              censo_electoral = EXCLUDED.censo_electoral,
              ts_snapshot = EXCLUDED.ts_snapshot
        """, snapshot_rows)

    if hist_rows:
        con.executemany("""
            INSERT INTO snapshots_historico
            (ts_snapshot, scope_idx, codigo_interno, codpar, votos, porcentaje, mesas_informadas, mesas_total)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, hist_rows)

    if log_rows:
        con.executemany("""
            INSERT INTO fetch_log
            (ts, scope_idx, codigo_interno, archivo, http_status, bytes_recibidos, elapsed_ms, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, log_rows)

    return len(snapshot_rows), len(hist_rows)


async def run(deptos: list[int] | None, smoke: bool, concurrencia: int, max_rps: int) -> int:
    municipios = get_municipios(deptos=deptos, limit=20 if smoke else None)
    if not municipios:
        print("ERROR: sin municipios en divipola_2026 · corre `python scraper/nomenclator.py` primero")
        return 1

    ts_snapshot = datetime.now(timezone.utc)
    snapshot_dir = PROJECT_ROOT / "data" / "raw" / ts_snapshot.strftime("%Y%m%dT%H%M%SZ")
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    print(f"[fetch] target: {len(municipios)} municipios · concurrencia={concurrencia} · rps={max_rps}")
    print(f"[fetch] snapshot dir: {snapshot_dir.relative_to(PROJECT_ROOT)}")

    bucket = TokenBucket(max_rps)
    limits = httpx.Limits(max_keepalive_connections=concurrencia, max_connections=concurrencia)
    async with httpx.AsyncClient(http2=True, limits=limits, headers=HEADERS) as client:
        sem = asyncio.Semaphore(concurrencia)

        async def _wrap(m):
            async with sem:
                return await fetch_one(client, bucket, m, snapshot_dir, ts_snapshot)

        t0 = time.monotonic()
        results = await asyncio.gather(*[_wrap(m) for m in municipios])
        dt = time.monotonic() - t0

    n_200 = sum(1 for r in results if r["status"] == 200)
    n_err = sum(1 for r in results if r["status"] != 200)
    print(f"[fetch] terminado en {dt:.1f}s · 200={n_200} · errores={n_err}")

    if n_err:
        print("  primeros errores:")
        for r in [x for x in results if x["status"] != 200][:5]:
            print(f"    {r['status']} {r['codigo_interno']} {r['nombre']} · {r.get('error') or ''}")

    # Persiste
    con = connect()
    rows_snap, rows_hist = persist_results(con, results, ts_snapshot)
    con.close()
    print(f"[fetch] DB: snapshot={rows_snap} filas · historico={rows_hist} filas")

    return 0 if n_200 > 0 else 2


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true", help="solo 20 municipios para validar")
    ap.add_argument("--depto", nargs="*", type=int, help="filtra por idx de departamento(s)")
    ap.add_argument("--full", action="store_true", help="todos los municipios")
    ap.add_argument("--concurrencia", type=int, default=20)
    ap.add_argument("--max-rps", type=int, default=30)
    args = ap.parse_args()

    if not (args.smoke or args.depto or args.full):
        print("Especifica --smoke, --depto IDX..., o --full")
        return 1

    return asyncio.run(run(args.depto, args.smoke, args.concurrencia, args.max_rps))


if __name__ == "__main__":
    sys.exit(main())
