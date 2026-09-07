import os
import re
import unicodedata
from datetime import datetime
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor

from logic import db


def prediccion_desde_mongo(estado, municipio=None, mes_solicitado=None):
    """
    Reemplaza a prediccion() como fuente del motor de recomendación:
    en vez de entrenar un modelo sobre CSV históricos, agrega las lecturas
    reales capturadas por Siembra Link y guardadas en MongoDB para la
    ubicación pedida.

    Degrada de municipio+mes -> municipio -> estado si no hay suficientes
    lecturas específicas, para no dejar al usuario sin nada por falta de
    datos exactos.

    Devuelve:
    {
        "disponible": bool,
        "temp_min": float | None, "temp_max": float | None,
        "humedad": float | None,
        "n_lecturas": int,
        "nivel_match": "estado+municipio+mes" | "estado+municipio" | "estado" | None,
    }
    """
    resultado = {
        "disponible": False, "temp_min": None, "temp_max": None,
        "humedad": None, "n_lecturas": 0, "nivel_match": None,
    }

    if not db.is_configured() or not estado:
        return resultado

    intentos = []
    if municipio and mes_solicitado:
        intentos.append((municipio, mes_solicitado, "estado+municipio+mes"))
    if municipio:
        intentos.append((municipio, None, "estado+municipio"))
    intentos.append((None, None, "estado"))

    for muni, mes, nivel in intentos:
        resumen = db.resumen_clima(estado, municipio=muni, mes=mes)
        if resumen and resumen.get("n_lecturas", 0) > 0:
            resultado.update({
                "disponible": True,
                "temp_min": resumen.get("temp_min"),
                "temp_max": resumen.get("temp_max"),
                "humedad": resumen.get("humedad_prom"),
                "n_lecturas": resumen.get("n_lecturas", 0),
                "nivel_match": nivel,
            })
            return resultado

    return resultado


