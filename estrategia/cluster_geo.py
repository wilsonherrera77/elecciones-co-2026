"""cluster_geo.py · agrupa los 1.189 municipios en clusters geo-políticos.

Mapeo POR NOMBRE NORMALIZADO de departamento (más estable que código interno).
Cubre los 34 nombres reales del nomenclator 2026 (incluyendo el truncado
"NORTE DE SAN" y encoding roto "NARI?O").

Output: data/processed/cluster_mapping.csv + tabla cluster_mapping en votos.duckdb.
"""

from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, PROJECT_ROOT.as_posix())

from scraper.db import connect  # noqa: E402


def _norm(s: str) -> str:
    """Normaliza para join: NFKD + upper + sin tildes/puntuación + colapsa espacios.

    Crítico: maneja encoding roto del nomenclator (e.g. 'NARI?O' donde Ñ se rompió).
    """
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s.upper())
    s = "".join(c for c in s if not unicodedata.combining(c))
    for ch in ".,()-?":
        s = s.replace(ch, " ")
    return " ".join(s.split())


# Mapeo por nombre normalizado de departamento → cluster por defecto.
# Override por municipio se aplica después para casos especiales.
DEPTO_NOMBRE_TO_CLUSTER: dict[str, str] = {
    "AMAZONAS": "Amazonía",
    "ANTIOQUIA": "Antioquia rural uribista",      # default · override por mpio
    "ARAUCA": "Llanos petroleros",
    "ATLANTICO": "Caribe norte",
    "BOGOTA D C": "Bogotá centro/occidente",      # override por localidad si hubiera drill-down
    "BOLIVAR": "Caribe + Magdalena Medio",
    "BOYACA": "Boyacá-Cundi rural",
    "CALDAS": "Eje cafetero",
    "CAQUETA": "Sur Tolima-Huila-Caquetá",
    "CASANARE": "Llanos petroleros",
    "CAUCA": "Pacífico indígena/campesino",       # default · override por mpio
    "CESAR": "Caribe norte",
    "CHOCO": "Pacífico afro",
    "CONSULADOS": "Exterior (consulados)",
    "CORDOBA": "Caribe + Magdalena Medio",
    "CUNDINAMARCA": "Bogotá región",              # default · ciudades grandes override
    "GUAINIA": "Amazonía",
    "GUAVIARE": "Amazonía",
    "HUILA": "Sur Tolima-Huila-Caquetá",
    "LA GUAJIRA": "Caribe norte",
    "MAGDALENA": "Caribe norte",
    "META": "Llanos petroleros",
    "NARINO": "Sur andino Nariño",                # default · override Pacífico para mpios costeros
    "NORTE DE SAN": "Catatumbo / Frontera",       # truncado en nomenclator
    "NORTE DE SANTANDER": "Catatumbo / Frontera",
    "PUTUMAYO": "Amazonía",
    "QUINDIO": "Eje cafetero",
    "RISARALDA": "Eje cafetero",
    "SAN ANDRES": "Caribe insular",
    "SANTANDER": "Santanderes",                   # default · override Magdalena Medio
    "SUCRE": "Caribe + Magdalena Medio",
    "TOLIMA": "Sur Tolima-Huila-Caquetá",
    "VALLE": "Valle del Cauca",                   # default · override Buenaventura
    "VAUPES": "Amazonía",
    "VICHADA": "Llanos petroleros",
}

# Overrides por nombre de municipio (case-insensitive · match exacto sobre nombre normalizado)
ANTIOQUIA_URABA = {"APARTADO", "CAREPA", "CHIGORODO", "MUTATA", "NECOCLI",
                   "SAN JUAN DE URABA", "SAN PEDRO DE URABA", "TURBO", "ARBOLETES",
                   "VIGIA DEL FUERTE", "MURINDO"}
ANTIOQUIA_METRO = {"MEDELLIN", "BELLO", "ITAGUI", "ENVIGADO", "SABANETA",
                   "LA ESTRELLA", "CALDAS", "COPACABANA", "GIRARDOTA", "BARBOSA"}
ANTIOQUIA_MAG_MEDIO = {"PUERTO BERRIO", "PUERTO NARE", "YONDO", "PUERTO TRIUNFO",
                       "MACEO", "CARACOLI"}

BOGOTA_SUR = {"BOSA", "KENNEDY", "CIUDAD BOLIVAR", "USME", "TUNJUELITO",
              "RAFAEL URIBE URIBE", "SAN CRISTOBAL"}
BOGOTA_NORTE = {"USAQUEN", "CHAPINERO", "TEUSAQUILLO", "BARRIOS UNIDOS", "SUBA"}

CUNDINAMARCA_BOGOTA_REGION = {"SOACHA", "CHIA", "ZIPAQUIRA", "MOSQUERA", "MADRID",
                               "FUNZA", "FACATATIVA", "CAJICA", "COTA", "TENJO"}

