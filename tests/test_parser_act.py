"""Tests del parser de archivos ACT/PR (estructura real Registraduría 2026)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, ROOT.as_posix())

from scraper.fetch_estatico import _parse_act, _to_int, _to_float


def test_to_int_formato_colombiano():
    assert _to_int("7.590") == 7590
    assert _to_int("7,590") == 7590
    assert _to_int("100") == 100
    assert _to_int(None) is None
    assert _to_int("") is None


def test_to_float_porcentaje():
    assert _to_float("49,29%") == 49.29
    assert _to_float("12.36") == 12.36
    assert _to_float("0%") == 0.0
    assert _to_float(None) is None


def test_parse_act_estructura_real():
    """Estructura confirmada en Abejorral (01004) snapshot real."""
    sample = {
        "elec": "1", "amb": "01004", "dept": "01",
        "totales": {"act": {
            "metota": "48", "mesesc": "48", "centota": "15398",
            "votant": "7590", "absten": "7808",
            "votnul": "65", "votnma": "53", "votblan": "113", "votval": "7472",
        }},
        "camaras": [{
            "partotabla": [
                {"act": {"codpar": "7", "vot": "924", "pvot": "12,36%",
                         "cantotabla": [{"codcan": "1", "cedula": "79262397",
                                         "nomcan": "IVÁN", "apecan": "CEPEDA CASTRO",
                                         "vot": "924", "pvot": "12,36%"}]}},
                {"act": {"codpar": "10", "vot": "4191", "pvot": "56,08%",
                         "cantotabla": [{"codcan": "4", "nomcan": "ABELARDO",
                                         "apecan": "DE LA ESPRIELLA", "vot": "4191"}]}},
            ]
        }],
    }
    import json
    parsed = _parse_act(json.dumps(sample).encode("utf-8"))
    assert parsed["mesas_total"] == 48
    assert parsed["mesas_informadas"] == 48
    assert parsed["votos_validos"] == 7472
    assert parsed["votos_blanco"] == 113
    assert len(parsed["partidos"]) == 2

    cepeda = [p for p in parsed["partidos"] if p["codpar"] == "7"][0]
    assert cepeda["votos"] == 924
    assert cepeda["porcentaje"] == 12.36
    assert "CEPEDA" in (cepeda["candidato_nombre"] or "")


def test_parse_act_body_vacio():
    assert _parse_act(b"") == {}
    assert _parse_act(b"not json") == {}
