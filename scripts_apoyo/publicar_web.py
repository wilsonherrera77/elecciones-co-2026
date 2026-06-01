"""publicar_web.py · genera docs/ para GitHub Pages.

Pasos:
1. Copia los 4 mapas HTML a docs/mapas/
2. Copia los CSVs cuadrantes + outputs a docs/descargas/
3. Copia el Word a docs/descargas/
4. Genera docs/index.html (landing) con stats live de la DB
5. Genera docs/reporte.html (versión HTML del reporte 2da vuelta)

Uso: `python -m scripts_apoyo.publicar_web`
"""

from __future__ import annotations

import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB = PROJECT_ROOT / "data" / "processed" / "votos.duckdb"
DOCS = PROJECT_ROOT / "docs"
OUTPUTS = PROJECT_ROOT / "data" / "outputs"


def copy_assets() -> dict:
    """Copia mapas, CSVs y Word a docs/."""
    (DOCS / "mapas").mkdir(parents=True, exist_ok=True)
    (DOCS / "descargas").mkdir(parents=True, exist_ok=True)

    # Mapas (4)
    mapas = ["mapa_afinidad_cepeda.html", "mapa_ganador_local.html",
             "mapa_brecha_vs_espriella.html", "mapa_oportunidad_2da_vuelta.html"]
    for m in mapas:
        src = OUTPUTS / m
        if src.exists():
            shutil.copy2(src, DOCS / "mapas" / m)

    # CSVs (cuadrantes + top 200 + defender + perdidos)
    for csv in OUTPUTS.glob("*.csv"):
        shutil.copy2(csv, DOCS / "descargas" / csv.name)

    # Reporte 2da vuelta markdown
    rep = OUTPUTS / "segunda_vuelta_3M.md"
    if rep.exists():
        shutil.copy2(rep, DOCS / "descargas" / rep.name)

    # Word (puede no existir aún si está corriendo en background)
    docx = OUTPUTS / "analisis_departamental_3M_cepeda.docx"
    docx_exists = docx.exists()
    if docx_exists:
        shutil.copy2(docx, DOCS / "descargas" / docx.name)

    # CSV cluster_mapping
    cl_csv = PROJECT_ROOT / "data" / "processed" / "cluster_mapping.csv"
    if cl_csv.exists():
        shutil.copy2(cl_csv, DOCS / "descargas" / "cluster_mapping.csv")

    return {"docx": docx_exists, "n_csvs": len(list((DOCS / "descargas").glob("*.csv")))}


def get_stats() -> dict:
    """Lee stats de la DB para el dashboard."""
    con = duckdb.connect(DB.as_posix(), read_only=True)
    nac = con.execute("""
        SELECT
            (SELECT SUM(censo_electoral) FROM (SELECT DISTINCT scope_idx, censo_electoral FROM votos_municipio_snapshot)) censo,
            (SELECT SUM(votos_validos) FROM (SELECT DISTINCT scope_idx, votos_validos FROM votos_municipio_snapshot)) validos,
            (SELECT SUM(votos) FROM votos_municipio_snapshot WHERE codpar='7') cepeda,
            (SELECT SUM(votos) FROM votos_municipio_snapshot WHERE codpar='10') espriella,
            (SELECT COUNT(*) FROM divipola_2026 WHERE level=3) mpios_total
    """).fetchone()
    cuads = dict(con.execute("""
        SELECT
            CASE WHEN cuadrante LIKE 'Q1%' THEN 'Q1' ELSE cuadrante END AS q,
            COUNT(*) AS n
        FROM cuadrantes_2v GROUP BY 1
    """).fetchall())
    top_op = con.execute("""
        SELECT nombre_municipio, departamento_nombre, votos_cepeda, pct_cepeda,
               no_votantes, brecha_vs_espriella
        FROM cuadrantes_2v
        WHERE cuadrante IN ('Q2_MOVILIZAR', 'Q3_CONVERTIR')
        ORDER BY no_votantes DESC LIMIT 20
    """).fetchall()
    pct_escrutinio = con.execute("""
        SELECT ROUND(SUM(mesas_informadas)::DOUBLE / NULLIF(SUM(mesas_total),0)*100, 2)
        FROM (SELECT DISTINCT scope_idx, mesas_informadas, mesas_total FROM votos_municipio_snapshot)
    """).fetchone()[0]
    con.close()
    return {
        "censo": nac[0] or 0,
        "validos": nac[1] or 0,
        "cepeda": nac[2] or 0,
        "espriella": nac[3] or 0,
        "mpios_total": nac[4] or 0,
        "brecha": (nac[3] or 0) - (nac[2] or 0),
        "pct_cep": (nac[2] or 0) / (nac[1] or 1) * 100,
        "pct_esp": (nac[3] or 0) / (nac[1] or 1) * 100,
        "q1": cuads.get("Q1", 0),
        "q2": cuads.get("Q2_MOVILIZAR", 0),
        "q3": cuads.get("Q3_CONVERTIR", 0),
        "q4": cuads.get("Q4_RESISTIR", 0),
        "pct_escrutinio": pct_escrutinio,
        "top_op": top_op,
    }


