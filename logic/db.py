"""
Conexión perezosa a MongoDB para las lecturas de Siembra Link.

Sigue el mismo patrón de "servicio externo opcional" que ya usan
routes/auth_snap.py y routes/siembra_snap.py para Cognito/S3: no se conecta
al importar el módulo, y todas las funciones públicas devuelven None cuando
MONGODB_URI no está configurada (distinto de [] / False, que significa
"configurado pero sin resultados/sin éxito").
"""
import os
import json
import uuid
import threading
from datetime import datetime, timezone

from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import PyMongoError
from bson import ObjectId
from bson.errors import InvalidId

_MONGODB_URI = os.environ.get("MONGODB_URI")
_DB_NAME = os.environ.get("MONGODB_DB_NAME", "siembramas")

COLLECTION_LECTURAS = "siembra_link_lecturas"

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL_STORAGE_PATH = os.path.join(_BASE_DIR, "data", "siembra_link_local.json")
_local_lock = threading.Lock()

_client = None
_lock = threading.Lock()
_indices_creados = False
_ultimo_intento_fallido = 0.0
_COOLDOWN_REINTENTO = 30.0  # segundos antes de reintentar si Mongo falló


def is_configured() -> bool:
    return bool(_MONGODB_URI)


def get_client():
    global _client, _ultimo_intento_fallido
    if not _MONGODB_URI:
        return None
    import time
    ahora = time.time()
    if _client is None:
        if (ahora - _ultimo_intento_fallido) < _COOLDOWN_REINTENTO:
            return None
        with _lock:
            if _client is None:
                if (ahora - _ultimo_intento_fallido) < _COOLDOWN_REINTENTO:
                    return None
                try:
                    cliente = MongoClient(
                        _MONGODB_URI,
                        serverSelectionTimeoutMS=1500,
                        connectTimeoutMS=1500,
                    )
                    cliente.admin.command("ping")
                    _client = cliente
                    _ultimo_intento_fallido = 0.0
                except PyMongoError as e:
                    print(f"[Mongo] No se pudo conectar: {e}")
                    _client = None
                    _ultimo_intento_fallido = ahora
    return _client


def _get_collection(nombre):
    cliente = get_client()
    if cliente is None:
        return None
    coleccion = cliente[_DB_NAME][nombre]
    _asegurar_indices(coleccion)
    return coleccion


def _asegurar_indices(coleccion):
    global _indices_creados
    if _indices_creados:
        return
    try:
        coleccion.create_index([("estado", ASCENDING), ("municipio", ASCENDING)])
        coleccion.create_index([("creado_en", DESCENDING)])
        _indices_creados = True
    except PyMongoError as e:
        print(f"[Mongo] No se pudieron crear índices: {e}")


def _doc_a_publico(doc):
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    if isinstance(doc.get("creado_en"), datetime):
        doc["creado_en"] = doc["creado_en"].isoformat()
    return doc


def guardar_lectura(doc: dict) -> bool:
    coleccion = _get_collection(COLLECTION_LECTURAS)
    if coleccion is None:
        return False
    try:
        doc = dict(doc)
        doc.setdefault("creado_en", datetime.now(timezone.utc))
        coleccion.insert_one(doc)
        return True
    except PyMongoError as e:
        print(f"[Mongo] Error guardando lectura: {e}")
        return False


def listar_lecturas(filtro: dict = None, limit: int = 200, skip: int = 0):
    """None = Mongo no configurado. [] = configurado pero sin resultados."""
    coleccion = _get_collection(COLLECTION_LECTURAS)
    if coleccion is None:
        return None
    try:
        cursor = (
            coleccion.find(filtro or {})
            .sort("creado_en", DESCENDING)
            .skip(max(0, skip))
            .limit(max(1, min(limit, 1000)))
        )
        return [_doc_a_publico(d) for d in cursor]
    except PyMongoError as e:
        print(f"[Mongo] Error listando lecturas: {e}")
        return []


def obtener_lectura(id_str: str):
    coleccion = _get_collection(COLLECTION_LECTURAS)
    if coleccion is None:
        return None
    try:
        doc = coleccion.find_one({"_id": ObjectId(id_str)})
        return _doc_a_publico(doc) if doc else None
    except (PyMongoError, InvalidId) as e:
        print(f"[Mongo] Error obteniendo lectura {id_str}: {e}")
        return None


