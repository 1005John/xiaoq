#include <WebServer.h>
#include <WiFi.h>
#include <ESPmDNS.h>

#include "secrets.h"

namespace {

WebServer server(80);
String currentColor = "green";
const char* REQUEST_HEADERS[] = {"X-XiaoQ-Token"};
bool mdnsStarted = false;
unsigned long lastWifiAttemptMs = 0;
constexpr unsigned long WIFI_RETRY_MS = 10000;

struct Rgb {
  uint8_t red;
  uint8_t green;
  uint8_t blue;
};

bool parseColor(const String& value, Rgb* rgb) {
  String color = value;
  color.toLowerCase();
  if (color == "red") { *rgb = {255, 0, 0}; return true; }
  if (color == "green") { *rgb = {0, 255, 0}; return true; }
  if (color == "blue") { *rgb = {0, 0, 255}; return true; }
  if (color == "white") { *rgb = {255, 255, 255}; return true; }
  if (color == "yellow") { *rgb = {255, 180, 0}; return true; }
  if (color == "purple") { *rgb = {180, 0, 255}; return true; }
  if (color == "off") { *rgb = {0, 0, 0}; return true; }
  return false;
}

void setColor(const String& value) {
  Rgb rgb{};
  if (!parseColor(value, &rgb)) {
    return;
  }
  neopixelWrite(RGB_LED_PIN, rgb.red, rgb.green, rgb.blue);
  currentColor = value;
  currentColor.toLowerCase();
}

bool authorized() {
  return server.header("X-XiaoQ-Token") == API_TOKEN;
}

void sendJson(int status, const String& body) {
  server.send(status, "application/json; charset=utf-8", body);
}

void handleStatus() {
  if (!authorized()) {
    sendJson(401, "{\"ok\":false,\"error\":\"unauthorized\"}");
    return;
  }
  sendJson(200, "{\"ok\":true,\"color\":\"" + currentColor + "\",\"ip\":\"" + WiFi.localIP().toString() + "\"}");
}

void handleSetColor() {
  if (!authorized()) {
    sendJson(401, "{\"ok\":false,\"error\":\"unauthorized\"}");
    return;
  }
  String color = server.arg("color");
  Rgb rgb{};
  if (!parseColor(color, &rgb)) {
    sendJson(400, "{\"ok\":false,\"error\":\"unsupported color\"}");
    return;
  }
  setColor(color);
  sendJson(200, "{\"ok\":true,\"color\":\"" + currentColor + "\"}");
}

void connectWifi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  lastWifiAttemptMs = millis();
  Serial.printf("Connecting to Wi-Fi %s\n", WIFI_SSID);
}

void updateWifi() {
  if (WiFi.status() == WL_CONNECTED) {
    if (!mdnsStarted) {
      Serial.printf("Wi-Fi connected: %s\n", WiFi.localIP().toString().c_str());
      mdnsStarted = MDNS.begin(MDNS_HOSTNAME);
      if (mdnsStarted) {
      MDNS.addService("http", "tcp", 80);
      }
    }
    return;
  }
  if (millis() - lastWifiAttemptMs >= WIFI_RETRY_MS) {
    WiFi.disconnect();
    connectWifi();
  }
}

}  // namespace

void setup() {
  Serial.begin(115200);
  setColor("green");
  connectWifi();
  server.collectHeaders(REQUEST_HEADERS, 1);
  server.on("/api/status", HTTP_GET, handleStatus);
  server.on("/api/led", HTTP_POST, handleSetColor);
  server.begin();
  Serial.println("XiaoQ LED controller ready");
}

void loop() {
  server.handleClient();
  updateWifi();
  delay(2);
}
