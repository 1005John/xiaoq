#include <BLEDevice.h>

namespace {
constexpr uint8_t RGB_LED_PIN = 48;
}

void setup() {
  Serial.begin(115200);
  BLEDevice::init("XiaoQ-BLE-Test");
  BLEAdvertising* advertising = BLEDevice::getAdvertising();
  advertising->setScanResponse(true);
  advertising->start();
  neopixelWrite(RGB_LED_PIN, 0, 255, 0);
}

void loop() {
  delay(1000);
}
