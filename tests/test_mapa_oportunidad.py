"""Tests de la lógica del score de oportunidad y la consulta agregada."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, ROOT.as_posix())

from scraper.db import connect


def test_mapa_oportunidad_municipio_existe():
    """La tabla mapa_oportunidad_municipio debe existir tras correr el script."""
    con = connect(read_only=True)
    n = con.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name='mapa_oportunidad_municipio'"
    ).fetchone()[0]
    con.close()
    assert n == 1, "Falta correr `python -m estrategia.mapa_oportunidad`"


def test_view_v_score_columnas_minimas():
    con = connect(read_only=True)
    cols = {r[0] for r in con.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name='v_score'"
    ).fetchall()}
    con.close()
    for c in ("nombre_municipio", "departamento_nombre", "votos_cepeda",
              "potencial_no_votante", "afinidad", "score_oportunidad", "score_defensa"):
        assert c in cols, f"falta columna {c} en v_score · cols={cols}"


def test_cepeda_codpar_consistente():
    """codpar='7' en datos = Pacto Histórico (Iván Cepeda)."""
    con = connect(read_only=True)
    nombres = {n for (n,) in con.execute(
        "SELECT DISTINCT partido_nombre FROM votos_municipio_snapshot WHERE codpar='7' AND partido_nombre IS NOT NULL"
    ).fetchall()}
    con.close()
    cepeda_present = any("CEPEDA" in (n or "").upper() for n in nombres)
    assert cepeda_present, f"codpar=7 no contiene candidato Cepeda · nombres encontrados: {nombres}"


def test_total_cepeda_positivo():
    con = connect(read_only=True)
    total = con.execute(
        "SELECT SUM(votos) FROM votos_municipio_snapshot WHERE codpar='7'"
    ).fetchone()[0]
    con.close()
    assert total and total > 0, "Total Cepeda debería ser > 0 tras fetch full"
