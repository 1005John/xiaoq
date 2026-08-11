#include <BLEDevice.h>
#include <BLEHIDDevice.h>
#include <BLESecurity.h>
#include <HIDTypes.h>

namespace {
constexpr uint8_t BOOT_PIN = 0;
constexpr uint8_t RGB_LED_PIN = 48;
constexpr uint32_t DEBOUNCE_MS = 35;
constexpr uint8_t REPORT_ID = 1;

const uint8_t REPORT_MAP[] = {
  USAGE_PAGE(1), 0x01, USAGE(1), 0x06, COLLECTION(1), 0x01,
  REPORT_ID(1), REPORT_ID,
  USAGE_PAGE(1), 0x07, USAGE_MINIMUM(1), 0xE0, USAGE_MAXIMUM(1), 0xE7,
  LOGICAL_MINIMUM(1), 0x00, LOGICAL_MAXIMUM(1), 0x01,
  REPORT_SIZE(1), 0x01, REPORT_COUNT(1), 0x08, HIDINPUT(1), 0x02,
  REPORT_COUNT(1), 0x01, REPORT_SIZE(1), 0x08, HIDINPUT(1), 0x01,
  REPORT_COUNT(1), 0x06, REPORT_SIZE(1), 0x08,
  LOGICAL_MINIMUM(1), 0x00, LOGICAL_MAXIMUM(1), 0x65,
  USAGE_PAGE(1), 0x07, USAGE_MINIMUM(1), 0x00, USAGE_MAXIMUM(1), 0x65,
  HIDINPUT(1), 0x00, END_COLLECTION(0)
};

struct KeyReport { uint8_t modifiers; uint8_t reserved; uint8_t keys[6]; };
bool connected = false;
BLECharacteristic* inputReport = nullptr;
bool stablePressed = false;
bool lastRawPressed = false;
uint32_t rawChangedAt = 0;

class ServerCallbacks final : public BLEServerCallbacks {
  void onConnect(BLEServer*) override { connected = true; }
  void onDisconnect(BLEServer*) override {
    connected = false;
    delay(100);
    BLEDevice::startAdvertising();
  }
};

class SecurityCallbacks final : public BLESecurityCallbacks {
  uint32_t onPassKeyRequest() override { return 0; }
  void onPassKeyNotify(uint32_t) override {}
  bool onSecurityRequest() override { return true; }
  void onAuthenticationComplete(esp_ble_auth_cmpl_t) override {}
  bool onConfirmPIN(uint32_t) override { return true; }
};

void setLed(bool active) { neopixelWrite(RGB_LED_PIN, 0, 0, active ? 255 : 0); }

void setSpace(bool down) {
  if (!connected || inputReport == nullptr) return;
  KeyReport report{};
  if (down) report.keys[0] = 0x2C;
  inputReport->setValue(reinterpret_cast<uint8_t*>(&report), sizeof(report));
  inputReport->notify();
}

void handleButton(bool down) {
  if (down == stablePressed) return;
  stablePressed = down;
  setLed(down);
  setSpace(down);
}
} // namespace

void setup() {
  Serial.begin(115200);
  pinMode(BOOT_PIN, INPUT_PULLUP);
  setLed(false);
  delay(250);
  lastRawPressed = digitalRead(BOOT_PIN) == LOW;
  stablePressed = lastRawPressed;

  BLEDevice::init("XiaoQ-PTT");
  BLEServer* server = BLEDevice::createServer();
  server->setCallbacks(new ServerCallbacks());
  BLEHIDDevice* hid = new BLEHIDDevice(server);
  inputReport = hid->inputReport(REPORT_ID);
  hid->manufacturer()->setValue("XiaoQ");
  hid->pnp(0x02, 0xE502, 0xA111, 0x0210);
  hid->hidInfo(0x00, 0x01);
  hid->reportMap(const_cast<uint8_t*>(REPORT_MAP), sizeof(REPORT_MAP));
  hid->startServices();
  hid->setBatteryLevel(100);

  BLESecurity* security = new BLESecurity();
  security->setAuthenticationMode(ESP_LE_AUTH_REQ_SC_MITM_BOND);
  security->setCapability(ESP_IO_CAP_IO);
  security->setInitEncryptionKey(ESP_BLE_ENC_KEY_MASK | ESP_BLE_ID_KEY_MASK);
  security->setRespEncryptionKey(ESP_BLE_ENC_KEY_MASK | ESP_BLE_ID_KEY_MASK);
  BLEDevice::setSecurityCallbacks(new SecurityCallbacks());

  BLEAdvertising* advertising = server->getAdvertising();
  advertising->setAppearance(0x03C1);
  advertising->addServiceUUID(hid->hidService()->getUUID());
  advertising->setScanResponse(false);
  advertising->start();
}

void loop() {
  const uint32_t now = millis();
  const bool down = digitalRead(BOOT_PIN) == LOW;
  if (down != lastRawPressed) { lastRawPressed = down; rawChangedAt = now; }
  if (now - rawChangedAt >= DEBOUNCE_MS) handleButton(down);
  delay(5);
}
