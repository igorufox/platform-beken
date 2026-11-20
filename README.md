ESPurna's PlatformIO platform for the Beken BK7231N: nothing but the toolchain (GCC 14.2, toolchain-gccarmnoneeabi), the SDK package (framework-beken-bdk) and the BK7231N board with the Tuya flash layout. The SDK comes COMPILED from `sdk/` (as Espressif's lib-builder for Arduino-ESP32): the firmware only links it. The images are built by ESPurna's own scripts. Releases are made by GitHub Actions from the version of platform.json.

- `platform.json`, `platform.py` — the platform and its packages
- `builder/main.py` — the program (`firmware.elf`, `firmware.bin`)
- `boards/bk7231n-tuya.json` — the BK7231N board, Tuya bootloader and flash layout
- `.github/workflows/release.yml` — a push to main releases the version of `platform.json` when it is not released yet
- `sdk/build.py`, `sdk/glue/` — the SDK package: the BDK 3.0.33 with its glue (entry, clocks, malloc on the FreeRTOS heap, the rtos_* layer on FreeRTOS 11, the lwIP options, the Mbed TLS config), FreeRTOS-Kernel with the ARM968 port, lwIP 2.2.0 with the BDK port and Mbed TLS 3.6.6, compiled into archives + headers + linker script + `flags.json`
- `.github/workflows/sdk.yml` — builds the SDK package, links a test image from it, releases `sdk-<version of sdk/package.json>`
