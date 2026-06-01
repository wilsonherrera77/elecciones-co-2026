# elecciones-co-2026 · Análisis Primera Vuelta Presidencial Colombia 2026

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![LOCAL-FIRST](https://img.shields.io/badge/LOCAL--FIRST-Ollama%20qwen2.5%3A14b-green.svg)]()
[![Plotly](https://img.shields.io/badge/maps-plotly-3F4F75.svg)](https://plotly.com/python/)

Herramienta de captura municipio-a-municipio + análisis estratégico de la **primera vuelta presidencial Colombia 2026** desde la fuente oficial `https://resultados.registraduria.gov.co/`.

**Web pública (mapas + dashboard + descargas)**: <https://wilsonherrera77.github.io/elecciones-co-2026/>

---

## ¿Qué hace?

1. **Scrapea** los resultados oficiales municipio-a-municipio (1.189 mpios · 14 listas · censo 41.4M).
2. **Persiste** en DuckDB analítico + Parquet append-only para histórico (polling cada 5 min disponible).
3. **Clasifica** los 1.189 municipios en 23 clusters geo-políticos (Caribe, Pacífico, Eje cafetero, Urabá, Catatumbo, etc.).
4. **Calcula** mapa de oportunidad para conseguir **+3 millones de votos para Iván Cepeda** (Pacto Histórico) en 2da vuelta.
5. **Genera 4 mapas HTML interactivos** (afinidad, ganador local, brecha vs rival, score 2da vuelta).
6. **Produce reporte Word departamental** con narrativa local LLM (Ollama qwen2.5:14b) para 34 departamentos.

## Hallazgos clave (datos reales · escrutinio al 99.92%)

| Indicador | Valor |
|---|---:|
| Censo nacional | 41.421.973 |
| Votos válidos 1ra vuelta | 23.668.108 |
| **Espriella (Defensores de la Patria)** | **10.351.548 · 43.74%** |
| **Cepeda (Pacto Histórico)** | **9.683.743 · 40.91%** |
| Brecha 1ra vuelta | 667.805 votos (Espriella +2.83 pp) |
| Meta operativa 2da vuelta | +3.000.000 votos para Cepeda |
| Mpios que ganó Cepeda | 432 |
| Mpios que ganó Espriella | 756 |

## Quickstart

```powershell
# Setup (una vez)
git clone https://github.com/wilsonherrera77/elecciones-co-2026
cd elecciones-co-2026
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium  # solo para discovery

# Pipeline completo (de cero a reporte)
python -m scripts_apoyo.elecciones_doctor        # health check
python scraper/discovery_playwright.py           # descubrir URL pattern (1 vez)
python scraper/nomenclator.py                    # DIVIPOLA + 14 partidos
python scraper/fetch_estatico.py --full          # captura 1.189 mpios (24s · cero errores)
python -m scraper.geojsons --modo departamentos  # 35 geojsons unificados

# Análisis estratégico
python -m estrategia.cluster_geo                 # 23 clusters geo-políticos
python -m estrategia.mapa_oportunidad            # ranking municipios
python -m estrategia.segunda_vuelta_3M           # cuadrantes Q1/Q2/Q3/Q4
python -m estrategia.mapas                       # 4 mapas HTML
python -m estrategia.docx_departamental          # Word con narrativa LLM
python -m estrategia.cepeda_3M                   # reporte final markdown
```

## Arquitectura

```
elecciones-co-2026/
├── scraper/              # Captura datos Registraduría (Playwright + httpx async)
│   ├── discovery_playwright.py  # Descubre URLs reales del SPA Vite/React (1 vez)
│   ├── fetch_estatico.py        # async httpx · 1.189 mpios en ~25 s · cero errores
│   ├── nomenclator.py           # DIVIPOLA + 14 partidos + parser jerárquico
│   ├── geojsons.py              # Baja 35 geojsons (Colombia + 34 deptos)
│   ├── incremental.py           # Polling cada 5 min hasta cierre escrutinio
│   ├── schema.py                # Pydantic models de los JSON ACT/PR
│   └── db.py                    # DuckDB schema + helpers
├── estrategia/
│   ├── cluster_geo.py           # 1.189 mpios → 23 clusters geo-políticos
│   ├── mapa_oportunidad.py      # SQL puro · score por mpio
│   ├── segunda_vuelta_3M.py     # Cuadrantes Q1/Q2/Q3/Q4 + simulación 3M
│   ├── mapas.py                 # 4 mapas plotly HTML offline
│   ├── narrative_brief.py       # Briefs cluster LOCAL Ollama
│   ├── docx_departamental.py    # Word 34 deptos · narrativa LLM
│   └── cepeda_3M.py             # Reporte ejecutivo markdown
├── data/
│   ├── raw/                     # JSONs crudos comprimidos por snapshot
│   ├── processed/               # votos.duckdb + parquets derivados
│   └── outputs/                 # CSVs · markdown · Word · HTML mapas
├── docs/                        # GitHub Pages (web pública)
├── scripts_apoyo/
│   ├── elecciones_doctor.py     # Health check (9 checks)
│   └── ...
├── tests/                       # pytest 11/11 PASS
└── infra/ports.yml              # Reserva 8520 (dashboard opcional)
```

## Patrón técnico clave · scraper de SPA con WAF

El sitio `resultados.registraduria.gov.co` es un SPA Vite/React con WAF (Cloudfront/Akamai) que bloquea HTTP requests sin headers de browser real. Este proyecto resuelve la trampa en 2 fases:

1. **Discovery (Playwright headed, 1 vez)**: navegar al sitio, interceptar XHRs con `page.on("response", ...)`, capturar URL pattern + headers exactos.
2. **Extracción masiva (httpx async, N veces)**: replicar los headers Chrome (UA + Referer + Origin + Sec-Fetch-Mode/Site/Dest), HTTP/2, token bucket rate limiter.

**Resultado**: 1.189 endpoints en 24.6 s · cero errores · cero cloud API.

Esta lección está documentada en el framework Visual_Agentes como `_doctrina/LECCIONES.md` (lección 2026-05-31b · "Patrón scraper de SPA con WAF para sitios gubernamentales colombianos").

## Mapas

| Mapa | URL | Lectura |
|---|---|---|
| Afinidad Cepeda | [mapa_afinidad_cepeda.html](./data/outputs/mapa_afinidad_cepeda.html) | Verde fuerte donde Cepeda obtuvo >50% · rojo donde <20% |
| Ganador local | [mapa_ganador_local.html](./data/outputs/mapa_ganador_local.html) | Verde = Cepeda ganó · Rojo = Espriella ganó |
| Brecha vs Espriella | [mapa_brecha_vs_espriella.html](./data/outputs/mapa_brecha_vs_espriella.html) | Rojo = Cepeda atrás · Verde = Cepeda adelante |
| Score 2da vuelta | [mapa_oportunidad_2da_vuelta.html](./data/outputs/mapa_oportunidad_2da_vuelta.html) | Azul oscuro = mayor potencial de sumar votos |

## Outputs

- `data/outputs/segunda_vuelta_3M.md` · análisis estratégico completo
- `data/outputs/analisis_departamental_3M_cepeda.docx` · Word con 34 capítulos departamentales
- `data/outputs/cuadrante_q*.csv` · 5 CSVs (Q1 defender · Q2 movilizar · Q3 convertir · Q4 resistir)
- `data/outputs/mapa_oportunidad_top200.csv` · top 200 municipios por score
- `data/outputs/defender_top100.csv` · 100 municipios donde Cepeda ya tiene afinidad >30%

## Cuadrantes operativos (2da vuelta)

Los 1.189 municipios se clasifican según margen Cepeda vs Espriella en 1ra vuelta:

| Cuadrante | Margen | Mpios | Estrategia |
|---|---|---:|---|
| **Q1 Defender** | Cepeda ganó · afinidad ≥40% | 425 | Proteger turnout con testigos electorales |
| Q1 Defender frágil | Cepeda ganó · margen menor | 6 | Reforzar antes que se pierda |
| **Q2 Movilizar** | Margen ≤10 pp | 81 | Empujar no-votantes · mensajería puerta a puerta |
| **Q3 Convertir** | Gap 10-30 pp | 240 | Coalición Dignidad + voto blanco + persuasión centro |
| Q4 Resistir | Gap >30 pp | 437 | Piso digno · no derrochar recursos |

## Reglas duras (heredadas de Visual_Agentes)

- **R#1** Cero `import anthropic` / `openai` / `google.generativeai`. Cero API keys pagas.
- **R#11 LOCAL-FIRST estricto**: Ollama primero · cloud-free después · cloud pago jamás.
- **R#16 Gateway VA**: toda llamada LLM va por `templates/routing_inteligente.py` del framework Visual_Agentes.
- **R#21 Defensa multicapa**: `secrets_scrubber` pre-commit · no se sube ningún token API.

## Stack técnico

- Python 3.11+ · venv local
- `httpx[http2]` · async + HTTP/2 + token bucket
- `playwright` · solo para discovery (1 vez)
- `duckdb` · base analítica · 23 clusters · score determinístico
- `plotly` · 4 mapas HTML interactivos offline
- `python-docx` · documento ejecutivo departamental
- `pydantic v2` · validación de schema
- Ollama qwen2.5:14b · LOCAL · narrativa departamental

## Fuente de datos

- **Resultados**: `https://resultados.registraduria.gov.co/json/ACT/PR/<codigo>.json` (público · escrutinio al 99.92%)
- **DIVIPOLA**: `https://resultados.registraduria.gov.co/json/nomenclator.json`
- **Geojsons**: `https://resultados.registraduria.gov.co/maps/<codigo>.geojson`

## Limitaciones reconocidas

- No usa NBI municipal DANE (URL automática DANE devolvió 404 · queda como deuda).
- Bogotá está agregada como un solo municipio (level=3) · drill-down por localidad requiere extender a level=4 (ZONA) o level=6 (PUESTO).
- Las recomendaciones tácticas del Word son generadas con qwen2.5:14b local · útiles como punto de partida pero NO reemplazan análisis humano.

## Licencia

MIT · ver [LICENSE](./LICENSE)

## Créditos

Construido con el framework [Visual_Agentes](https://github.com/wilsonherrera77) (LOCAL-FIRST · gateway VA · 18 reglas duras). El patrón "scraper de SPA con WAF" está documentado en `_doctrina/LECCIONES.md` del framework para reutilización en futuros proyectos similares.

---

**Autor**: Wilson Herrera Quiroga · 2026-05-31 · cierre escrutinio 1ra vuelta presidencial Colombia 2026.
