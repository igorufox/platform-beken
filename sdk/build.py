#!/usr/bin/env python3
"""The binary SDK package of the Beken BK7231N for ESPurna (as Espressif's lib-builder for Arduino-ESP32): the BDK, the
FreeRTOS kernel with its ARM968 port, lwIP 2.2.0 with the BDK port and Mbed TLS 3.6.6 compiled once here, by the
release of this repository, and linked by the firmware - the firmware never compiles them.

    build.py --bdk DIR --kernel DIR --lwip DIR --mbedtls DIR --toolchain DIR --version V --out DIR [--work DIR] [--test]

  --bdk        framework-beken-bdk (BDK 3.0.33, libretiny-eu/framework-beken-bdk)
  --kernel     FreeRTOS-Kernel V11.1.0 with portable/GCC/ARM968 (igorufox/FreeRTOS-Kernel)
  --lwip       lwIP 2.2.0 with the BDK port (libretiny-eu/lwip), --mbedtls  Mbed TLS 3.6.6 (igorufox/mbedtls)
  --toolchain  arm-none-eabi GCC 14.2 (bin/arm-none-eabi-gcc)

What is compiled: the BDK sources the BK7231N needs (what LibreTiny 1.14 compiled of it, beken378/beken_src.mk: no BLE in
the image, no Arduino), the fixups of the BDK and its glue (sdk/glue: entry, clocks, malloc on the FreeRTOS heap, the
heap and random of Mbed TLS, the rtos_* layer of the BDK on V11), the kernel and its port, lwIP with the options of
sdk/glue/lwipopts (ESPurna's and the Matter library's) and Mbed TLS with sdk/glue/config/tls_config.h; and the BLE 5.x
stack as an archive of its own that no image links (the ble module of the firmware links it).
The flash layout of the board is the firmware's: it compiles the flash partitions (BkDriverFlash wraps, FAL) itself.

The package (--out, also zipped next to it):

  package.json     framework-beken-bdk <version>
  flags.json       the flags the firmware compiles with (cflags, cxxflags, asflags, defines, includes - every path as
                   ${PKG}/...), its link (linkflags, libs in order: the archives here, the closed libraries of the BDK,
                   the C libraries), the linker script, and what it was built of
  include/{bdk,kernel,lwip,mbedtls,glue}/...   the headers of every include folder
  lib/*.a          the archives (libble_stack.a: for the ble module only)
  ld/bk7231n_bsp.ld

--test links a test image from the package alone, by flags.json, as the firmware does.
"""

import argparse
import concurrent.futures
import json
import os
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
GLUE = os.path.join(HERE, "glue")
SOC = "bk7231n"
HEADERS = (".h", ".hpp", ".inc", ".def")

CPU = ["-mcpu=arm968e-s", "-march=armv5te", "-mthumb-interwork"]
CCFLAGS = CPU + [
    "-mthumb", "-fsigned-char", "-g2", "-fdata-sections", "-ffunction-sections", "-fno-strict-aliasing",
    "-fno-delete-null-pointer-checks", "-fno-common", "-fno-exceptions", "-Wno-write-strings", "-Wno-attributes",
]
CFLAGS = ["-std=gnu99"]
CXXFLAGS = ["-fno-rtti", "-Wno-psabi"]
ASFLAGS = CPU + ["-marm", "-g", "-x", "assembler-with-cpp"]
# GCC 14 made three old C warnings errors; the C of the BDK has them (as GCC 10.3 had them: warnings)
GCC14_C = ["-Wno-error=implicit-function-declaration", "-Wno-error=incompatible-pointer-types",
           "-Wno-error=int-conversion"]
