# elecciones-co-2026

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Plotly](https://img.shields.io/badge/maps-plotly-3F4F75.svg)](https://plotly.com/python/)

Análisis municipio-a-municipio de la **primera vuelta presidencial Colombia 2026** y mapa de oportunidad estratégica para la segunda vuelta.

**Web pública (mapas + dashboard + descargas)**: <https://wilsonherrera77.github.io/elecciones-co-2026/>

---

## Qué hace

1. Captura los resultados oficiales municipio-a-municipio desde la fuente pública de la Registraduría (1.189 municipios · 14 listas · censo 41.4M).
2. Persiste en DuckDB analítico + Parquet append-only.
3. Clasifica los 1.189 municipios en 23 clusters geo-políticos.
4. Calcula mapa de oportunidad para conseguir **+3 millones de votos para Iván Cepeda** (Pacto Histórico) en segunda vuelta.
5. Genera 4 mapas interactivos (afinidad, ganador local, brecha vs rival, score 2da vuelta).
6. Produce reporte ejecutivo Word por departamento (34 capítulos).

## Hallazgos clave (datos reales · escrutinio al 99.92%)

| Indicador | Valor |
|---|---:|
| Censo nacional | 41.421.973 |
| Votos válidos 1ra vuelta | 23.668.108 |
| **Espriella (Defensores de la Patria)** | **10.351.548 · 43.74%** |
| **Cepeda (Pacto Histórico)** | **9.683.743 · 40.91%** |
| Brecha 1ra vuelta | 667.805 votos (Espriella +2.83 pp) |
| Meta operativa 2da vuelta | +3.000.000 votos para Cepeda |
| Municipios que ganó Cepeda | 432 |
| Municipios que ganó Espriella | 756 |

## Quickstart

```powershell
git clone https://github.com/wilsonherrera77/elecciones-co-2026
cd elecciones-co-2026
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium

# Pipeline completo
python scraper/discovery_playwright.py
python scraper/nomenclator.py
python scraper/fetch_estatico.py --full
python -m scraper.geojsons --modo departamentos

python -m estrategia.cluster_geo
python -m estrategia.mapa_oportunidad
python -m estrategia.segunda_vuelta_3M
python -m estrategia.mapas
python -m estrategia.docx_departamental
python -m estrategia.cepeda_3M
```

## Arquitectura

```
elecciones-co-2026/
├── scraper/              # Captura datos
│   ├── discovery_playwright.py  # Descubre URLs del portal SPA (1 vez)
│   ├── fetch_estatico.py        # async httpx · 1.189 mpios en ~25s
│   ├── nomenclator.py           # División política + 14 partidos
│   ├── geojsons.py              # 35 geojsons (Colombia + 34 deptos)
│   ├── incremental.py           # Polling cada 5 min
│   ├── schema.py                # Pydantic models
│   └── db.py                    # DuckDB schema
├── estrategia/
│   ├── cluster_geo.py           # 23 clusters geo-políticos
│   ├── mapa_oportunidad.py      # Score por municipio
│   ├── segunda_vuelta_3M.py     # Cuadrantes Q1/Q2/Q3/Q4
│   ├── mapas.py                 # 4 mapas plotly HTML
│   ├── docx_departamental.py    # Word ejecutivo 34 deptos
│   └── cepeda_3M.py             # Reporte ejecutivo
├── data/
│   ├── raw/                     # JSONs crudos
│   ├── processed/               # DB + parquets
│   └── outputs/                 # CSVs + markdown + Word + HTML
├── docs/                        # Sitio público (GitHub Pages)
├── scripts_apoyo/               # Doctor, publicación
├── tests/                       # pytest
└── infra/ports.yml
```

## Mapas

| Mapa | Lectura |
|---|---|
| Afinidad Cepeda | Verde fuerte donde Cepeda obtuvo >50% · rojo donde <20% |
| Ganador local | Verde = Cepeda · Rojo = Espriella |
| Brecha vs Espriella | Rojo = Cepeda atrás · Verde = Cepeda adelante |
| Score 2da vuelta | Azul oscuro = mayor potencial de sumar votos |

## Outputs

- `data/outputs/segunda_vuelta_3M.md` · análisis estratégico completo
- `data/outputs/analisis_departamental_3M_cepeda.docx` · 34 capítulos departamentales
- `data/outputs/cuadrante_q*.csv` · 5 CSVs (Q1 defender · Q2 movilizar · Q3 convertir · Q4 resistir)
- `data/outputs/mapa_oportunidad_top200.csv` · top 200 municipios por score
- `data/outputs/defender_top100.csv` · 100 municipios donde Cepeda ya gana

## Cuadrantes operativos (2da vuelta)

| Cuadrante | Margen | Mpios | Estrategia |
|---|---|---:|---|
| **Q1 Defender** | Cepeda ganó · afinidad ≥40% | 425 | Proteger turnout con testigos electorales |
| Q1 Defender frágil | Cepeda ganó · margen menor | 6 | Reforzar antes que se pierda |
| **Q2 Movilizar** | Margen ≤10 pp | 81 | Empujar no-votantes · puerta a puerta |
| **Q3 Convertir** | Gap 10-30 pp | 240 | Coalición Dignidad + voto blanco |
| Q4 Resistir | Gap >30 pp | 437 | Piso digno · no derrochar recursos |

## Stack técnico

- Python 3.11+ · venv local
- `httpx[http2]` · async + HTTP/2
- `playwright` · descubrimiento del portal
- `duckdb` · base analítica
- `plotly` · 4 mapas HTML interactivos
- `python-docx` · documento ejecutivo
- `pydantic v2` · validación

## Fuente de datos

Resultados oficiales públicos de la Registraduría Nacional del Estado Civil. División política, partidos y polígonos vienen del mismo origen público.

## Limitaciones

- Bogotá D.C. agregada como un solo municipio en este nivel · drill-down por localidad requiere extender el scraper.
- No incorpora datos de pobreza/NBI municipal (queda como mejora futura).

## Licencia

MIT · ver [LICENSE](./LICENSE)

---

Wilson Herrera Quiroga · 2026
