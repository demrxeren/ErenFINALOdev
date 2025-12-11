#include "DHT.h"
#include <ArduinoJson.h>
#include <SoftwareSerial.h>

#define DHTTYPE DHT11

// ================================================================
// OTOMATİK TARAMA AYARLARI
// ================================================================
// Hangi pinler taranacak? (Pin 2'den Pin 9'a kadar tara)
const int START_PIN = 2; 
const int END_PIN = 9;

// Haberleşme Pinleri (ESP32'ye giden)
// Arduino Pin 11 (TX) ---> ESP32 GPIO 3 (RX)'e bağlanmalı
// Arduino Pin 10 (RX) ---> ESP32 GPIO 1 (TX)'e bağlanmalı
#define RX_PIN 10
#define TX_PIN 11 
// ================================================================

// Maksimum sensör sayısı
const int MAX_SENSORS = END_PIN - START_PIN + 1;

// Sensör nesneleri
DHT* dhtSensors[MAX_SENSORS];

SoftwareSerial espSerial(RX_PIN, TX_PIN); 

void setup() {
  Serial.begin(9600);
  espSerial.begin(9600);

  Serial.println("--- OTOMATIK PIN TARAMA MODU ---");
  Serial.println("Sensorleri sirasiyla Pin 2, Pin 3, Pin 4... seklinde takin.");

  // Sensörleri Başlat
  for (int i = 0; i < MAX_SENSORS; i++) {
    int currentPin = START_PIN + i;
    
    // Haberleşme pinlerini atla
    if (currentPin == RX_PIN || currentPin == TX_PIN) {
      dhtSensors[i] = NULL;
      continue;
    }

    dhtSensors[i] = new DHT(currentPin, DHTTYPE);
    dhtSensors[i]->begin();
  }
}

void loop() {
  delay(10000); // 3 Saniye bekle

  // Tüm pinleri kontrol et
  for (int i = 0; i < MAX_SENSORS; i++) {
    if (dhtSensors[i] == NULL) continue;

    int pinNumarasi = START_PIN + i;
    
    // Sensörü okumayı dene
    float h = dhtSensors[i]->readHumidity();
    float t = dhtSensors[i]->readTemperature();

    // Veri geçerliyse işlem yap
    if (!isnan(h) && !isnan(t)) {
      
      StaticJsonDocument<200> doc;
      
      // Pin numarasına göre ID hesapla (Pin 2 -> ID 1)
      int targetID = (pinNumarasi - START_PIN) + 1;
      
      doc["target_id"] = targetID;
      doc["temperature"] = t;
      doc["humidity"] = h;
      
      // ESP32'ye gönder
      serializeJson(doc, espSerial);
      espSerial.println(); 
      
      // Bilgisayar ekranına yaz (Artık Nemi de görüyoruz)
      Serial.print("[GONDERILDI] Pin ");
      Serial.print(pinNumarasi);
      Serial.print(" -> Hedef ID: ");
      Serial.print(targetID);
      Serial.print(" | Sicaklik: ");
      Serial.print(t);
      Serial.print(" | Nem: ");
      Serial.println(h);
      
      delay(500); // Paketler karışmasın
    }
  }
}