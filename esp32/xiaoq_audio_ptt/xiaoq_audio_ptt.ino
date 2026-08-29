/*
 * XiaoQ Wi-Fi push-to-talk remote for ESP32-S3.
 *
 * Hold BOOT: INMP441 records at 16 kHz and the RGB LED is blue.
 * Release BOOT: recording stops, RGB turns off, WAV is uploaded to XiaoQ.
 * XiaoQ's /api/voice endpoint transcribes and injects the text into the
 * existing assistant pipeline. The reply is synthesized as PCM and played
 * through the I2S speaker attached to this ESP32.
 *
 * Mic: SCK/BCLK=4, WS/LRCLK=5, SD=6.  RGB LED: GPIO48.
 * Speaker: DIN=7, BCLK=15, LRCLK=16.
 *
 * Serial commands (115200):
 *   token <mobile-control-token>   persist the XiaoQ API token in NVS
 *   status                         show Wi-Fi/configuration state
 *   clear-token                    erase the stored API token
 *   gpio scan                      print the current level of safe GPIOs
 *   gpio watch                     print GPIO changes for 20 seconds
 */

#include <Arduino.h>
#include <Preferences.h>
#include <WiFi.h>
#include <driver/i2s.h>
#include <esp_system.h>

#include "secrets.h"

// This board's left USB-C "COM" connector is a CH340 bridge wired to UART0.
// Use it for diagnostics when the right USB-C connector is dedicated to power.
#define Serial Serial0

