"""incremental.py · polling cada N segundos hasta una hora límite.

Ejecuta `fetch_estatico.run(full)` en loop. Cada snapshot deja:
- /data/raw/<ts>/<scope>.json.gz
- INSERT en snapshots_historico (append-only)
- UPSERT en votos_municipio_snapshot (estado actual)

Uso:
    python scraper/incremental.py --interval 300              # 5 min
    python scraper/incremental.py --interval 60 --hasta 23:59 # hasta hora local
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, PROJECT_ROOT.as_posix())

from scraper.fetch_estatico import run as fetch_run  # noqa: E402


def _parse_hora_limite(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        hh, mm = s.split(":")
        now = datetime.now()
        return now.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
    except (ValueError, AttributeError):
        return None


async def loop(interval: int, hasta: datetime | None, deptos: list[int] | None,
               concurrencia: int, max_rps: int) -> int:
    n = 0
    while True:
        n += 1
        t0 = time.monotonic()
        print(f"\n=== ciclo {n} · {datetime.now().isoformat(timespec='seconds')} ===")
        try:
            await fetch_run(deptos=deptos, smoke=False, concurrencia=concurrencia, max_rps=max_rps)
        except Exception as e:  # noqa: BLE001
            print(f"  ERROR ciclo {n}: {type(e).__name__}: {e}")
        dt = time.monotonic() - t0

        if hasta and datetime.now() >= hasta:
            print(f"[incremental] llegamos a {hasta.isoformat(timespec='seconds')} · saliendo")
            return 0

        wait = max(0, interval - int(dt))
        print(f"[incremental] esperando {wait}s al siguiente ciclo")
        if wait > 0:
            await asyncio.sleep(wait)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=int, default=300, help="segundos entre ciclos (default 300 = 5 min)")
    ap.add_argument("--hasta", type=str, default=None, help="hora local HH:MM para detener")
    ap.add_argument("--depto", nargs="*", type=int, default=None, help="restringir a deptos")
    ap.add_argument("--concurrencia", type=int, default=25)
    ap.add_argument("--max-rps", type=int, default=50)
    args = ap.parse_args()

    hasta = _parse_hora_limite(args.hasta)
    return asyncio.run(loop(args.interval, hasta, args.depto, args.concurrencia, args.max_rps))


if __name__ == "__main__":
    sys.exit(main())
