/*

The BLE of the head: the BLE 5.x stack of the BDK is an object of the ble module (sdk/build.py, its BLE
block; arch/beken/ble_beken.cpp), the head only answers for it. The head's BDK is built with CFG_SUPPORT_BLE 1
(config/sys_config.h): the coexistence of its Wi-Fi with the BLE (power_save.c, mcu_ps.c, sys_ctrl.c with
CFG_USE_BLE_PS, the closed librwnx: td.c, me_task.c) asks the BLE whether it sleeps and holds the RF.

Every name the head calls is here: the answers of a BLE that always sleeps and never holds the RF while no module
set the hooks (ble_hooks_set()), the functions of the module's stack after. The module's stack objects are built
with those names renamed (bk_stack_*, beken_bdk.py): its link finds its own functions, not these.

ble_switch_mac_sleeped is the one variable of the head the Wi-Fi reads directly; the module's stack (ble_rf_port.c,
a tentative definition built with -fcommon) writes this one.

*/

#include <stddef.h>
#include <stdint.h>

#include "ble_hooks.h"

uint8_t ble_switch_mac_sleeped = 0;

static const struct ble_hooks* hooks = NULL;

void ble_hooks_set(const struct ble_hooks* value) {
    hooks = value;
}

// app.c (app_pre_start) and the device table of dd.c start the BLE at boot: the module does that when it starts
void ble_entry(void) {
}

void ble_init(void) {
}

void ble_exit(void) {
}

uint8_t if_ble_sleep(void) {
    return hooks ? hooks->if_ble_sleep() : 1;
}

void ble_switch_rf_to_wifi(void) {
    if (hooks) {
        hooks->switch_rf_to_wifi();
    }
}

void rf_wifi_used_set(void) {
    if (hooks) {
        hooks->rf_wifi_used_set();
    }
}

void rf_wifi_used_clr(void) {
    if (hooks) {
        hooks->rf_wifi_used_clr();
    }
}

void ps_recover_ble_switch_mac_status(void) {
    if (hooks) {
        hooks->ps_recover_ble_switch_mac_status();
    }
}