def prediccion(ruta, lugar, mes_solicitado=None, Cultivo=None):
    """
    Predicciones de temperatura mínima y máxima normalizadas usando Random Forest.
    Compatible con Estados y Municipios.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    if ruta == "Estados":
        dir_lugar = os.path.join(base_dir, "data", "datos", "Estados", lugar)
        if not os.path.exists(dir_lugar):
            dir_lugar = os.path.join(base_dir, "data", "Datos", "Estados", lugar)
        archivos = {
            "TempMin": os.path.join(dir_lugar, f"{lugar}-TempMin.csv"),
            "tempMax": os.path.join(dir_lugar, f"{lugar}-tempMax.csv")
        }
    elif ruta == "Municipios":
        dir_lugar = os.path.join(base_dir, "data", "datos", "municipios", lugar)
        if not os.path.exists(dir_lugar):
            dir_lugar = os.path.join(base_dir, "data", "datos", "Municipios", lugar)
        if not os.path.exists(dir_lugar):
            dir_lugar = os.path.join(base_dir, "data", "Datos", "municipios", lugar)
        
        # Buscar variantes de nombres
        archivos = {
            "TempMin": _encontrar_archivo(dir_lugar, ["TEMP MÍN EXT", "TEMP MIN EXT", "TEMP MÍN PROM", "TEMP MIN PROM", "TempMin"]),
            "tempMax": _encontrar_archivo(dir_lugar, ["TEMP MÁX EXT", "TEMP MAX EXT", "TEMP MÁX PROM", "TEMP MAX PROM", "tempMax"])
        }
    else:
        raise ValueError(f"Ruta desconocida: {ruta}")
    
    predicciones = {}
    
    for tipo, archivo in archivos.items():
        if not archivo or not os.path.exists(archivo):
            continue
        try:
            df = pd.read_csv(archivo, encoding="utf-8")
        except Exception:
            try:
                df = pd.read_csv(archivo, encoding="latin-1")
            except Exception as e:
                print(f"Advertencia: Error leyendo {archivo}: {e}")
                continue
        
        # Normalizar columnas
        df.rename(columns=lambda x: "Mes" if str(x).strip().upper() == "MES" else str(x).strip(), inplace=True)
        for col_cand in ["TEMP MIN EXT", "TEMP MÍN EXT", "TEMP MIN PROM", "TEMP MÍN PROM", "Valor", "VALOR"]:
            if tipo == "TempMin" and col_cand in df.columns:
                df.rename(columns={col_cand: "Valor"}, inplace=True)
                break
        for col_cand in ["Temp Max EXT", "TEMP MÁX EXT", "TEMP MAX EXT", "TEMP MÁX PROM", "TEMP MAX PROM", "Valor", "VALOR"]:
            if tipo == "tempMax" and col_cand in df.columns:
                df.rename(columns={col_cand: "Valor"}, inplace=True)
                break
        
        # Columnas a entrenar (años)
        columnas_a_entrenar = [col for col in df.columns if col not in ["Mes", "Valor"] and str(col).isdigit() and int(col) < 2025]
        if columnas_a_entrenar:
            df_largo = df.melt(id_vars="Mes", value_vars=columnas_a_entrenar, var_name="Año", value_name="Valor")
        else:
            if "Valor" in df.columns:
                df_largo = df[["Mes", "Valor"]].copy()
            else:
                continue
            df_largo["Año"] = 2025
        
        df_largo.dropna(subset=["Valor"], inplace=True)
        df_largo["Valor"] = pd.to_numeric(df_largo["Valor"], errors="coerce")
        df_largo.dropna(subset=["Valor"], inplace=True)
        df_largo["Año"] = df_largo["Año"].astype(int)
        df_largo["Mes"] = df_largo["Mes"].astype(int)
        
        if df_largo.empty:
            continue
        
        # Entrenamiento Random Forest
        X = df_largo[["Mes", "Año"]]
        y = df_largo["Valor"]
        modelo = RandomForestRegressor(n_estimators=100, random_state=42)
        modelo.fit(X, y)
        
        # Predecir para 2025
        meses = list(range(1, 13))
        futuros = pd.DataFrame({"Mes": meses, "Año": [2025]*12})
        predicciones[tipo] = modelo.predict(futuros)

    if not predicciones:
        return pd.DataFrame()

    meses = list(range(1, 13))
    resultados = pd.DataFrame({"Año": [2025]*12, "Mes": meses})
    if "TempMin" in predicciones:
        resultados["Pred_TempMin"] = predicciones["TempMin"]
    else:
        resultados["Pred_TempMin"] = 15.0
    if "tempMax" in predicciones:
        resultados["Pred_tempMax"] = predicciones["tempMax"]
    else:
        resultados["Pred_tempMax"] = 28.0

    nombres_meses = {i+1: m for i, m in enumerate(
        ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
         "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"])}
    resultados["Nombre_Mes"] = resultados["Mes"].map(nombres_meses)

    if mes_solicitado:
        if isinstance(mes_solicitado, int):
            resultados = resultados[resultados["Mes"] == mes_solicitado]
        else:
            resultados = resultados[resultados["Nombre_Mes"].str.lower() == str(mes_solicitado).lower()]

    return resultados


def _encontrar_archivo(directorio, prefijos):
    """Busca un archivo en el directorio que contenga alguno de los prefijos."""
    if not os.path.exists(directorio):
        return None
    for f in os.listdir(directorio):
        f_norm = unicodedata.normalize("NFD", f).lower()
        for pref in prefijos:
            pref_norm = unicodedata.normalize("NFD", pref).lower()
            if pref_norm in f_norm and f.endswith(".csv"):
                return os.path.join(directorio, f)
    return None


def obtener_precipitacion_local(ruta: str, lugar: str, mes_solicitado: int = None) -> float:
    """
    Obtiene la precipitación estimada/histórica local desde los archivos CSV
    de lluvia sin requerir ninguna API en la nube (Open-Meteo).
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if ruta == "Estados":
        dir_lugar = os.path.join(base_dir, "data", "datos", "Estados", lugar)
        if not os.path.exists(dir_lugar):
            dir_lugar = os.path.join(base_dir, "data", "Datos", "Estados", lugar)
        archivo_lluvia = _encontrar_archivo(dir_lugar, ["Lluvias", "Lluvia", "LLUVIA"])
    else:
        dir_lugar = os.path.join(base_dir, "data", "datos", "municipios", lugar)
        if not os.path.exists(dir_lugar):
            dir_lugar = os.path.join(base_dir, "data", "datos", "Municipios", lugar)
        if not os.path.exists(dir_lugar):
            dir_lugar = os.path.join(base_dir, "data", "Datos", "municipios", lugar)
        archivo_lluvia = _encontrar_archivo(dir_lugar, ["LLUVIA TOTAL MENSUAL", "LLUVIA", "Lluvia"])

    if not archivo_lluvia or not os.path.exists(archivo_lluvia):
        return 75.0  # Valor promedio por defecto de testing si no hay archivo

    try:
        df = pd.read_csv(archivo_lluvia)
        df.rename(columns=lambda x: "Mes" if str(x).strip().upper() == "MES" else str(x).strip(), inplace=True)
        if "Mes" in df.columns:
            if mes_solicitado:
                df_mes = df[df["Mes"] == mes_solicitado]
            else:
                df_mes = df
            if not df_mes.empty:
                cols_num = [c for c in df_mes.columns if c != "Mes" and not c.startswith("Unnamed")]
                vals = df_mes[cols_num].values.flatten()
                vals_num = pd.to_numeric(vals, errors="coerce")
                vals_clean = vals_num[~np.isnan(vals_num)]
                if len(vals_clean) > 0:
                    return round(float(np.mean(vals_clean)), 1)
    except Exception as e:
        print(f"Error procesando lluvia local para {lugar}: {e}")

    return 75.0