LINKFLAGS = CPU + [
    "-marm", "--specs=nano.specs", "-Wl,--gc-sections", "-Wl,--no-enum-size-warning", "-Wl,--no-wchar-size-warning",
    "-Wl,--no-undefined", "-Wl,--build-id=none",
    # malloc() and friends on the FreeRTOS heap (glue/port/malloc.c)
    "-Wl,-wrap,malloc", "-Wl,-wrap,calloc", "-Wl,-wrap,zalloc", "-Wl,-wrap,realloc", "-Wl,-wrap,free",
    "-Wl,-wrap,_malloc_r", "-Wl,-wrap,_calloc_r", "-Wl,-wrap,_realloc_r", "-Wl,-wrap,_free_r",
    # the BDK's partitions of the firmware's layout (its BkDriverFlash wraps)
    "-Wl,-wrap,bk_flash_get_info", "-Wl,-wrap,bk_flash_erase", "-Wl,-wrap,bk_flash_write", "-Wl,-wrap,bk_flash_read",
]
CLOSED = ["airkiss", "sensor", "ble_" + SOC, "cal_" + SOC, "rf_test_" + SOC, "rf_use_" + SOC, "rwnx_" + SOC,
          "supplicant_" + SOC, "uart_debug_" + SOC,
          # once more: the Wi-Fi of librwnx calls the BLE coexistence of libble (one pass of the linker)
          "ble_" + SOC]
SYSTEM = ["stdc++", "supc++", "gcc", "g", "c", "m", "nosys"]

INCLUDES = [
    "app", "app/config", "common", "driver/entry", "driver/intc", "release", "../release",
    "app/http", "app/net_work", "app/standalone-ap", "app/standalone-station", "app/video_work",
    "driver/common", "driver/common/reg", "driver/dma", "driver/flash", "driver/general_dma", "driver/gpio",
    "driver/i2c", "driver/icu", "driver/include", "driver/jpeg", "driver/phy", "driver/pwm", "driver/rc_beken",
    "driver/rw_pub", "driver/spi", "driver/spidma", "driver/sys_ctrl", "driver/uart", "driver/usb",
]
# after the driver's, before func's (as beken_src.mk / LibreTiny): ip/lmac/src/scan/scan.h, not the supplicant's scan.h
FUNC_INCLUDES = [
    "func/base64", "func/ble_wifi_exchange", "func/camera_intf", "func/ethernet_intf", "func/force_sleep",
    "func/include", "func/joint_up", "func/lwip_intf", "func/misc", "func/ntp", "func/power_save", "func/rf_test",
    "func/rf_use", "func/rtc", "func/rwnx_intf", "func/saradc_intf", "func/sensor", "func/spidma_intf",
    "func/temp_detect", "func/uart_debug", "func/usb", "func/user_driver", "func/utf8", "func/video_transfer",
    "func/wpa_supplicant_2_9/bk_patch", "func/wpa_supplicant_2_9/hostapd", "func/wpa_supplicant_2_9/src",
    "func/wpa_supplicant_2_9/src/ap", "func/wpa_supplicant_2_9/src/common", "func/wpa_supplicant_2_9/src/drivers",
    "func/wpa_supplicant_2_9/src/utils", "func/wpa_supplicant_2_9/src/wps", "func/wpa_supplicant_2_9/wpa_supplicant",
    "func/mbedtls/mbedtls-port/inc",
]

BLE_RENAMED = (
    "ble_entry", "ble_init", "ble_exit", "if_ble_sleep", "ble_switch_rf_to_wifi", "rf_wifi_used_set",
    "rf_wifi_used_clr", "ps_recover_ble_switch_mac_status",
)


def posix(path):
    return os.path.abspath(path).replace(os.sep, "/").rstrip("/")


def select(base, filters):
    """the files of PlatformIO's src_filter: +<glob> / -<glob> in order, relative to base, ** for any folders"""
    import glob
    chosen = []
    for item in filters:
        sign, pattern = item[0], item[2:-1]
        hit = sorted(os.path.normpath(path) for path in glob.glob(os.path.join(base, pattern), recursive=True)
                     if os.path.isfile(path))
        if sign == "+":
            chosen += [path for path in hit if path not in chosen]
        else:
            chosen = [path for path in chosen if path not in hit]
    return [path for path in chosen if path.endswith((".c", ".S", ".s", ".cpp"))]