namespace {

constexpr uint8_t BOOT_PIN = 0;
constexpr uint8_t RGB_LED_PIN = 48;
constexpr int MIC_BCLK_PIN = 4;
constexpr int MIC_WS_PIN = 5;
constexpr int MIC_DATA_PIN = 6;
constexpr i2s_port_t MIC_PORT = I2S_NUM_0;
constexpr i2s_port_t SPEAKER_PORT = I2S_NUM_1;
constexpr int SPEAKER_DATA_PIN = 7;
constexpr int SPEAKER_BCLK_PIN = 15;
constexpr int SPEAKER_WS_PIN = 16;
// Keep the same rate as the proven xiaoq_audio_io speaker test. The gateway
// resamples MiMo's 24 kHz PCM before ESP32 downloads it.
constexpr uint32_t SPEAKER_SAMPLE_RATE = 16000;
constexpr uint32_t SAMPLE_RATE = 16000;
constexpr uint16_t BITS_PER_SAMPLE = 32;
constexpr uint8_t CHANNELS = 1;
constexpr uint32_t MAX_RECORD_SECONDS = 25;
constexpr size_t MAX_RECORD_BYTES = SAMPLE_RATE * (BITS_PER_SAMPLE / 8) * MAX_RECORD_SECONDS;
constexpr uint32_t DEBOUNCE_MS = 35;
constexpr uint32_t WIFI_RETRY_MS = 10000;
constexpr uint32_t MIN_RECORD_BYTES = SAMPLE_RATE * (BITS_PER_SAMPLE / 8) / 3;
constexpr size_t SPEAKER_FRAMES_PER_WRITE = 512;
constexpr size_t MAX_REPLY_AUDIO_BYTES = 2 * 1024 * 1024;
// The speaker amp shares USB power with Wi-Fi on this compact board. MiMo PCM
// can peak near full-scale, so leave headroom to avoid a brownout at playback.
constexpr uint8_t SPEAKER_VOLUME_PERCENT = 75;

Preferences preferences;
uint8_t* recordingBuffer = nullptr;
size_t recordedBytes = 0;
bool recording = false;
bool stablePressed = false;
bool lastRawPressed = false;
bool playing = false;
volatile bool voiceJobActive = false;
bool speakerInstalled = false;
uint32_t rawChangedAt = 0;
uint32_t lastWifiAttemptMs = 0;
String apiToken;

// Keep these buffers out of the Arduino loop/FreeRTOS task stacks. Reply
// playback already needs Wi-Fi and HTTP objects; putting this 3 KiB expansion
// buffer on that stack can reset an ESP32-S3 as soon as I2S begins playing.
int16_t speakerMono[SPEAKER_FRAMES_PER_WRITE];
int16_t speakerStereo[SPEAKER_FRAMES_PER_WRITE * 2];
uint8_t ledRed = 255;
uint8_t ledGreen = 255;
uint8_t ledBlue = 255;

void setLed(uint8_t red, uint8_t green, uint8_t blue) {
  if (red == ledRed && green == ledGreen && blue == ledBlue) {
    return;
  }
  neopixelWrite(RGB_LED_PIN, red, green, blue);
  ledRed = red;
  ledGreen = green;
  ledBlue = blue;
}

void updateLed() {
  if (stablePressed) {
    setLed(0, 0, 255);
  } else if (WiFi.status() == WL_CONNECTED) {
    setLed(0, 255, 0);
  } else {
    setLed(0, 0, 0);
  }
}

void configureBootButton() {
  // I2S setup can leave GPIO0's pull state behind on this S3 board. The
  // microphone-only diagnostic proved that reapplying pinMode is sufficient;
  // direct gpio_* calls disturb the Arduino GPIO matrix on this core.
  pinMode(BOOT_PIN, INPUT_PULLUP);
}

void connectWifi() {
  WiFi.mode(WIFI_STA);
  // CMCC-IOT is an open network. Use the SSID-only overload to avoid an
  // empty password being interpreted as WPA credentials by the ESP32-S3.
  if (strlen(WIFI_PASSWORD) == 0) {
    WiFi.begin(WIFI_SSID);
  } else {
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  }
  lastWifiAttemptMs = millis();
  Serial.printf("[ptt] connecting to Wi-Fi %s\n", WIFI_SSID);
}

void updateWifi() {
  if (WiFi.status() == WL_CONNECTED) {
    updateLed();
    return;
  }
  if (millis() - lastWifiAttemptMs >= WIFI_RETRY_MS) {
    WiFi.disconnect();
    connectWifi();
  }
  updateLed();
}

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
    .sample_rate = SPEAKER_SAMPLE_RATE,
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

void ensureSpeaker() {
  if (speakerInstalled) {
    return;
  }
  Serial.println("[ptt] installing I2S speaker");
  installSpeaker();
  speakerInstalled = true;
  // Speaker I2S setup can also alter GPIO0's pull mode on this board.
  configureBootButton();
  Serial.println("[ptt] I2S speaker ready");
}

bool writeSpeakerFrames(size_t frameCount) {
  const size_t byteCount = frameCount * sizeof(int16_t) * 2;
  const uint8_t* bytes = reinterpret_cast<const uint8_t*>(speakerStereo);
  size_t sent = 0;
  while (sent < byteCount) {
    size_t written = 0;
    const esp_err_t result = i2s_write(
        SPEAKER_PORT, bytes + sent, byteCount - sent, &written, pdMS_TO_TICKS(1000));
    if (result != ESP_OK || written == 0) {
      Serial.printf("[ptt] I2S write failed: result=%d written=%u/%u\n",
                    static_cast<int>(result), static_cast<unsigned>(written),
                    static_cast<unsigned>(byteCount - sent));
      return false;
    }
    sent += written;
  }
  return true;
}

int16_t speakerSample(int16_t sample) {
  return static_cast<int16_t>(
      (static_cast<int32_t>(sample) * SPEAKER_VOLUME_PERCENT) / 100);
}

void writeLe16(uint8_t* target, uint16_t value) {
  target[0] = value & 0xff;
  target[1] = (value >> 8) & 0xff;
}

void writeLe32(uint8_t* target, uint32_t value) {
  target[0] = value & 0xff;
  target[1] = (value >> 8) & 0xff;
  target[2] = (value >> 16) & 0xff;
  target[3] = (value >> 24) & 0xff;
}

void makeWavHeader(uint8_t (&header)[44], size_t pcmBytes) {
  memcpy(header, "RIFF", 4);
  writeLe32(header + 4, static_cast<uint32_t>(36 + pcmBytes));
  memcpy(header + 8, "WAVEfmt ", 8);
  writeLe32(header + 16, 16);
  writeLe16(header + 20, 1);
  writeLe16(header + 22, CHANNELS);
  writeLe32(header + 24, SAMPLE_RATE);
  const uint32_t bytesPerSecond = SAMPLE_RATE * CHANNELS * BITS_PER_SAMPLE / 8;
  writeLe32(header + 28, bytesPerSecond);
  writeLe16(header + 32, CHANNELS * BITS_PER_SAMPLE / 8);
  writeLe16(header + 34, BITS_PER_SAMPLE);
  memcpy(header + 36, "data", 4);
  writeLe32(header + 40, static_cast<uint32_t>(pcmBytes));
}

bool writeAll(WiFiClient& client, const uint8_t* data, size_t length) {
  while (length > 0) {
    const size_t written = client.write(data, length);
    if (written == 0) {
      return false;
    }
    data += written;
    length -= written;
  }
  return true;
}

bool writeAll(WiFiClient& client, const String& text) {
  return writeAll(client, reinterpret_cast<const uint8_t*>(text.c_str()), text.length());
}

bool readHttpResponse(WiFiClient& client, String& body, uint32_t timeoutMs = 15000) {
  const uint32_t deadline = millis() + timeoutMs;
  while (!client.available() && client.connected() && static_cast<int32_t>(deadline - millis()) > 0) {
    delay(5);
  }
  String headers;
  while (static_cast<int32_t>(deadline - millis()) > 0) {
    while (client.available()) {
      const char c = static_cast<char>(client.read());
      headers += c;
      if (headers.endsWith("\r\n\r\n")) {
        body = headers.substring(headers.indexOf("\r\n\r\n") + 4);
        while (client.connected() || client.available()) {
          while (client.available()) body += static_cast<char>(client.read());
          delay(2);
        }
        return headers.startsWith("HTTP/1.1 2") || headers.startsWith("HTTP/1.0 2");
      }
      if (headers.length() > 4096) return false;
    }
    delay(5);
  }
  return false;
}

String jsonStringField(const String& json, const char* field) {
  const String key = String("\"") + field + "\"";
  int start = json.indexOf(key);
  if (start < 0) return "";
  start = json.indexOf(':', start + key.length());
  if (start < 0) return "";
  start = json.indexOf('"', start + 1);
  if (start < 0) return "";
  const int end = json.indexOf('"', start + 1);
  return end < 0 ? "" : json.substring(start + 1, end);
}

bool jsonBoolField(const String& json, const char* field) {
  const String key = String("\"") + field + "\"";
  int start = json.indexOf(key);
  if (start < 0) return false;
  start = json.indexOf(':', start + key.length());
  if (start < 0) return false;
  ++start;
  while (start < json.length() && isspace(static_cast<unsigned char>(json[start]))) {
    ++start;
  }
  return json.substring(start).startsWith("true");
}

bool requestJson(const String& path, String& body) {
  WiFiClient client;
  if (!client.connect(XIAOQ_HOST, XIAOQ_PORT)) return false;
  const String request = "GET " + path + " HTTP/1.1\r\n"
      "Host: " + String(XIAOQ_HOST) + ":" + String(XIAOQ_PORT) + "\r\n"
      "X-XiaoQ-Token: " + apiToken + "\r\n"
      "Connection: close\r\n\r\n";
  if (!writeAll(client, request)) {
    client.stop();
    return false;
  }
  const bool ok = readHttpResponse(client, body);
  client.stop();
  return ok;
}

void reportPlaybackStage(const char* event, const String& jobId) {
  if (WiFi.status() != WL_CONNECTED || apiToken.isEmpty()) {
    return;
  }
  WiFiClient client;
  if (!client.connect(XIAOQ_HOST, XIAOQ_PORT)) {
    return;
  }
  const String body = String("{\"event\":\"") + event + "\",\"job_id\":\"" + jobId + "\"}";
  const String request = "POST /api/esp32/debug HTTP/1.1\r\n"
      "Host: " + String(XIAOQ_HOST) + ":" + String(XIAOQ_PORT) + "\r\n"
      "X-XiaoQ-Token: " + apiToken + "\r\n"
      "Content-Type: application/json\r\n"
      "Content-Length: " + String(body.length()) + "\r\n"
      "Connection: close\r\n\r\n";
  if (writeAll(client, request)) {
    writeAll(client, body);
  }
  client.stop();
}

bool playReplyAudio(const String& jobId) {
  reportPlaybackStage("audio_download_start", jobId);
  WiFiClient client;
  client.setTimeout(2000);
  if (!client.connect(XIAOQ_HOST, XIAOQ_PORT)) {
    Serial.println("[ptt] unable to connect for reply audio");
    return false;
  }
  const String request = "GET /api/voice/" + jobId + "/audio HTTP/1.1\r\n"
      "Host: " + String(XIAOQ_HOST) + ":" + String(XIAOQ_PORT) + "\r\n"
      "X-XiaoQ-Token: " + apiToken + "\r\n"
      "Connection: close\r\n\r\n";
  if (!writeAll(client, request)) {
    client.stop();
    return false;
  }
  const uint32_t deadline = millis() + 15000;
  String headers;
  while (static_cast<int32_t>(deadline - millis()) > 0 && client.connected()) {
    while (client.available()) {
      headers += static_cast<char>(client.read());
      if (headers.endsWith("\r\n\r\n")) break;
    }
    if (headers.endsWith("\r\n\r\n")) break;
    delay(5);
  }
  if (!headers.startsWith("HTTP/1.1 200") && !headers.startsWith("HTTP/1.0 200")) {
    Serial.printf("[ptt] reply audio HTTP error: %s\n", headers.substring(0, headers.indexOf("\r\n")).c_str());
    client.stop();
    return false;
  }

  const int lengthMarker = headers.indexOf("Content-Length:");
  if (lengthMarker < 0) {
    Serial.println("[ptt] reply audio has no Content-Length");
    client.stop();
    return false;
  }
  const int lengthStart = lengthMarker + strlen("Content-Length:");
  const int lengthEnd = headers.indexOf("\r\n", lengthStart);
  const size_t expectedBytes = strtoul(headers.substring(lengthStart, lengthEnd).c_str(), nullptr, 10);
  if (expectedBytes < 2) {
    Serial.println("[ptt] reply audio length is invalid");
    client.stop();
    return false;
  }
  if (expectedBytes > MAX_REPLY_AUDIO_BYTES) {
    Serial.printf("[ptt] reply audio is too large: %u bytes\n", static_cast<unsigned>(expectedBytes));
    client.stop();
    return false;
  }

  // Download before playback. Wi-Fi RX and the I2S amplifier together cause
  // a brownout on USB-powered ESP32-S3 boards, even with modest PCM volume.
  uint8_t* replyAudio = static_cast<uint8_t*>(ps_malloc(expectedBytes));
  if (replyAudio == nullptr) {
    replyAudio = static_cast<uint8_t*>(malloc(expectedBytes));
  }
  if (replyAudio == nullptr) {
    Serial.println("[ptt] unable to allocate reply audio buffer");
    client.stop();
    return false;
  }

  size_t receivedBytes = 0;
  while (receivedBytes < expectedBytes) {
    const int available = client.available();
    if (available <= 0) {
      if (!client.connected()) break;
      delay(2);
      continue;
    }
    const size_t want = min(static_cast<size_t>(available), expectedBytes - receivedBytes);
    const int read = client.readBytes(replyAudio + receivedBytes, want);
    if (read <= 0) break;
    receivedBytes += read;
  }
  client.stop();
  if (receivedBytes != expectedBytes) {
    Serial.printf("[ptt] incomplete reply download: %u/%u bytes\n",
                  static_cast<unsigned>(receivedBytes), static_cast<unsigned>(expectedBytes));
    free(replyAudio);
    return false;
  }

  reportPlaybackStage("audio_download_complete", jobId);
  Serial.printf("[ptt] downloaded %.1f KiB reply audio; pausing Wi-Fi for playback\n",
                expectedBytes / 1024.0f);
  reportPlaybackStage("playback_start", jobId);
  WiFi.mode(WIFI_OFF);
  updateLed();
  delay(250);
  ensureSpeaker();

  playing = true;
  size_t pending = 0;
  size_t total = 0;
  size_t offset = 0;
  while (offset < expectedBytes) {
    const size_t copied = min(sizeof(speakerMono) - pending, expectedBytes - offset);
    memcpy(reinterpret_cast<uint8_t*>(speakerMono) + pending, replyAudio + offset, copied);
    pending += copied;
    offset += copied;
    if (pending < sizeof(speakerMono)) {
      continue;
    }
    for (size_t i = 0; i < SPEAKER_FRAMES_PER_WRITE; ++i) {
      const int16_t sample = speakerSample(speakerMono[i]);
      speakerStereo[i * 2] = sample;
      speakerStereo[i * 2 + 1] = sample;
    }
    if (!writeSpeakerFrames(SPEAKER_FRAMES_PER_WRITE)) break;
    total += pending;
    pending = 0;
  }
  if (pending >= 2) {
    const size_t samples = pending / 2;
    for (size_t i = 0; i < samples; ++i) {
      const int16_t sample = speakerSample(speakerMono[i]);
      speakerStereo[i * 2] = sample;
      speakerStereo[i * 2 + 1] = sample;
    }
    if (writeSpeakerFrames(samples)) {
      total += pending;
    }
  }
  // Arduino-ESP32 2.x has no i2s_wait_tx_done(). Eight 256-frame DMA
  // buffers take about 128 ms at 16 kHz, so give the final buffer time to drain.
  delay(180);
  i2s_zero_dma_buffer(SPEAKER_PORT);
  playing = false;
  free(replyAudio);
  WiFi.mode(WIFI_STA);
  connectWifi();
  updateLed();
  Serial.printf("[ptt] played %.1f KiB reply audio (%u/%u bytes)\n",
                total / 1024.0f, static_cast<unsigned>(expectedBytes),
                static_cast<unsigned>(expectedBytes));
  return total > 0 && total == expectedBytes;
}

void waitAndPlayReply(const String& jobId) {
  Serial.printf("[ptt] waiting for reply job %s\n", jobId.c_str());
  const uint32_t deadline = millis() + 180000;
  while (static_cast<int32_t>(deadline - millis()) > 0) {
    String body;
    if (requestJson("/api/voice/" + jobId, body)) {
      const String status = jsonStringField(body, "status");
      if (status == "completed") {
        // XiaoQ writes the textual reply first, then the ESP32-specific TTS
        // worker changes it to synthesizing and finally marks audio_ready.
        // Do not request /audio during that short transition or it returns 404.
        if (!jsonBoolField(body, "audio_ready")) {
          delay(500);
          continue;
        }
        reportPlaybackStage("reply_ready", jobId);
        if (!playReplyAudio(jobId)) Serial.println("[ptt] reply playback failed");
        return;
      }
      if (status == "failed") {
        Serial.printf("[ptt] XiaoQ voice job failed: %s\n", jsonStringField(body, "error").c_str());
        return;
      }
    }
    delay(500);
  }
  Serial.println("[ptt] reply wait timed out");
}

void uploadRecording() {
  if (recordedBytes < MIN_RECORD_BYTES) {
    Serial.println("[ptt] recording too short; discarded");
    return;
  }
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[ptt] Wi-Fi is not connected; recording discarded");
    return;
  }
  if (apiToken.isEmpty()) {
    Serial.println("[ptt] XiaoQ token is missing; use: token <mobile-control-token>");
    return;
  }

