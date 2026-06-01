"""narrative_brief.py · genera 1 brief markdown por cluster usando Ollama LOCAL.

Estrategia LOCAL-FIRST (regla #11 VA):
1. Lee de DuckDB el resumen agregado por cluster (votos Cepeda actuales,
   afinidad, potencial, top mpios oportunidad, top mpios defensa).
2. Por cluster, prepara un prompt estructurado.
3. Invoca por subprocess `python -m templates.routing_inteligente --tipo razonamiento
   --prompt-file <ruta>` con cwd=VA_ROOT (regla #16 gateway).
4. Escribe el output en data/outputs/brief_cluster_<slug>.md.

Si Ollama no responde, escribe un brief mínimo determinista (sin LLM)
para que el pipeline no se bloquee. Lo marca claramente con "[FALLBACK_OFFLINE]".

Uso:
  python -m estrategia.narrative_brief --all
  python -m estrategia.narrative_brief --cluster "Pacífico afro"
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, PROJECT_ROOT.as_posix())

from scraper.db import connect  # noqa: E402

VA_ROOT_DEFAULT = r"C:\Users\wilso\Desktop\Escritorio2026\Visual_Agentes"
LOG_PATH = PROJECT_ROOT / "logs" / "estrategia.jsonl"


def _slugify(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s).strip("_").lower()
    return s or "cluster"


def _log(event: dict) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    event["ts"] = datetime.now(timezone.utc).isoformat()
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def get_cluster_summary(con, cluster: str) -> dict:
    """Datos agregados + top municipios para un cluster."""
    summary = con.execute("""
        SELECT cluster,
               COUNT(*) AS mpios,
               SUM(votos_cepeda) AS votos_cepeda,
               ROUND(AVG(afinidad)*100, 1) AS afinidad_avg_pct,
               SUM(potencial_no_votante) AS potencial,
               SUM(votos_validos) AS votos_validos,
               SUM(censo) AS censo
        FROM v_score
        WHERE cluster = ?
        GROUP BY cluster
    """, [cluster]).fetchone()

    if not summary:
        return {}

    top_oport = con.execute("""
        SELECT nombre_municipio, departamento_nombre,
               votos_cepeda, ROUND(pct_cepeda, 1) AS pct,
               potencial_no_votante, ROUND(score_oportunidad, 0) AS score
        FROM v_score
        WHERE cluster = ?
        ORDER BY score_oportunidad DESC
        LIMIT 10
    """, [cluster]).fetchall()

    top_defensa = con.execute("""
        SELECT nombre_municipio, departamento_nombre,
               votos_cepeda, ROUND(pct_cepeda, 1) AS pct,
               ROUND(afinidad*100, 1) AS afinidad_pct
        FROM v_score
        WHERE cluster = ? AND afinidad > 0.30
        ORDER BY score_defensa DESC
        LIMIT 10
    """, [cluster]).fetchall()

    return {
        "cluster": summary[0],
        "mpios": summary[1],
        "votos_cepeda": summary[2] or 0,
        "afinidad_avg_pct": summary[3] or 0,
        "potencial": summary[4] or 0,
        "votos_validos": summary[5] or 0,
        "censo": summary[6] or 0,
        "top_oportunidad": [
            {"mpio": r[0], "depto": r[1], "votos": r[2], "pct": r[3],
             "potencial": r[4], "score": r[5]} for r in top_oport
        ],
        "top_defensa": [
            {"mpio": r[0], "depto": r[1], "votos": r[2], "pct": r[3], "afinidad": r[4]}
            for r in top_defensa
        ],
    }


def build_prompt(data: dict) -> str:
    """Construye el prompt para Ollama (qwen2.5:14b LOCAL)."""
    cl = data["cluster"]
    top_op = "\n".join(
        f"  - {x['mpio']:30s} {x['depto']:15s} votos_cepeda={x['votos']:>7,} pct={x['pct']}% potencial={x['potencial']:>7,}"
        for x in data["top_oportunidad"]
    )
    top_def = "\n".join(
        f"  - {x['mpio']:30s} {x['depto']:15s} votos={x['votos']:>7,} afinidad={x['afinidad']}%"
        for x in data["top_defensa"]
    ) or "  (sin municipios con afinidad >30% en este cluster)"

    return f"""Eres analista político senior asesorando a la campaña de IVÁN CEPEDA (Movimiento Político Pacto Histórico, primera vuelta presidencial Colombia 2026). Tu tarea es producir un BRIEF NARRATIVO TÁCTICO para un cluster geo-político específico, basado SOLO en los datos abajo (no inventes cifras).

