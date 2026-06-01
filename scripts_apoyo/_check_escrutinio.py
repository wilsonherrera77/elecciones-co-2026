"""Verifica estado del escrutinio nacional."""
import duckdb
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "processed" / "votos.duckdb"
con = duckdb.connect(DB.as_posix(), read_only=True)

# Estado nacional
r = con.execute("""
    WITH t AS (
        SELECT DISTINCT scope_idx, mesas_informadas, mesas_total
        FROM votos_municipio_snapshot
    )
    SELECT
        SUM(mesas_informadas) AS total_informadas,
        SUM(mesas_total) AS total_mesas,
        ROUND(SUM(mesas_informadas)::DOUBLE / NULLIF(SUM(mesas_total), 0) * 100, 3) AS pct,
        COUNT(*) AS mpios,
        SUM(CASE WHEN mesas_informadas < mesas_total THEN 1 ELSE 0 END) AS mpios_abiertos
    FROM t
""").fetchone()

print(f"NACIONAL:")
print(f"  mesas informadas / total: {r[0]:,} / {r[1]:,}")
print(f"  porcentaje escrutinio: {r[2]}%")
print(f"  municipios con datos: {r[3]}")
print(f"  municipios con mesas pendientes: {r[4]}")
print()

# Distribución
print("DISTRIBUCIÓN por % escrutinio:")
rows = con.execute("""
    WITH t AS (
        SELECT DISTINCT scope_idx, mesas_informadas, mesas_total,
               (mesas_informadas::DOUBLE / NULLIF(mesas_total, 0)) AS pct
        FROM votos_municipio_snapshot
    )
    SELECT
        CASE
            WHEN pct >= 1.0 THEN '100%'
            WHEN pct >= 0.95 THEN '95-99.9%'
            WHEN pct >= 0.80 THEN '80-94.9%'
            WHEN pct >= 0.50 THEN '50-79.9%'
            WHEN pct > 0 THEN '<50%'
            ELSE '0%'
        END AS bucket,
        COUNT(*) mpios
    FROM t GROUP BY 1 ORDER BY 1 DESC
""").fetchall()
for r in rows:
    print(f"  {r[0]:>10s}  {r[1]:>5} mpios")

print()
print("Snapshots históricos hasta ahora:", con.execute("SELECT COUNT(*) FROM snapshots_historico").fetchone()[0])
print("Distintos ts_snapshot:", con.execute("SELECT COUNT(DISTINCT ts_snapshot) FROM snapshots_historico").fetchone()[0])

con.close()
