"""mapas.py · genera mapas HTML interactivos OFFLINE con plotly.

Mapas producidos:
  A) data/outputs/mapa_afinidad_cepeda.html       · %votos Cepeda por mpio
  B) data/outputs/mapa_ganador_local.html         · quién ganó cada mpio (Espriella/Cepeda/otros)
  C) data/outputs/mapa_brecha_vs_espriella.html   · brecha en votos vs el rival de 2da vuelta
  D) data/outputs/mapa_oportunidad_2da_vuelta.html · score 2da vuelta por mpio

Plotly genera HTML autoejecutable sin servidor · 100% offline · cero cloud.

Uso: `python -m estrategia.mapas`
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb
import plotly.express as px
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GEOJSON = PROJECT_ROOT / "data" / "processed" / "colombia_municipios.geojson"
OUT_DIR = PROJECT_ROOT / "data" / "outputs"

# Codpar de los 2 candidatos finalistas
CEPEDA = "7"
ESPRIELLA = "10"


def load_data() -> pd.DataFrame:
    db_path = PROJECT_ROOT / "data" / "processed" / "votos.duckdb"
    con = duckdb.connect(db_path.as_posix(), read_only=True)
    df_pd = con.execute(f"""
        WITH cepeda AS (
            SELECT scope_idx, codigo_interno, votos AS votos_cepeda, porcentaje AS pct_cepeda
            FROM votos_municipio_snapshot WHERE codpar = '{CEPEDA}'
        ),
        espriella AS (
            SELECT scope_idx, votos AS votos_espriella, porcentaje AS pct_espriella
            FROM votos_municipio_snapshot WHERE codpar = '{ESPRIELLA}'
        ),
        base AS (
            SELECT scope_idx, codigo_interno, nombre_municipio, departamento_nombre,
                   MAX(censo_electoral) AS censo,
                   MAX(votos_validos) AS validos
            FROM votos_municipio_snapshot
            GROUP BY 1, 2, 3, 4
        ),
        ganador AS (
            SELECT scope_idx, codpar AS ganador_codpar
            FROM (
                SELECT scope_idx, codpar, votos,
                       ROW_NUMBER() OVER (PARTITION BY scope_idx ORDER BY votos DESC) AS rn
                FROM votos_municipio_snapshot
            ) WHERE rn = 1
        )
        SELECT b.scope_idx, b.codigo_interno, b.nombre_municipio, b.departamento_nombre,
               b.censo, b.validos,
               COALESCE(c.votos_cepeda, 0) AS votos_cepeda,
               COALESCE(c.pct_cepeda, 0.0) AS pct_cepeda,
               COALESCE(e.votos_espriella, 0) AS votos_espriella,
               COALESCE(e.pct_espriella, 0.0) AS pct_espriella,
               (COALESCE(c.votos_cepeda, 0) - COALESCE(e.votos_espriella, 0)) AS brecha_cepeda_espriella,
               g.ganador_codpar,
               CASE
                   WHEN g.ganador_codpar = '7' THEN 'Cepeda'
                   WHEN g.ganador_codpar = '10' THEN 'Espriella'
                   ELSE 'Otro'
               END AS ganador_label,
               cm.cluster
        FROM base b
        LEFT JOIN cepeda c ON b.scope_idx = c.scope_idx
        LEFT JOIN espriella e ON b.scope_idx = e.scope_idx
        LEFT JOIN ganador g ON b.scope_idx = g.scope_idx
        LEFT JOIN cluster_mapping cm ON b.scope_idx = cm.idx
    """).fetchdf()
    con.close()
    return df_pd


FEATUREIDKEY = "properties.name"
MAPBOX_STYLE = "carto-positron"
ZOOM = 4.4
CENTER = {"lat": 4.6, "lon": -74.1}


def _layout_continuous(title_text: str, cbar_title: str):
    """Layout estándar con colorbar horizontal abajo + título centrado."""
    return dict(
        title={"text": title_text, "x": 0.5, "xanchor": "center",
               "font": {"size": 17, "family": "Inter, system-ui, sans-serif"}},
        margin={"r": 10, "t": 70, "l": 10, "b": 110},
        coloraxis_colorbar={
            "orientation": "h",
            "y": -0.04,
            "x": 0.5,
            "xanchor": "center",
            "len": 0.72,
            "thickness": 22,
            "title": {"text": cbar_title, "side": "top", "font": {"size": 13}},
            "tickfont": {"size": 12},
            "outlinewidth": 0,
            "bgcolor": "rgba(255,255,255,0.6)",
        },
        font={"family": "Inter, system-ui, sans-serif"},
    )


def make_map_afinidad(pdf: pd.DataFrame, geojson: dict) -> None:
    fig = px.choropleth_mapbox(
        pdf,
        geojson=geojson,
        locations="codigo_interno",
        featureidkey=FEATUREIDKEY,
        color="pct_cepeda",
        color_continuous_scale=[
            (0.0, "#7a0c2e"), (0.25, "#d44b3f"), (0.5, "#f5f5f5"),
            (0.65, "#7fc97f"), (1.0, "#0a6e3a")
        ],
        range_color=[0, 80],
        mapbox_style=MAPBOX_STYLE,
        zoom=ZOOM, center=CENTER,
        opacity=0.78,
        hover_data={
            "nombre_municipio": True,
            "departamento_nombre": True,
            "pct_cepeda": ":.1f",
            "votos_cepeda": ":,",
            "censo": ":,",
            "cluster": True,
            "codigo_interno": False,
        },
    )
    fig.update_layout(**_layout_continuous(
        "Afinidad Iván Cepeda · % votos por municipio · 1ra vuelta presidencial Colombia 2026",
        "% de votos válidos para Cepeda (rojo = bajo · verde = alto)",
    ))
    out = OUT_DIR / "mapa_afinidad_cepeda.html"
    fig.write_html(out, include_plotlyjs="cdn", full_html=True)
    print(f"  -> {out.relative_to(PROJECT_ROOT)}")


def make_map_ganador(pdf: pd.DataFrame, geojson: dict) -> None:
    color_map = {"Cepeda": "#0a6e3a", "Espriella": "#c43d2e", "Otro": "#cccccc"}
    fig = px.choropleth_mapbox(
        pdf,
        geojson=geojson,
        locations="codigo_interno",
        featureidkey=FEATUREIDKEY,
        color="ganador_label",
        color_discrete_map=color_map,
        category_orders={"ganador_label": ["Cepeda", "Espriella", "Otro"]},
        mapbox_style=MAPBOX_STYLE,
        zoom=ZOOM, center=CENTER,
        opacity=0.78,
        labels={"ganador_label": "Ganador 1ra vuelta"},
        hover_data={
            "nombre_municipio": True,
            "departamento_nombre": True,
            "ganador_label": True,
            "pct_cepeda": ":.1f",
            "pct_espriella": ":.1f",
            "codigo_interno": False,
        },
    )
    fig.update_layout(
        title={"text": "¿Quién ganó cada municipio? · Cepeda vs Espriella · 1ra vuelta 2026",
               "x": 0.5, "xanchor": "center",
               "font": {"size": 17, "family": "Inter, system-ui, sans-serif"}},
        margin={"r": 10, "t": 70, "l": 10, "b": 110},
        legend={"orientation": "h", "y": -0.05, "x": 0.5, "xanchor": "center",
                "title": {"text": "Ganador local"}, "font": {"size": 13},
                "bgcolor": "rgba(255,255,255,0.6)", "bordercolor": "#cccccc", "borderwidth": 1},
        font={"family": "Inter, system-ui, sans-serif"},
    )
    out = OUT_DIR / "mapa_ganador_local.html"
    fig.write_html(out, include_plotlyjs="cdn", full_html=True)
    print(f"  -> {out.relative_to(PROJECT_ROOT)}")


def make_map_brecha(pdf: pd.DataFrame, geojson: dict) -> None:
    fig = px.choropleth_mapbox(
        pdf,
        geojson=geojson,
        locations="codigo_interno",
        featureidkey=FEATUREIDKEY,
        color="brecha_cepeda_espriella",
        color_continuous_scale="RdYlGn",
        range_color=[-20000, 20000],
        mapbox_style=MAPBOX_STYLE,
        zoom=ZOOM, center=CENTER,
        opacity=0.78,
        hover_data={
            "nombre_municipio": True,
            "departamento_nombre": True,
            "votos_cepeda": ":,",
            "votos_espriella": ":,",
            "brecha_cepeda_espriella": ":,",
            "codigo_interno": False,
        },
    )
    fig.update_layout(**_layout_continuous(
        "Brecha Cepeda − Espriella en votos · por municipio · 1ra vuelta 2026",
        "Votos Cepeda − Votos Espriella (rojo = Cepeda atrás · verde = Cepeda adelante)",
    ))
    out = OUT_DIR / "mapa_brecha_vs_espriella.html"
    fig.write_html(out, include_plotlyjs="cdn", full_html=True)
    print(f"  -> {out.relative_to(PROJECT_ROOT)}")


def make_map_oportunidad(pdf: pd.DataFrame, geojson: dict) -> None:
    pdf = pdf.copy()
    pdf["no_votantes"] = (pdf["censo"] - pdf["validos"]).clip(lower=0)
    pdf["score_2v"] = (
        pdf["pct_cepeda"] / 100.0 * pdf["no_votantes"]
        + (pdf["votos_espriella"] - pdf["votos_cepeda"]).clip(lower=0, upper=10000) * 0.5
    )
    fig = px.choropleth_mapbox(
        pdf,
        geojson=geojson,
        locations="codigo_interno",
        featureidkey=FEATUREIDKEY,
        color="score_2v",
        color_continuous_scale="YlGnBu",
        range_color=[0, pdf["score_2v"].quantile(0.95)],
        mapbox_style=MAPBOX_STYLE,
        zoom=ZOOM, center=CENTER,
        opacity=0.78,
        hover_data={
            "nombre_municipio": True,
            "departamento_nombre": True,
            "score_2v": ":,.0f",
            "no_votantes": ":,",
            "pct_cepeda": ":.1f",
            "votos_espriella": ":,",
            "codigo_interno": False,
        },
    )
    fig.update_layout(**_layout_continuous(
        "Score de oportunidad 2da vuelta · municipios donde Cepeda puede sumar votos",
        "Score = afinidad × no-votantes + brecha capturable (azul oscuro = mayor potencial)",
    ))
    out = OUT_DIR / "mapa_oportunidad_2da_vuelta.html"
    fig.write_html(out, include_plotlyjs="cdn", full_html=True)
    print(f"  -> {out.relative_to(PROJECT_ROOT)}")


def main() -> int:
    if not GEOJSON.exists():
        print(f"ERROR: falta {GEOJSON}. Corre `python -m scraper.geojsons --modo departamentos`")
        return 1
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("[mapas] cargando geojson...")
    geojson = json.loads(GEOJSON.read_text(encoding="utf-8"))
    print(f"  features en geojson: {len(geojson['features'])}")

    print("[mapas] cargando datos electorales...")
    df = load_data()
    print(f"  municipios con datos: {len(df)}")

    print("[mapas] generando mapa A: afinidad Cepeda")
    make_map_afinidad(df, geojson)
    print("[mapas] generando mapa B: ganador local")
    make_map_ganador(df, geojson)
    print("[mapas] generando mapa C: brecha vs Espriella")
    make_map_brecha(df, geojson)
    print("[mapas] generando mapa D: score oportunidad 2da vuelta")
    make_map_oportunidad(df, geojson)
    return 0


if __name__ == "__main__":
    sys.exit(main())
