# logic/monitor_logic.py
import serial
import serial.tools.list_ports
import pandas as pd
import time
import threading
from datetime import datetime
import os

# VIDs de chips USB-Serial usados frecuentemente en Arduino y clones
_ARDUINO_VIDS = {0x2341, 0x1A86, 0x0403, 0x10C4, 0x2A03, 0x0483, 0x1EAF}
_ARDUINO_KEYWORDS = ('arduino', 'ch340', 'ch341', 'ftdi', 'cp210', 'usb serial', 'usb-serial')

def listar_puertos_seriales():
    """Devuelve lista de dicts con info de cada puerto disponible."""
    result = []
    for p in serial.tools.list_ports.comports():
        result.append({
            "puerto": p.device,
            "descripcion": p.description or "Puerto Serie",
            "es_arduino": (
                (p.vid in _ARDUINO_VIDS if p.vid else False) or
                any(kw in (p.description or '').lower() for kw in _ARDUINO_KEYWORDS)
            )
        })
    return result

def detectar_arduino():
    """Retorna el puerto más probable para un Arduino, o None si no hay ninguno."""
    puertos = listar_puertos_seriales()
    # Prioridad 1: coincidencia explícita de VID/descripción
    for p in puertos:
        if p["es_arduino"]:
            return p["puerto"]
    # Prioridad 2: cualquier puerto disponible
    if puertos:
        return puertos[0]["puerto"]
    return None


