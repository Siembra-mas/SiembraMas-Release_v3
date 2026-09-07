"""
Reverse geocoding (lat/lon -> estado/municipio de México) vía Nominatim
(OpenStreetMap), el mismo tipo de API pública sin API key que ya usa el
proyecto para clima reciente (routes/general.py, Open-Meteo).

Se debe llamar una sola vez por sesión de monitoreo de Siembra Link (al
iniciar), no en cada lectura del sensor, para respetar el límite de uso de
Nominatim (~1 solicitud/segundo).
"""
import os
import threading
import time

import requests

from logic import geo_mexico

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
_USER_AGENT = os.environ.get("NOMINATIM_USER_AGENT", "SiembraMas/1.0 (contacto@siembramas.app)")
_MIN_INTERVAL = 1.1  # segundos, política de uso de Nominatim

_rate_lock = threading.Lock()
_ultima_solicitud = 0.0


def _respetar_rate_limit():
    global _ultima_solicitud
    with _rate_lock:
        espera = _MIN_INTERVAL - (time.time() - _ultima_solicitud)
        if espera > 0:
            time.sleep(espera)
        _ultima_solicitud = time.time()


def reverse_geocode(lat, lon, timeout=6) -> dict:
    """
    -> {
        "encontrado": bool,
        "estado": str | None,       # nombre canónico del catálogo nacional
        "municipio": str | None,    # nombre canónico del catálogo nacional
        "estado_raw": str | None,   # lo que devolvió Nominatim, sin normalizar
        "municipio_raw": str | None,
        "lat": float, "lon": float,
        "error": str | None,
    }
    Nunca lanza excepción: cualquier fallo se refleja en "error".
    """
    base = {"encontrado": False, "estado": None, "municipio": None,
            "estado_raw": None, "municipio_raw": None, "lat": lat, "lon": lon, "error": None}

    try:
        lat = float(lat)
        lon = float(lon)
    except (TypeError, ValueError):
        base["error"] = "Coordenadas inválidas."
        return base

    try:
        _respetar_rate_limit()
        resp = requests.get(
            _NOMINATIM_URL,
            params={"format": "jsonv2", "lat": lat, "lon": lon, "zoom": 10, "addressdetails": 1},
            headers={"User-Agent": _USER_AGENT},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as e:
        base["error"] = f"No se pudo contactar el servicio de geolocalización: {e}"
        return base

    addr = data.get("address", {})
    if addr.get("country_code", "").lower() != "mx":
        base["error"] = "La ubicación detectada no está dentro de México."
        return base

    estado_raw = addr.get("state")
    municipio_raw = (
        addr.get("county")
        or addr.get("municipality")
        or addr.get("city")
        or addr.get("town")
        or addr.get("village")
    )

    base["estado_raw"] = estado_raw
    base["municipio_raw"] = municipio_raw

    estado = geo_mexico.normalizar_estado(estado_raw) if estado_raw else None
    municipio = geo_mexico.normalizar_municipio(estado, municipio_raw) if estado and municipio_raw else None

    base["estado"] = estado
    base["municipio"] = municipio
    base["encontrado"] = estado is not None

    if not base["encontrado"]:
        base["error"] = "No se pudo determinar el estado a partir de la ubicación."

    return base