class Builder:
    def __init__(self, args):
        self.args = args
        self.bdk = os.path.abspath(args.bdk)
        self.root = os.path.join(self.bdk, "beken378")
        self.kernel = os.path.abspath(args.kernel)
        self.port = os.path.join(self.kernel, "portable", "GCC", "ARM968")
        self.lwip = os.path.abspath(args.lwip)
        self.mbedtls = os.path.abspath(args.mbedtls)
        self.prefix = os.path.join(os.path.abspath(args.toolchain), "bin", "arm-none-eabi-")
        self.work = os.path.abspath(args.work)
        self.out = os.path.abspath(args.out)

    def ip_includes(self):
        out = []
        for folder, dirs, _ in os.walk(os.path.join(self.root, "ip")):
            dirs.sort()
            out.append(folder)
        return out

    def includes(self):
        """ESPurna's fixups and config of the BDK first (they replace some of its headers), the lwIP options, the
        FreeRTOS port's config before the BDK's own, then the BDK (beken_src.mk), FreeRTOS, lwIP, Mbed TLS"""
        return ([os.path.join(GLUE, "fixups"), os.path.join(GLUE, "config"), GLUE, os.path.join(GLUE, "lwipopts"),
                 self.port]
                + [os.path.join(self.root, path) for path in INCLUDES]
                + self.ip_includes()
                + [os.path.join(self.root, path) for path in FUNC_INCLUDES]
                + [os.path.join(self.root, "os", "include"),
                   # rtos.h of the BDK's rtos_* layer (macros only)
                   os.path.join(self.root, "os", "FreeRTOSv9.0.0"),
                   os.path.join(self.kernel, "include"),
                   os.path.join(self.lwip, "src", "include"),
                   os.path.join(self.lwip, "src", "include", "ipv4"),
                   os.path.join(self.lwip, "port"),
                   os.path.join(self.mbedtls, "include"),
                   # <sockets.h> ... of the BDK's sources: lwIP's (as LibreTiny's compat/)
                   os.path.join(GLUE, "compat")])

    def defines(self):
        return [
            "CFG_OS_FREERTOS=1",
            'MBEDTLS_CONFIG_FILE="tls_config.h"',
            "WIFI_BLE_COEXIST=1",
            "WOLFSSL_BEKEN=0",
            "MBEDTLS_KEY_EXCHANGE__SOME__PSK_ENABLED",
            "INCLUDE_xTaskGetHandle=1",
            "CFG_BDK_VERSION=30033",
            # IPv6 in the BDK's lwIP port and the firmware (Matter)
            "CONFIG_IPV6",
            # the kernel's list.h and the supplicant's share the guard LIST_H: the port reads both by these paths
            'FREERTOS_KERNEL_LIST_H="%s"' % posix(os.path.join(self.kernel, "include", "list.h")),
            'BDK_DL_LIST_H="%s"' % posix(os.path.join(self.root, "func", "wpa_supplicant_2_9", "src", "utils",
                                                         "list.h")),
        ]

    def compile(self, source, obj, flags):
        os.makedirs(os.path.dirname(obj), exist_ok=True)
        if source.endswith((".S", ".s")):
            cmd = [self.prefix + "gcc"] + ASFLAGS + flags["as"]
        elif source.endswith(".cpp"):
            cmd = [self.prefix + "g++"] + flags["cc"] + CXXFLAGS
        else:
            cmd = [self.prefix + "gcc"] + flags["cc"] + CFLAGS + GCC14_C
        cmd += ["-D" + d for d in flags["defines"]] + ["-I" + i for i in flags["includes"]] + ["-c", source, "-o", obj]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        if result.returncode != 0:
            return "%s\n%s" % (" ".join(cmd), result.stdout)
        return None

    def library(self, pool, name, base, filters, flags):
        sources = select(base, filters)
        if not sources:
            raise SystemExit("build.py: %s has no sources" % name)
        objs = []
        jobs = []
        for source in sources:
            rel = os.path.relpath(source, base)
            obj = os.path.join(self.work, "obj", name, rel + ".o")
            objs.append(obj)
            jobs.append(pool.submit(self.compile, source, obj, flags))
        errors = [job.result() for job in jobs if job.result()]
        if errors:
            sys.stdout.write("\n".join(errors[:5]) + "\n")
            raise SystemExit("build.py: %s: %d files failed" % (name, len(errors)))
        lib = os.path.join(self.out, "lib", "lib%s.a" % name)
        os.makedirs(os.path.dirname(lib), exist_ok=True)
        if os.path.isfile(lib):
            os.remove(lib)
        listing = os.path.join(self.work, name + ".objs")
        with open(listing, "w", encoding="utf-8") as f:
            f.write("\n".join(o.replace(os.sep, "/") for o in objs) + "\n")
        subprocess.run([self.prefix + "gcc-ar", "rcs", lib, "@" + listing], check=True)
        print("build.py: lib%s.a, %d objects" % (name, len(objs)), flush=True)
        return "lib%s.a" % name

    def flags(self, cc, includes=None, defines=None):
        return {"cc": cc, "as": [], "defines": defines if defines is not None else self.defines(),
                "includes": includes if includes is not None else self.includes()}

    def build(self):
        if os.path.isdir(self.out):
            shutil.rmtree(self.out)
        if os.path.isdir(self.work):
            shutil.rmtree(self.work)
        os.makedirs(self.out)

        # the BDK's own sources: its warnings are not ours; -O1: anything higher gives random lockups and blank strings
        # in the BDK (LibreTiny's experience)
        bdk_cc = CCFLAGS + ["-w", "-O1"]
        bdk = self.flags(bdk_cc, defines=self.defines() + ["SDK_COMMIT_ID=NULL"])
        bdk["as"] = ["-w"]
        # FreeRTOS and its port (and heap) in ARM mode, as the BDK built them; the rtos_* layer in Thumb
        arm_cc = [f for f in bdk_cc if f != "-mthumb"] + ["-marm"]
        arm = self.flags(arm_cc, defines=bdk["defines"])
        # the kernel's list.h before the supplicant's; -Os: the tick and switch go to the 4.5 KiB ITCM (V11's are
        # bigger than 9.0.0's: -O1 8 bytes over, -Os 156 bytes smaller)
        kernel = self.flags([f for f in arm_cc if f != "-O1"] + ["-Os"],
                            includes=[os.path.join(self.kernel, "include")] + self.includes(), defines=bdk["defines"])

        libs = []
        with concurrent.futures.ThreadPoolExecutor(self.args.jobs) as pool:
            # the glue first in the link: its fixups replace members of the BDK's archives
            libs.append(self.library(pool, "bdk_glue", GLUE, ["+<fixups/*.c>", "+<port/*.c>", "+<freertos/*.c>"],
                                     bdk))
            libs.append(self.library(pool, "freertos", self.kernel,
                                     ["+<event_groups.c>", "+<list.c>", "+<queue.c>", "+<stream_buffer.c>",
                                      "+<tasks.c>", "+<timers.c>"], kernel))
            libs.append(self.library(pool, "freertos_port", self.port, ["+<port.c>", "+<heap_beken.c>"], arm))
            for name, base, filters in (
                ("bdk_core", self.root, ["+<app/app.c>", "+<app/config/param_config.c>",
                                         "+<driver/entry/boot_vectors.S>", "+<driver/entry/boot_handlers.S>",
                                         "+<func/wlan_ui/wlan_ui.c>"]),
                ("bdk_app", os.path.join(self.root, "app"),
                 ["+<http/*.c>", "+<net_work/*.c>", "+<standalone-ap/*.c>", "+<standalone-station/*.c>",
                  "+<video_work/*.c>"]),
                ("bdk_driver", os.path.join(self.root, "driver"),
                 ["+<driver.c>", "+<common/*.c>", "+<dma/*.c>", "+<fft/*.c>", "+<flash/*.c>", "+<gpio/*.c>",
                  "+<i2c/i2c2.c>", "+<icu/*.c>", "+<macphy_bypass/*.c>", "+<phy/*.c>", "+<pwm/*.c>",
                  "-<pwm/pwm_bk7271.c>", "-<pwm/pwm_new.c>", "+<rw_pub/*.c>", "+<saradc/*.c>", "+<security/*.c>",
                  "+<spi/*.c>", "-<spi/spi_psram.c>", "+<spidma/*.c>", "+<sys_ctrl/*.c>", "+<uart/uart.c>",
                  "+<wdt/*.c>", "+<calendar/calendar.c>", "+<general_dma/general_dma.c>", "+<i2c/i2c1.c>",
                  "+<i2s/i2s.c>", "+<irda/irda.c>", "+<jpeg/jpeg_encoder.c>", "+<qspi/qspi.c>"]),
                ("bdk_func", os.path.join(self.root, "func"),
                 ["+<func.c>", "+<airkiss/*.c>", "+<base64/*.c>", "+<bk7011_cal/*.c>", "+<ble_wifi_exchange/*.c>",
                  "+<camera_intf/*.c>", "+<force_sleep/*.c>", "+<hostapd_intf/*.c>", "+<joint_up/*.c>",
                  "+<lwip_intf/dhcpd/*.c>", "+<misc/*.c>", "-<misc/fake_clock.c>", "+<net_param_intf/*.c>",
                  "+<ntp/*.c>", "+<power_save/*.c>", "-<power_save/low_voltage_compensation.c>",
                  "-<power_save/low_voltage_ps.c>", "+<rtc/*.c>", "-<rtc/alarm.c>", "+<rwnx_intf/*.c>",
                  "+<saradc_intf/*.c>", "+<security/*.c>", "+<sim_uart/*.c>", "+<spidma_intf/*.c>",
                  "+<temp_detect/*.c>", "+<usb_plug/*.c>", "+<user_driver/*.c>", "-<user_driver/BkDriverQspi.c>",
                  "+<utf8/*.c>", "+<video_transfer/*.c>"]),
                # the rtos_* layer: the glue's copy on V11 (glue/freertos/rtos_pub.c)
                ("bdk_os", self.root, ["+<os/**/*.c>", "-<os/platform_stub.c>", "-<os/FreeRTOSv9.0.0/rtos_pub.c>"]),
                # Mbed TLS 3.6.6 (its heap and random: glue/port/mbedtls_beken.c)
                ("mbedtls", os.path.join(self.mbedtls, "library"),
                 ["+<*.c>", "-<net_sockets.c>", "-<psa_its_file.c>"]),
                ("lwip", self.lwip,
                 ["+<src/api/*.c>", "+<src/core/*.c>", "+<src/core/ipv4/*.c>", "+<src/core/ipv6/*.c>",
                  "+<src/netif/ethernet.c>", "+<src/netif/etharp.c>", "+<src/apps/mdns/*.c>",
                  "+<src/apps/sntp/sntp.c>", "+<port/*.c>"]),
            ):
                libs.append(self.library(pool, name, base, filters, bdk))

            # the BLE 5.x stack for the ble module only: the names its Wi-Fi and its boot call are renamed (bk_stack_*,
            # the image answers them: glue/fixups/ble_off.c), the module links its own; -fcommon: the tentative
            # ble_switch_mac_sleeped of ble_rf_port.c is the image's variable in the module's link
            ble_dir = os.path.join(self.root, "driver", "ble_5_x_rw")
            ble_includes = []
            for folder, dirs, files in os.walk(ble_dir):
                dirs.sort()
                if any(name.endswith(".h") for name in files):
                    ble_includes.append(folder)
            ble = self.flags([f for f in bdk_cc if f != "-fno-common"] + ["-fcommon"],
                             includes=[os.path.join(GLUE, "fixups"), os.path.join(GLUE, "config"), GLUE]
                             + ble_includes + self.includes(),
                             defines=bdk["defines"] + ["%s=bk_stack_%s" % (n, n) for n in BLE_RENAMED])
            self.library(pool, "ble_stack", ble_dir,
                         ["+<ble_pub/**/*.c>", "+<platform/7231n/**/*.c>", "-<ble_pub/app/src/app_ble_task.c>",
                          "-<platform/7231n/nvds/src/nvds.c>"], ble)

        # the closed libraries of the BDK for the chip
        closed_dirs = [os.path.join(self.root, "lib"), os.path.join(self.root, "func", "airkiss")]
        for name in sorted(set(CLOSED)):
            for folder in closed_dirs:
                path = os.path.join(folder, "lib%s.a" % name)
                if os.path.isfile(path):
                    shutil.copy2(path, os.path.join(self.out, "lib"))
                    break
            else:
                raise SystemExit("build.py: lib%s.a not found in the BDK" % name)

        os.makedirs(os.path.join(self.out, "ld"))
        shutil.copy2(os.path.join(GLUE, "bk7231n_bsp.ld"), os.path.join(self.out, "ld"))

        # the headers, every path of the flags as ${PKG}/include/<root>/...
        roots = sorted(((posix(path), name) for path, name in (
            (self.bdk, "bdk"), (self.kernel, "kernel"), (self.lwip, "lwip"), (self.mbedtls, "mbedtls"),
            (GLUE, "glue"))), key=lambda r: -len(r[0]))

        def mapped(path):
            path = posix(path)
            for root, name in roots:
                if path == root or path.startswith(root + "/"):
                    return name + path[len(root):]
            raise SystemExit("build.py: %s is outside the sources" % path)

        copied = set()

        def include(path):
            inside = mapped(path)
            if path not in copied:
                copied.add(path)
                for name in os.listdir(path):
                    if name.endswith(HEADERS) and os.path.isfile(os.path.join(path, name)):
                        target = os.path.join(self.out, "include", inside)
                        os.makedirs(target, exist_ok=True)
                        shutil.copy2(os.path.join(path, name), target)
            return "${PKG}/include/" + inside

        # the folders the firmware compiles with (the BDK's include folders hold their headers flat; the compat and
        # lwIP / Mbed TLS / kernel include folders have subfolders: copied whole)
        includes = []
        # the BDK's lists name some folders this BDK has not (func/force_sleep ...): the compiler skips them, so here
        for path in [path for path in self.includes() if os.path.isdir(path)]:
            if mapped(path).split("/")[0] in ("lwip", "mbedtls", "kernel") or path == os.path.join(GLUE, "compat"):
                inside = mapped(path)
                target = os.path.join(self.out, "include", inside)
                for folder, _, names in os.walk(path):
                    for name in names:
                        if name.endswith(HEADERS):
                            rel = os.path.relpath(os.path.join(folder, name), path)
                            os.makedirs(os.path.dirname(os.path.join(target, rel)), exist_ok=True)
                            shutil.copy2(os.path.join(folder, name), os.path.join(target, rel))
                includes.append("${PKG}/include/" + inside)
            else:
                includes.append(include(path))
        # the two list.h the port reads by their full paths
        for path in (os.path.join(self.kernel, "include", "list.h"),
                     os.path.join(self.root, "func", "wpa_supplicant_2_9", "src", "utils", "list.h")):
            target = os.path.join(self.out, "include", mapped(path))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copy2(path, target)
        defines = []
        for define in self.defines():
            for root, name in roots:
                define = define.replace(root + "/", "${PKG}/include/%s/" % name)
            defines.append(define)

        def version_of(folder):
            try:
                with open(os.path.join(folder, "package.json"), encoding="utf-8") as f:
                    return json.load(f)["version"]
            except (OSError, KeyError, ValueError):
                return "?"

        gcc = subprocess.run([self.prefix + "gcc", "-dumpversion"], stdout=subprocess.PIPE,
                             universal_newlines=True).stdout.strip()
        flags = {
            "cflags": CCFLAGS + CFLAGS + GCC14_C,
            "cxxflags": CCFLAGS + CXXFLAGS,
            "asflags": ASFLAGS,
            "defines": defines,
            "includes": includes,
            "linkflags": LINKFLAGS,
            # the archives in the order of the link (the glue first), then the closed libraries and the C libraries
            "libs": ["${PKG}/lib/" + name for name in libs] + ["-L${PKG}/lib"] + ["-l" + name for name in CLOSED]
                    + ["-l" + name for name in SYSTEM],
            "ldscript": "bk7231n_bsp.ld",
            "built": {
                "repository": os.environ.get("GITHUB_SHA") or "local",
                "gcc": gcc,
                "bdk": version_of(self.bdk),
                "freertos_kernel": version_of(self.kernel),
                "lwip": version_of(self.lwip),
                "mbedtls": version_of(self.mbedtls),
            },
        }
        with open(os.path.join(self.out, "flags.json"), "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(flags, indent=1) + "\n")
        with open(os.path.join(self.out, "package.json"), "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps({
                "name": "framework-beken-bdk",
                "version": self.args.version,
                "description": "The BK7231N SDK compiled for ESPurna (igorufox/platform-beken sdk/build.py): BDK 3.0.33, "
                               "FreeRTOS-Kernel %s, lwIP %s, Mbed TLS %s, GCC %s - archives, headers, linker script, "
                               "flags" % (flags["built"]["freertos_kernel"], flags["built"]["lwip"],
                                          flags["built"]["mbedtls"], gcc),
                "license": "Apache-2.0",
                "repository": {"type": "git", "url": "https://github.com/igorufox/platform-beken"},
            }, indent=2) + "\n")

        if self.args.test:
            self.test(flags)

        archive = self.out.rstrip("/\\") + ".zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
            for folder, _, files in os.walk(self.out):
                for name in files:
                    path = os.path.join(folder, name)
                    z.write(path, os.path.relpath(path, self.out).replace(os.sep, "/"))
        print("build.py: %s" % archive)

    def test(self, flags):
        """an image from the package alone: the entry of the BDK, a main of its own and the flash wraps a firmware
        gives (here empty)"""
        def expand(items):
            return [item.replace("${PKG}", posix(self.out)) for item in items]

        work = os.path.join(self.work, "test")
        os.makedirs(work, exist_ok=True)
        source = os.path.join(work, "app.c")
        with open(source, "w", encoding="utf-8") as f:
            f.write("#include <stdint.h>\n"
                    "void app_main(void) {\n}\n"
                    "int __wrap_bk_flash_get_info(void) { return 0; }\n"
                    "int __wrap_bk_flash_erase(void) { return 0; }\n"
                    "int __wrap_bk_flash_write(void) { return 0; }\n"
                    "int __wrap_bk_flash_read(void) { return 0; }\n")
        obj = source + ".o"
        cmd = ([self.prefix + "gcc"] + expand(flags["cflags"]) + ["-D" + d for d in expand(flags["defines"])]
               + ["-I" + i for i in expand(flags["includes"])] + ["-c", source, "-o", obj])
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        if result.returncode:
            raise SystemExit("build.py: test compile\n" + result.stdout)
        elf = os.path.join(work, "app.elf")
        cmd = ([self.prefix + "g++"] + flags["linkflags"] + ["-L" + posix(os.path.join(self.out, "ld")),
               "-T", flags["ldscript"], "-o", elf, obj, "-Wl,--start-group"] + expand(flags["libs"])
               + ["-Wl,--end-group"])
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        if result.returncode:
            sys.stdout.write(result.stdout[-6000:])
            raise SystemExit("build.py: test link failed")
        print("build.py: test %s, %d bytes" % (elf, os.path.getsize(elf)))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    for name in ("bdk", "kernel", "lwip", "mbedtls", "toolchain", "version", "out"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--work", default=os.path.join(HERE, "..", "build-sdk"))
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--test", action="store_true")
    Builder(parser.parse_args()).build()


if __name__ == "__main__":
    main()
