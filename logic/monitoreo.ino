// ====================================================================================
// Código unificado para sensores de humedad, nivel de agua y lluvia
// Fecha: Agosto 2025
// ====================================================================================

#include <Bonezegei_DHT11.h>

// Definición de pines para los sensores
const int SOIL_MOISTURE_PIN = A0;  // Sensor de humedad del suelo FC-28
const int WATER_LEVEL_PIN = A1;    // Sensor de nivel de agua
const int RAIN_SENSOR_PIN = A2;    // Sensor de lluvia, pin analógico
const int DHT_PIN = 2;             // Pin de señal para el DHT11

// Instancia del objeto para el sensor DHT11
Bonezegei_DHT11 dht(DHT_PIN);

void setup() {
  Serial.begin(9600);
  // Inicializar el sensor DHT11
  dht.begin();
  delay(100);
  Serial.println("Estación de monitoreo iniciada...");
  Serial.println("-------------------------------------");
}

void loop() {
  // 1. Lectura del sensor de humedad y temperatura DHT11
  if (dht.getData()) {
    float tempDeg = dht.getTemperature();
    int hum = dht.getHumidity();
    Serial.print("Temperatura: ");
    Serial.print(tempDeg);
    Serial.print("°C | Humedad ambiente: ");
    Serial.print(hum);
    Serial.println("%");
  } else {
    Serial.println("Error al leer datos del DHT11.");
  }

  // 2. Lectura del sensor de humedad del suelo FC-28
  int soilMoistureValue = analogRead(SOIL_MOISTURE_PIN);
  Serial.print("Humedad del suelo (valor): ");
  Serial.print(soilMoistureValue);
  Serial.print(" -> ");
  if (soilMoistureValue > 700) {
    Serial.println("¡Suelo muy seco! 🏜️");
  } else if (soilMoistureValue > 400) {
    Serial.println("Humedad baja. 💧");
  } else if (soilMoistureValue > 200) {
    Serial.println("Humedad óptima. 🌱");
  } else {
    Serial.println("¡Suelo muy húmedo! 🌊");
  }

  // 3. Lectura del sensor de nivel de agua
  int waterLevelValue = analogRead(WATER_LEVEL_PIN);
  Serial.print("Nivel de agua (valor): ");
  Serial.println(waterLevelValue);

  // 4. Lectura del sensor de lluvia
  int rainValue = analogRead(RAIN_SENSOR_PIN);
  Serial.print("Intensidad de lluvia (valor): ");
  Serial.print(rainValue);
  
  // Conversión del valor analógico a una aproximación en milímetros (mm)
  // Nota: Esto es una aproximación y requiere calibración.
  float rainMM = map(rainValue, 1023, 0, 0, 100); // Mapea el valor de 1023 (sin lluvia) a 0 mm y 0 (mucha lluvia) a 100 mm.
  if (rainMM > 0) {
    Serial.print(" -> Lluvia detectada: ");
    Serial.print(rainMM, 2); // Imprime el valor con 2 decimales
    Serial.println(" mm");
  } else {
    Serial.println(" -> Sin lluvia");
  }

  Serial.println("-------------------------------------");
  delay(3000); // Retardo de 3 segundos para una lectura estable
}