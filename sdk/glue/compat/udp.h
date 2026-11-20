// the BDK includes <udp.h>: lwIP's (as LibreTiny's compat/udp.h, MIT, Kuba Szczodrzynski)
#pragma once
#include <lwip/udp.h>

// only wifi_simple_config.c includes it, it calls lwip_ntohl without parentheses (the macro of lwip/def.h does not apply)
#undef lwip_ntohl
#define lwip_ntohl lwip_htonl
