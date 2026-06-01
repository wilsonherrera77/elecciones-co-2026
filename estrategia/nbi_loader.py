"""nbi_loader.py · carga NBI municipal DANE 2018.

Estrategia:
- Si existe el archivo local en data/raw/nbi/, lo usa.
- Si no, intenta bajar de URLs públicas DANE conocidas.
- Si la URL DANE no responde, deja NBI=NULL y advierte (no bloquea pipeline).

NBI = Necesidades Básicas Insatisfechas (índice 0-100, mayor = más vulnerable).

Output: tabla `nbi_municipal` en votos.duckdb (DIVIPOLA_DANE, depto, mpio, nbi_total)
y parquet en data/processed/nbi_municipal.parquet.

Nota: la DIVIPOLA DANE (`05001`=MEDELLIN) NO coincide con el código interno
Registraduría (`01001`). El loader hace su mejor esfuerzo en mapear por nombre+depto.
"""

from __future__ import annotations

import gzip
import io
import sys
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, PROJECT_ROOT.as_posix())

from scraper.db import connect  # noqa: E402

NBI_FUENTE_LOCAL = PROJECT_ROOT / "data" / "raw" / "nbi" / "nbi_municipal_2018.csv"
NBI_URLS = [
    # Datos abiertos GobCo · NBI 2018 (formato CSV)
    "https://www.datos.gov.co/api/views/q4j7-2gpv/rows.csv?accessType=DOWNLOAD",
]


def _try_download() -> bytes | None:
    for url in NBI_URLS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                if resp.status == 200:
                    return resp.read()
        except Exception as e:  # noqa: BLE001
            print(f"  warn URL {url}: {type(e).__name__}: {e}")
    return None


def _normalize(nombre: str) -> str:
    """Normaliza nombre para join: upper, sin tildes ni puntuación."""
    import unicodedata
    s = unicodedata.normalize("NFKD", nombre.upper())
    s = "".join(c for c in s if not unicodedata.combining(c))
    for ch in ".,()-":
        s = s.replace(ch, " ")
    return " ".join(s.split())


def main() -> int:
    print("[nbi] cargando NBI municipal 2018 DANE...")
    NBI_FUENTE_LOCAL.parent.mkdir(parents=True, exist_ok=True)

    raw_bytes: bytes | None = None
    if NBI_FUENTE_LOCAL.exists():
        raw_bytes = NBI_FUENTE_LOCAL.read_bytes()
        print(f"  fuente local: {NBI_FUENTE_LOCAL.relative_to(PROJECT_ROOT)} ({len(raw_bytes)} bytes)")
    else:
        raw_bytes = _try_download()
        if raw_bytes:
            NBI_FUENTE_LOCAL.write_bytes(raw_bytes)
            print(f"  bajado y guardado: {NBI_FUENTE_LOCAL.relative_to(PROJECT_ROOT)} ({len(raw_bytes)} bytes)")
        else:
            print("  WARN: no se pudo bajar NBI · creando tabla vacía y siguiendo")
            con = connect()
            con.execute("""
                CREATE OR REPLACE TABLE nbi_municipal (
                    divipola_dane VARCHAR,
                    nombre_norm VARCHAR,
                    departamento_norm VARCHAR,
                    nbi_total DOUBLE
                );
            """)
            con.close()
            return 0  # no bloquea

    # Parsea CSV con polars (robust a separadores y encoding)
    import polars as pl
    try:
        df = pl.read_csv(io.BytesIO(raw_bytes), separator=",", encoding="utf8-lossy", ignore_errors=True)
    except Exception:
        df = pl.read_csv(io.BytesIO(raw_bytes), separator=";", encoding="utf8-lossy", ignore_errors=True)

    print(f"  filas leídas: {df.height}")
    print(f"  columnas: {df.columns[:10]}")

    # Heurística: buscar columna NBI y nombre municipio
    cols = {c.lower(): c for c in df.columns}
    col_nbi = next((cols[k] for k in cols if "nbi" in k and ("tot" in k or "total" in k or "prop" in k)),
                   next((cols[k] for k in cols if "nbi" in k), None))
    col_mpio = next((cols[k] for k in cols if "municip" in k and "nombre" in k),
                    next((cols[k] for k in cols if "nombre_mun" in k), None))
    col_depto = next((cols[k] for k in cols if "depart" in k and "nombre" in k),
                     next((cols[k] for k in cols if "dept" in k), None))
    col_divi = next((cols[k] for k in cols if "divipola" in k or "cod_mun" in k or "codmunicipio" in k), None)

    print(f"  col NBI: {col_nbi} · col mpio: {col_mpio} · col depto: {col_depto} · col divipola: {col_divi}")

    if not col_nbi or not col_mpio:
        print("  ERROR: no se encontraron columnas NBI / municipio · revisar fuente")
        return 1

    df_clean = df.select([
        pl.col(col_divi).alias("divipola_dane") if col_divi else pl.lit(None).alias("divipola_dane"),
        pl.col(col_mpio).alias("nombre_raw"),
        pl.col(col_depto).alias("depto_raw") if col_depto else pl.lit(None).alias("depto_raw"),
        pl.col(col_nbi).cast(pl.Float64, strict=False).alias("nbi_total"),
    ]).filter(pl.col("nbi_total").is_not_null())

    out_pq = PROJECT_ROOT / "data" / "processed" / "nbi_municipal.parquet"
    df_clean.write_parquet(out_pq)
    print(f"  parquet: {out_pq.relative_to(PROJECT_ROOT)}")

    # Vuelca a DuckDB normalizando nombres
    pdf = df_clean.to_pandas()
    pdf["nombre_norm"] = pdf["nombre_raw"].fillna("").map(_normalize)
    pdf["departamento_norm"] = pdf["depto_raw"].fillna("").map(_normalize)

    con = connect()
    con.execute("DROP TABLE IF EXISTS nbi_municipal;")
    con.execute("""
        CREATE TABLE nbi_municipal (
            divipola_dane VARCHAR,
            nombre_norm VARCHAR,
            departamento_norm VARCHAR,
            nbi_total DOUBLE
        );
    """)
    con.executemany(
        "INSERT INTO nbi_municipal VALUES (?, ?, ?, ?)",
        list(pdf[["divipola_dane", "nombre_norm", "departamento_norm", "nbi_total"]]
             .itertuples(index=False, name=None))
    )
    n = con.execute("SELECT COUNT(*) FROM nbi_municipal").fetchone()[0]
    con.close()
    print(f"  duckdb nbi_municipal: {n} filas")
    return 0


if __name__ == "__main__":
    sys.exit(main())
