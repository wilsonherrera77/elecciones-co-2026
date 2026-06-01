"""Tests del nomenclator + DIVIPOLA + partidos."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, ROOT.as_posix())

from scraper.db import connect


def test_divipola_estructura_jerarquica():
    con = connect(read_only=True)
    counts = dict(con.execute(
        "SELECT level, COUNT(*) FROM divipola_2026 GROUP BY level ORDER BY level"
    ).fetchall())
    con.close()
    assert counts.get(1) == 1, f"Esperaba 1 nivel COLOMBIA, hay {counts.get(1)}"
    assert counts.get(2) == 34, f"Esperaba 34 departamentos, hay {counts.get(2)}"
    assert counts.get(3) == 1189, f"Esperaba 1189 municipios, hay {counts.get(3)}"


def test_partidos_2026_pacto_historico():
    con = connect(read_only=True)
    rows = con.execute("SELECT codpar, nombre FROM partidos_2026 WHERE codpar='7'").fetchall()
    con.close()
    assert len(rows) == 1, f"Esperaba 1 fila para codpar=7, hay {len(rows)}"
    nombre = rows[0][1].upper()
    assert "PACTO" in nombre and "HIST" in nombre, f"codpar=7 esperaba Pacto Histórico, encontré {nombre!r}"


def test_partidos_2026_count():
    con = connect(read_only=True)
    n = con.execute("SELECT COUNT(*) FROM partidos_2026").fetchone()[0]
    con.close()
    assert n == 14, f"Esperaba 14 listas en boleta, hay {n}"