  uint8_t wavHeader[44];
  makeWavHeader(wavHeader, recordedBytes);
  const String boundary = "----XiaoQEsp32Ptt" + String(millis());
  const String prefix = "--" + boundary + "\r\n"
      // The mobile service currently converts uploaded files to WAV. Use a
      // distinct accepted extension so its input and output paths differ.
      "Content-Disposition: form-data; name=\"file\"; filename=\"esp32-ptt.m4a\"\r\n"
      "Content-Type: audio/wav\r\n\r\n";
  const String suffix = "\r\n--" + boundary + "--\r\n";
  const size_t contentLength = prefix.length() + sizeof(wavHeader) + recordedBytes + suffix.length();

  WiFiClient client;
  Serial.printf("[ptt] uploading %.1f KiB to XiaoQ\n", recordedBytes / 1024.0f);
  if (!client.connect(XIAOQ_HOST, XIAOQ_PORT)) {
    Serial.println("[ptt] unable to connect to XiaoQ service");
    return;
  }
  const String request = "POST /api/voice HTTP/1.1\r\n"
      "Host: " + String(XIAOQ_HOST) + ":" + String(XIAOQ_PORT) + "\r\n"
      "X-XiaoQ-Token: " + apiToken + "\r\n"
      "X-XiaoQ-Reply-Channel: esp32\r\n"
      "Content-Type: multipart/form-data; boundary=" + boundary + "\r\n"
      "Content-Length: " + String(contentLength) + "\r\n"
      "Connection: close\r\n\r\n";
  if (!writeAll(client, request) || !writeAll(client, prefix) || !writeAll(client, wavHeader, sizeof(wavHeader)) ||
      !writeAll(client, recordingBuffer, recordedBytes) || !writeAll(client, suffix)) {
    Serial.println("[ptt] upload write failed");
    client.stop();
    return;
  }

