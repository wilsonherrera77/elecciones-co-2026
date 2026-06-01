"""cepeda_3M.py · orquestador final · genera reporte_final.md.

Combina:
- Total Cepeda en datos actuales (todos los snapshots agregados a v_score)
- Top 200 municipios oportunidad (atacar)
- Top 100 municipios defensa (proteger turnout)
- Suma proyectada con escenarios conservador/realista/optimista
- Gap vs meta 3.000.000

Output: data/outputs/reporte_final.md
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, PROJECT_ROOT.as_posix())

from scraper.db import connect  # noqa: E402

META = 3_000_000


def main() -> int:
    con = connect()
    has_view = con.execute(
        "SELECT COUNT(*) FROM information_schema.views WHERE table_name='v_score'"
    ).fetchone()[0]
    if not has_view:
        print("ERROR: corre `python -m estrategia.mapa_oportunidad` primero")
        return 1

    tot = con.execute("""
        SELECT COALESCE(SUM(votos_cepeda), 0),
               COUNT(*),
               COUNT(*) FILTER (WHERE votos_cepeda > 0),
               ROUND(AVG(afinidad) * 100, 2),
               COALESCE(SUM(potencial_no_votante), 0),
               COALESCE(SUM(censo), 0),
               COALESCE(SUM(votos_validos), 0)
        FROM v_score
    """).fetchone()
    total_actual, n_mpios, n_con_votos, afinidad_avg, potencial, censo_total, validos_total = tot

    top_op = con.execute("""
        SELECT nombre_municipio, departamento_nombre, cluster,
               votos_cepeda, pct_cepeda, potencial_no_votante,
               ROUND(score_oportunidad, 0) AS score
        FROM v_score ORDER BY score_oportunidad DESC LIMIT 20
    """).fetchall()

    top_def = con.execute("""
        SELECT nombre_municipio, departamento_nombre, cluster,
               votos_cepeda, ROUND(afinidad*100, 1) AS afinidad_pct
        FROM v_score
        WHERE afinidad > 0.30
        ORDER BY votos_cepeda DESC LIMIT 20
    """).fetchall()

    cluster_summary = con.execute("""
        SELECT cluster,
               COUNT(*) mpios,
               SUM(votos_cepeda) v,
               ROUND(AVG(afinidad)*100, 1) af,
               SUM(potencial_no_votante) pot
        FROM v_score
        GROUP BY cluster
        ORDER BY v DESC NULLS LAST
    """).fetchall()

    # Escenarios de captura
    afinidad_dec = (afinidad_avg or 0) / 100
    scen_conservador = int(potencial * 0.07 * afinidad_dec)
    scen_realista = int(potencial * 0.12 * afinidad_dec)
    scen_optimista = int(potencial * 0.20 * (afinidad_dec * 1.2))

    proj_cons = total_actual + scen_conservador
    proj_real = total_actual + scen_realista
    proj_opt = total_actual + scen_optimista

    gap_cons = max(0, META - proj_cons)
    gap_real = max(0, META - proj_real)
    gap_opt = max(0, META - proj_opt)

    out = PROJECT_ROOT / "data" / "outputs" / "reporte_final.md"
    out.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    lines.append(f"# Reporte estratégico · 3M votos para Iván Cepeda · Pacto Histórico 2026")
    lines.append(f"_Generado: {datetime.now(timezone.utc).isoformat()}_")
    lines.append("")
    lines.append("## Snapshot actual (datos Registraduría)")
    lines.append(f"- Municipios analizados: **{n_mpios:,}** (de 1.189 totales)")
    lines.append(f"- Municipios con votos contabilizados: **{n_con_votos:,}**")
    lines.append(f"- Censo electoral en muestra: **{censo_total:,}**")
    lines.append(f"- Votos válidos en muestra: **{validos_total:,}**")
    lines.append(f"- **VOTOS CEPEDA ACTUALES: {total_actual:,}**")
    lines.append(f"- Afinidad promedio (Cepeda/válidos): **{afinidad_avg}%**")
    lines.append(f"- Potencial (no-votantes): **{potencial:,}**")
    lines.append("")
    lines.append(f"## Meta vs realidad")
    lines.append(f"- Meta: **{META:,}**")
    lines.append(f"- Actual: **{total_actual:,}**")
    lines.append(f"- Gap absoluto: **{max(0, META - total_actual):,}** votos por conseguir")
    lines.append(f"- Cobertura actual: **{total_actual/META*100:.1f}%** de la meta")
    lines.append("")
    lines.append("## Escenarios de campaña")
    lines.append("| Escenario | Asunciones | Votos adicionales | Proyectado total | Gap vs 3M |")
    lines.append("|---|---|---:|---:|---:|")
    lines.append(f"| Conservador | 7% del potencial × afinidad actual | {scen_conservador:,} | {proj_cons:,} | {gap_cons:,} |")
    lines.append(f"| Realista | 12% del potencial × afinidad actual | {scen_realista:,} | {proj_real:,} | {gap_real:,} |")
    lines.append(f"| Optimista | 20% potencial × afinidad +20% | {scen_optimista:,} | {proj_opt:,} | {gap_opt:,} |")
    lines.append("")
    lines.append("## Conclusión sobre la meta")
    if proj_real >= META:
        lines.append(f"En el escenario realista, **se alcanza la meta** (+{proj_real - META:,}).")
    elif proj_opt >= META:
        lines.append(f"En el escenario optimista se alcanza, en el realista falta **{gap_real:,}**.")
    else:
        deficit = META - proj_opt
        lines.append(f"Incluso en el escenario optimista falta **{deficit:,}**. ")
        lines.append(f"Cerrar el gap requiere acciones extraordinarias: subir afinidad en los clusters")
        lines.append(f"de bajo Cepeda (top 'Perdidos') o capturar más del 25% del potencial no votante.")
    lines.append("")
    lines.append("## Top 20 municipios OPORTUNIDAD (atacar)")
    lines.append("| # | Municipio | Departamento | Cluster | Votos hoy | % | Potencial | Score |")
    lines.append("|---:|---|---|---|---:|---:|---:|---:|")
    for i, r in enumerate(top_op, 1):
        lines.append(f"| {i} | {r[0]} | {r[1]} | {r[2] or '-'} | {r[3] or 0:,} | {r[4] or 0:.1f}% | {r[5] or 0:,} | {r[6] or 0:,} |")
    lines.append("")
    lines.append("## Top 20 municipios DEFENSA (afinidad > 30%, proteger turnout)")
    lines.append("| # | Municipio | Departamento | Cluster | Votos | Afinidad |")
    lines.append("|---:|---|---|---|---:|---:|")
    for i, r in enumerate(top_def, 1):
        lines.append(f"| {i} | {r[0]} | {r[1]} | {r[2] or '-'} | {r[3] or 0:,} | {r[4]}% |")
    lines.append("")
    lines.append("## Resumen por cluster geo-político")
    lines.append("| Cluster | Mpios | Votos Cepeda | Afinidad | Potencial |")
    lines.append("|---|---:|---:|---:|---:|")
    for r in cluster_summary:
        lines.append(f"| {r[0] or '?'} | {r[1]} | {r[2] or 0:,} | {r[3] or 0}% | {r[4] or 0:,} |")
    lines.append("")
    lines.append("## Briefs narrativos por cluster")
    briefs = sorted((PROJECT_ROOT / "data" / "outputs").glob("brief_cluster_*.md"))
    if briefs:
        for b in briefs:
            lines.append(f"- [{b.stem}](./{b.name})")
    else:
        lines.append("_(aún no generados · corre `python -m estrategia.narrative_brief --all`)_")
    lines.append("")
    lines.append("## Outputs adicionales")
    lines.append("- `mapa_oportunidad_top200.csv` · 200 municipios con mayor score de oportunidad")
    lines.append("- `defender_top100.csv` · 100 municipios donde Cepeda ya tiene afinidad >30%")
    lines.append("- `perdidos_top100.csv` · 100 municipios con potencial alto pero afinidad <10%")
    lines.append("")
    lines.append("---")
    lines.append("_Fuente: scrapeo público de https://resultados.registraduria.gov.co/ · esquema /json/ACT/PR/<codigo>.json_")
    lines.append(f"_Pacto Histórico · codpar=7 (orden boleta) · candidato confirmado en datos: IVÁN CEPEDA CASTRO_")

    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[cepeda_3M] reporte: {out.relative_to(PROJECT_ROOT)}")
    print(f"  Cepeda actual: {total_actual:,} · gap: {max(0, META - total_actual):,}")
    print(f"  Escenario realista: {proj_real:,} (gap {gap_real:,})")
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