def fmt(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def render_index(stats: dict, docx_exists: bool) -> str:
    """Genera el HTML del index."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    rows_top = "".join(
        f"<tr><td>{i}</td><td>{r[0]}</td><td>{r[1]}</td>"
        f"<td class='num'>{fmt(r[2])}</td><td class='num'>{r[3]:.1f}%</td>"
        f"<td class='num'>{fmt(r[4])}</td><td class='num'>{r[5]:+,}</td></tr>"
        for i, r in enumerate(stats["top_op"], 1)
    )

    docx_link = (
        '<a class="download-card" href="descargas/analisis_departamental_3M_cepeda.docx" download>'
        '<span class="icon">📄</span><div><div class="title">Documento Word departamental</div>'
        '<div class="desc">Análisis 34 departamentos · narrativa LLM local · ~80 páginas</div></div></a>'
        if docx_exists else
        '<div class="download-card" style="opacity:0.5"><span class="icon">⏳</span>'
        '<div><div class="title">Documento Word departamental</div>'
        '<div class="desc">En generación · regenerar y volver a publicar</div></div></div>'
    )

    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Elecciones Colombia 2026 · análisis 2da vuelta Cepeda + 3M</title>
<meta name="description" content="Captura municipio-a-municipio Registraduría Colombia 2026 + análisis estratégico para conseguir 3M votos extra para Iván Cepeda en 2da vuelta presidencial.">
<meta property="og:title" content="Elecciones Colombia 2026 · Cepeda + 3M">
<meta property="og:description" content="Análisis 1.189 municipios · 4 mapas interactivos · Word ejecutivo por departamento.">
<meta property="og:type" content="website">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="styles.css">
</head>
<body>

<header class="hero">
  <div class="container">
    <div class="meta">Iván Cepeda · Pacto Histórico · 2da vuelta presidencial 2026</div>
    <h1>¿Dónde están los 3 millones de votos<br>para ganar la segunda vuelta?</h1>
    <p class="subtitle">Análisis municipio a municipio (1.189 municipios · 41.4M electores) basado en los datos oficiales de la Registraduría Nacional. Escrutinio al {stats['pct_escrutinio']:.2f}% · captura completa.</p>
    <div class="stats">
      <div class="stat-card"><div class="label">Cepeda · Pacto Histórico</div><div class="value">{fmt(stats['cepeda'])}</div><div class="delta">{stats['pct_cep']:.2f}% de votos válidos</div></div>
      <div class="stat-card"><div class="label">Espriella · Defensores</div><div class="value">{fmt(stats['espriella'])}</div><div class="delta">{stats['pct_esp']:.2f}% · pasa primero a runoff</div></div>
      <div class="stat-card"><div class="label">Brecha de 1ra vuelta</div><div class="value">{fmt(stats['brecha'])}</div><div class="delta">Espriella +{stats['pct_esp']-stats['pct_cep']:.2f} pp</div></div>
      <div class="stat-card"><div class="label">Meta 2da vuelta</div><div class="value">+3.000.000</div><div class="delta">para superar 50%+1 con turnout +5pp</div></div>
    </div>
  </div>
</header>

<section>
  <div class="container">
    <h2>4 mapas interactivos <span class="accent">municipio a municipio</span></h2>
    <p class="section-subtitle">Cada mapa muestra los 1.189 municipios coloreados según una dimensión analítica. Hover sobre cualquier municipio para ver el detalle. Toda la data viene de fuente oficial Registraduría.</p>
    <div class="map-tabs" id="mapTabs">
      <button class="map-tab active" data-target="map-afinidad">Afinidad Cepeda</button>
      <button class="map-tab" data-target="map-ganador">¿Quién ganó?</button>
      <button class="map-tab" data-target="map-brecha">Brecha vs Espriella</button>
      <button class="map-tab" data-target="map-oport">Score 2da vuelta</button>
    </div>
    <div class="map-container">
      <iframe class="map-frame" id="map-afinidad" src="mapas/mapa_afinidad_cepeda.html" title="Afinidad Cepeda"></iframe>
      <iframe class="map-frame hidden" id="map-ganador" src="mapas/mapa_ganador_local.html" title="Ganador local"></iframe>
      <iframe class="map-frame hidden" id="map-brecha" src="mapas/mapa_brecha_vs_espriella.html" title="Brecha vs Espriella"></iframe>
      <iframe class="map-frame hidden" id="map-oport" src="mapas/mapa_oportunidad_2da_vuelta.html" title="Score 2da vuelta"></iframe>
    </div>
  </div>
</section>

<section class="tinted">
  <div class="container">
    <h2>4 cuadrantes operativos <span class="accent">para los 1.189 municipios</span></h2>
    <p class="section-subtitle">Cada municipio se clasifica según la distancia entre Cepeda y Espriella en 1ra vuelta. La táctica de campaña cambia por cuadrante.</p>
    <div class="cuadrantes">
      <div class="cuad-card q1">
        <h3>Q1 · DEFENDER</h3>
        <div class="mpios">{stats['q1']}</div>
        <p>Municipios donde Cepeda ganó. Acción: proteger turnout con testigos electorales · al menos 1 por puesto.</p>
      </div>
      <div class="cuad-card q2">
        <h3>Q2 · MOVILIZAR</h3>
        <div class="mpios">{stats['q2']}</div>
        <p>Margen ≤10 pp en cualquier dirección. Aquí se gana o se pierde · empujar no-votantes Pacto + capturar voto blanco.</p>
      </div>
      <div class="cuad-card q3">
        <h3>Q3 · CONVERTIR</h3>
        <div class="mpios">{stats['q3']}</div>
        <p>Cepeda detrás por 10-30 pp. Persuasión de centro · alianza con Dignidad & Compromiso · capturar voto blanco urbano.</p>
      </div>
      <div class="cuad-card q4">
        <h3>Q4 · RESISTIR</h3>
        <div class="mpios">{stats['q4']}</div>
        <p>Cepeda detrás >30 pp. Territorio hostil · piso digno >20% · no derrochar recursos en mpios irrecuperables.</p>
      </div>
    </div>
  </div>
</section>

<section>
  <div class="container">
    <h2>Top 20 municipios <span class="accent">de oportunidad (Q2 + Q3)</span></h2>
    <p class="section-subtitle">Ordenados por cantidad de no-votantes (techo de turnout movilizable). Estos 20 municipios suman el grueso del potencial para los 3M extra.</p>
    <div style="overflow-x:auto;">
    <table>
      <thead><tr><th>#</th><th>Municipio</th><th>Departamento</th><th>Votos Cepeda</th><th>% Cep</th><th>No-votantes</th><th>Brecha</th></tr></thead>
      <tbody>{rows_top}</tbody>
    </table>
    </div>
  </div>
</section>

<section class="tinted">
  <div class="container">
    <h2>Descargas <span class="accent">data abierta</span></h2>
    <p class="section-subtitle">Todos los outputs analíticos en formato listo para usar. Reproducible con `git clone` + corrida de pipeline.</p>
    <div class="downloads">
      {docx_link}
      <a class="download-card" href="descargas/segunda_vuelta_3M.md" download><span class="icon">📋</span><div><div class="title">Reporte ejecutivo</div><div class="desc">Análisis 2da vuelta + cuadrantes + simulación 3M</div></div></a>
      <a class="download-card" href="descargas/como_leer_los_mapas.md" download><span class="icon">📖</span><div><div class="title">Cómo leer los mapas</div><div class="desc">Guía de interpretación + fórmulas del score 2da vuelta</div></div></a>
      <a class="download-card" href="presentacion.html" style="background:#0a6e3a; color:white; border-color:#0a6e3a"><span class="icon">▶️</span><div><div class="title" style="color:white">Presentación de campaña</div><div class="desc" style="color:rgba(255,255,255,0.85)">12 slides · navegación por teclado · mapas embebidos</div></div></a>
      <a class="download-card" href="descargas/cuadrante_q2_movilizar.csv" download><span class="icon">🎯</span><div><div class="title">CSV Q2 movilizar</div><div class="desc">81 mpios decisivos · margen ≤10pp</div></div></a>
      <a class="download-card" href="descargas/cuadrante_q3_convertir.csv" download><span class="icon">🔄</span><div><div class="title">CSV Q3 convertir</div><div class="desc">240 mpios · persuasión centro</div></div></a>
      <a class="download-card" href="descargas/cuadrante_q1_defender.csv" download><span class="icon">🛡️</span><div><div class="title">CSV Q1 defender</div><div class="desc">425 mpios · proteger turnout</div></div></a>
      <a class="download-card" href="descargas/mapa_oportunidad_top200.csv" download><span class="icon">📊</span><div><div class="title">Top 200 oportunidad</div><div class="desc">Ranking por score (afinidad × potencial)</div></div></a>
      <a class="download-card" href="descargas/cluster_mapping.csv" download><span class="icon">🗺️</span><div><div class="title">Mapeo cluster geo-político</div><div class="desc">1.189 mpios → 23 clusters territoriales</div></div></a>
      <a class="download-card" href="https://github.com/wilsonherrera77/elecciones-co-2026"><span class="icon">💻</span><div><div class="title">Código fuente</div><div class="desc">Repositorio GitHub · MIT · Python 3.11+</div></div></a>
    </div>
  </div>
</section>

<footer>
  <div class="container">
    <p>Fuente: <a href="https://resultados.registraduria.gov.co/">Registraduría Nacional del Estado Civil</a> · escrutinio al {stats['pct_escrutinio']:.2f}% · captura {now} · MIT License</p>
    <p style="margin-top:8px">Wilson Herrera Quiroga · 2026</p>
  </div>
</footer>

<script>
  // Tabs simples para los 4 mapas
  const tabs = document.querySelectorAll('.map-tab');
  const frames = document.querySelectorAll('.map-frame');
  tabs.forEach(t => t.addEventListener('click', () => {{
    tabs.forEach(x => x.classList.remove('active'));
    t.classList.add('active');
    const target = t.getAttribute('data-target');
    frames.forEach(f => {{
      f.classList.toggle('hidden', f.id !== target);
    }});
  }}));
</script>

</body>
</html>
"""


def main() -> int:
    if not DB.exists():
        print("ERROR: corre el pipeline antes")
        return 1
    DOCS.mkdir(exist_ok=True)
    info = copy_assets()
    print(f"[publicar] assets copiados · csvs={info['n_csvs']} · docx={info['docx']}")
    stats = get_stats()
    html = render_index(stats, info["docx"])
    (DOCS / "index.html").write_text(html, encoding="utf-8")
    print(f"[publicar] docs/index.html generado · {len(html)/1024:.1f} KB")
    print(f"[publicar] listo · abrir docs/index.html localmente para verificar antes de push")
    return 0


if __name__ == "__main__":
    sys.exit(main())
