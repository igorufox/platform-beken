/*
 * The port of mbedTLS 3.6.6 to the BDK (bdk/config/tls_config.h): its heap, what the BDK's mbedtls-port/src/tls_mem.c
 * was for its 2.6.0 (that one includes the 2.x config.h; the rest of that port, the BDK's own TLS client and sockets,
 * nothing calls). The entropy source, its tls_hardware.c, is the chip's TRNG in core_beken.cpp.
 */

#include <stddef.h>
#include <stdlib.h>

#include "mem_pub.h"

void *tls_mbedtls_mem_calloc(size_t n, size_t size)
{
    const size_t len = n * size;
    if (!len || ((len / n) != size)) {
        return NULL;
    }

    return os_zalloc(len);
}

void tls_mbedtls_mem_free(void *ptr)
{
    os_free(ptr);
}

/* MBEDTLS_ENTROPY_HARDWARE_ALT: mbedtls_hardware_poll() is the TRNG of the chip, arch/beken/core_beken.cpp */
