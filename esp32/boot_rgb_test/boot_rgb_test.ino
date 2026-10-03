#include <Arduino.h>

constexpr uint8_t BOOT_PIN = 0;
constexpr uint8_t RGB_LED_PIN = 48;

bool previousPressed = false;

void setup() {
  pinMode(BOOT_PIN, INPUT_PULLUP);
  previousPressed = digitalRead(BOOT_PIN) == LOW;
  neopixelWrite(RGB_LED_PIN, 0, 0, previousPressed ? 255 : 0);
}

void loop() {
  const bool pressed = digitalRead(BOOT_PIN) == LOW;
  if (pressed != previousPressed) {
    previousPressed = pressed;
    neopixelWrite(RGB_LED_PIN, 0, 0, pressed ? 255 : 0);
  }
  delay(5);
}
