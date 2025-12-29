#include "esp_camera.h"
#include <WiFi.h>
#include "esp_http_server.h"
#include <HTTPClient.h>
#include <ArduinoJson.h> // JSON işlemleri için gerekli
#include "soc/soc.h"
#include "soc/rtc_cntl_reg.h"
#include "DHT.h" // Sıcaklık sensörü kütüphanesi

// ================= AYARLAR =================
const char *ssid = "HONOR 200 Pro";      // WiFi Adı
const char *password = "12345678";       // WiFi Şifresi
String serverBase = "http://10.220.172.170:5001"; // Sunucu adresi

// API Yolları
String uploadUrl = serverBase + "/api/sensor-upload";
String registerUrl = serverBase + "/api/register-device";

int CAMERA_ID = 0;              // Sunucudan alınacak ID
long lastSensorTime = 0;        // Son sensör okuma zamanı
const long sensorInterval = 10000; // 10 saniyede bir sensör verisi gönder

// --- DHT11 SENSÖR AYARLARI ---
#define DHT_PIN 14  // Sensörün bağlı olduğu pin (IO14)
#define DHTTYPE DHT11
DHT dht(DHT_PIN, DHTTYPE);

// --- KAMERA PIN TANIMLARI (AI-THINKER MODELİ) ---
#define PWDN_GPIO_NUM  32
#define RESET_GPIO_NUM -1
#define XCLK_GPIO_NUM  0
#define SIOD_GPIO_NUM  26
#define SIOC_GPIO_NUM  27
#define Y9_GPIO_NUM    35
#define Y8_GPIO_NUM    34
#define Y7_GPIO_NUM    39
#define Y6_GPIO_NUM    36
#define Y5_GPIO_NUM    21
#define Y4_GPIO_NUM    19
#define Y3_GPIO_NUM    18
#define Y2_GPIO_NUM    5
#define VSYNC_GPIO_NUM 25
#define HREF_GPIO_NUM  23
#define PCLK_GPIO_NUM  22
#define FLASH_LED_PIN  4

httpd_handle_t camera_httpd = NULL; // Web sunucusu nesnesi

// --- VİDEO AKIŞ (STREAM) BAŞLIKLARI ---
#define PART_BOUNDARY "123456789000000000000987654321"
static const char *_STREAM_CONTENT_TYPE = "multipart/x-mixed-replace;boundary=" PART_BOUNDARY;
static const char *_STREAM_BOUNDARY = "\r\n--" PART_BOUNDARY "\r\n";
static const char *_STREAM_PART = "Content-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n";

// --- SENSÖR VERİSİNİ OKU VE GÖNDER ---
void sendSensorData() {
  // Belirlenen süre (10sn) geçmediyse işlem yapma
  if (millis() - lastSensorTime < sensorInterval) return;
  lastSensorTime = millis();
  
  // Sıcaklık ve nemi oku
  float h = dht.readHumidity();
  float t = dht.readTemperature();

  // Okuma başarısız mı kontrol et
  if (isnan(h) || isnan(t)) {
    Serial.println("DHT Okuma Hatasi!");
    return;
  }
  
  // WiFi bağlıysa ve ID alınmışsa veriyi gönder
  if (WiFi.status() == WL_CONNECTED && CAMERA_ID != 0) {
    HTTPClient http;
    http.begin(uploadUrl); // Hedef adresi ayarla
    http.addHeader("Content-Type", "application/json");
    
    // JSON paketini hazırla
    DynamicJsonDocument sendDoc(512);
    sendDoc["camera_id"] = CAMERA_ID;
    sendDoc["temperature"] = t;
    sendDoc["humidity"] = h;
    
    String jsonOutput;
    serializeJson(sendDoc, jsonOutput); // JSON'u String'e çevir

    int httpResponseCode = http.POST(jsonOutput); // Gönder
    http.end(); // Bağlantıyı kapat
  }
}

// --- SUNUCUDAN ID AL (KAYIT OL) ---
void getCameraID() {
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(registerUrl);
    http.addHeader("Content-Type", "application/json");
    
    // MAC adresini JSON olarak paketle
    StaticJsonDocument<200> doc;
    doc["mac_address"] = WiFi.macAddress();
    String requestBody;
    serializeJson(doc, requestBody);
    
    // İsteği gönder ve cevabı bekle
    int httpResponseCode = http.POST(requestBody);
    if (httpResponseCode > 0) {
      String response = http.getString();
      StaticJsonDocument<200> resDoc;
      deserializeJson(resDoc, response);
      CAMERA_ID = resDoc["id"]; // Gelen ID'yi kaydet
      Serial.println("Kamera ID Alindi: " + String(CAMERA_ID));
    }
    http.end();
  }
}