  String response;
  readHttpResponse(client, response);
  client.stop();
  const String jobId = jsonStringField(response, "job_id");
  if (jobId.isEmpty()) {
    Serial.printf("[ptt] XiaoQ did not return a job id: %s\n", response.substring(0, 180).c_str());
    return;
  }
  waitAndPlayReply(jobId);
}

void uploadRecordingTask(void*) {
  uploadRecording();
  voiceJobActive = false;
  vTaskDelete(nullptr);
}

void queueRecordingUpload() {
  if (voiceJobActive) {
    Serial.println("[ptt] a voice reply is already in progress");
    return;
  }
  voiceJobActive = true;
  // Network upload, XiaoQ processing, and I2S playback can take minutes.
  // Keep them off the Arduino loop so BOOT and its LED remain responsive.
  if (xTaskCreate(uploadRecordingTask, "xiaoq-voice", 16384, nullptr, 1, nullptr) != pdPASS) {
    voiceJobActive = false;
    Serial.println("[ptt] unable to start voice upload task");
  }
}

void beginRecording() {
  if (recording || recordingBuffer == nullptr) {
    return;
  }
  if (voiceJobActive) {
    Serial.println("[ptt] reply in progress; new recording ignored");
    return;
  }
  recordedBytes = 0;
  recording = true;
  updateLed();
  i2s_zero_dma_buffer(MIC_PORT);
  Serial.println("[ptt] recording started");
}

