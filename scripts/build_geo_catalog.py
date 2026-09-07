"""
Script de un solo uso (no forma parte del runtime de la app).

Genera data/geo/mexico_estados_municipios.json: catálogo completo de los 32
estados de México y sus municipios (~2478), con coordenadas aproximadas.

Fuente de nombres de estados/municipios: catálogo público basado en datos del
INEGI (https://github.com/cisnerosnow/json-estados-municipios-mexico).

Los nombres de estado se normalizan a la misma convención corta que ya usa
el proyecto en data/datos/Estados/<Estado>/ y logic/catalogos.py (p.ej.
"Coahuila" en vez de "Coahuila de Zaragoza"), distinguiendo explícitamente
"Ciudad de México" de "Estado de México" (hoy conviven ambas grafías en el
repo pero logic/catalogos.py solo cubre la segunda bajo el nombre "México").

Las coordenadas de municipio son aproximadas (se usa la coordenada del
estado como fallback) salvo para los municipios de Veracruz, donde ya existe
un catálogo preciso en logic/catalogos.py::coordenadas_municipios. Los
registros con coordenada aproximada se marcan con "coords_aprox": true.

Uso: python scripts/build_geo_catalog.py
"""
import json
import os
import sys
import urllib.request

RAW_URL = "https://raw.githubusercontent.com/cisnerosnow/json-estados-municipios-mexico/master/estados-municipios.json"

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from logic.catalogos import coordenadas, coordenadas_municipios  # noqa: E402

OUTPUT_PATH = os.path.join(PROJECT_ROOT, "data", "geo", "mexico_estados_municipios.json")

# Mapeo de nombre crudo (fuente INEGI) -> nombre canónico usado en este proyecto
RENOMBRE_ESTADOS = {
    "Coahuila de Zaragoza": "Coahuila",
    "Michoacán de Ocampo": "Michoacán",
    "Veracruz de Ignacio de la Llave": "Veracruz",
    "México": "Estado de México",
}

# Coordenada de respaldo para Ciudad de México (no existe en logic/catalogos.py)
COORD_CDMX = (19.4326, -99.1332)


def cargar_fuente():
    with urllib.request.urlopen(RAW_URL, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def coord_estado(nombre_canonico):
    if nombre_canonico == "Ciudad de México":
        return COORD_CDMX
    if nombre_canonico == "Estado de México":
        # logic/catalogos.py guarda el Estado de México bajo la clave "México"
        return coordenadas.get("México")
    return coordenadas.get(nombre_canonico)


def construir_catalogo(data_cruda):
    catalogo = {}
    total_municipios = 0

    for nombre_crudo, municipios in data_cruda.items():
        nombre = RENOMBRE_ESTADOS.get(nombre_crudo, nombre_crudo)
        coord_e = coord_estado(nombre)
        if coord_e is None:
            raise ValueError(f"Sin coordenada de respaldo para el estado: {nombre}")

        municipios_out = {}
        for muni in municipios:
            muni_limpio = muni.strip()
            coord_precisa = None
            if nombre == "Veracruz":
                coord_precisa = coordenadas_municipios.get(muni_limpio.upper())

            if coord_precisa:
                municipios_out[muni_limpio] = {
                    "coordenadas": list(coord_precisa),
                    "coords_aprox": False,
                }
            else:
                municipios_out[muni_limpio] = {
                    "coordenadas": list(coord_e),
                    "coords_aprox": True,
                }
            total_municipios += 1

        catalogo[nombre] = {
            "coordenadas": list(coord_e),
            "municipios": municipios_out,
        }

    return catalogo, total_municipios


def main():
    print(f"Descargando catálogo fuente desde {RAW_URL} ...")
    data_cruda = cargar_fuente()

    catalogo, total_municipios = construir_catalogo(data_cruda)

    n_estados = len(catalogo)
    print(f"Estados: {n_estados}  Municipios: {total_municipios}")
    assert n_estados == 32, f"Se esperaban 32 estados, se obtuvieron {n_estados}"
    assert 2400 <= total_municipios <= 2600, f"Total de municipios fuera de rango esperado: {total_municipios}"

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(catalogo, f, ensure_ascii=False, indent=2, sort_keys=True)

    print(f"Catálogo escrito en {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