def actualizar_lectura(id_str: str, cambios: dict) -> bool:
    coleccion = _get_collection(COLLECTION_LECTURAS)
    if coleccion is None:
        return False
    try:
        cambios = {k: v for k, v in cambios.items() if k not in ("_id", "id")}
        resultado = coleccion.update_one({"_id": ObjectId(id_str)}, {"$set": cambios})
        return resultado.matched_count > 0
    except (PyMongoError, InvalidId) as e:
        print(f"[Mongo] Error actualizando lectura {id_str}: {e}")
        return False


def eliminar_lectura(id_str: str) -> bool:
    coleccion = _get_collection(COLLECTION_LECTURAS)
    if coleccion is None:
        return False
    try:
        resultado = coleccion.delete_one({"_id": ObjectId(id_str)})
        return resultado.deleted_count > 0
    except (PyMongoError, InvalidId) as e:
        print(f"[Mongo] Error eliminando lectura {id_str}: {e}")
        return False


def cobertura():
    """None = Mongo no configurado. [] = configurado, sin lecturas aún.
    En caso contrario: [{estado, municipio, conteo, ultima_fecha}, ...]"""
    coleccion = _get_collection(COLLECTION_LECTURAS)
    if coleccion is None:
        return None
    try:
        pipeline = [
            {"$match": {"estado": {"$ne": None}}},
            {
                "$group": {
                    "_id": {"estado": "$estado", "municipio": "$municipio"},
                    "conteo": {"$sum": 1},
                    "ultima_fecha": {"$max": "$creado_en"},
                }
            },
        ]
        resultados = []
        for r in coleccion.aggregate(pipeline):
            ultima = r.get("ultima_fecha")
            resultados.append(
                {
                    "estado": r["_id"].get("estado"),
                    "municipio": r["_id"].get("municipio"),
                    "conteo": r["conteo"],
                    "ultima_fecha": ultima.isoformat() if isinstance(ultima, datetime) else ultima,
                }
            )
        return resultados
    except PyMongoError as e:
        print(f"[Mongo] Error calculando cobertura: {e}")
        return []


def resumen_clima(estado: str, municipio: str = None, mes: int = None):
    """Promedios de temperatura/humedad para una ubicación (y mes opcional),
    usados por el motor de predicción. None = Mongo no configurado."""
    coleccion = _get_collection(COLLECTION_LECTURAS)
    if coleccion is None:
        return None
    try:
        match = {"estado": estado}
        if municipio:
            match["municipio"] = municipio
        if mes:
            match["mes"] = mes

        pipeline = [
            {"$match": match},
            {
                "$group": {
                    "_id": None,
                    "temp_min": {"$min": "$temperatura"},
                    "temp_max": {"$max": "$temperatura"},
                    "humedad_prom": {"$avg": "$humedad_ambiente"},
                    "n_lecturas": {"$sum": 1},
                }
            },
        ]
        resultado = list(coleccion.aggregate(pipeline))
        if not resultado or resultado[0]["n_lecturas"] == 0:
            return {"n_lecturas": 0}
        r = resultado[0]
        return {
            "temp_min": r["temp_min"],
            "temp_max": r["temp_max"],
            "humedad_prom": round(r["humedad_prom"], 1) if r["humedad_prom"] is not None else None,
            "n_lecturas": r["n_lecturas"],
        }
    except PyMongoError as e:
        print(f"[Mongo] Error calculando resumen de clima: {e}")
        return {"n_lecturas": 0}


# ============================================================================
# PERSISTENCIA LOCAL Y TESTING OFFLINE (SIN CONEXIÓN A LA NUBE)
# ============================================================================

def _leer_archivo_local() -> list:
    if not os.path.exists(LOCAL_STORAGE_PATH):
        return []
    try:
        with open(LOCAL_STORAGE_PATH, "r", encoding="utf-8") as f:
            datos = json.load(f)
            return datos if isinstance(datos, list) else []
    except Exception as e:
        print(f"[LocalDB] Error leyendo almacenamiento local: {e}")
        return []


