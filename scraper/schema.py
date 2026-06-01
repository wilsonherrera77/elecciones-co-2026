"""Modelos pydantic para los JSON de Registraduría 2026.

Mantenido laxo con `extra='allow'` porque el esquema real de los archivos EST_*.json
se confirma sólo cuando los datos están publicados. Estos modelos validan campos
mínimos y dejan pasar el resto sin romper.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class NomenclatorElec(BaseModel):
    """Una elección dentro del nomenclator."""

    model_config = ConfigDict(extra="allow")

    i: int                          # índice
    elec: int                       # código elección (1 = PR Presidente)
    sigla: str                      # "PR"
    n: str                          # "PRESIDENTE"


class NomenclatorPartido(BaseModel):
    """Un partido/lista en boleta."""

    model_config = ConfigDict(extra="allow")

    codpar: str                     # "26" = Pacto Histórico
    nombre: str
    color: str | None = None
    i: str                          # índice como string
    s: str                          # sigla normalizada


class NomenclatorAmbito(BaseModel):
    """Un ámbito territorial (COLOMBIA / DEPTO / MPIO / ZONA / etc)."""

    model_config = ConfigDict(extra="allow")

    i: int                          # índice en array plano
    n: str                          # nombre
    co: str                         # código interno Registraduría
    s: str                          # sigla
    l: int                          # level (1..7)
    p: list[Any] = Field(default_factory=list)   # parents
    r: list[int] = Field(default_factory=list)   # ids de resultado
    h: list[Any] = Field(default_factory=list)   # children por nivel


class EstResultadoPartido(BaseModel):
    """Una fila de resultado por partido/lista dentro de EST_RGP.

    Campos esperados: codpar, votos, porcentaje. El resto laxo.
    """

    model_config = ConfigDict(extra="allow")

    codpar: str | None = None
    nombre: str | None = None
    votos: int | None = None
    porcentaje: float | None = None


class EstResumenAmbito(BaseModel):
    """Resumen general por ámbito (EST_RGP / EST_RPA / EST_RVV).

    Campo `partidos` (o `listas` o `lista`) contiene la lista de resultados.
    Mesas informadas / total / escrutadas / votos válidos / blanco / nulos.
    """

    model_config = ConfigDict(extra="allow")

    scope_code: str | None = None
    mesas_informadas: int | None = None
    mesas_total: int | None = None
    mesas_escrutadas: int | None = None
    votos_validos: int | None = None
    votos_blanco: int | None = None
    votos_nulos: int | None = None
    votos_no_marcados: int | None = None
    censo_electoral: int | None = None
    partidos: list[EstResultadoPartido] = Field(default_factory=list)


EST_FILES = Literal[
    "EST_CAB", "EST_CNM", "EST_CVB", "EST_CVN", "EST_CVT", "EST_CVV",
    "EST_RAB", "EST_RGP", "EST_RNM", "EST_RPA", "EST_RVB", "EST_RVN", "EST_RVP", "EST_RVV",
]
"""Los 14 nombres canónicos de archivos EST_*.json por ámbito."""


PACTO_HISTORICO_CODPAR = "26"
"""Código del partido del Pacto Histórico en esta elección. Donde irían los votos de Iván Cepeda."""
