#pragma once

// Copy to secrets.h and set the Wi-Fi network used by XiaoQ.
#define WIFI_SSID "YOUR_WIFI_SSID"
#define WIFI_PASSWORD "YOUR_WIFI_PASSWORD"

// XiaoQ mobile-control service.  The ESP32 stores the API token separately in
// NVS after the serial command: token <mobile-control-token>
#define XIAOQ_HOST "192.168.137.116"
#define XIAOQ_PORT 8788