def _escribir_archivo_local(datos: list) -> bool:
    try:
        os.makedirs(os.path.dirname(LOCAL_STORAGE_PATH), exist_ok=True)
        with open(LOCAL_STORAGE_PATH, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[LocalDB] Error escribiendo en almacenamiento local: {e}")
        return False


def guardar_lectura_local(doc: dict) -> bool:
    """Guarda una lectura en el archivo local para pruebas sin MongoDB."""
    with _local_lock:
        datos = _leer_archivo_local()
        item = dict(doc)
        if "id" not in item and "_id" not in item:
            item["id"] = str(uuid.uuid4())
        elif "_id" in item:
            item["id"] = str(item.pop("_id"))

        if "creado_en" not in item:
            item["creado_en"] = datetime.now(timezone.utc).isoformat()
        elif isinstance(item["creado_en"], datetime):
            item["creado_en"] = item["creado_en"].isoformat()

        datos.append(item)
        return _escribir_archivo_local(datos)


def listar_lecturas_local(filtro: dict = None, limit: int = 200, skip: int = 0) -> list:
    """Lista lecturas almacenadas en local aplicando filtros opcionales."""
    with _local_lock:
        datos = _leer_archivo_local()

    if filtro:
        def coincide(item):
            for k, v in filtro.items():
                if v is not None and item.get(k) != v:
                    return False
            return True
        datos = [d for d in datos if coincide(d)]

    # Ordenar por creado_en descendente
    datos.sort(key=lambda x: str(x.get("creado_en", "")), reverse=True)
    return datos[max(0, skip): max(0, skip) + max(1, min(limit, 1000))]


def obtener_lectura_local(id_str: str):
    with _local_lock:
        datos = _leer_archivo_local()
    for d in datos:
        if d.get("id") == id_str:
            return d
    return None


def actualizar_lectura_local(id_str: str, cambios: dict) -> bool:
    with _local_lock:
        datos = _leer_archivo_local()
        encontrado = False
        for d in datos:
            if d.get("id") == id_str:
                for k, v in cambios.items():
                    if k not in ("id", "_id"):
                        d[k] = v
                encontrado = True
                break
        if encontrado:
            return _escribir_archivo_local(datos)
        return False


def eliminar_lectura_local(id_str: str) -> bool:
    with _local_lock:
        datos = _leer_archivo_local()
        nuevos = [d for d in datos if d.get("id") != id_str]
        if len(nuevos) < len(datos):
            return _escribir_archivo_local(nuevos)
        return False


def cobertura_local() -> list:
    """Calcula la cobertura geográfica de lecturas guardadas localmente."""
    with _local_lock:
        datos = _leer_archivo_local()

    agrupados = {}
    for d in datos:
        estado = d.get("estado")
        if not estado:
            continue
        muni = d.get("municipio")
        clave = (estado, muni)
        if clave not in agrupados:
            agrupados[clave] = {"conteo": 0, "ultima_fecha": d.get("creado_en")}
        agrupados[clave]["conteo"] += 1
        if d.get("creado_en", "") > (agrupados[clave]["ultima_fecha"] or ""):
            agrupados[clave]["ultima_fecha"] = d.get("creado_en")

    return [
        {
            "estado": est,
            "municipio": mun,
            "conteo": info["conteo"],
            "ultima_fecha": info["ultima_fecha"],
        }
        for (est, mun), info in agrupados.items()
    ]


def resumen_clima_local(estado: str, municipio: str = None, mes: int = None) -> dict:
    """Calcula promedios de temperatura y humedad de las lecturas locales."""
    with _local_lock:
        datos = _leer_archivo_local()

    filtrados = [
        d for d in datos
        if d.get("estado") == estado
        and (municipio is None or d.get("municipio") == municipio)
        and (mes is None or d.get("mes") == mes)
        and d.get("temperatura") is not None
    ]

    if not filtrados:
        return {"n_lecturas": 0}

    temps = [float(d["temperatura"]) for d in filtrados if d.get("temperatura") is not None]
    hums = [float(d["humedad_ambiente"]) for d in filtrados if d.get("humedad_ambiente") is not None]

    if not temps:
        return {"n_lecturas": 0}

    return {
        "temp_min": min(temps),
        "temp_max": max(temps),
        "humedad_prom": round(sum(hums) / len(hums), 1) if hums else None,
        "n_lecturas": len(filtrados),
    }


LOCAL_SESSIONS_PATH = os.path.join(_BASE_DIR, "data", "siembra_link_sesiones.json")
COLLECTION_SESIONES = "siembra_link_sesiones"


def _leer_sesiones_local() -> list:
    if not os.path.exists(LOCAL_SESSIONS_PATH):
        return []
    try:
        with open(LOCAL_SESSIONS_PATH, "r", encoding="utf-8") as f:
            datos = json.load(f)
            return datos if isinstance(datos, list) else []
    except Exception as e:
        print(f"[LocalDB] Error leyendo sesiones locales: {e}")
        return []


def _escribir_sesiones_local(datos: list) -> bool:
    try:
        os.makedirs(os.path.dirname(LOCAL_SESSIONS_PATH), exist_ok=True)
        with open(LOCAL_SESSIONS_PATH, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[LocalDB] Error guardando sesiones locales: {e}")
        return False


def guardar_o_actualizar_sesion(sesion_doc: dict) -> dict:
    """
    Guarda o actualiza un registro agrupado de sesión de monitoreo con
    todas las muestras capturadas en su intervalo y estadísticas consolidadas.
    """
    with _local_lock:
        sesiones = _leer_sesiones_local()
        item = dict(sesion_doc)

        sid = item.get("id") or item.get("sesion_id")
        if not sid:
            sid = str(uuid.uuid4())
            item["id"] = sid
            item["sesion_id"] = sid
        else:
            item["id"] = str(sid)
            item["sesion_id"] = str(sid)

        # Recalcular métricas acumuladas a partir de todas las muestras de la sesión
        muestras = item.get("muestras", [])
        item["total_muestras"] = len(muestras)

        if muestras:
            temps = [float(m["temperatura"]) for m in muestras if m.get("temperatura") is not None]
            hums = [float(m["humedad_ambiente"]) for m in muestras if m.get("humedad_ambiente") is not None]
            suelos = [float(m["humedad_suelo_pct"]) for m in muestras if m.get("humedad_suelo_pct") is not None]
            lluvias = [float(m["precipitacion_raw"]) for m in muestras if m.get("precipitacion_raw") is not None]

            item["temp_min"] = round(min(temps), 1) if temps else None
            item["temp_max"] = round(max(temps), 1) if temps else None
            item["temp_prom"] = round(sum(temps) / len(temps), 1) if temps else None
            item["humedad_prom"] = round(sum(hums) / len(hums), 1) if hums else None
            item["humedad_suelo_prom"] = round(sum(suelos) / len(suelos), 1) if suelos else None
            item["precipitacion_raw_prom"] = round(sum(lluvias) / len(lluvias), 1) if lluvias else None

            # Propiedades de acceso directo para modelos de ML y vistas
            item["temperatura"] = item["temp_prom"]
            item["humedad_ambiente"] = item["humedad_prom"]
            item["humedad_suelo_pct"] = item["humedad_suelo_prom"]
            item["precipitacion_raw"] = item["precipitacion_raw_prom"]

        # Insertar o actualizar en lista local
        indice = -1
        for i, s in enumerate(sesiones):
            if s.get("id") == item["id"] or s.get("sesion_id") == item["sesion_id"]:
                indice = i
                break

        if indice >= 0:
            sesiones[indice] = item
        else:
            sesiones.insert(0, item)

        _escribir_sesiones_local(sesiones)

    # Persistir en Mongo si está disponible
    col_sesiones = _get_collection(COLLECTION_SESIONES)
    if col_sesiones is not None:
        try:
            doc_mongo = dict(item)
            doc_mongo["_id"] = str(item["id"])
            col_sesiones.update_one({"_id": str(item["id"])}, {"$set": doc_mongo}, upsert=True)
        except Exception as e:
            print(f"[Mongo] Error actualizando sesión: {e}")

    return item


def _agrupar_lecturas_sueltas_en_sesiones(lecturas: list) -> list:
    """Convierte lecturas individuales anteriores en registros de sesión agrupados."""
    if not lecturas:
        return []
    grupos = {}
    for l in lecturas:
        sid = l.get("sesion_id")
        if not sid:
            fecha = l.get("fecha") or "2026-08-22"
            hora = (l.get("hora") or "00:00:00")[:5]
            sid = f"legacy-{fecha}-{hora}-{l.get('cultivo', 'cultivo')}"
        
        if sid not in grupos:
            grupos[sid] = {
                "id": sid,
                "sesion_id": sid,
                "fecha": l.get("fecha"),
                "fecha_inicio": l.get("fecha"),
                "hora_inicio": l.get("hora") or l.get("timestamp") or "00:00:00",
                "timestamp_inicio": l.get("creado_en") or l.get("timestamp"),
                "duracion_programada_minutos": l.get("duracion_minutos", 5),
                "cultivo": l.get("cultivo"),
                "etapa": l.get("etapa", "1"),
                "estado": l.get("estado"),
                "municipio": l.get("municipio"),
                "lat": l.get("lat"),
                "lon": l.get("lon"),
                "estado_sesion": "COMPLETADA",
                "muestras": []
            }
        grupos[sid]["muestras"].append(l)

    sesiones_resultantes = []
    for g in grupos.values():
        muestras = g["muestras"]
        g["total_muestras"] = len(muestras)
        temps = [float(m["temperatura"]) for m in muestras if m.get("temperatura") is not None]
        hums = [float(m["humedad_ambiente"]) for m in muestras if m.get("humedad_ambiente") is not None]
        suelos = [float(m["humedad_suelo_pct"]) for m in muestras if m.get("humedad_suelo_pct") is not None]
        lluvias = [float(m["precipitacion_raw"]) for m in muestras if m.get("precipitacion_raw") is not None]

        g["temp_min"] = round(min(temps), 1) if temps else None
        g["temp_max"] = round(max(temps), 1) if temps else None
        g["temp_prom"] = round(sum(temps) / len(temps), 1) if temps else None
        g["humedad_prom"] = round(sum(hums) / len(hums), 1) if hums else None
        g["humedad_suelo_prom"] = round(sum(suelos) / len(suelos), 1) if suelos else None
        g["precipitacion_raw_prom"] = round(sum(lluvias) / len(lluvias), 1) if lluvias else None

        g["temperatura"] = g["temp_prom"]
        g["humedad_ambiente"] = g["humedad_prom"]
        g["humedad_suelo_pct"] = g["humedad_suelo_prom"]
        g["precipitacion_raw"] = g["precipitacion_raw_prom"]
        sesiones_resultantes.append(g)

    return sesiones_resultantes


def listar_todas_las_sesiones(filtro: dict = None, limit: int = 100) -> list:
    """
    Retorna la lista de registros de sesión de monitoreo con sus muestras agrupadas.
    """
    sesiones = []
    ids_vistos = set()

    # 1. Sesiones explícitas locales
    locales = _leer_sesiones_local()
    for s in locales:
        sid = s.get("id") or s.get("sesion_id")
        if sid and sid not in ids_vistos:
            ids_vistos.add(sid)
            sesiones.append(s)

    # 2. Sesiones en MongoDB si existen
    col_sesiones = _get_collection(COLLECTION_SESIONES)
    if col_sesiones is not None:
        try:
            cursor = col_sesiones.find({}).sort("timestamp_inicio", DESCENDING).limit(limit)
            for d in cursor:
                doc = _doc_a_publico(d)
                sid = doc.get("id") or doc.get("sesion_id")
                if sid and sid not in ids_vistos:
                    ids_vistos.add(sid)
                    sesiones.append(doc)
        except Exception as e:
            print(f"[Mongo] Error listando sesiones: {e}")

    # 3. Si no hay sesiones registradas, agrupar las lecturas sueltas existentes
    if not sesiones:
        lecturas_sueltas = listar_lecturas_local(limit=500)
        sesiones = _agrupar_lecturas_sueltas_en_sesiones(lecturas_sueltas)

    if filtro:
        def coincide(item):
            for k, v in filtro.items():
                if v is not None and item.get(k) != v:
                    return False
            return True
        sesiones = [s for s in sesiones if coincide(s)]

    # Ordenar por fecha/hora de inicio descendente
    def clave_orden(item):
        return str(item.get("timestamp_inicio") or item.get("fecha_inicio") or item.get("fecha") or "")

    sesiones.sort(key=clave_orden, reverse=True)
    return sesiones[:limit]


def obtener_sesion_monitoreo(id_str: str) -> dict:
    """Busca un registro de sesión por ID (local o Mongo)."""
    if not id_str:
        return None
    with _local_lock:
        sesiones = _leer_sesiones_local()
        for s in sesiones:
            if s.get("id") == id_str or s.get("sesion_id") == id_str:
                return s

    col_sesiones = _get_collection(COLLECTION_SESIONES)
    if col_sesiones is not None:
        try:
            d = col_sesiones.find_one({"$or": [{"_id": str(id_str)}, {"id": str(id_str)}, {"sesion_id": str(id_str)}]})
            if d:
                return _doc_a_publico(d)
        except Exception as e:
            print(f"[Mongo] Error buscando sesión: {e}")

    # Si no se encuentra como sesión, buscar en lecturas sueltas y empaquetar
    lectura = obtener_cualquier_lectura(id_str)
    if lectura:
        grupos = _agrupar_lecturas_sueltas_en_sesiones([lectura])
        return grupos[0] if grupos else None

    return None


def listar_todas_las_muestras(filtro: dict = None, limit: int = 200) -> list:
    """
    Retorna el historial de registros de monitoreo (sesiones agrupadas)
    garantizando que cada elemento represente una sesión con todas sus muestras.
    """
    return listar_todas_las_sesiones(filtro=filtro, limit=limit)


def obtener_cualquier_lectura(id_str: str) -> dict:
    """Busca una lectura o registro de sesión por ID en local o en Mongo."""
    if not id_str:
        return None
    # Prioridad 1: Sesión agrupada
    ses = obtener_sesion_monitoreo(id_str)
    if ses:
        return ses
    loc = obtener_lectura_local(id_str)
    if loc:
        return loc
    return obtener_lectura(id_str)

