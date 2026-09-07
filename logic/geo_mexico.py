"""
Catálogo geográfico nacional (32 estados, ~2478 municipios de México) y
utilidades de normalización de nombres, usados por Siembra Link para la
cobertura nacional, el selector de ubicación y el reverse geocoding.

Fuente de datos: data/geo/mexico_estados_municipios.json (ver
scripts/build_geo_catalog.py para cómo se generó).
"""
import json
import os
import threading
import unicodedata

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CATALOGO_PATH = os.path.join(_BASE_DIR, "data", "geo", "mexico_estados_municipios.json")

_catalogo = None
_lock = threading.Lock()

# Variantes conocidas -> nombre canónico (el usado como llave en el catálogo).
# Incluye grafías del catálogo INEGI crudo, de data/datos/Estados/*, de
# logic/catalogos.py y las que suele devolver Nominatim.
ALIAS_ESTADOS = {
    "COAHUILA DE ZARAGOZA": "Coahuila",
    "MICHOACAN DE OCAMPO": "Michoacán",
    "VERACRUZ DE IGNACIO DE LA LLAVE": "Veracruz",
    "MEXICO": "Estado de México",
    "ESTADO DE MEXICO": "Estado de México",
    "CIUDAD DE MEXICO": "Ciudad de México",
    "DISTRITO FEDERAL": "Ciudad de México",
    "CDMX": "Ciudad de México",
}


def _normalizar(texto: str) -> str:
    if not isinstance(texto, str):
        return ""
    texto = unicodedata.normalize("NFD", texto).encode("ascii", "ignore").decode("utf-8")
    return texto.strip().upper()


def cargar_catalogo() -> dict:
    global _catalogo
    if _catalogo is None:
        with _lock:
            if _catalogo is None:
                with open(_CATALOGO_PATH, "r", encoding="utf-8") as f:
                    _catalogo = json.load(f)
    return _catalogo


def _mapa_normalizado_estados() -> dict:
    """{nombre_estado_normalizado: nombre_canonico}"""
    catalogo = cargar_catalogo()
    return {_normalizar(nombre): nombre for nombre in catalogo.keys()}


def listar_estados() -> list:
    return sorted(cargar_catalogo().keys())


def listar_municipios(estado: str) -> list:
    catalogo = cargar_catalogo()
    entrada = catalogo.get(estado)
    if not entrada:
        return []
    return sorted(entrada["municipios"].keys())


def coordenadas_estado(estado: str):
    catalogo = cargar_catalogo()
    entrada = catalogo.get(estado)
    return tuple(entrada["coordenadas"]) if entrada else None


def coordenadas_municipio(estado: str, municipio: str):
    catalogo = cargar_catalogo()
    entrada = catalogo.get(estado)
    if not entrada:
        return None
    muni = entrada["municipios"].get(municipio)
    return tuple(muni["coordenadas"]) if muni else None


def normalizar_estado(nombre_raw: str):
    """Devuelve el nombre canónico del estado, o None si no se reconoce."""
    if not nombre_raw:
        return None
    clave = _normalizar(nombre_raw)
    if clave in ALIAS_ESTADOS:
        return ALIAS_ESTADOS[clave]
    return _mapa_normalizado_estados().get(clave)


def normalizar_municipio(estado_canonico: str, nombre_raw: str):
    """Devuelve el nombre canónico del municipio dentro de un estado ya
    normalizado, o None si no se reconoce."""
    if not estado_canonico or not nombre_raw:
        return None
    catalogo = cargar_catalogo()
    entrada = catalogo.get(estado_canonico)
    if not entrada:
        return None
    clave = _normalizar(nombre_raw)
    for nombre_muni in entrada["municipios"].keys():
        if _normalizar(nombre_muni) == clave:
            return nombre_muni
    return None
