import pandas as pd

def obtener_cultivos(ruta_csv):
    df = pd.read_csv(ruta_csv)
    
    # Agrupar por entidad y convertir a diccionario
    return df.groupby("Entidad")["Cultivo"].apply(list).to_dict()

