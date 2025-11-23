import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor

def prediccion(ruta, lugar, mes_solicitado=None, Cultivo=None):
    """
    Predicciones de temperatura mínima y máxima normalizadas.
    Compatible con Estados y Municipios.
    Rutas ajustadas para estructura: root -> data -> Datos -> ...
    """
    
    # Definir archivos según ruta (ACTUALIZADO CON ./data/)
    if ruta == "Estados":
        archivos = {
            "TempMin": f"./data/Datos/Estados/{lugar}/{lugar}-TempMin.csv",
            "tempMax": f"./data/Datos/Estados/{lugar}/{lugar}-tempMax.csv"
        }
    elif ruta == "Municipios":
        archivos = {
            "TempMin": f"./data/Datos/Municipios/{lugar}/TEMP MÍN EXT-{lugar}.csv",
            "tempMax": f"./data/Datos/Municipios/{lugar}/TEMP MÁX EXT-{lugar}.csv"
        }
    else:
        raise ValueError("Ruta desconocida")
    
    predicciones = {}
    
    for tipo, archivo in archivos.items():
        try:
            df = pd.read_csv(archivo)
        except FileNotFoundError:
            # Manejo básico de error si no existe el archivo
            print(f"Advertencia: Archivo no encontrado: {archivo}")
            return pd.DataFrame()
        
        # Normalizar columnas
        df.rename(columns=lambda x: "Mes" if x.upper() == "MES" else x, inplace=True)
        if tipo == "TempMin" and "TEMP MIN EXT" in df.columns:
            df.rename(columns={"TEMP MIN EXT": "Valor"}, inplace=True)
        if tipo == "tempMax" and "Temp Max EXT" in df.columns:
            df.rename(columns={"Temp Max EXT": "Valor"}, inplace=True)
        
        # Columnas a entrenar (años)
        columnas_a_entrenar = [col for col in df.columns if col not in ["Mes", "Valor"] and col.isdigit() and int(col) < 2025]
        if columnas_a_entrenar:
            df_largo = df.melt(id_vars="Mes", value_vars=columnas_a_entrenar, var_name="Año", value_name="Valor")
        else:
            df_largo = df[["Mes", "Valor"]].copy()
            df_largo["Año"] = 2025
        
        df_largo["Año"] = df_largo["Año"].astype(int)
        df_largo["Mes"] = df_largo["Mes"].astype(int)
        
        # Entrenamiento Random Forest
        X = df_largo[["Mes", "Año"]]
        y = df_largo["Valor"]
        modelo = RandomForestRegressor(n_estimators=100, random_state=42)
        modelo.fit(X, y)
        
        # Predecir para 2025
        meses = list(range(1, 13))
        futuros = pd.DataFrame({"Mes": meses, "Año": [2025]*12})
        futuros[f"Pred_{tipo}"] = modelo.predict(futuros)
        predicciones[tipo] = futuros[f"Pred_{tipo}"]

    # Combinar predicciones
    resultados = pd.DataFrame({
        "Año": [2025]*12,
        "Mes": meses,
        "Pred_TempMin": predicciones["TempMin"],
        "Pred_tempMax": predicciones["tempMax"]
    })

    # Nombres de meses
    nombres_meses = {i+1: m for i, m in enumerate(
        ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
         "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"])}
    resultados["Nombre_Mes"] = resultados["Mes"].map(nombres_meses)

    # Filtrar mes si se solicita
    if mes_solicitado:
        if isinstance(mes_solicitado, int):
            resultados = resultados[resultados["Mes"] == mes_solicitado]
        else:
            resultados = resultados[resultados["Nombre_Mes"].str.lower() == mes_solicitado.lower()]

    return resultados