CAUCA_PACIFICO = {"GUAPI", "LOPEZ", "TIMBIQUI"}
NARINO_PACIFICO = {"TUMACO", "FRANCISCO PIZARRO", "MOSQUERA", "OLAYA HERRERA",
                   "EL CHARCO", "LA TOLA", "MAGUI", "SANTA BARBARA", "ROBERTO PAYAN"}
VALLE_PACIFICO = {"BUENAVENTURA"}

NORTE_SANTANDER_CATATUMBO = {"TIBU", "EL TARRA", "CONVENCION", "EL CARMEN", "TEORAMA",
                              "SAN CALIXTO", "HACARI", "LA PLAYA", "OCANA", "SARDINATA"}
NORTE_SANTANDER_URBANO = {"CUCUTA", "VILLA DEL ROSARIO", "LOS PATIOS"}

SANTANDER_URBANO = {"BUCARAMANGA", "GIRON", "FLORIDABLANCA", "PIEDECUESTA"}
SANTANDER_MAG_MEDIO = {"BARRANCABERMEJA", "SAN VICENTE DE CHUCURI", "PUERTO WILKES",
                       "PUERTO PARRA"}


def classify(municipio_nombre: str, departamento_nombre: str) -> str:
    """Asigna cluster al municipio. Match por nombre normalizado de depto + override por mpio."""
    mun = _norm(municipio_nombre)
    depto = _norm(departamento_nombre)
    base = DEPTO_NOMBRE_TO_CLUSTER.get(depto, "Otro")

    if depto == "ANTIOQUIA":
        if mun in ANTIOQUIA_URABA:
            return "Urabá"
        if mun in ANTIOQUIA_METRO:
            return "Antioquia metropolitana"
        if mun in ANTIOQUIA_MAG_MEDIO:
            return "Magdalena Medio"
        return "Antioquia rural uribista"

    if depto == "BOGOTA D C":
        # En level=3 Bogotá es un sólo mpio · drill-down por localidad requiere level=4+
        return "Bogotá centro/occidente"

    if depto == "CUNDINAMARCA" and mun in CUNDINAMARCA_BOGOTA_REGION:
        return "Bogotá región"

    if depto == "SANTANDER":
        if mun in SANTANDER_MAG_MEDIO:
            return "Magdalena Medio"
        if mun in SANTANDER_URBANO:
            return "Santanderes urbanos"
        return "Santanderes rurales"

    if depto in ("NORTE DE SAN", "NORTE DE SANTANDER"):
        if mun in NORTE_SANTANDER_CATATUMBO:
            return "Catatumbo / Frontera"
        if mun in NORTE_SANTANDER_URBANO:
            return "Norte Santander urbano (Cúcuta)"
        return "Catatumbo / Frontera"

    if depto == "CAUCA":
        if mun in CAUCA_PACIFICO:
            return "Pacífico afro"
        return "Pacífico indígena/campesino"

    if depto == "NARINO":
        if mun in NARINO_PACIFICO:
            return "Pacífico afro"
        return "Sur andino Nariño"

    if depto == "VALLE":
        if mun in VALLE_PACIFICO:
            return "Pacífico afro"
        return "Valle del Cauca"

    return base


def main() -> int:
    con = connect()
    rows = con.execute("""
        SELECT idx, codigo_interno, nombre, departamento_idx, departamento_nombre
        FROM divipola_2026 WHERE level=3 ORDER BY departamento_idx, nombre
    """).fetchall()

    out_rows: list[tuple] = []
    cluster_counts: dict[str, int] = {}
    for idx, ci, nombre, depto_idx, depto_nombre in rows:
        cl = classify(nombre, depto_nombre)
        out_rows.append((idx, ci, nombre, depto_idx, depto_nombre, cl))
        cluster_counts[cl] = cluster_counts.get(cl, 0) + 1

    con.execute("""
        CREATE OR REPLACE TABLE cluster_mapping (
            idx INTEGER,
            codigo_interno VARCHAR,
            nombre VARCHAR,
            departamento_idx INTEGER,
            departamento_nombre VARCHAR,
            cluster VARCHAR
        );
    """)
    con.executemany(
        "INSERT INTO cluster_mapping VALUES (?, ?, ?, ?, ?, ?)",
        out_rows,
    )

    out_csv = PROJECT_ROOT / "data" / "processed" / "cluster_mapping.csv"
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    import csv
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["idx", "codigo_interno", "nombre", "departamento_idx",
                    "departamento_nombre", "cluster"])
        w.writerows(out_rows)

    print(f"cluster_mapping · {len(out_rows)} municipios · {len(cluster_counts)} clusters")
    for c, n in sorted(cluster_counts.items(), key=lambda x: -x[1]):
        marker = "  <-- BUG" if c == "Otro" and n > 5 else ""
        print(f"  {c:35s} {n:>5} mpios{marker}")
    print(f"\nCSV: {out_csv.relative_to(PROJECT_ROOT)}")
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
