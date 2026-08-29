#include <Arduino.h>

constexpr uint8_t RGB_LED_PIN = 48;

void setup() {
  neopixelWrite(RGB_LED_PIN, 0, 0, 0);
}

void loop() {
  neopixelWrite(RGB_LED_PIN, 0, 0, 255);
  delay(2000);
  neopixelWrite(RGB_LED_PIN, 0, 0, 0);
  delay(2000);
}
