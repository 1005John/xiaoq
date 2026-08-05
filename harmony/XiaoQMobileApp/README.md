# XiaoQ HarmonyOS Mobile

HarmonyOS companion application for XiaoQ. It provides LAN-authenticated text chat, meeting recording and summaries, editable meeting todos, camera viewing, and manual gimbal control.

## Build Setup

1. Open this directory in DevEco Studio.
2. Copy `build-profile.example.json5` to `build-profile.json5`.
3. Configure the local signing certificate, profile, and keystore paths.
4. Build the `default` debug product and install the generated HAP.

`build-profile.json5`, signing material, local SDK paths, and build outputs are deliberately ignored. Do not commit credentials or generated HAP files.

## Connection

On first run, set the Raspberry Pi LAN address and device token in the Settings tab. The token is read from `data/mobile_control_token` on XiaoQ and is required by every mobile API call.
