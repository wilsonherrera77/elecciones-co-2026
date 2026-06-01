"""Quick inspector · uso interno · verifica estado de votos.duckdb."""
import duckdb
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "processed" / "votos.duckdb"
con = duckdb.connect(DB.as_posix(), read_only=True)

print("=" * 70)
print("partidos_2026 (orden boleta):")
for r in con.execute("SELECT codpar, nombre, orden_boleta FROM partidos_2026 ORDER BY orden_boleta").fetchall():
    print(f"  codpar={r[0]:>3} orden={r[2]:>2} {r[1]}")

n_snap = con.execute("SELECT COUNT(*) FROM votos_municipio_snapshot").fetchone()[0]
n_hist = con.execute("SELECT COUNT(*) FROM snapshots_historico").fetchone()[0]
print(f"\nvotos_municipio_snapshot: {n_snap} filas · snapshots_historico: {n_hist}")

print("\nTOP 10 Cepeda (codpar='7') por votos:")
rows = con.execute("""
  SELECT nombre_municipio, departamento_nombre, votos, porcentaje, mesas_informadas, mesas_total
  FROM votos_municipio_snapshot WHERE codpar='7'
  ORDER BY votos DESC LIMIT 10
""").fetchall()
for r in rows:
    print(f"  {r[0]:25s} {r[1]:15s} votos={r[2]:>7,} pct={r[3] or 0:>5.1f}% mesas={r[4]}/{r[5]}")

print("\nTotal Cepeda en muestra:")
tot = con.execute("SELECT SUM(votos), COUNT(DISTINCT scope_idx) FROM votos_municipio_snapshot WHERE codpar='7'").fetchone()
print(f"  votos={tot[0]:,} en {tot[1]} municipios")

print("\nTodos los partidos · totales en muestra:")
rows = con.execute("""
  SELECT s.codpar, p.nombre, SUM(s.votos) AS votos
  FROM votos_municipio_snapshot s
  JOIN partidos_2026 p ON s.codpar = p.codpar
  WHERE s.votos IS NOT NULL
  GROUP BY s.codpar, p.nombre
  ORDER BY votos DESC
""").fetchall()
for r in rows:
    print(f"  codpar={r[0]:>3} {r[1][:45]:45s} {r[2]:>10,}")

con.close()