void captureAudio() {
  if (!recording || recordedBytes >= MAX_RECORD_BYTES) {
    return;
  }
  size_t read = 0;
  const size_t space = MAX_RECORD_BYTES - recordedBytes;
  const esp_err_t result = i2s_read(MIC_PORT, recordingBuffer + recordedBytes, min(space, static_cast<size_t>(4096)), &read, pdMS_TO_TICKS(20));
  if (result == ESP_OK && read > 0) {
    recordedBytes += read;
  }
  if (recordedBytes >= MAX_RECORD_BYTES) {
    recording = false;
    updateLed();
    Serial.println("[ptt] maximum recording length reached");
    queueRecordingUpload();
  }
}

void finishRecording() {
  if (!recording) {
    return;
  }
  recording = false;
  updateLed();
  Serial.printf("[ptt] recording stopped: %u bytes\n", static_cast<unsigned>(recordedBytes));
  queueRecordingUpload();
}

void handleButton() {
  const uint32_t now = millis();
  const bool down = digitalRead(BOOT_PIN) == LOW;
  if (down != lastRawPressed) {
    lastRawPressed = down;
    rawChangedAt = now;
  }
  if (now - rawChangedAt < DEBOUNCE_MS) {
    return;
  }
  if (stablePressed == down) {
    return;
  }
  stablePressed = down;
  // Follow the debounced state so switch bounce cannot appear as blue flashes.
  updateLed();
  if (stablePressed && !recording) {
    beginRecording();
  } else if (!stablePressed && recording) {
    finishRecording();
  }
}

