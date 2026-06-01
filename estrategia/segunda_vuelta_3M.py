"""segunda_vuelta_3M.py · análisis estratégico para conseguir 3M votos extra en 2da vuelta.

Marco analítico:
- En 1ra vuelta Cepeda obtuvo 9.683.743 (40.91% de 23.66M válidos).
- Espriella obtuvo 10.351.548 (43.74%) → pasa primero a 2da vuelta.
- Brecha 1ra vuelta: 667.805 votos (Espriella +6.9%).
- Universo 1ra vuelta: 41.42M censo · 23.66M validos · turnout 57.1%.
- En 2da vuelta colombiana el turnout sube en promedio 5-15 pp (escenario base +10pp = 28M votos).
- Para 50%+1 en universo 28M: ~14.0M → Cepeda necesita ~4.3M más.
- "3M" del director = meta operativa intermedia (escenario más conservador con turnout +5pp).

Categorización de los 1.189 municipios en 4 cuadrantes operativos:
  Q1 · DEFENDER: Cepeda ganó · alta afinidad >40% · proteger turnout con testigos electorales
  Q2 · MOVILIZAR: Cepeda perdió por margen <10% · empujar no-votantes Pacto + capturar voto blanco
  Q3 · CONVERTIR: Cepeda perdió >10% pero <30% · persuadir voto centro / Dignidad / sin uribistas
  Q4 · RESISTIR: Cepeda perdió >30% · territorio hostil · meta defensiva: no perder más

Output:
  data/outputs/segunda_vuelta_3M.md
  data/outputs/cuadrantes_2v.csv
  data/outputs/top50_movilizar.csv
  data/outputs/top50_convertir.csv
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB = PROJECT_ROOT / "data" / "processed" / "votos.duckdb"
OUT = PROJECT_ROOT / "data" / "outputs"

CEPEDA = "7"
ESPRIELLA = "10"
DIGNIDAD = "3"
META_3M = 3_000_000


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(DB.as_posix(), read_only=False)

    # Tabla cuadrantes municipal
    con.execute(f"""
    CREATE OR REPLACE TABLE cuadrantes_2v AS
    WITH cep AS (
        SELECT scope_idx, votos AS votos_cepeda, porcentaje AS pct_cepeda
        FROM votos_municipio_snapshot WHERE codpar='{CEPEDA}'
    ),
    esp AS (
        SELECT scope_idx, votos AS votos_espriella, porcentaje AS pct_espriella
        FROM votos_municipio_snapshot WHERE codpar='{ESPRIELLA}'
    ),
    dig AS (
        SELECT scope_idx, votos AS votos_dignidad, porcentaje AS pct_dignidad
        FROM votos_municipio_snapshot WHERE codpar='{DIGNIDAD}'
    ),
    base AS (
        SELECT scope_idx, codigo_interno, nombre_municipio, departamento_nombre,
               MAX(censo_electoral) censo,
               MAX(votos_validos) validos,
               MAX(votos_blanco) blanco,
               MAX(votos_no_marcados) no_marcados
        FROM votos_municipio_snapshot GROUP BY 1,2,3,4
    )
    SELECT
        b.scope_idx, b.codigo_interno, b.nombre_municipio, b.departamento_nombre,
        b.censo, b.validos, b.blanco, b.no_marcados,
        COALESCE(c.votos_cepeda, 0) AS votos_cepeda,
        COALESCE(c.pct_cepeda, 0.0) AS pct_cepeda,
        COALESCE(e.votos_espriella, 0) AS votos_espriella,
        COALESCE(e.pct_espriella, 0.0) AS pct_espriella,
        COALESCE(d.votos_dignidad, 0) AS votos_dignidad,
        COALESCE(d.pct_dignidad, 0.0) AS pct_dignidad,
        (b.censo - b.validos) AS no_votantes,
        (COALESCE(e.votos_espriella, 0) - COALESCE(c.votos_cepeda, 0)) AS brecha_vs_espriella,
        (COALESCE(c.pct_cepeda, 0.0) - COALESCE(e.pct_espriella, 0.0)) AS margen_pct,
        cm.cluster,
        CASE
            WHEN COALESCE(c.pct_cepeda, 0) > COALESCE(e.pct_espriella, 0)
                 AND COALESCE(c.pct_cepeda, 0) >= 40
                THEN 'Q1_DEFENDER'
            WHEN COALESCE(c.pct_cepeda, 0) > COALESCE(e.pct_espriella, 0)
                THEN 'Q1_DEFENDER_FRAGIL'
            WHEN ABS(COALESCE(c.pct_cepeda, 0) - COALESCE(e.pct_espriella, 0)) <= 10
                THEN 'Q2_MOVILIZAR'
            WHEN ABS(COALESCE(c.pct_cepeda, 0) - COALESCE(e.pct_espriella, 0)) <= 30
                THEN 'Q3_CONVERTIR'
            ELSE 'Q4_RESISTIR'
        END AS cuadrante
    FROM base b
    LEFT JOIN cep c ON b.scope_idx=c.scope_idx
    LEFT JOIN esp e ON b.scope_idx=e.scope_idx
    LEFT JOIN dig d ON b.scope_idx=d.scope_idx
    LEFT JOIN cluster_mapping cm ON b.scope_idx = cm.idx
    """)

    # Agregados por cuadrante
    print("=" * 70)
    print("CUADRANTES DE 2DA VUELTA · ESCENARIO 3M VOTOS PARA CEPEDA")
    print("=" * 70)
    print()
    print(f"{'Cuadrante':25s} {'Mpios':>6} {'Cepeda hoy':>14} {'Espriella':>14} {'No-votantes':>14}")
    print("-" * 75)
    cuads = con.execute("""
        SELECT cuadrante, COUNT(*) mpios,
               SUM(votos_cepeda), SUM(votos_espriella), SUM(no_votantes)
        FROM cuadrantes_2v GROUP BY cuadrante
        ORDER BY CASE cuadrante
            WHEN 'Q1_DEFENDER' THEN 1 WHEN 'Q1_DEFENDER_FRAGIL' THEN 2
            WHEN 'Q2_MOVILIZAR' THEN 3 WHEN 'Q3_CONVERTIR' THEN 4
            WHEN 'Q4_RESISTIR' THEN 5 END
    """).fetchall()
    tot_cepeda = tot_espriella = tot_no = 0
    for r in cuads:
        print(f"  {r[0]:23s} {r[1]:>6} {r[2] or 0:>14,} {r[3] or 0:>14,} {r[4] or 0:>14,}")
        tot_cepeda += r[2] or 0
        tot_espriella += r[3] or 0
        tot_no += r[4] or 0
    print("-" * 75)
    print(f"  {'TOTAL':23s} {sum(r[1] for r in cuads):>6} {tot_cepeda:>14,} {tot_espriella:>14,} {tot_no:>14,}")
    print()

    # Simulación 3M: cuánto puede aportar cada cuadrante
    print("APORTE POTENCIAL A LOS 3M EXTRA · supuestos por cuadrante:")
    print()
    asunciones = [
        ("Q1_DEFENDER",       0.10, 0.55, "movilizar 10% de no-votantes + 55% afinidad histórica"),
        ("Q1_DEFENDER_FRAGIL", 0.08, 0.50, "movilizar 8% no-votantes + 50% afinidad"),
        ("Q2_MOVILIZAR",      0.12, 0.55, "movilizar 12% no-votantes + 55% (voto consciente)"),
        ("Q3_CONVERTIR",      0.08, 0.35, "movilizar 8% no-votantes + 35% (persuasión centro/Dignidad/blanco)"),
        ("Q4_RESISTIR",       0.03, 0.20, "blindar piso · solo 3% no-votantes × 20%"),
    ]
    proyectado_total = 0
    for q, mov_pct, afi, descr in asunciones:
        no_v = con.execute(
            "SELECT COALESCE(SUM(no_votantes), 0), COALESCE(SUM(blanco + no_marcados), 0) FROM cuadrantes_2v WHERE cuadrante=?",
            [q]
        ).fetchone()
        aporte_no_v = int(no_v[0] * mov_pct * afi)
        aporte_voto_blanco = int(no_v[1] * 0.35) if q == "Q3_CONVERTIR" else int(no_v[1] * 0.20)
        total_q = aporte_no_v + aporte_voto_blanco
        proyectado_total += total_q
        print(f"  {q:23s} aporte ~{total_q:>9,} ({aporte_no_v:,} no-votantes + {aporte_voto_blanco:,} blanco/nm)  · {descr}")
    print("-" * 70)
    print(f"  {'TOTAL PROYECTADO':23s} ~{proyectado_total:,}  (meta = 3M)")
    gap = META_3M - proyectado_total
    if gap > 0:
        print(f"  {'GAP vs 3M':23s} {gap:,} faltarían con estos supuestos")
    else:
        print(f"  {'MARGEN':23s} {abs(gap):,} (los 3M son alcanzables)")
    print()

    # Top municipios por cuadrante movilizar y convertir
    print("TOP 15 mpios Q2_MOVILIZAR (margen estrecho · empujar turnout):")
    rows = con.execute("""
        SELECT nombre_municipio, departamento_nombre, cluster,
               pct_cepeda, pct_espriella, no_votantes, brecha_vs_espriella
        FROM cuadrantes_2v WHERE cuadrante='Q2_MOVILIZAR'
        ORDER BY no_votantes DESC LIMIT 15
    """).fetchall()
    for r in rows:
        print(f"  {r[0]:25s} {r[1]:15s} {r[2] or '':20s} Cep={r[3]:5.1f}% Esp={r[4]:5.1f}% no_v={r[5]:>7,} brecha={r[6]:>+7,}")
    print()

    print("TOP 15 mpios Q3_CONVERTIR (gap 10-30% · persuasión centro):")
    rows = con.execute("""
        SELECT nombre_municipio, departamento_nombre, cluster,
               pct_cepeda, pct_espriella, pct_dignidad, no_votantes
        FROM cuadrantes_2v WHERE cuadrante='Q3_CONVERTIR'
        ORDER BY (no_votantes + votos_dignidad * 3) DESC LIMIT 15
    """).fetchall()
    for r in rows:
        print(f"  {r[0]:25s} {r[1]:15s} Cep={r[3]:5.1f}% Esp={r[4]:5.1f}% Dig={r[5]:5.1f}% no_v={r[6]:>7,}")
    print()

    # Exporta CSVs
    for q in ("Q1_DEFENDER", "Q1_DEFENDER_FRAGIL", "Q2_MOVILIZAR", "Q3_CONVERTIR", "Q4_RESISTIR"):
        out_csv = OUT / f"cuadrante_{q.lower()}.csv"
        con.execute(f"""
            COPY (
                SELECT codigo_interno, nombre_municipio, departamento_nombre, cluster,
                       censo, validos, no_votantes, blanco, no_marcados,
                       votos_cepeda, pct_cepeda, votos_espriella, pct_espriella,
                       votos_dignidad, brecha_vs_espriella, margen_pct
                FROM cuadrantes_2v WHERE cuadrante='{q}'
                ORDER BY ABS(brecha_vs_espriella) DESC
            ) TO '{out_csv.as_posix()}' (HEADER, DELIMITER ',')
        """)
        print(f"  -> {out_csv.relative_to(PROJECT_ROOT)}")

    # Reporte markdown final
    rep = OUT / "segunda_vuelta_3M.md"
    lines = []
    lines.append("# Cómo conseguir los 3 millones de votos extra para ganar la 2da vuelta")
    lines.append(f"_Iván Cepeda · Movimiento Político Pacto Histórico_  ")
    lines.append(f"_Generado: {datetime.now(timezone.utc).isoformat()}_")
    lines.append("")
    lines.append("## 1. El runoff: contexto numérico")
    lines.append("")
    lines.append("| Indicador | Valor |")
    lines.append("|---|---:|")
    lines.append(f"| Censo electoral nacional | 41.421.973 |")
    lines.append(f"| Votos válidos 1ra vuelta | 23.668.108 |")
    lines.append(f"| Turnout 1ra vuelta | 57.1% |")
    lines.append(f"| **Espriella (Defensores)** | **10.351.548 · 43.74%** |")
    lines.append(f"| **Cepeda (Pacto)** | **9.683.743 · 40.91%** |")
    lines.append(f"| Brecha 1ra vuelta | 667.805 votos (Espriella +2.83 pp) |")
    lines.append(f"| Voto blanco/nulo/no marcado | ~1.36M |")
    lines.append(f"| Tercero (Centro Democrático) | 1.638.338 · 6.92% |")
    lines.append(f"| Cuarto (Dignidad & Compromiso) | 1.008.111 · 4.26% |")
    lines.append("")
    lines.append("## 2. ¿Por qué la meta son 3 millones?")
    lines.append("")
    lines.append("Tres escenarios de turnout para la 2da vuelta:")
    lines.append("")
    lines.append("| Escenario | Turnout 2v | Universo válidos | 50% + 1 | Votos extra que necesita Cepeda |")
    lines.append("|---|---:|---:|---:|---:|")
    lines.append("| Conservador (igual a 1ra) | 57% | 23.7M | 11.83M | **+2.15M** |")
    lines.append("| Base (+5 pp · histórico CO) | 62% | 25.7M | 12.85M | **+3.17M** ← **meta operativa** |")
    lines.append("| Alto (+10 pp · polarización) | 67% | 27.8M | 13.91M | **+4.22M** |")
    lines.append("")
    lines.append("La meta de 3M es el escenario realista. Si turnout solo sube 5 pp (lo histórico colombiano en 2das vueltas polarizadas), Cepeda necesita exactamente ~3.17M más para superar el 50%+1.")
    lines.append("")
    lines.append("## 3. Cuatro cuadrantes operativos de los 1.189 municipios")
    lines.append("")
    lines.append("Asignación por margen de 1ra vuelta:")
    lines.append("")
    lines.append("| Cuadrante | Definición | Mpios | Cepeda hoy | Espriella hoy | No-votantes (techo) |")
    lines.append("|---|---|---:|---:|---:|---:|")
    cuads_full = con.execute("""
        SELECT cuadrante, COUNT(*),
               COALESCE(SUM(votos_cepeda),0), COALESCE(SUM(votos_espriella),0),
               COALESCE(SUM(no_votantes),0)
        FROM cuadrantes_2v GROUP BY cuadrante
        ORDER BY CASE cuadrante
            WHEN 'Q1_DEFENDER' THEN 1 WHEN 'Q1_DEFENDER_FRAGIL' THEN 2
            WHEN 'Q2_MOVILIZAR' THEN 3 WHEN 'Q3_CONVERTIR' THEN 4
            WHEN 'Q4_RESISTIR' THEN 5 END
    """).fetchall()
    descripciones = {
        "Q1_DEFENDER": "Cepeda gana · afinidad ≥40% · proteger turnout con testigos electorales",
        "Q1_DEFENDER_FRAGIL": "Cepeda gana pero <40% afinidad · territorio movible · reforzar antes que se pierda",
        "Q2_MOVILIZAR": "Margen ≤10 pp en cualquier dirección · empujar turnout es la palanca clave",
        "Q3_CONVERTIR": "Cepeda detrás por 10-30 pp · persuadir centro / votantes Dignidad / blanco",
        "Q4_RESISTIR": "Cepeda detrás >30 pp · territorio hostil · meta defensiva: piso digno",
    }
    for r in cuads_full:
        lines.append(f"| **{r[0]}** | {descripciones.get(r[0], '')} | {r[1]} | {r[2]:,} | {r[3]:,} | {r[4]:,} |")
    lines.append("")
    lines.append("## 4. Aporte potencial por cuadrante (modelo · 3M target)")
    lines.append("")
    lines.append("Asunciones por cuadrante:")
    lines.append("")
    lines.append("| Cuadrante | % no-votantes movilizables | Afinidad de los nuevos | % voto blanco capturable | Aporte estimado |")
    lines.append("|---|---:|---:|---:|---:|")
    aporte_total = 0
    for q, mov_pct, afi, _descr in asunciones:
        no_v = con.execute(
            "SELECT COALESCE(SUM(no_votantes), 0), COALESCE(SUM(blanco + no_marcados), 0) FROM cuadrantes_2v WHERE cuadrante=?",
            [q]
        ).fetchone()
        aporte_no_v = int(no_v[0] * mov_pct * afi)
        blanco_pct = 0.35 if q == "Q3_CONVERTIR" else 0.20
        aporte_blanco = int(no_v[1] * blanco_pct)
        total_q = aporte_no_v + aporte_blanco
        aporte_total += total_q
        lines.append(f"| {q} | {mov_pct*100:.0f}% | {afi*100:.0f}% | {blanco_pct*100:.0f}% | **{total_q:,}** |")
    lines.append(f"| **TOTAL** | | | | **{aporte_total:,}** |")
    lines.append("")
    gap = META_3M - aporte_total
    if gap > 0:
        lines.append(f"**Resultado del modelo**: gap de **{gap:,} votos** vs meta 3M. La campaña necesita superar al menos uno de los supuestos (subir % movilizados, mejorar afinidad de los nuevos, o capturar más voto blanco).")
    else:
        lines.append(f"**Resultado del modelo**: meta de 3M es alcanzable con holgura de **{abs(gap):,} votos** según estos supuestos. La ejecución debe respetar los porcentajes asumidos por cuadrante.")
    lines.append("")

    # Top 15 por cuadrante
    for q, titulo, ord_sql in [
        ("Q2_MOVILIZAR", "Top 15 Q2_MOVILIZAR · margen estrecho · empujar turnout", "no_votantes DESC"),
        ("Q3_CONVERTIR", "Top 15 Q3_CONVERTIR · persuasión centro/Dignidad/blanco", "(no_votantes + votos_dignidad * 3) DESC"),
        ("Q1_DEFENDER", "Top 15 Q1_DEFENDER · territorio Cepeda · proteger turnout", "votos_cepeda DESC"),
    ]:
        lines.append(f"## 5. {titulo}")
        lines.append("")
        lines.append("| # | Municipio | Departamento | Cluster | Cep% | Esp% | No-votantes | Brecha |")
        lines.append("|---:|---|---|---|---:|---:|---:|---:|")
        rows = con.execute(f"""
            SELECT nombre_municipio, departamento_nombre, cluster,
                   pct_cepeda, pct_espriella, no_votantes, brecha_vs_espriella, votos_cepeda
            FROM cuadrantes_2v WHERE cuadrante=?
            ORDER BY {ord_sql} LIMIT 15
        """, [q]).fetchall()
        for i, r in enumerate(rows, 1):
            lines.append(f"| {i} | {r[0]} | {r[1]} | {r[2] or '-'} | {r[3]:.1f}% | {r[4]:.1f}% | {r[5]:,} | {r[6]:+,} |")
        lines.append("")

    # Mapas + outputs
    lines.append("## 6. Mapas interactivos generados (abrir con doble-click en navegador)")
    lines.append("")
    lines.append("- [`mapa_afinidad_cepeda.html`](./mapa_afinidad_cepeda.html) · % Cepeda por municipio (verde=fuerte, rojo=débil)")
    lines.append("- [`mapa_ganador_local.html`](./mapa_ganador_local.html) · quién ganó en cada municipio (verde=Cepeda, rojo=Espriella)")
    lines.append("- [`mapa_brecha_vs_espriella.html`](./mapa_brecha_vs_espriella.html) · diferencia Cepeda-Espriella en votos (rojo=detrás, verde=adelante)")
    lines.append("- [`mapa_oportunidad_2da_vuelta.html`](./mapa_oportunidad_2da_vuelta.html) · score 2da vuelta por mpio")
    lines.append("")
    lines.append("## 7. CSVs exportados (un archivo por cuadrante)")
    lines.append("")
    lines.append("- `cuadrante_q1_defender.csv` · municipios a proteger")
    lines.append("- `cuadrante_q1_defender_fragil.csv` · ganados con margen estrecho")
    lines.append("- `cuadrante_q2_movilizar.csv` · margen ≤10 pp · palanca turnout")
    lines.append("- `cuadrante_q3_convertir.csv` · gap 10-30 pp · persuasión")
    lines.append("- `cuadrante_q4_resistir.csv` · territorio hostil · defensa de piso")
    lines.append("")
    lines.append("## 8. Acción prioritaria sugerida")
    lines.append("")
    lines.append("1. **Q2_MOVILIZAR + Q1_DEFENDER_FRAGIL**: aquí se gana o se pierde. Son los municipios con margen <10 pp en cualquier dirección. Concentrar testigos electorales (2 por puesto mínimo · más que la 1ra), brigadas de transporte el día E, mensajería puerta a puerta.")
    lines.append("2. **Q3_CONVERTIR**: trabajo de coalición con Dignidad & Compromiso y con votantes en blanco/centristas. Mensaje: alternativa al modelo Espriella sin radicalismos. Foco en los top 50 por (no-votantes + 3×votos_Dignidad).")
    lines.append("3. **Q1_DEFENDER**: NO descuidar. La trampa clásica es asumir que está ganado. Mantener al menos un testigo por puesto y comunicación local activa hasta el día E.")
    lines.append("4. **Q4_RESISTIR**: invertir lo justo. Piso digno (>20%) es suficiente. No gastar recursos en mpios donde la brecha es matemáticamente irrecuperable. Decisión basada en datos, no en ego.")
    lines.append("")
    lines.append("---")
    lines.append("_Fuente: scrapeo público https://resultados.registraduria.gov.co/ · 1ra vuelta presidencial Colombia 2026 · escrutinio al 99.92%_  ")
    lines.append("_Código: `C:\\Users\\wilso\\Desktop\\Escritorio2026\\elecciones\\estrategia\\segunda_vuelta_3M.py`_")

    rep.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[reporte] {rep.relative_to(PROJECT_ROOT)}")

    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
