"""nomenclator.py · descarga y parsea /json/nomenclator.json
Carga las tablas `divipola_2026` y `partidos_2026` en DuckDB.

Uso: `python scraper/nomenclator.py`
"""

from __future__ import annotations

import gzip
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, PROJECT_ROOT.as_posix())

from scraper.db import connect  # noqa: E402

REGISTRADURIA_BASE = "https://resultados.registraduria.gov.co"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def download_nomenclator() -> tuple[dict, Path]:
    """Baja /json/nomenclator.json con headers Chrome y lo guarda en data/raw."""
    url = f"{REGISTRADURIA_BASE}/json/nomenclator.json"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Referer": REGISTRADURIA_BASE + "/", "Accept": "application/json"},
    )
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_dir = PROJECT_ROOT / "data" / "raw" / "nomenclator"
    raw_dir.mkdir(parents=True, exist_ok=True)
    out = raw_dir / f"nomenclator_{ts}.json.gz"

    with urllib.request.urlopen(req, timeout=15) as resp:
        body = resp.read()
    with gzip.open(out, "wb") as f:
        f.write(body)
    data = json.loads(body)
    return data, out


def parse_ambitos(nomenclator: dict) -> list[dict]:
    """Convierte el array plano + jerarquía indexada a filas tabulares.

    Cada ámbito sabe su departamento padre (si l >= 3) cruzando `p[].p`.
    """
    elec_idx = 0  # presidente
    amb_block = nomenclator["amb"][elec_idx]
    ambitos = amb_block["ambitos"]

    # Diccionario rápido idx -> ámbito
    by_idx = {a["i"]: a for a in ambitos}

    rows: list[dict] = []
    for a in ambitos:
        parent_idx: int | None = None
        departamento_idx: int | None = None
        departamento_nombre: str | None = None

        # `p` es lista de {l, p[...]} con índices padre por nivel
        for parent_block in a.get("p", []) or []:
            pl = parent_block.get("l")
            indices = parent_block.get("p", [])
            if not indices:
                continue
            if parent_idx is None:
                parent_idx = indices[0]
            if pl == 2 and departamento_idx is None:
                departamento_idx = indices[0]
                dep_ambito = by_idx.get(departamento_idx)
                if dep_ambito is not None:
                    departamento_nombre = dep_ambito["n"]

        # Si el ámbito ES un departamento, su propio idx es el "departamento"
        if a["l"] == 2:
            departamento_idx = a["i"]
            departamento_nombre = a["n"]

        # has_children: si h tiene contenido
        has_children = any((child.get("p") or []) for child in (a.get("h") or []))

        rows.append({
            "idx": a["i"],
            "nombre": a["n"],
            "codigo_interno": a["co"],
            "sigla": a.get("s"),
            "level": a["l"],
            "parent_idx": parent_idx,
            "departamento_idx": departamento_idx,
            "departamento_nombre": departamento_nombre,
            "resultado_idx": (a.get("r") or [None])[0],
            "has_children": has_children,
        })
    return rows


def parse_partidos(nomenclator: dict) -> list[dict]:
    """En los datos ACT/PR/*.json, el `codpar` corresponde al `i` (orden de boleta)
    del nomenclator, NO al `codpar` oficial declarado. Por eso aquí usamos `i`
    como key principal para que joins por codpar funcionen.

    Mapeo confirmado en Abejorral 01004:
      - Cepeda Castro (Pacto Histórico) viene como codpar='7' en datos
      - En nomenclator: codpar=26, i=7, sigla=PACTO-HISTORICO
    """
    rows: list[dict] = []
    for p in nomenclator.get("partidos", []):
        # Normaliza encoding (latin-1 mis-decoded a veces)
        nombre = p.get("nombre", "")
        try:
            nombre = nombre.encode("latin-1").decode("utf-8")
        except (UnicodeDecodeError, UnicodeEncodeError):
            pass
        rows.append({
            "codpar": str(p.get("i", "")),          # ORDEN BOLETA = codpar en datos
            "nombre": nombre,
            "color": p.get("color"),
            "sigla": p.get("s"),
            "orden_boleta": int(p.get("i", 0) or 0),
        })
    return rows


def main() -> int:
    t0 = time.time()
    print("Descargando nomenclator desde Registraduría...")
    data, out_path = download_nomenclator()
    print(f"  guardado: {out_path.relative_to(PROJECT_ROOT)}")
    print(f"  versión: {data.get('ver')} · año: {data.get('y')}")
    print(f"  elecciones: {[e.get('n') for e in data.get('elec', [])]}")
    print(f"  niveles: {[lv.get('n') for lv in data.get('levels', [])]}")

    rows_amb = parse_ambitos(data)
    rows_part = parse_partidos(data)

    # Count por nivel
    from collections import Counter
    by_level = Counter(r["level"] for r in rows_amb)
    print(f"  ámbitos: total={len(rows_amb)} · por nivel={dict(sorted(by_level.items()))}")
    print(f"  partidos en boleta: {len(rows_part)}")

    con = connect()
    con.execute("DELETE FROM divipola_2026;")
    con.executemany(
        """INSERT INTO divipola_2026 (idx, nombre, codigo_interno, sigla, level,
            parent_idx, departamento_idx, departamento_nombre, resultado_idx, has_children)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [(r["idx"], r["nombre"], r["codigo_interno"], r["sigla"], r["level"],
          r["parent_idx"], r["departamento_idx"], r["departamento_nombre"],
          r["resultado_idx"], r["has_children"]) for r in rows_amb],
    )
    con.execute("DELETE FROM partidos_2026;")
    con.executemany(
        """INSERT INTO partidos_2026 (codpar, nombre, color, sigla, orden_boleta)
           VALUES (?, ?, ?, ?, ?)""",
        [(r["codpar"], r["nombre"], r["color"], r["sigla"], r["orden_boleta"]) for r in rows_part],
    )
    con.close()

    dt = time.time() - t0
    print(f"OK · cargado a DuckDB en {dt:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
