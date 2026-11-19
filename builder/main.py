# ESPurna Beken platform: the program (firmware.elf) of ESPurna's sources with the arm-none-eabi toolchain. The BDK,
# its flags, the linker script: scripts/beken_bdk.py (pre:); the images (RBL, UF2, the .ota head): scripts/beken_image.py

import os

from SCons.Script import AlwaysBuild, Default, DefaultEnvironment

env = DefaultEnvironment()
platform = env.PioPlatform()

env.Replace(PROGNAME="firmware", PROGSUFFIX=".elf")

target_elf = env.BuildProgram()
target_bin = env.Command(
    os.path.join("$BUILD_DIR", "firmware.bin"),
    target_elf,
    env.VerboseAction("$OBJCOPY -O binary $SOURCE $TARGET", "Building $TARGET"),
)

env.AddPlatformTarget(
    "size",
    target_elf,
    env.VerboseAction("$SIZEPRINTCMD", "Calculating size $SOURCE"),
    "Program Size",
)

AlwaysBuild(env.Alias("nobuild", target_bin))
Default([target_bin])