void printStatus() {
  Serial.printf("[ptt] Wi-Fi=%s ip=%s token=%s recording=%s boot=%s reset=%d\n",
                WiFi.status() == WL_CONNECTED ? "connected" : "offline",
                WiFi.localIP().toString().c_str(), apiToken.isEmpty() ? "missing" : "configured",
                recording ? "yes" : "no", digitalRead(BOOT_PIN) == LOW ? "pressed" : "released",
                static_cast<int>(esp_reset_reason()));
}

// GPIOs 22-37 are reserved by the ESP32-S3 flash/PSRAM package. GPIOs 4-6
// belong to the microphone, 19-20 to USB, and 48 to the RGB LED. The listed
// candidates can be safely pulled up during a button diagnostic, preventing
// otherwise-floating pins from producing misleading changes.
constexpr uint8_t DIAGNOSTIC_GPIOS[] = {
    0, 1, 2, 3, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 21,
    45, 46, 47,
};

void printGpioLevels(bool changesOnly) {
  static uint64_t previous = 0;
  uint64_t levels = 0;
  for (size_t index = 0; index < sizeof(DIAGNOSTIC_GPIOS); ++index) {
    const uint8_t pin = DIAGNOSTIC_GPIOS[index];
    if (digitalRead(pin) == HIGH) {
      levels |= (UINT64_C(1) << index);
    }
  }
  if (changesOnly && levels == previous) {
    return;
  }
  Serial.printf("[ptt] gpio levels:");
  for (size_t index = 0; index < sizeof(DIAGNOSTIC_GPIOS); ++index) {
    const uint8_t pin = DIAGNOSTIC_GPIOS[index];
    Serial.printf(" %u=%u", pin,
                  static_cast<unsigned>((levels >> index) & UINT64_C(1)));
  }
  Serial.println();
  previous = levels;
}