def _slug_cultivo(nombre: str) -> str:
    s = unicodedata.normalize("NFD", nombre).encode("ascii", "ignore").decode("utf-8")
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s.strip().lower())
    return re.sub(r"-+", "-", s).strip("-")


def calcular_probabilidad_local(preds: dict, optimos: dict) -> int:
    """Cálculo local del score de probabilidad y viabilidad agronómica."""
    pesos = {"tmin": 0.18, "tmax": 0.18, "tmed": 0.24, "precip": 0.24, "hum": 0.16}
    config = {
        "precip_deficit_tol": 0.20,
        "hum_tolerancia": 0.10,
        "hum_rolloff": 0.50,
        "temp_holgura_c": 5.0,
        "tmed_holgura_c": 3.0,
    }

    def clamp01(x): return max(0.0, min(1.0, x))

    def score_precipitacion(pred, p_opt, deficit_tol):
        if p_opt <= 0: return 0.0
        if pred >= p_opt: return 1.0
        piso = p_opt * (1.0 - deficit_tol)
        if pred <= piso: return 0.0
        return (pred - piso) / (p_opt - piso)

    def score_humedad(pred, h_opt, tol_centro, rolloff):
        if h_opt <= 0: return 0.0
        delta_rel = abs(pred - h_opt) / h_opt
        if delta_rel <= tol_centro: return 1.0
        exceso = delta_rel - tol_centro
        if exceso >= rolloff: return 0.0
        return 1.0 - (exceso / rolloff)

    def score_temperatura(valor, rango_min, rango_max, holgura):
        if rango_min is None or rango_max is None: return 0.0
        if rango_min > rango_max: rango_min, rango_max = rango_max, rango_min
        if rango_min <= valor <= rango_max: return 1.0
        distancia = (rango_min - valor) if valor < rango_min else (valor - rango_max)
        if distancia >= holgura: return 0.0
        return 1.0 - (distancia / holgura)

    def score_temperatura_central(valor, t_opt, holgura):
        if t_opt is None or holgura is None or holgura <= 0: return 0.0
        d = abs(valor - t_opt)
        if d >= holgura: return 0.0
        return 1.0 - (d / holgura)

    p_opt = optimos.get("p_opt", (optimos["pmin"] + optimos["pmax"]) / 2.0)
    h_opt = optimos.get("h_opt", (optimos["hmin"] + optimos["hmax"]) / 2.0)

    tmin_pred = preds.get("tmin", 18.0)
    tmax_pred = preds.get("tmax", 28.0)
    tmed_pred = preds.get("tmed", (tmin_pred + tmax_pred) / 2.0)
    tmed_opt = optimos.get("tmed_opt", (optimos["tmin"] + optimos["tmax"]) / 2.0)

    s_tmin = score_temperatura(tmin_pred, optimos["tmin"], optimos["tmax"], config["temp_holgura_c"])
    s_tmax = score_temperatura(tmax_pred, optimos["tmin"], optimos["tmax"], config["temp_holgura_c"])
    s_tmed = score_temperatura_central(tmed_pred, tmed_opt, config["tmed_holgura_c"])
    s_prec = score_precipitacion(preds.get("precip", 70.0), p_opt, config["precip_deficit_tol"])
    s_hum  = score_humedad(preds.get("hum", 65.0), h_opt, config["hum_tolerancia"], config["hum_rolloff"])

    total_pesos = sum(pesos.values()) or 1.0
    score = (
        pesos["tmin"] * s_tmin +
        pesos["tmax"] * s_tmax +
        pesos["tmed"] * s_tmed +
        pesos["precip"] * s_prec +
        pesos["hum"] * s_hum
    ) / total_pesos

    valor = int(round(100 * clamp01(score)))
    return 99 if valor == 100 else valor