# CLUSTER: {cl}
- Municipios: {data['mpios']}
- Censo electoral total: {data['censo']:,}
- Votos válidos contabilizados: {data['votos_validos']:,}
- Votos Cepeda en cluster: {data['votos_cepeda']:,}
- Afinidad promedio Cepeda: {data['afinidad_avg_pct']}%
- Potencial (no votantes): {data['potencial']:,}

# TOP 10 MUNICIPIOS OPORTUNIDAD (ranking por score = potencial × afinidad × NBI)
{top_op}

# TOP 10 MUNICIPIOS A DEFENDER (afinidad > 30%)
{top_def}

# QUÉ DEBES PRODUCIR (en markdown, máximo 600 palabras, idioma español)

## 1. Diagnóstico
2-3 frases. ¿Cómo está el cluster hoy para Cepeda? ¿Es zona ganadora, perdedora, o de oportunidad latente?

## 2. Mensaje sugerido
Un mensaje político concreto adaptado al cluster (no genérico). Tono y temas a enfatizar (paz/víctimas/educación rural/etnicidad/empleo/minería/etc.) según el contexto del cluster ({cl}). Cita 1-2 municipios específicos.

## 3. Capilaridad organizativa
¿Con qué organizaciones del territorio se apoya la campaña en este cluster? (sindicatos, JAC, consejos comunitarios afro, cabildos indígenas, gremios, iglesias, asociaciones campesinas). Sé concreto si conoces el territorio.

## 4. Recursos humanos prioritarios
¿Cuántos coordinadores territoriales, testigos electorales por puesto, y eventos públicos sugieres? Pon números aproximados.

## 5. Riesgos
2-3 riesgos específicos del cluster (violencia, fraude, restricción de movilidad, presencia armada). Sé conciso.

## 6. Apuesta numérica
¿Cuántos VOTOS ADICIONALES sugieres que la campaña puede alcanzar en este cluster antes de la segunda vuelta? Da un número concreto justificado en el potencial no-votante y la afinidad actual.

REGLA: usa solo datos arriba. NO inventes municipios fuera de los listados. Si no sabes algo, dilo. Idioma español Colombia (no españolismos).
""".strip()


def invoke_va_routing(prompt: str, va_root: Path, max_tokens: int = 1800) -> tuple[str, dict]:
    """Llama por subprocess a templates.routing_inteligente (LOCAL-FIRST)."""
    # Escribe prompt a archivo temporal
    prompt_dir = PROJECT_ROOT / "data" / "raw" / "_prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_%f")
    prompt_file = prompt_dir / f"brief_{ts}.txt"
    prompt_file.write_text(prompt, encoding="utf-8")

    cmd = [
        sys.executable, "-m", "templates.routing_inteligente",
        "--tipo", "razonamiento",
        "--prompt-file", prompt_file.as_posix(),
        "--max-tokens", str(max_tokens),
    ]
    print(f"  [VA-ROUTE] {prompt_file.relative_to(PROJECT_ROOT)} · {len(prompt)} chars")
    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            cmd, cwd=va_root.as_posix(),
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=180,
        )
        elapsed = time.monotonic() - t0
        out = proc.stdout.strip()
        err = proc.stderr.strip()
        return out, {"rc": proc.returncode, "elapsed_s": round(elapsed, 1),
                     "stderr_tail": err[-400:] if err else ""}
    except subprocess.TimeoutExpired:
        return "", {"rc": -1, "elapsed_s": 180, "stderr_tail": "TIMEOUT 180s"}
    except Exception as e:  # noqa: BLE001
        return "", {"rc": -1, "elapsed_s": 0, "stderr_tail": f"{type(e).__name__}: {e}"}


def fallback_brief(data: dict) -> str:
    """Brief mínimo determinista cuando Ollama no responde."""
    cl = data["cluster"]
    top_op_lines = "\n".join(
        f"- **{x['mpio']}** ({x['depto']}) · {x['votos']:,} votos ({x['pct']}%) · potencial {x['potencial']:,}"
        for x in data["top_oportunidad"][:5]
    )
    top_def_lines = "\n".join(
        f"- **{x['mpio']}** ({x['depto']}) · {x['votos']:,} votos · afinidad {x['afinidad']}%"
        for x in data["top_defensa"][:5]
    ) or "_(no hay municipios con afinidad >30% en este cluster)_"

    return f"""# Brief táctico cluster · {cl}

