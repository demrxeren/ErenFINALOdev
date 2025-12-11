#include "esp_camera.h"
#include <WiFi.h>
#include "esp_http_server.h"
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include "soc/soc.h"
#include "soc/rtc_cntl_reg.h"

// ================= AYARLAR =================
const char* ssid = "HONOR 200 Pro";
const char* password = "12345678";
// IP adresinizi kontrol edin!
String serverBase = "https://conspiringly-desmotropic-tyisha.ngrok-free.dev/"; 

String uploadUrl = serverBase + "/api/sensor-upload";
String registerUrl = serverBase + "/api/register-device";
int CAMERA_ID = 0;

// Arduino İletişim Pinleri (ESP32-CAM için güvenli pinler)
// Arduino TX (Pin 11) -> ESP32 RX (GPIO 13)
// Arduino RX (Pin 10) -> ESP32 TX (GPIO 12)
#define RXD2 13
#define TXD2 12

// Kamera Pinleri
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM       5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22
#define FLASH_LED_PIN      4

httpd_handle_t camera_httpd = NULL;

// --- YARDIMCI FONKSİYON: Sensör Verisini Oku ve Gönder ---
// Bu fonksiyon SADECE loop() içinde çağrılacak
void handleSensorData() {
    if (Serial2.available()) {
        String data = Serial2.readStringUntil('\n');
        data.trim(); 
        
        if (data.length() > 0 && data.startsWith("{")) {
            DynamicJsonDocument doc(1024);
            DeserializationError error = deserializeJson(doc, data);
            
            if (!error) {
                int targetID = doc["target_id"];
                float temperature = doc["temperature"];
                float humidity = doc["humidity"];
                
                Serial.print("Arduino'dan Veri Alindi -> ID: ");
                Serial.print(targetID);
                Serial.print(", Sicaklik: ");
                Serial.print(temperature);
                Serial.print(", Nem: ");
                Serial.println(humidity);

                if(WiFi.status() == WL_CONNECTED){
                    HTTPClient http;
                    http.begin(uploadUrl);
                    http.addHeader("Content-Type", "application/json");
                    
                    // Backend için doğru JSON yapısı
                    DynamicJsonDocument sendDoc(512);
                    sendDoc["camera_id"] = targetID;
                    sendDoc["temperature"] = temperature;
                    sendDoc["humidity"] = humidity;
                    
                    String jsonOutput;
                    serializeJson(sendDoc, jsonOutput);
                    
                    Serial.println("Backend'e Gonderiliyor: " + jsonOutput);
                    
                    int httpResponseCode = http.POST(jsonOutput);
                    
                    if(httpResponseCode > 0) {
                        Serial.print("Backend Yaniti: ");
                        Serial.println(httpResponseCode);
                    } else {
                        Serial.print("Hata: ");
                        Serial.println(httpResponseCode);
                    }
                    
                    http.end();
                } else {
                    Serial.println("WiFi Bagli Degil!");
                }
            } else {
                Serial.println("JSON parse hatasi!");
            }
        }
    }
}

// --- STREAM (VIDEO) AYARLARI ---
#define PART_BOUNDARY "123456789000000000000987654321"
static const char* _STREAM_CONTENT_TYPE = "multipart/x-mixed-replace;boundary=" PART_BOUNDARY;
static const char* _STREAM_BOUNDARY = "\r\n--" PART_BOUNDARY "\r\n";
static const char* _STREAM_PART = "Content-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n";

static esp_err_t stream_handler(httpd_req_t *req) {
    camera_fb_t * fb = NULL;
    esp_err_t res = ESP_OK;
    size_t _jpg_buf_len = 0;
    uint8_t * _jpg_buf = NULL;
    char * part_buf[64];

    res = httpd_resp_set_type(req, _STREAM_CONTENT_TYPE);
    if(res != ESP_OK) return res;

    // Sonsuz video döngüsü
    while(true){
        
        // DÜZELTME: Buradaki handleSensorData() kaldırıldı!
        // Artık çakışma olmayacak.
        
        fb = esp_camera_fb_get();
        if (!fb) {
            Serial.println("Kamera hatasi");
            res = ESP_FAIL;
        } else {
            _jpg_buf_len = fb->len;
            _jpg_buf = fb->buf;
        }
        if(res == ESP_OK){
            size_t hlen = snprintf((char *)part_buf, 64, _STREAM_PART, _jpg_buf_len);
            res = httpd_resp_send_chunk(req, (const char *)part_buf, hlen);
        }
        if(res == ESP_OK){
            res = httpd_resp_send_chunk(req, (const char *)_jpg_buf, _jpg_buf_len);
        }
        if(res == ESP_OK){
            res = httpd_resp_send_chunk(req, _STREAM_BOUNDARY, strlen(_STREAM_BOUNDARY));
        }
        if(fb){
            esp_camera_fb_return(fb);
            fb = NULL;
            _jpg_buf = NULL;
        } else if(_jpg_buf){
            free(_jpg_buf);
            _jpg_buf = NULL;
        }
        if(res != ESP_OK) break;
        
        // DÜZELTME: İşlemciye nefes aldır (ÖNEMLİ)
        // Bu gecikme sırasında loop() fonksiyonu çalışır ve sensör verisini okur.
        delay(10); 
    }
    return res;
}