// --- VİDEO AKIŞ (STREAM) YÖNETİCİSİ ---
static esp_err_t stream_handler(httpd_req_t *req) {
  camera_fb_t *fb = NULL;
  esp_err_t res = ESP_OK;
  char *part_buf[64];

  // Tarayıcıya "sürekli veri (video) geliyor" de
  res = httpd_resp_set_type(req, _STREAM_CONTENT_TYPE);
  if (res != ESP_OK) return res;

  while (true) {
    fb = esp_camera_fb_get(); // Kameradan bir kare al
    if (!fb) {
      res = ESP_FAIL;
    } else {
      // Kare boyutunu başlığa yaz
      size_t hlen = snprintf((char *)part_buf, 64, _STREAM_PART, fb->len);
      res = httpd_resp_send_chunk(req, (const char *)part_buf, hlen);
    }
    
    // Resim verisini gönder
    if (res == ESP_OK) res = httpd_resp_send_chunk(req, (const char *)fb->buf, fb->len);
    // Sınır çizgisini gönder (diğer kareye geçiş için)
    if (res == ESP_OK) res = httpd_resp_send_chunk(req, _STREAM_BOUNDARY, strlen(_STREAM_BOUNDARY));
    
    // Hafızayı temizle (önemli!)
    if (fb) {
      esp_camera_fb_return(fb);
      fb = NULL;
    }
    
    if (res != ESP_OK) break; // Bağlantı koptuysa döngüden çık
    delay(10); 
  }
  return res;
}

// --- TEK FOTOĞRAF ÇEKME YÖNETİCİSİ ---
static esp_err_t capture_handler(httpd_req_t *req) {
  camera_fb_t *fb = esp_camera_fb_get(); // Kare al
  if (!fb) {
    httpd_resp_send_500(req); // Hata varsa 500 kodu dön
    return ESP_FAIL;
  }
  
  // Resim formatında gönder
  httpd_resp_set_type(req, "image/jpeg");
  httpd_resp_set_hdr(req, "Content-Disposition", "inline; filename=capture.jpg");
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*"); // Her yerden erişime izin ver
  
  esp_err_t res = httpd_resp_send(req, (const char *)fb->buf, fb->len);
  esp_camera_fb_return(fb); // Hafızayı temizle
  return res;
}

// --- WEB SUNUCUSUNU BAŞLAT ---
void startCameraServer() {
  httpd_config_t config = HTTPD_DEFAULT_CONFIG();
  config.server_port = 80;

  // URL rotalarını tanımla (/capture ve /stream)
  httpd_uri_t capture_uri = {.uri="/capture", .method=HTTP_GET, .handler=capture_handler, .user_ctx=NULL};
  httpd_uri_t stream_uri = {.uri="/stream", .method=HTTP_GET, .handler=stream_handler, .user_ctx=NULL};

  // Sunucuyu başlat ve rotaları ekle
  if (httpd_start(&camera_httpd, &config) == ESP_OK) {
    httpd_register_uri_handler(camera_httpd, &capture_uri);
    httpd_register_uri_handler(camera_httpd, &stream_uri);
  }
}

// --- KURULUM (SETUP) ---
void setup() {
  // Voltaj düşüklüğü korumasını kapat (Reset atmaması için)
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0); 
  
  Serial.begin(115200);
  dht.begin(); // Sensörü başlat
  pinMode(FLASH_LED_PIN, OUTPUT); // Flash LED pini
  
  // Kamera ayarları yapılandırması
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 10000000;       // Saat hızı
  config.pixel_format = PIXFORMAT_JPEG; // Format JPEG
  
  // --- ÖNEMLİ: HIZ İÇİN DÜŞÜK KALİTE AYARLARI ---
  config.frame_size = FRAMESIZE_QVGA;   // 320x240 Çözünürlük
  config.jpeg_quality = 20;             // Kalite (10-63 arası, yüksek sayı = düşük kalite)
  config.fb_count = 1;                  // Tampon bellek sayısı
  
  // Kamerayı başlat
  esp_err_t cam_err = esp_camera_init(&config);
  if (cam_err != ESP_OK) {
    Serial.printf("Kamera Başlatılamadı! Hata: 0x%x", cam_err);
    while(1);
  }

  // WiFi bağlantısını başlat
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) { 
    delay(500); 
    Serial.print("."); 
  }
  
  getCameraID();       // Sunucudan ID iste
  startCameraServer(); // Web sunucusunu aç
  
  Serial.println("\nSistem Hazır! IP Adresi: " + WiFi.localIP().toString());
}

// --- ANA DÖNGÜ ---
void loop() {
  sendSensorData(); // Sensör kontrolü yap
  delay(10);        // İşlemciyi yormamak için minik bekleme
}