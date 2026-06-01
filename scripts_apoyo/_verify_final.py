"""Verificación final · Tier 1 cerrado."""
import duckdb
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
con = duckdb.connect((ROOT / "data" / "processed" / "votos.duckdb").as_posix(), read_only=True)

print("=" * 60)
print("VERIFICACIÓN FINAL · proyecto elecciones")
print("=" * 60)

n_otro = con.execute("SELECT COUNT(*) FROM cluster_mapping WHERE cluster='Otro'").fetchone()[0]
n_total = con.execute("SELECT COUNT(*) FROM cluster_mapping").fetchone()[0]
n_clusters = con.execute("SELECT COUNT(DISTINCT cluster) FROM cluster_mapping").fetchone()[0]
print(f"\nCluster fix:")
print(f"  municipios totales en cluster_mapping: {n_total}")
print(f"  clusters distintos: {n_clusters}")
print(f"  municipios en cluster 'Otro': {n_otro}  {'OK' if n_otro <= 20 else 'FAIL'}")

n_snap = con.execute("SELECT COUNT(*) FROM votos_municipio_snapshot").fetchone()[0]
total_cepeda = con.execute("SELECT SUM(votos) FROM votos_municipio_snapshot WHERE codpar='7'").fetchone()[0] or 0
mpios_cepeda = con.execute("SELECT COUNT(DISTINCT scope_idx) FROM votos_municipio_snapshot WHERE codpar='7' AND votos > 0").fetchone()[0]
print(f"\nDatos en DB:")
print(f"  filas snapshot: {n_snap:,}")
print(f"  votos Cepeda: {total_cepeda:,}")
print(f"  municipios donde Cepeda tiene votos: {mpios_cepeda}")

# Top 5 oportunidad después del fix
print(f"\nTop 5 oportunidad post-fix:")
rows = con.execute("""
    SELECT nombre_municipio, departamento_nombre, cluster,
           votos_cepeda, ROUND(score_oportunidad, 0) AS score
    FROM v_score ORDER BY score_oportunidad DESC LIMIT 5
""").fetchall()
for r in rows:
    print(f"  {r[0]:25s} {r[1]:15s} cluster={r[2]:30s} votos={r[3]:,} score={r[4]:,}")

con.close()
print()
