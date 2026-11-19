ESPurna's PlatformIO platform for the Beken BK7231N: nothing but the toolchain (GCC 14.2, toolchain-gccarmnoneeabi), the BDK package (framework-beken-bdk) and the BK7231N board with the Tuya flash layout. The BDK and the images are built by ESPurna's own scripts. Releases are made by GitHub Actions from the version of platform.json.

- `platform.json`, `platform.py` — the platform and its packages
- `builder/main.py` — the program (`firmware.elf`, `firmware.bin`)
- `boards/bk7231n-tuya.json` — the BK7231N board, Tuya bootloader and flash layout
- `.github/workflows/release.yml` — a push to main releases the version of `platform.json` when it is not released yet
