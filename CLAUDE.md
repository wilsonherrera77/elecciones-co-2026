# elecciones · contexto canónico

Proyecto **standalone** para reconstruir resultados de la primera vuelta presidencial Colombia 2026 (liberación 31-may-2026 16:00h UTC-5) municipio-a-municipio, con capa estratégica para mapear dónde conseguir **3 millones de votos para Iván Cepeda** (Pacto Histórico).

## Reglas locales

1. **LOCAL-FIRST estricto** (hereda regla #11 VA). Toda llamada a LLM va por subprocess a `python -m templates.routing_inteligente` (Ollama qwen2.5:14b primero). Cero `import anthropic / openai / google.generativeai`.
2. **Gateway VA obligatorio** (regla #16). Antes de pensar siquiera en Claude, pasar por VA. Log con header `[VA-ROUTE] <ruta> · <justificación>`.
3. **Solo datos públicos**. Resultados Registraduría son públicos; NBI municipal DANE es público. Si se cruzara con padrón individual, marcar `dato_sensible` (no es el caso actual).
4. **Carpeta aislada**. Nunca leer/escribir fuera de `C:\Users\wilso\Desktop\Escritorio2026\elecciones\`. Para reusar VA, invocar por subprocess con cwd absoluto a `Visual_Agentes\`.
5. **Fuente única de verdad**: `data/processed/votos.duckdb`. Toda salida deriva de ahí.
6. **Snapshots inmutables**: `data/raw/<ts>/<scope_code>.json.gz` append-only. Nunca sobreescribir.

## Doctrina VA heredada (referencia, no copia)

- Reglas duras V2.4: `C:\Users\wilso\Desktop\Escritorio2026\Visual_Agentes\_doctrina\REGLAS_DURAS_FRAMEWORK.md`
- Stack multimodelo: `C:\Users\wilso\Desktop\Escritorio2026\Visual_Agentes\_doctrina\STACK_MULTIMODELO.md`
- Routing canónico: `C:\Users\wilso\Desktop\Escritorio2026\Visual_Agentes\templates\routing_inteligente.py`

## Comandos canónicos

```powershell
# Health check
python -m scripts_apoyo.elecciones_doctor

# Bootstrap (1 vez)
python scraper/discovery_playwright.py
python scraper/nomenclator.py

# Captura
python scraper/fetch_estatico.py --smoke --depto 11      # Bogotá smoke
python scraper/fetch_estatico.py --full                  # 1.123 mpios
python scraper/incremental.py --interval 300             # polling 5 min

# Estrategia
python -m estrategia.nbi_loader
python -m estrategia.cluster_geo
python -m estrategia.mapa_oportunidad
python -m estrategia.narrative_brief --all
python -m estrategia.cepeda_3M
```

## Layout

```
scraper/        captura datos Registraduría
estrategia/     análisis 3M Cepeda
data/raw/       JSONs crudos comprimidos por snapshot
data/processed/ votos.duckdb + parquet derivados
data/outputs/   CSVs y reportes markdown finales
scripts_apoyo/  doctor + backup
infra/          ports.yml + config local
logs/           JSONL append-only (scraper, estrategia)
tests/          pytest
```

## Puertos reservados

Ver `infra/ports.yml`. Reservados: **8520** (dashboard opcional Streamlit, no obligatorio).

## Entregable final

`data/outputs/reporte_final.md` con:
1. Tabla de los 200 municipios objetivo (potencial × afinidad × NBI).
2. Tabla de los 100 municipios de defensa.
3. 22 briefs narrativos por cluster geo-político (generados por Ollama local).
4. Proyección numérica: ¿estos 300 municipios alcanzan los 3M para Cepeda? Gap si no.