static esp_err_t capture_handler(httpd_req_t *req) {
    camera_fb_t * fb = esp_camera_fb_get();
    if (!fb) {
        httpd_resp_send_500(req);
        return ESP_FAIL;
    }
    httpd_resp_set_type(req, "image/jpeg");
    httpd_resp_set_hdr(req, "Content-Disposition", "inline; filename=capture.jpg");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
    esp_err_t res = httpd_resp_send(req, (const char *)fb->buf, fb->len);
    esp_camera_fb_return(fb);
    return res;
}

void startCameraServer() {
    httpd_config_t config = HTTPD_DEFAULT_CONFIG();
    config.server_port = 80;

    httpd_uri_t capture_uri = {
        .uri       = "/capture",
        .method    = HTTP_GET,
        .handler   = capture_handler,
        .user_ctx  = NULL
    };
    
    httpd_uri_t stream_uri = {
        .uri       = "/stream",
        .method    = HTTP_GET,
        .handler   = stream_handler,
        .user_ctx  = NULL
    };

    if (httpd_start(&camera_httpd, &config) == ESP_OK) {
        httpd_register_uri_handler(camera_httpd, &capture_uri);
        httpd_register_uri_handler(camera_httpd, &stream_uri);
    }
}

void getCameraID() {
  if(WiFi.status() == WL_CONNECTED) {
    Serial.println("\n--- KAMERA KAYIT ISLEMI ---");
    Serial.println("Backend URL: " + registerUrl);
    Serial.println("MAC Address: " + WiFi.macAddress());
    
    HTTPClient http;
    http.begin(registerUrl);
    http.addHeader("Content-Type", "application/json");
    
    StaticJsonDocument<200> doc;
    doc["mac_address"] = WiFi.macAddress();
    String requestBody;
    serializeJson(doc, requestBody);
    
    Serial.println("Gonderilen JSON: " + requestBody);
    
    int httpResponseCode = http.POST(requestBody);
    
    Serial.print("HTTP Yanit Kodu: ");
    Serial.println(httpResponseCode);
    
    if (httpResponseCode > 0) {
      String response = http.getString();
      Serial.println("Backend Yaniti: " + response);
      
      StaticJsonDocument<200> resDoc;
      DeserializationError error = deserializeJson(resDoc, response);
      
      if (!error) {
        CAMERA_ID = resDoc["id"];
        Serial.println("\n*** BASARILI! Kamera ID: " + String(CAMERA_ID) + " ***\n");
      } else {
        Serial.println("JSON Parse Hatasi!");
      }
    } else {
      Serial.println("HTTP HATA! Backend'e ulasilamiyor!");
      Serial.println("Lutfen Backend'in calisti[ini kontrol edin.");
    }
    http.end();
  } else {
    Serial.println("WiFi Bagli Degil!");
  }
}

void setup() {
    WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);
    Serial.begin(9600);  // USB Debug
    Serial2.begin(9600, SERIAL_8N1, RXD2, TXD2);  // Arduino İletişim
    
    Serial.println("ESP32-CAM Baslatiliyor...");
    Serial.println("Arduino verisi bekleniyor (GPIO 13 RX)");
    
    pinMode(FLASH_LED_PIN, OUTPUT);
    
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
    config.xclk_freq_hz = 20000000;
    config.pixel_format = PIXFORMAT_JPEG;
    
    if(psramFound()){
      config.frame_size = FRAMESIZE_VGA;
      config.jpeg_quality = 10;
      config.fb_count = 2;
    } else {
      config.frame_size = FRAMESIZE_SVGA;
      config.jpeg_quality = 12;
      config.fb_count = 1;
    }
    
    esp_camera_init(&config);

    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.println("\nWiFi Baglandi!");
    Serial.println("IP: " + WiFi.localIP().toString());

    getCameraID();
    startCameraServer();
    
    digitalWrite(FLASH_LED_PIN, HIGH);
    delay(200);
    digitalWrite(FLASH_LED_PIN, LOW);
    
    Serial.println("Sistem Hazir!");
}

void loop() {
    // Normal modda sensör verisi dinle
    // Video izlenirken de burası çalışır (çünkü stream_handler içinde delay(10) var)
    handleSensorData();
    delay(10);
}