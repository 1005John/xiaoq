/*
 * XiaoQ ESP32-S3 audio I/O hardware test
 *
 * I2S microphone (INMP441): BCLK/SCK=GPIO4, LRCLK/WS=GPIO5, DATA=GPIO6
 * I2S speaker amp:            DIN=GPIO7, BCLK=GPIO15, LRCLK=GPIO16
 *
 * Commands at 115200 baud:
 *   tone   play the verification chime
 *   help   print this command list
 */

#include <Arduino.h>
#include <driver/i2s.h>
#include <math.h>

namespace {

constexpr i2s_port_t MIC_PORT = I2S_NUM_0;
constexpr i2s_port_t SPEAKER_PORT = I2S_NUM_1;
constexpr int MIC_BCLK_PIN = 4;
constexpr int MIC_WS_PIN = 5;
constexpr int MIC_DATA_PIN = 6;
constexpr int SPEAKER_DATA_PIN = 7;
constexpr int SPEAKER_BCLK_PIN = 15;
constexpr int SPEAKER_WS_PIN = 16;
constexpr int SAMPLE_RATE = 16000;
constexpr size_t MIC_SAMPLES = 256;

int32_t micBuffer[MIC_SAMPLES];
uint32_t lastMeterMs = 0;

void installMicrophone() {
  const i2s_config_t config = {
    .mode = static_cast<i2s_mode_t>(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = SAMPLE_RATE,
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
  ESP_ERROR_CHECK(i2s_driver_install(MIC_PORT, &config, 0, nullptr));
  ESP_ERROR_CHECK(i2s_set_pin(MIC_PORT, &pins));
  i2s_zero_dma_buffer(MIC_PORT);
}

void installSpeaker() {
  const i2s_config_t config = {
    .mode = static_cast<i2s_mode_t>(I2S_MODE_MASTER | I2S_MODE_TX),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_RIGHT_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 8,
    .dma_buf_len = 256,
    .use_apll = false,
    .tx_desc_auto_clear = true,
    .fixed_mclk = 0,
  };
  const i2s_pin_config_t pins = {
    .bck_io_num = SPEAKER_BCLK_PIN,
    .ws_io_num = SPEAKER_WS_PIN,
    .data_out_num = SPEAKER_DATA_PIN,
    .data_in_num = I2S_PIN_NO_CHANGE,
  };
  ESP_ERROR_CHECK(i2s_driver_install(SPEAKER_PORT, &config, 0, nullptr));
  ESP_ERROR_CHECK(i2s_set_pin(SPEAKER_PORT, &pins));
  i2s_zero_dma_buffer(SPEAKER_PORT);
}

void playChime() {
  Serial.println("[audio] speaker chime");
  constexpr int frequencies[] = {880, 1320};
  int16_t frames[256 * 2];
  for (int frequency : frequencies) {
    const int frameCount = SAMPLE_RATE / 5;
    for (int offset = 0; offset < frameCount; offset += 256) {
      const int count = min(256, frameCount - offset);
      for (int index = 0; index < count; ++index) {
        const float phase = 2.0f * PI * frequency * (offset + index) / SAMPLE_RATE;
        const int16_t sample = static_cast<int16_t>(sinf(phase) * 5000.0f);
        frames[index * 2] = sample;
        frames[index * 2 + 1] = sample;
      }
      size_t written = 0;
      i2s_write(SPEAKER_PORT, frames, count * sizeof(int16_t) * 2, &written, portMAX_DELAY);
    }
    delay(35);
  }
}

void reportMicrophoneLevel() {
  size_t bytesRead = 0;
  if (i2s_read(MIC_PORT, micBuffer, sizeof(micBuffer), &bytesRead, pdMS_TO_TICKS(100)) != ESP_OK || bytesRead == 0) {
    Serial.println("[audio] microphone read timeout");
    return;
  }
  const size_t count = bytesRead / sizeof(int32_t);
  double sumSquares = 0.0;
  int32_t peak = 0;
  for (size_t index = 0; index < count; ++index) {
    const int32_t sample = micBuffer[index] >> 8;
    const int32_t magnitude = abs(sample);
    peak = max(peak, magnitude);
    sumSquares += static_cast<double>(sample) * sample;
  }
  const uint32_t rms = static_cast<uint32_t>(sqrt(sumSquares / count));
  Serial.printf("[audio] mic samples=%u rms=%lu peak=%ld\n",
                static_cast<unsigned>(count), static_cast<unsigned long>(rms),
                static_cast<long>(peak));
}

void handleConsole() {
  if (!Serial.available()) return;
  const String command = Serial.readStringUntil('\n');
  if (command == "tone") {
    playChime();
  } else if (command == "help") {
    Serial.println("[audio] commands: tone, help");
  } else {
    Serial.println("[audio] unknown command; type help");
  }
}

}  // namespace

void setup() {
  Serial.begin(115200);
  delay(400);
  Serial.println("\n[xiaoq-audio] ESP32-S3 I2S audio test starting");
  Serial.printf("[audio] mic BCLK=%d WS=%d DATA=%d | speaker DIN=%d BCLK=%d WS=%d\n",
                MIC_BCLK_PIN, MIC_WS_PIN, MIC_DATA_PIN,
                SPEAKER_DATA_PIN, SPEAKER_BCLK_PIN, SPEAKER_WS_PIN);
  installMicrophone();
  installSpeaker();
  playChime();
  Serial.println("[audio] ready; speak near the board or type tone");
}

void loop() {
  handleConsole();
  if (millis() - lastMeterMs >= 500) {
    lastMeterMs = millis();
    reportMicrophoneLevel();
  }
}
