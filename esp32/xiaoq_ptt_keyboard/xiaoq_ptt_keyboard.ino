// XiaoQ push-to-talk BLE keyboard for ESP32-S3.
// Hold BOOT to hold the space key; release BOOT to stop recording.
#include <ESP32BLECombo.h>

namespace {

constexpr uint8_t BOOT_PIN = 0;
constexpr uint8_t RGB_LED_PIN = 48;
constexpr uint32_t DEBOUNCE_MS = 35;
ESP32BLECombo bleKeyboard;
bool stablePressed = false;
bool lastRawPressed = false;
uint32_t rawChangedAt = 0;

void setPttLed(bool active) {
  neopixelWrite(RGB_LED_PIN, active ? 0 : 0, active ? 0 : 0, active ? 255 : 0);
}

void handleButton(bool pressed) {
  if (pressed == stablePressed) {
    return;
  }
  stablePressed = pressed;
  setPttLed(pressed);
  if (!bleKeyboard.isConnected()) {
    Serial.println(pressed ? "BOOT pressed (BLE not connected)" : "BOOT released");
    return;
  }
  if (pressed) {
    bleKeyboard.press(' ');
    Serial.println("PTT down: SPACE");
  } else {
    bleKeyboard.release(' ');
    Serial.println("PTT up: SPACE");
  }
}

}  // namespace

void setup() {
  Serial.begin(115200);
  pinMode(BOOT_PIN, INPUT_PULLUP);
  setPttLed(false);
  delay(250);  // Let GPIO0 settle after reset; do not hold BOOT during power-on.
  lastRawPressed = digitalRead(BOOT_PIN) == LOW;
  stablePressed = lastRawPressed;

  ESP32BLEComboConfig config;
  config.mode = ESP32BLEComboMode::KEYBOARD_ONLY;
  config.deviceName = "XiaoQ-PTT";
  config.manufacturer = "XiaoQ";
  config.batteryLevel = 100;
  config.appearance = ESP32BLEComboAppearance::KEYBOARD;
  config.enableSecurity = true;
  config.keyPressDelayMs = 8;
  config.keyReleaseDelayMs = 8;
  bleKeyboard.begin(config);
  Serial.println("XiaoQ PTT BLE keyboard ready: hold BOOT to talk");
}

void loop() {
  const uint32_t now = millis();
  const bool rawPressed = digitalRead(BOOT_PIN) == LOW;
  if (rawPressed != lastRawPressed) {
    lastRawPressed = rawPressed;
    rawChangedAt = now;
  }
  if (now - rawChangedAt >= DEBOUNCE_MS) {
    handleButton(rawPressed);
  }
  delay(5);
}
