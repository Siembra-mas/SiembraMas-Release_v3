import serial
import time
import pandas as pd
import streamlit as st

# Configuración del puerto serial
# Cambiar 'COM3' por el puerto de tu Arduino 
try:
    ser = serial.Serial('COM3', 9600, timeout=1)
    time.sleep(2)  # Espera a que la conexión serial se establezca
    st.success("Conexión con Arduino establecida correctamente.")
except serial.SerialException as e:
    st.error(f"Error al conectar con Arduino: {e}. Revisa que el puerto sea el correcto.")
    ser = None # Establecer ser en None para evitar errores si no se conecta

# Encabezados para el DataFrame
columnas = ['Temperatura (°C)', 'Humedad ambiente (%)', 'Humedad del suelo (valor)', 
            'Nivel de agua (valor)', 'Intensidad de lluvia (valor)', 'Lluvia detectada (mm)']

# Inicializar un DataFrame vacío
data_df = pd.DataFrame(columns=columnas)

# Título de la aplicación en Streamlit
st.title("Monitoreo de Sensores con Arduino")

if ser:
    # Botón para iniciar la lectura de datos
    if st.button("Iniciar lectura de datos"):
        st.write("Leyendo datos de Arduino...")
        barra_progreso = st.progress(0)
        datos_leidos = []

        for i in range(10):  # Lee 10 muestras para este ejemplo. Puedes cambiar este número.
            linea = ser.readline().decode('utf-8').strip()
            
            # El código de Arduino envía varias líneas. Solo procesamos las que contienen datos.
            # Los datos están en las líneas que empiezan con "Temperatura:".
            if linea.startswith("Temperatura:"):
                # Procesa los datos de la línea
                partes = linea.split(" | Humedad ambiente: ")
                temp_str = partes[0].replace("Temperatura: ", "").strip().replace("°C", "")
                hum_str = partes[1].replace("%", "").strip()
                
                # Lee las siguientes líneas para obtener los otros datos
                try:
                    humedad_suelo_str = ser.readline().decode('utf-8').strip().split("valor): ")[1].split(" ")[0].strip()
                    nivel_agua_str = ser.readline().decode('utf-8').strip().split("valor): ")[1].strip()
                    lluvia_str = ser.readline().decode('utf-8').strip().split("valor): ")[1].split(" ")[0].strip()
                    lluvia_mm_str = ser.readline().decode('utf-8').strip().split("Lluvia detectada: ")[1].strip().replace(" mm", "")
                except IndexError:
                    st.warning("No se pudieron leer todas las líneas de datos. Asegúrate de que el formato de salida de Arduino es el esperado.")
                    continue

                # Convierte los valores a los tipos de datos correctos
                try:
                    temp = float(temp_str)
                    hum = int(hum_str)
                    humedad_suelo = int(humedad_suelo_str)
                    nivel_agua = int(nivel_agua_str)
                    lluvia_valor = int(lluvia_str)
                    lluvia_mm = float(lluvia_mm_str)
                    
                    datos_leidos.append([temp, hum, humedad_suelo, nivel_agua, lluvia_valor, lluvia_mm])
                except (ValueError, IndexError):
                    st.warning(f"Error al convertir los datos de la línea: {linea}. Ignorando esta muestra.")
                    continue

                barra_progreso.progress((i + 1) / 10)
        
        # Agrega los nuevos datos al DataFrame
        nuevos_datos_df = pd.DataFrame(datos_leidos, columns=columnas)
        data_df = pd.concat([data_df, nuevos_datos_df], ignore_index=True)
        
        st.dataframe(data_df) # Muestra los datos en una tabla de Streamlit
        
        # Crea el botón para descargar el CSV
        csv = data_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Descargar datos en CSV",
            data=csv,
            file_name='datos_sensores.csv',
            mime='text/csv',
        )
else:
    st.info("No hay conexión con Arduino. Por favor, revisa que esté conectado y el puerto sea el correcto.")