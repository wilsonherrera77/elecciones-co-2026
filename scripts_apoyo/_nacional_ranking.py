"""Ranking nacional de partidos · identifica runoff."""
import duckdb
from pathlib import Path

con = duckdb.connect(
    (Path(__file__).resolve().parent.parent / "data" / "processed" / "votos.duckdb").as_posix(),
    read_only=True,
)

# Ranking nacional · suma votos por codpar
rows = con.execute("""
    SELECT s.codpar, p.nombre,
           SUM(s.votos) AS votos,
           COUNT(DISTINCT s.scope_idx) FILTER (WHERE s.votos > 0) AS mpios_con_voto,
           COUNT(DISTINCT s.scope_idx) FILTER (
               WHERE s.votos = (SELECT MAX(s2.votos) FROM votos_municipio_snapshot s2 WHERE s2.scope_idx = s.scope_idx)
           ) AS mpios_ganados
    FROM votos_municipio_snapshot s
    LEFT JOIN partidos_2026 p ON s.codpar = p.codpar
    GROUP BY s.codpar, p.nombre
    ORDER BY votos DESC NULLS LAST
""").fetchall()

print("RANKING NACIONAL 1RA VUELTA · PRESIDENCIAL 2026")
print("=" * 90)
print(f"{'#':>3} {'codpar':>6} {'partido':45s} {'votos':>12} {'%':>7} {'mpios_gan':>10}")
print("-" * 90)

total_validos = con.execute("""
    SELECT SUM(votos_validos) FROM (
        SELECT DISTINCT scope_idx, votos_validos FROM votos_municipio_snapshot
    )
""").fetchone()[0]

for i, r in enumerate(rows, 1):
    pct = (r[2] / total_validos * 100) if r[2] and total_validos else 0
    print(f"{i:>3} {r[0]:>6} {(r[1] or '?')[:45]:45s} {r[2] or 0:>12,} {pct:>6.2f}% {r[4]:>10}")

print()
print(f"Total válidos nacional: {total_validos:,}")
mitad_mas_uno = total_validos // 2 + 1
print(f"Mitad+1 (umbral 2da vuelta): {mitad_mas_uno:,}")
print()

# Top 2 va a 2da vuelta (si nadie llegó al 50%)
print("ESCENARIO 2DA VUELTA:")
top2 = rows[:2]
ganador, segundo = top2[0], top2[1]
print(f"  1° {ganador[1]} (codpar={ganador[0]}): {ganador[2]:,} votos")
print(f"  2° {segundo[1]} (codpar={segundo[0]}): {segundo[2]:,} votos")
brecha_lider = ganador[2] - segundo[2]
print(f"  Brecha líder-segundo: {brecha_lider:,}")

# Para Cepeda llegar al 50%+1 en universo actual
votos_cepeda = next((r[2] for r in rows if r[0] == "7"), 0)
gap_a_50 = max(0, mitad_mas_uno - votos_cepeda)
print(f"\n  Cepeda actual: {votos_cepeda:,}")
print(f"  Gap a 50%+1 del universo 1ra vuelta: {gap_a_50:,}")
print(f"  Si turnout en 2da sube 15% (universo 27.2M), 50%+1 = {int(27_200_000 / 2 + 1):,}")
print(f"  Gap a 50%+1 universo 2da vuelta hipotético: {max(0, int(27_200_000/2+1) - votos_cepeda):,}")

con.close()
