"""DuckDB connection + schema + helpers para el proyecto elecciones.

Tablas:
- `divipola_2026`              · 1.224 ámbitos planos del nomenclator (colombia + 34 deptos + 1.189 mpios + ...)
- `partidos_2026`              · 14 listas/partidos en boleta
- `votos_municipio_snapshot`   · snapshot ACTUAL por (scope_code, codpar)
- `snapshots_historico`        · append-only · todos los snapshots con timestamp
- `discovery_meta`             · resultado del discovery_playwright (url base, patterns)
"""

from __future__ import annotations

import duckdb
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "processed" / "votos.duckdb"


DDL = """
CREATE TABLE IF NOT EXISTS divipola_2026 (
    idx                INTEGER PRIMARY KEY,
    nombre             VARCHAR NOT NULL,
    codigo_interno     VARCHAR NOT NULL,
    sigla              VARCHAR,
    level              INTEGER NOT NULL,
    parent_idx         INTEGER,
    departamento_idx   INTEGER,
    departamento_nombre VARCHAR,
    resultado_idx      INTEGER,
    has_children       BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_divipola_level ON divipola_2026(level);
CREATE INDEX IF NOT EXISTS idx_divipola_codigo ON divipola_2026(codigo_interno);
CREATE INDEX IF NOT EXISTS idx_divipola_depto ON divipola_2026(departamento_idx);

CREATE TABLE IF NOT EXISTS partidos_2026 (
    codpar             VARCHAR PRIMARY KEY,
    nombre             VARCHAR NOT NULL,
    color              VARCHAR,
    sigla              VARCHAR,
    orden_boleta       INTEGER
);

CREATE TABLE IF NOT EXISTS votos_municipio_snapshot (
    scope_idx          INTEGER NOT NULL,
    codigo_interno     VARCHAR NOT NULL,
    nombre_municipio   VARCHAR NOT NULL,
    departamento_idx   INTEGER NOT NULL,
    departamento_nombre VARCHAR NOT NULL,
    codpar             VARCHAR NOT NULL,
    partido_nombre     VARCHAR,
    votos              INTEGER,
    porcentaje         DOUBLE,
    mesas_informadas   INTEGER,
    mesas_total        INTEGER,
    votos_validos      INTEGER,
    votos_blanco       INTEGER,
    votos_nulos        INTEGER,
    votos_no_marcados  INTEGER,
    censo_electoral    INTEGER,
    ts_snapshot        TIMESTAMP NOT NULL,
    PRIMARY KEY (scope_idx, codpar)
);

CREATE INDEX IF NOT EXISTS idx_snap_codpar ON votos_municipio_snapshot(codpar);
CREATE INDEX IF NOT EXISTS idx_snap_depto ON votos_municipio_snapshot(departamento_idx);

CREATE TABLE IF NOT EXISTS snapshots_historico (
    ts_snapshot        TIMESTAMP NOT NULL,
    scope_idx          INTEGER NOT NULL,
    codigo_interno     VARCHAR NOT NULL,
    codpar             VARCHAR NOT NULL,
    votos              INTEGER,
    porcentaje         DOUBLE,
    mesas_informadas   INTEGER,
    mesas_total        INTEGER
);

CREATE INDEX IF NOT EXISTS idx_hist_ts ON snapshots_historico(ts_snapshot);
CREATE INDEX IF NOT EXISTS idx_hist_scope ON snapshots_historico(scope_idx);

CREATE TABLE IF NOT EXISTS discovery_meta (
    key                VARCHAR PRIMARY KEY,
    value              VARCHAR NOT NULL,
    captured_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fetch_log (
    ts                 TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    scope_idx          INTEGER,
    codigo_interno     VARCHAR,
    archivo            VARCHAR,
    http_status        INTEGER,
    bytes_recibidos    INTEGER,
    elapsed_ms         INTEGER,
    error              VARCHAR
);
"""


def connect(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Conexión a la base · crea schema si no existe."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(DB_PATH.as_posix(), read_only=read_only)
    if not read_only:
        con.execute(DDL)
    return con


def reset_snapshot(con: duckdb.DuckDBPyConnection) -> None:
    """Limpia el snapshot ACTUAL (mantiene histórico)."""
    con.execute("DELETE FROM votos_municipio_snapshot;")