void watchGpios() {
  Serial.println("[ptt] watching GPIO changes for 20 seconds");
  for (const uint8_t pin : DIAGNOSTIC_GPIOS) {
    pinMode(pin, INPUT_PULLUP);
  }
  delay(30);
  printGpioLevels(false);
  const uint32_t endAt = millis() + 20000;
  while (static_cast<int32_t>(endAt - millis()) > 0) {
    printGpioLevels(true);
    delay(100);
  }
  Serial.println("[ptt] GPIO watch finished");
}

void handleConsole() {
  if (!Serial.available()) {
    return;
  }
  const String command = Serial.readStringUntil('\n');
  if (command.startsWith("token ") && command.length() > 6) {
    apiToken = command.substring(6);
    apiToken.trim();
    preferences.putString("api_token", apiToken);
    Serial.println("[ptt] XiaoQ token stored");
  } else if (command == "clear-token") {
    apiToken = "";
    preferences.remove("api_token");
    Serial.println("[ptt] XiaoQ token cleared");
  } else if (command == "status") {
    printStatus();
  } else if (command == "gpio scan") {
    printGpioLevels(false);
  } else if (command == "gpio watch") {
    watchGpios();
  } else if (command == "led blue") {
    setLed(0, 0, 255);
    Serial.println("[ptt] RGB test: blue");
  } else if (command == "led red") {
    setLed(255, 0, 0);
    Serial.println("[ptt] RGB test: red");
  } else if (command == "led green") {
    setLed(0, 255, 0);
    Serial.println("[ptt] RGB test: green");
  } else if (command == "led off") {
    setLed(0, 0, 0);
    Serial.println("[ptt] RGB test: off");
  } else if (command.startsWith("play ") && command.length() > 5) {
    const String jobId = command.substring(5);
    if (WiFi.status() != WL_CONNECTED || apiToken.isEmpty()) {
      Serial.println("[ptt] cannot play: Wi-Fi or XiaoQ token is unavailable");
    } else {
      Serial.printf("[ptt] diagnostic playback for %s\n", jobId.c_str());
      playReplyAudio(jobId);
    }
  } else if (command == "help") {
    Serial.println("[ptt] commands: token <value>, clear-token, status, play <voice-job-id>, led blue|red|green|off, help");
  } else {
    Serial.println("[ptt] unknown command; type help");
  }
}

}  // namespace

void setup() {
  Serial.begin(115200, SERIAL_8N1, 44, 43);
  delay(300);
  configureBootButton();
  lastRawPressed = digitalRead(BOOT_PIN) == LOW;
  stablePressed = lastRawPressed;
  rawChangedAt = millis() - DEBOUNCE_MS;
  updateLed();
  preferences.begin("xiaoq-ptt", false);
  apiToken = preferences.getString("api_token", "");
  if (psramFound()) {
    recordingBuffer = static_cast<uint8_t*>(ps_malloc(MAX_RECORD_BYTES));
  }
  if (recordingBuffer == nullptr) {
    Serial.println("[ptt] PSRAM allocation failed; recording is unavailable");
  }
  installMicrophone();
  // Keep the speaker peripheral uninitialized until an actual reply must play.
  // That prevents its I2S setup from disturbing BOOT while recording.
  configureBootButton();
  lastRawPressed = digitalRead(BOOT_PIN) == LOW;
  stablePressed = lastRawPressed;
  rawChangedAt = millis() - DEBOUNCE_MS;
  connectWifi();
  Serial.printf("[ptt] ready; max recording=%u seconds\n", MAX_RECORD_SECONDS);
  printStatus();
}

void loop() {
  updateWifi();
  handleConsole();
  handleButton();
  captureAudio();
  delay(1);
}
