"""mapa_oportunidad.py · ranking de municipios para campaña 3M Cepeda.

Score por municipio:
  potencial_m   = max(0, censo - (votantes_m))
  afinidad_m    = votos_cepeda_m / NULLIF(votos_validos_m, 0)
  ganador_pct   = pct del partido líder
  brecha_pct    = ganador_pct - afinidad_m * 100

  score_oportunidad = potencial_m * (0.5 + 0.4 * afinidad_m + 0.1 * nbi/100)
  score_defensa     = afinidad_m * votos_cepeda_m   # quemar turnout donde ya gana

Outputs:
  data/outputs/mapa_oportunidad_top200.csv
  data/outputs/defender_top100.csv
  data/outputs/perdidos_top100.csv  (donde Cepeda está MUY abajo pero hay potencial alto)
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, PROJECT_ROOT.as_posix())

from scraper.db import connect  # noqa: E402

CODPAR_CEPEDA = "7"  # Pacto Histórico (orden boleta i=7 · confirmado en datos reales)


def main() -> int:
    con = connect()

    # SQL: pivota tabla snapshot a wide (un row por municipio) con votos por candidato
    # Y trae cluster + nbi
    con.execute("DROP TABLE IF EXISTS mapa_oportunidad_municipio;")
    con.execute(f"""
    CREATE TABLE mapa_oportunidad_municipio AS
    WITH base AS (
      SELECT
        s.scope_idx,
        s.codigo_interno,
        s.nombre_municipio,
        s.departamento_idx,
        s.departamento_nombre,
        MAX(s.censo_electoral) AS censo,
        MAX(s.votos_validos) AS votos_validos,
        MAX(s.votos_blanco) AS votos_blanco,
        MAX(s.votos_nulos) AS votos_nulos,
        MAX(s.votos_no_marcados) AS votos_no_marcados,
        MAX(s.mesas_informadas) AS mesas_informadas,
        MAX(s.mesas_total) AS mesas_total,
        MAX(s.ts_snapshot) AS ts_snapshot,
        SUM(s.votos) AS votos_total_partidos
      FROM votos_municipio_snapshot s
      GROUP BY 1, 2, 3, 4, 5
    ),
    cepeda AS (
      SELECT scope_idx, votos AS votos_cepeda, porcentaje AS pct_cepeda
      FROM votos_municipio_snapshot WHERE codpar='{CODPAR_CEPEDA}'
    ),
    ganador AS (
      SELECT scope_idx, codpar, votos, porcentaje,
             ROW_NUMBER() OVER (PARTITION BY scope_idx ORDER BY votos DESC NULLS LAST) AS rn
      FROM votos_municipio_snapshot
    )
    SELECT
      b.scope_idx,
      b.codigo_interno,
      b.nombre_municipio,
      b.departamento_idx,
      b.departamento_nombre,
      cm.cluster,
      b.censo,
      b.votos_validos,
      b.votos_blanco,
      b.votos_nulos,
      b.votos_no_marcados,
      b.mesas_informadas,
      b.mesas_total,
      COALESCE(c.votos_cepeda, 0) AS votos_cepeda,
      COALESCE(c.pct_cepeda, 0.0) AS pct_cepeda,
      g.codpar AS ganador_codpar,
      g.votos AS ganador_votos,
      g.porcentaje AS ganador_pct,
      (b.censo - COALESCE(b.votos_validos, 0)) AS potencial_no_votante,
      (g.votos - COALESCE(c.votos_cepeda, 0)) AS brecha_votos_vs_ganador,
      CASE WHEN b.votos_validos > 0
           THEN CAST(COALESCE(c.votos_cepeda, 0) AS DOUBLE) / b.votos_validos
           ELSE 0.0 END AS afinidad,
      b.ts_snapshot
    FROM base b
    LEFT JOIN cepeda c ON b.scope_idx = c.scope_idx
    LEFT JOIN ganador g ON b.scope_idx = g.scope_idx AND g.rn = 1
    LEFT JOIN cluster_mapping cm ON b.scope_idx = cm.idx;
    """)

    # Cantidad de mpios con datos
    n = con.execute("SELECT COUNT(*) FROM mapa_oportunidad_municipio WHERE votos_validos > 0").fetchone()[0]
    print(f"[mapa_oportunidad] municipios con datos: {n}")

    # Score con NBI si está disponible · si no, default 0.4 (promedio nacional aprox)
    has_nbi = con.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_name='nbi_municipal'").fetchone()[0]
    nbi_join = ""
    nbi_expr = "0.4"
    if has_nbi:
        nbi_join = """
        LEFT JOIN nbi_municipal nbi ON (
            (UPPER(REPLACE(m.nombre_municipio,'.','')) = nbi.nombre_norm)
            AND (UPPER(REPLACE(m.departamento_nombre,'.','')) = nbi.departamento_norm)
        )
        """
        nbi_expr = "COALESCE(nbi.nbi_total/100.0, 0.4)"

    con.execute(f"""
    CREATE OR REPLACE VIEW v_score AS
    SELECT m.*,
        {nbi_expr} AS nbi_score,
        (CAST(m.potencial_no_votante AS DOUBLE)
         * (0.5 + 0.4 * m.afinidad + 0.1 * {nbi_expr})
        ) AS score_oportunidad,
        (m.afinidad * COALESCE(m.votos_cepeda, 0)) AS score_defensa
    FROM mapa_oportunidad_municipio m
    {nbi_join}
    WHERE m.votos_validos > 0;
    """)

    # Top 200 oportunidad
    out = PROJECT_ROOT / "data" / "outputs"
    out.mkdir(parents=True, exist_ok=True)
    con.execute(f"""
        COPY (
            SELECT codigo_interno, nombre_municipio, departamento_nombre, cluster,
                   censo, votos_validos, votos_cepeda, pct_cepeda,
                   ganador_codpar, ganador_pct,
                   potencial_no_votante, brecha_votos_vs_ganador,
                   ROUND(nbi_score, 3) AS nbi_score,
                   ROUND(score_oportunidad, 0) AS score_oportunidad
            FROM v_score
            ORDER BY score_oportunidad DESC
            LIMIT 200
        ) TO '{(out / "mapa_oportunidad_top200.csv").as_posix()}' (HEADER, DELIMITER ',')
    """)

    con.execute(f"""
        COPY (
            SELECT codigo_interno, nombre_municipio, departamento_nombre, cluster,
                   censo, votos_validos, votos_cepeda, pct_cepeda,
                   ROUND(afinidad, 4) AS afinidad,
                   ROUND(score_defensa, 0) AS score_defensa
            FROM v_score
            WHERE afinidad > 0.30
            ORDER BY score_defensa DESC
            LIMIT 100
        ) TO '{(out / "defender_top100.csv").as_posix()}' (HEADER, DELIMITER ',')
    """)

    con.execute(f"""
        COPY (
            SELECT codigo_interno, nombre_municipio, departamento_nombre, cluster,
                   censo, votos_validos, votos_cepeda, pct_cepeda, afinidad,
                   ganador_codpar, ganador_pct,
                   potencial_no_votante
            FROM v_score
            WHERE afinidad < 0.10 AND potencial_no_votante > 5000
            ORDER BY potencial_no_votante DESC
            LIMIT 100
        ) TO '{(out / "perdidos_top100.csv").as_posix()}' (HEADER, DELIMITER ',')
    """)

    # Resumen agregado por cluster
    print("\n[resumen] votos Cepeda actuales por cluster:")
    rows = con.execute("""
        SELECT cluster,
               COUNT(*) AS mpios,
               SUM(votos_cepeda) AS votos_cepeda,
               ROUND(AVG(afinidad)*100, 1) AS afinidad_avg_pct,
               SUM(potencial_no_votante) AS potencial
        FROM v_score
        GROUP BY cluster
        ORDER BY votos_cepeda DESC NULLS LAST
    """).fetchall()
    for r in rows:
        print(f"  {(r[0] or '?'):30s} mpios={r[1]:>4} votos_cepeda={r[2] or 0:>10,} afinidad={r[3] or 0:>4}% potencial={r[4] or 0:>10,}")

    total_cepeda = con.execute("SELECT SUM(votos_cepeda) FROM v_score").fetchone()[0] or 0
    print(f"\nTOTAL Cepeda en muestra actual: {total_cepeda:,}")
    print(f"Meta: 3.000.000 · gap: {3_000_000 - total_cepeda:,}")
    print(f"Outputs: {out.relative_to(PROJECT_ROOT)}/mapa_oportunidad_top200.csv · defender_top100.csv · perdidos_top100.csv")
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
