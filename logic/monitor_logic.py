# logic/monitor_logic.py
import serial
import serial.tools.list_ports
import pandas as pd
import time
import threading
import uuid
from datetime import datetime
import os

from logic import db

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
        self.sesion_id = None

        # Frecuencia de muestreo / Intervalo mínimo de guardado histórico (segundos)
        # Default: 300 segundos (5 minutos) para entrenar Machine Learning sin saturar registros
        self.intervalo_guardado_segundos = 300
        self.ultimo_guardado_timestamp = 0.0

        # Cargar referencias
        self.dict_fases = self.cargar_datos_referencia()

        # Configuración actual del cultivo seleccionado
        self.config_cultivo_actual = None
        self.referencias_visuales = {}
        self.cultivo_actual = None
        self.etapa_actual = None

        # Ubicación geográfica asociada al monitoreo
        self.ubicacion_actual = {
            "estado": None, "municipio": None,
            "lat": None, "lon": None, "fuente": None,
        }

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
                    print(f"[OK] Cargado: {archivo}")
                else:
                    print(f"[AVISO] No encontrado: {ruta}")
            except Exception as e:
                print(f"[ERROR] Error leyendo {archivo}: {e}")
        
        return datos

    def set_ubicacion(self, resultado_geocode: dict, fuente="geolocation"):
        """Guarda la ubicación ya resuelta (ver logic/reverse_geocode.py).
        La llamada de red vive en la ruta Flask, no aquí."""
        self.ubicacion_actual = {
            "estado": resultado_geocode.get("estado"),
            "municipio": resultado_geocode.get("municipio"),
            "lat": resultado_geocode.get("lat"),
            "lon": resultado_geocode.get("lon"),
            "fuente": fuente if resultado_geocode.get("estado") else None,
        }

    def set_configuracion_cultivo(self, etapa_id, nombre_cultivo):
        """Busca los límites en los CSV cargados para el cultivo seleccionado"""
        self.cultivo_actual = nombre_cultivo
        self.etapa_actual = etapa_id
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
        print(f"[AVISO] No se encontró configuración para {nombre_cultivo} en etapa {etapa_id}")
        return False

    def conectar(self, puerto=None, intervalo_guardado=None, duracion_minutos=5):
        if intervalo_guardado:
            try:
                self.intervalo_guardado_segundos = max(5, int(intervalo_guardado))
            except (ValueError, TypeError):
                pass

        if self.ser and self.ser.is_open:
            return True

        puerto_objetivo = puerto or detectar_arduino()
        if not puerto_objetivo:
            print("[INFO] No se encontró ningún dispositivo serial conectado.")
            return False

        try:
            self.ser = serial.Serial(puerto_objetivo, self.baud_rate, timeout=2)
            self.puerto_detectado = puerto_objetivo
            
            ahora_dt = datetime.now()
            self.sesion_id = f"SES-{ahora_dt.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
            self.sesion_actual = {
                "id": self.sesion_id,
                "sesion_id": self.sesion_id,
                "fecha": ahora_dt.strftime("%Y-%m-%d"),
                "fecha_inicio": ahora_dt.strftime("%Y-%m-%d"),
                "hora_inicio": ahora_dt.strftime("%H:%M:%S"),
                "timestamp_inicio": ahora_dt.isoformat(),
                "fecha_fin": None,
                "hora_fin": None,
                "duracion_programada_minutos": int(duracion_minutos) if duracion_minutos else 5,
                "cultivo": self.cultivo_actual,
                "etapa": self.etapa_actual,
                "estado": self.ubicacion_actual.get("estado") or "Local",
                "municipio": self.ubicacion_actual.get("municipio") or "General",
                "lat": self.ubicacion_actual.get("lat"),
                "lon": self.ubicacion_actual.get("lon"),
                "fuente_ubicacion": self.ubicacion_actual.get("fuente") or "hardware",
                "estado_sesion": "EN_PROGRESO",
                "total_muestras": 0,
                "muestras": []
            }
            db.guardar_o_actualizar_sesion(self.sesion_actual)

            self.ultimo_guardado_timestamp = 0.0
            time.sleep(2)
            self.running = True
            self.datos_historial = []
            self.hilo = threading.Thread(target=self._leer_datos_loop, daemon=True)
            self.hilo.start()
            print(f"[OK] Conectado a {puerto_objetivo} (Sesión: {self.sesion_id} | Duración: {duracion_minutos} min)")
            return True
        except serial.SerialException as e:
            print(f"[ERROR] Error conexión serial en {puerto_objetivo}: {e}")
            self.puerto_detectado = None
            return False

    def desconectar(self):
        self.running = False
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.ser = None
        if hasattr(self, 'sesion_actual') and self.sesion_actual:
            self.sesion_actual["fecha_fin"] = datetime.now().strftime("%Y-%m-%d")
            self.sesion_actual["hora_fin"] = datetime.now().strftime("%H:%M:%S")
            self.sesion_actual["estado_sesion"] = "COMPLETADA"
            db.guardar_o_actualizar_sesion(self.sesion_actual)
        print("[INFO] Desconectado - Sesión finalizada y guardada")

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

                        # Agregar muestra a la sesión activa agrupada
                        if hasattr(self, 'sesion_actual') and self.sesion_actual is not None:
                            self.sesion_actual["muestras"].append(dato_procesado)
                            db.guardar_o_actualizar_sesion(self.sesion_actual)

                        # Guardado histórico con frecuencia de muestreo controlada
                        ahora = time.time()
                        if (ahora - self.ultimo_guardado_timestamp) >= self.intervalo_guardado_segundos or self.ultimo_guardado_timestamp == 0.0:
                            self._guardar_en_mongo(dato_procesado)
                            self._guardar_local(dato_procesado)
                            self.ultimo_guardado_timestamp = ahora
                time.sleep(1)
            except Exception as e:
                print(f"Error loop: {e}")
                self.running = False

    def _guardar_en_mongo(self, dato_procesado):
        """Persiste la lectura en MongoDB (entorno de producción)."""
        try:
            doc = dict(dato_procesado)
            try:
                doc["mes"] = datetime.strptime(doc["fecha"], "%Y-%m-%d").month
            except (KeyError, ValueError):
                doc["mes"] = None
            doc["cultivo"] = self.cultivo_actual
            doc["etapa"] = self.etapa_actual
            doc["estado"] = self.ubicacion_actual.get("estado")
            doc["municipio"] = self.ubicacion_actual.get("municipio")
            doc["lat"] = self.ubicacion_actual.get("lat")
            doc["lon"] = self.ubicacion_actual.get("lon")
            doc["fuente_ubicacion"] = self.ubicacion_actual.get("fuente")
            doc["sesion_id"] = self.sesion_id
            doc["origen"] = "arduino"
            db.guardar_lectura(doc)
        except Exception as e:
            print(f"[Mongo] Error preparando lectura para guardar: {e}")

    def _guardar_local(self, dato_procesado):
        """Persiste la lectura localmente sin conexión a la nube para testing y ML."""
        try:
            doc = dict(dato_procesado)
            try:
                doc["mes"] = datetime.strptime(doc["fecha"], "%Y-%m-%d").month
            except (KeyError, ValueError):
                doc["mes"] = None
            doc["cultivo"] = self.cultivo_actual
            doc["etapa"] = self.etapa_actual
            doc["estado"] = self.ubicacion_actual.get("estado") or "Local"
            doc["municipio"] = self.ubicacion_actual.get("municipio") or "Testing"
            doc["lat"] = self.ubicacion_actual.get("lat")
            doc["lon"] = self.ubicacion_actual.get("lon")
            doc["fuente_ubicacion"] = self.ubicacion_actual.get("fuente") or "local_test"
            doc["sesion_id"] = self.sesion_id or "local-session"
            doc["origen"] = "hardware_local"
            db.guardar_lectura_local(doc)
        except Exception as e:
            print(f"[LocalDB] Error guardando lectura local: {e}")

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

    def local(self, puerto=None, etapa="1", cultivo="Tomate", estado="Local", municipio="Testing", simular=False, datos_muestra=None, intervalo_guardado=None, duracion_minutos=5):
        """
        Función para entorno de pruebas/testing local.
        Permite leer datos desde hardware sin conexión a la nube, almacenándolos
        en un registro unificado de sesión para alimentar el modelo de Machine Learning.
        """
        if intervalo_guardado:
            try:
                self.intervalo_guardado_segundos = max(5, int(intervalo_guardado))
            except (ValueError, TypeError):
                pass

        self.set_configuracion_cultivo(etapa, cultivo)
        self.set_ubicacion({
            "estado": estado,
            "municipio": municipio,
            "lat": None,
            "lon": None
        }, fuente="testing_local")

        if simular or datos_muestra:
            if datos_muestra and isinstance(datos_muestra, dict):
                temp = float(datos_muestra.get("temp", datos_muestra.get("temperatura", 24.0)))
                hum_amb = float(datos_muestra.get("hum_amb", datos_muestra.get("humedad_ambiente", 60.0)))
                suelo_raw = int(datos_muestra.get("suelo_raw", 450))
                lluvia_raw = int(datos_muestra.get("lluvia_raw", datos_muestra.get("precipitacion_raw", 850)))
            else:
                temp, hum_amb, suelo_raw, lluvia_raw = 23.5, 62.0, 460, 850

            raw_str = f"{lluvia_raw},{suelo_raw},{hum_amb},{temp}".encode('utf-8')
            procesado = self.procesar_linea(raw_str)
            if procesado:
                self.ultima_lectura = procesado
                self.datos_historial.append(procesado)
                self._guardar_local(procesado)

                ahora_dt = datetime.now()
                sesion_test = {
                    "id": f"SES-TEST-{ahora_dt.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}",
                    "sesion_id": f"SES-TEST-{ahora_dt.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}",
                    "fecha": ahora_dt.strftime("%Y-%m-%d"),
                    "fecha_inicio": ahora_dt.strftime("%Y-%m-%d"),
                    "hora_inicio": ahora_dt.strftime("%H:%M:%S"),
                    "timestamp_inicio": ahora_dt.isoformat(),
                    "fecha_fin": ahora_dt.strftime("%Y-%m-%d"),
                    "hora_fin": ahora_dt.strftime("%H:%M:%S"),
                    "duracion_programada_minutos": int(duracion_minutos) if duracion_minutos else 5,
                    "cultivo": cultivo,
                    "etapa": etapa,
                    "estado": estado,
                    "municipio": municipio,
                    "lat": self.ubicacion_actual.get("lat"),
                    "lon": self.ubicacion_actual.get("lon"),
                    "fuente_ubicacion": "local_test",
                    "estado_sesion": "COMPLETADA",
                    "total_muestras": 1,
                    "muestras": [procesado]
                }
                db.guardar_o_actualizar_sesion(sesion_test)

                return {
                    "status": "ok",
                    "modo": "local_test_simulado",
                    "cultivo": cultivo,
                    "etapa": etapa,
                    "estado": estado,
                    "municipio": municipio,
                    "duracion_programada_minutos": int(duracion_minutos) if duracion_minutos else 5,
                    "intervalo_guardado_segundos": self.intervalo_guardado_segundos,
                    "lectura": procesado,
                    "sesion": sesion_test,
                    "total_historial": len(self.datos_historial)
                }

        exito = self.conectar(puerto=puerto, intervalo_guardado=intervalo_guardado, duracion_minutos=duracion_minutos)
        if exito:
            return {
                "status": "ok",
                "modo": "local_hardware",
                "puerto": self.puerto_detectado,
                "sesion_id": self.sesion_id,
                "cultivo": cultivo,
                "etapa": etapa,
                "estado": estado,
                "municipio": municipio,
                "duracion_programada_minutos": int(duracion_minutos) if duracion_minutos else 5,
                "intervalo_guardado_segundos": self.intervalo_guardado_segundos,
                "msg": f"Lectura de hardware local iniciada correctamente en {estado}, {municipio}."
            }
        else:
            puertos_disp = listar_puertos_seriales()
            return {
                "status": "error",
                "modo": "local_hardware",
                "msg": "No se pudo conectar al hardware serial.",
                "puertos_disponibles": puertos_disp
            }


monitor_service = MonitorSiembra()


def local(puerto=None, etapa="1", cultivo="Tomate", estado="Local", municipio="Testing", simular=False, datos_muestra=None, intervalo_guardado=None):
    """Función de nivel de módulo para pruebas locales de Siembra Link."""
    return monitor_service.local(
        puerto=puerto,
        etapa=etapa,
        cultivo=cultivo,
        estado=estado,
        municipio=municipio,
        simular=simular,
        datos_muestra=datos_muestra,
        intervalo_guardado=intervalo_guardado
    )