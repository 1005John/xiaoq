#include <Arduino.h>
#include <driver/i2s.h>

constexpr uint8_t BOOT_PIN = 0;
constexpr uint8_t RGB_LED_PIN = 48;
constexpr int MIC_BCLK_PIN = 4;
constexpr int MIC_WS_PIN = 5;
constexpr int MIC_DATA_PIN = 6;

void installMicrophone() {
  const i2s_config_t config = {
      .mode = static_cast<i2s_mode_t>(I2S_MODE_MASTER | I2S_MODE_RX),
      .sample_rate = 16000,
      .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,
      .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
      .communication_format = I2S_COMM_FORMAT_STAND_I2S,
      .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
      .dma_buf_count = 8,
      .dma_buf_len = 256,
      .use_apll = false,
      .tx_desc_auto_clear = false,
      .fixed_mclk = 0,
  };
  const i2s_pin_config_t pins = {
      .bck_io_num = MIC_BCLK_PIN,
      .ws_io_num = MIC_WS_PIN,
      .data_out_num = I2S_PIN_NO_CHANGE,
      .data_in_num = MIC_DATA_PIN,
  };
  ESP_ERROR_CHECK(i2s_driver_install(I2S_NUM_0, &config, 0, nullptr));
  ESP_ERROR_CHECK(i2s_set_pin(I2S_NUM_0, &pins));
}

void setup() {
  pinMode(BOOT_PIN, INPUT_PULLUP);
  installMicrophone();
  // I2S initialization changes GPIO0's pull configuration on this board.
  pinMode(BOOT_PIN, INPUT_PULLUP);
}

void loop() {
  const bool pressed = digitalRead(BOOT_PIN) == LOW;
  neopixelWrite(RGB_LED_PIN, 0, 0, pressed ? 255 : 0);
  delay(5);
}