class MonitorSiembra:
    def __init__(self):
        self.baud_rate = 9600
        self.ser = None
        self.running = False
        self.hilo = None
        self.datos_historial = []
        self.ultima_lectura = {}
        self.puerto_detectado = None

        # Cargar referencias
        self.dict_fases = self.cargar_datos_referencia()

        # Configuración actual del cultivo seleccionado
        self.config_cultivo_actual = None
        self.referencias_visuales = {}

    def cargar_datos_referencia(self):
        """
        Carga los CSVs de referencia. Se asegura de usar rutas absolutas o relativas correctas.
        """
        datos = {}
        # Mapeo de IDs de etapa a nombres de archivo
        archivos = {
            "1": "Germinacion_procesado.csv",
            "2": "Floracion_procesado.csv",
            "3": "Maduracion_procesado.csv"
        }
        
        base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "fase_cultivo")

        for k, archivo in archivos.items():
            try:
                ruta = os.path.join(base_dir, archivo)
                if not os.path.exists(ruta):
                    ruta = archivo # Intento en raíz
                
                if os.path.exists(ruta):
                    datos[k] = pd.read_csv(ruta)
                    print(f"✅ Cargado: {archivo}")
                else:
                    print(f"⚠️ No encontrado: {ruta}")
            except Exception as e:
                print(f"❌ Error leyendo {archivo}: {e}")
        
        return datos

    def set_configuracion_cultivo(self, etapa_id, nombre_cultivo):
        """Busca los límites en los CSV cargados para el cultivo seleccionado"""
        if etapa_id in self.dict_fases:
            df = self.dict_fases[etapa_id]
            filtro = df[df['Cultivo'] == nombre_cultivo]
            if not filtro.empty:
                row = filtro.iloc[0]
                self.config_cultivo_actual = row.to_dict()
                
                # --- CORRECCIÓN JSON SERIALIZABLE ---
                # Convertimos explícitamente a float() porque Pandas usa tipos numpy.int64 
                # que hacen fallar a Flask/JSON.
                
                # 1. Temperatura
                val_t_min = row.get('Temp. Opt. Mín. (°C)', row.get('Temp. Recomendada (°C)_valor_mínimo', 15))
                val_t_max = row.get('Temp. Opt. Máx. (°C)', row.get('Temp. Recomendada (°C)_valor_máximo', 30))
                val_t_avg = row.get('Temp. Opt. Promedio (°C)', row.get('Temp. Recomendada (°C)_valor_promedio', (val_t_min + val_t_max) / 2))
                
                t_min = float(val_t_min)
                t_max = float(val_t_max)
                t_avg = float(val_t_avg)

                # 2. Humedad Ambiental
                val_h_min = row.get('Humedad Ambiental (%)_valor_mínimo', 40)
                val_h_max = row.get('Humedad Ambiental (%)_valor_máximo', 80)
                val_h_avg = row.get('Humedad Ambiental (%)_valor_promedio', (val_h_min + val_h_max) / 2)

                h_min = float(val_h_min)
                h_max = float(val_h_max)
                h_avg = float(val_h_avg)

                # 3. Humedad Suelo
                val_s_min = row.get('Humedad Suelo (%)_valor_mínimo', 40)
                val_s_max = row.get('Humedad Suelo (%)_valor_máximo', 90)
                val_s_avg = row.get('Humedad Suelo (%)_valor_promedio', (val_s_min + val_s_max) / 2)

                s_min = float(val_s_min)
                s_max = float(val_s_max)
                s_avg = float(val_s_avg)

                self.referencias_visuales = {
                    "temp": { "min": t_min, "max": t_max, "avg": t_avg },
                    "hum_amb": { "min": h_min, "max": h_max, "avg": h_avg },
                    "hum_suelo": { "min": s_min, "max": s_max, "avg": s_avg }
                }
                return True
        print(f"⚠️ No se encontró configuración para {nombre_cultivo} en etapa {etapa_id}")
        return False

    def conectar(self, puerto=None):
        if self.ser and self.ser.is_open:
            return True

        puerto_objetivo = puerto or detectar_arduino()
        if not puerto_objetivo:
            print("❌ No se encontró ningún dispositivo serial conectado.")
            return False

        try:
            self.ser = serial.Serial(puerto_objetivo, self.baud_rate, timeout=2)
            self.puerto_detectado = puerto_objetivo
            time.sleep(2)
            self.running = True
            self.datos_historial = []
            self.hilo = threading.Thread(target=self._leer_datos_loop, daemon=True)
            self.hilo.start()
            print(f"✅ Conectado a {puerto_objetivo}")
            return True
        except serial.SerialException as e:
            print(f"❌ Error conexión serial en {puerto_objetivo}: {e}")
            self.puerto_detectado = None
            return False

    def desconectar(self):
        self.running = False
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.ser = None
        print("🔌 Desconectado")

    def _leer_datos_loop(self):
        while self.running and self.ser and self.ser.is_open:
            try:
                if self.ser.in_waiting > 0:
                    linea = self.ser.readline()
                    # Si necesitas depurar, descomenta la siguiente línea:
                    # print(f"Raw: {linea}")
                    dato_procesado = self.procesar_linea(linea)
                    if dato_procesado:
                        self.ultima_lectura = dato_procesado
                        self.datos_historial.append(dato_procesado)
                        if len(self.datos_historial) > 100:
                            self.datos_historial.pop(0)
                time.sleep(1)
            except Exception as e:
                print(f"Error loop: {e}")
                self.running = False

    def procesar_linea(self, linea):
        try:
            datos_raw = linea.decode('utf-8').strip().split(',')
            if len(datos_raw) != 4: return None

            lluvia_raw = int(datos_raw[0])
            suelo_raw = int(datos_raw[1])
            hum_amb = float(datos_raw[2])
            temp = float(datos_raw[3])

            # Calibración
            max_h, min_h = 670.0, 300.0
            hum_suelo_pct = 100 - (((suelo_raw - min_h) / (max_h - min_h)) * 100)
            hum_suelo_pct = max(0, min(100, hum_suelo_pct))

            # Alertas
            alertas = []
            st_temp, st_suelo, st_hum = "OK", "OK", "OK"
            
            refs = self.referencias_visuales
            
            if refs:
                # Temp
                if temp > refs['temp']['max']:
                    alertas.append(f"🌡️ Alta ({temp}°)")
                    st_temp = "ALTA"
                elif temp < refs['temp']['min']:
                    alertas.append(f"🌡️ Baja ({temp}°)")
                    st_temp = "BAJA"

                # Suelo
                if hum_suelo_pct > refs['hum_suelo']['max']:
                    alertas.append(f"💦 Suelo Exc.")
                    st_suelo = "ALTA"
                elif hum_suelo_pct < refs['hum_suelo']['min']:
                    alertas.append(f"🏜️ Suelo Seco")
                    st_suelo = "BAJA"

                # Hum Amb
                if hum_amb > refs['hum_amb']['max']: st_hum = "ALTA"
                elif hum_amb < refs['hum_amb']['min']: st_hum = "BAJA"

            nivel_alerta = "🟢 CONDICIONES ÓPTIMAS" if not alertas else "⚠️ " + " | ".join(alertas)

            return {
                "fecha": datetime.now().strftime("%Y-%m-%d"),
                "hora": datetime.now().strftime("%H:%M:%S"),
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "temperatura": temp,
                "humedad_ambiente": hum_amb,
                "humedad_suelo_pct": round(hum_suelo_pct, 2),
                "precipitacion_raw": lluvia_raw,
                "nivel_alerta": nivel_alerta,
                "status_temp": st_temp,
                "status_suelo": st_suelo,
                "status_hum": st_hum
            }
        except ValueError:
            return None

monitor_service = MonitorSiembra()