**[FALLBACK_OFFLINE]** _Ollama no disponible · brief generado de forma determinista (sin LLM)._

## Cifras base
- Municipios: {data['mpios']}
- Censo: {data['censo']:,}
- Votos válidos: {data['votos_validos']:,}
- Votos Cepeda actuales: **{data['votos_cepeda']:,}**
- Afinidad promedio: {data['afinidad_avg_pct']}%
- Potencial (no votantes): **{data['potencial']:,}**

## Top oportunidad (priorizar)
{top_op_lines}

## Top a defender
{top_def_lines}

## Apuesta numérica determinista
Si la campaña recupera 12% del potencial no-votante a la afinidad actual:
**{int(data['potencial'] * 0.12 * (data['afinidad_avg_pct']/100)):,} votos adicionales** estimados en este cluster.
"""


def write_brief(cluster: str, content: str, va_meta: dict | None = None) -> Path:
    out_dir = PROJECT_ROOT / "data" / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = _slugify(cluster)
    out = out_dir / f"brief_cluster_{slug}.md"

    header = f"""---
cluster: {cluster}
generated_at: {datetime.now(timezone.utc).isoformat()}
va_route: templates.routing_inteligente
va_route_rc: {(va_meta or {}).get('rc')}
va_route_elapsed_s: {(va_meta or {}).get('elapsed_s')}
---

"""
    out.write_text(header + content + "\n", encoding="utf-8")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="genera brief para todos los clusters")
    ap.add_argument("--cluster", type=str, default=None, help="genera brief para 1 cluster")
    ap.add_argument("--va-root", type=str, default=os.environ.get("VA_ROOT", VA_ROOT_DEFAULT))
    ap.add_argument("--fallback-only", action="store_true",
                    help="no llamar a Ollama · siempre fallback determinista")
    args = ap.parse_args()

    va_root = Path(args.va_root)
    con = connect(read_only=False)  # need write for view

    # Verifica que la view existe (si no, hay que correr mapa_oportunidad primero)
    has_view = con.execute(
        "SELECT COUNT(*) FROM information_schema.views WHERE table_name='v_score'"
    ).fetchone()[0]
    if not has_view:
        print("ERROR: la vista v_score no existe · corre `python -m estrategia.mapa_oportunidad` primero")
        return 1

    if args.cluster:
        clusters = [args.cluster]
    elif args.all:
        clusters = [r[0] for r in con.execute(
            "SELECT DISTINCT cluster FROM v_score WHERE cluster IS NOT NULL ORDER BY cluster"
        ).fetchall()]
    else:
        print("Especifica --all o --cluster <nombre>")
        con.close()
        return 1

    print(f"[narrative_brief] {len(clusters)} cluster(s) · VA_ROOT={va_root}")
    print(f"[narrative_brief] modo: {'fallback offline' if args.fallback_only else 'Ollama via VA (LOCAL-FIRST)'}")

    for i, cl in enumerate(clusters, 1):
        print(f"\n--- [{i}/{len(clusters)}] {cl}")
        data = get_cluster_summary(con, cl)
        if not data:
            print(f"  WARN: sin datos para {cl}, skipping")
            continue
        prompt = build_prompt(data)
        if args.fallback_only:
            content = fallback_brief(data)
            meta = {"rc": -1, "elapsed_s": 0, "stderr_tail": "fallback_only flag"}
        else:
            content, meta = invoke_va_routing(prompt, va_root)
            if not content or meta.get("rc") != 0:
                print(f"  WARN: routing falló ({meta}) · fallback determinista")
                content = fallback_brief(data)
        out = write_brief(cl, content, meta)
        _log({"event": "brief_written", "cluster": cl, "path": out.as_posix(),
              "meta": meta, "fallback": "[FALLBACK_OFFLINE]" in content})
        print(f"  -> {out.relative_to(PROJECT_ROOT)}")

    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
