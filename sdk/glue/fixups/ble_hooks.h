/*

The functions of the BLE stack of the ble module the head's Wi-Fi calls (fixups/ble_off.c): the module sets them when
its stack starts (arch/beken/ble_beken.cpp). C and C++.

*/

#pragma once

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

struct ble_hooks {
    uint8_t (*if_ble_sleep)(void);
    void (*switch_rf_to_wifi)(void);
    void (*rf_wifi_used_set)(void);
    void (*rf_wifi_used_clr)(void);
    void (*ps_recover_ble_switch_mac_status)(void);
};

void ble_hooks_set(const struct ble_hooks*);

#ifdef __cplusplus
}
#endif