# ============================================================================
# NUEVA FUNCIÓN LOCAL PARA TESTING Y RECOMENDACIÓN OFFLINE
# ============================================================================

def prediccion_local(estado: str, municipio: str = None, mes_solicitado: int = None, ruta: str = "Estados") -> dict:
    """
    Función de predicción y recomendación de cultivos 100% local:
    1. Revisa lecturas de hardware capturadas localmente por Siembra Link.
    2. Si no hay lecturas del sensor, entrena un modelo Random Forest (ML)
       sobre los CSVs históricos locales (data/datos/Estados o data/datos/municipios).
    3. Obtiene precipitación y humedad de forma local sin requerir Open-Meteo ni MongoDB.
    4. Evalúa y ordena recomendaciones contra CondicionesIdeales.csv.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if mes_solicitado is None:
        mes_solicitado = datetime.now().month

    lugar = municipio if (municipio and municipio not in ["Seleccionar...", "General", ""]) else estado
    ruta_efectiva = "Municipios" if (lugar == municipio and lugar) else "Estados"

    temp_min = temp_max = humedad = None
    fuente_clima = "ml_random_forest_local"
    n_lecturas_hardware = 0

    # 1. Intentar obtener datos de lecturas locales del hardware (Siembra Link)
    resumen_local = db.resumen_clima_local(estado, municipio=municipio if ruta_efectiva == "Municipios" else None, mes=mes_solicitado)
    if resumen_local and resumen_local.get("n_lecturas", 0) > 0:
        temp_min = resumen_local.get("temp_min")
        temp_max = resumen_local.get("temp_max")
        humedad = resumen_local.get("humedad_prom")
        n_lecturas_hardware = resumen_local.get("n_lecturas", 0)
        fuente_clima = "hardware_siembra_link_local"

    # 2. Si falta temperatura, entrenar modelo Random Forest local
    if temp_min is None or temp_max is None:
        df_pred = prediccion(ruta_efectiva, lugar, mes_solicitado=mes_solicitado)
        if not df_pred.empty:
            temp_min = round(float(df_pred["Pred_TempMin"].iloc[0]), 1)
            temp_max = round(float(df_pred["Pred_tempMax"].iloc[0]), 1)
        else:
            # Fallback a estado si municipio no tuvo datos
            if ruta_efectiva == "Municipios" and estado:
                df_pred_est = prediccion("Estados", estado, mes_solicitado=mes_solicitado)
                if not df_pred_est.empty:
                    temp_min = round(float(df_pred_est["Pred_TempMin"].iloc[0]), 1)
                    temp_max = round(float(df_pred_est["Pred_tempMax"].iloc[0]), 1)

    # Valores por defecto de seguridad si no hay datos históricos
    if temp_min is None: temp_min = 16.0
    if temp_max is None: temp_max = 28.0
    if humedad is None: humedad = 65.0

    temp_media = round((temp_min + temp_max) / 2.0, 1)

    # 3. Precipitación local
    precipitacion = obtener_precipitacion_local(ruta_efectiva, lugar, mes_solicitado)

    # 4. Cargar Condiciones Ideales y generar recomendaciones
    recomendaciones = []
    csv_condiciones = os.path.join(base_dir, "data", "condiciones_ideales", "CondicionesIdeales.csv")
    csv_zona = os.path.join(base_dir, "data", "ideal", "CultivoEstado.csv" if ruta_efectiva == "Estados" else "CultivoMunicipio.csv")
    if not os.path.exists(csv_zona):
        csv_zona = os.path.join(base_dir, "data", "Ideal", "CultivoEstado.csv" if ruta_efectiva == "Estados" else "CultivoMunicipio.csv")

    cultivos_zona = []
    try:
        from logic.cultivos import obtener_cultivos
        cultivos_zona = obtener_cultivos(csv_zona).get(lugar, [])
    except Exception as e:
        print(f"Advertencia al leer cultivos de zona: {e}")

    cultivos_zona_norm = [unicodedata.normalize("NFD", str(c)).encode("ascii", "ignore").decode("utf-8").upper() for c in cultivos_zona]

    if os.path.exists(csv_condiciones):
        try:
            df_cond = pd.read_csv(csv_condiciones, encoding="utf-8")
            df_cond.columns = [col.strip().replace(' ', '_') for col in df_cond.columns]
            preds_dict = {"tmin": temp_min, "tmax": temp_max, "tmed": temp_media, "precip": precipitacion, "hum": humedad}

            for cultivo in df_cond["Cultivo"].unique():
                cond = df_cond[df_cond["Cultivo"] == cultivo]
                if cond.empty:
                    continue
                lluvia_opt = float(str(cond["Lluvias_optima"].iloc[0]).replace(',', '.'))
                humedad_opt = float(str(cond["Humedad"].iloc[0]).replace(',', '.'))
                optimos = {
                    "tmin": float(str(cond["Temp_min_optima"].iloc[0]).replace(',', '.')),
                    "tmax": float(str(cond["Temp_max_optima"].iloc[0]).replace(',', '.')),
                    "pmin": lluvia_opt * 0.8,
                    "pmax": lluvia_opt * 1.2,
                    "hmin": humedad_opt * 0.9,
                    "hmax": humedad_opt * 1.1,
                    "p_opt": lluvia_opt,
                    "h_opt": humedad_opt,
                }
                prob = calcular_probabilidad_local(preds_dict, optimos)

                if prob >= 70:
                    texto = "Alta probabilidad de éxito."
                    clase_viabilidad = "bg-green"
                elif prob >= 40:
                    texto = "La siembra es posible con precauciones."
                    clase_viabilidad = "bg-yellow"
                else:
                    texto = "No se recomienda la siembra."
                    clase_viabilidad = "bg-red"

                cultivo_norm = unicodedata.normalize("NFD", str(cultivo)).encode("ascii", "ignore").decode("utf-8").upper()
                es_de_zona = cultivo_norm in cultivos_zona_norm

                recomendaciones.append({
                    "cultivo": cultivo,
                    "prob": prob,
                    "texto": texto,
                    "clase_viabilidad": clase_viabilidad,
                    "img_slug": _slug_cultivo(cultivo),
                    "es_zona": es_de_zona
                })
        except Exception as e:
            print(f"Error generando recomendaciones locales: {e}")

    recomendaciones.sort(key=lambda x: x["prob"], reverse=True)

    return {
        "status": "ok",
        "modo": "testing_local",
        "disponible": True,
        "lugar": lugar,
        "ruta": ruta_efectiva,
        "estado": estado,
        "municipio": municipio,
        "mes": mes_solicitado,
        "temp_min": temp_min,
        "temp_max": temp_max,
        "temp_media": temp_media,
        "precipitacion": precipitacion,
        "humedad": humedad,
        "fuente_clima": fuente_clima,
        "n_lecturas_hardware": n_lecturas_hardware,
        "recomendaciones": recomendaciones,
        "total_cultivos_evaluados": len(recomendaciones),
    }


def local(estado: str = "Veracruz", municipio: str = None, mes_solicitado: int = None, ruta: str = "Estados", **kwargs) -> dict:
    """
    Función `local` requerida para el entorno de testing:
    Ejecuta el ciclo completo de lectura/datos locales, entrenamiento ML
    y cálculo de predicciones y recomendaciones de cultivos 100% offline.
    """
    return prediccion_local(
        estado=estado,
        municipio=municipio,
        mes_solicitado=mes_solicitado,
        ruta=ruta
    )