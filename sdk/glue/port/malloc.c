/*

malloc() and friends of newlib on the FreeRTOS heap of the BDK (-Wl,-wrap of sdk/build.py), as LibreTiny's
fixups/malloc.c (MIT, Kuba Szczodrzyński). realloc() as LibreTiny's for the BK72xx (LT_REMALLOC 1): a new block, the copy,
the old one freed - what the boards ran with until now

*/

#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include <FreeRTOS.h>

static void* remalloc(void* ptr, size_t size) {
    void* out = pvPortMalloc(size);
    if (out && ptr) {
        memcpy(out, ptr, size);
        vPortFree(ptr);
    }

    return out;
}

void* __wrap_malloc(size_t size) {
    return pvPortMalloc(size);
}

void* __wrap_calloc(size_t num, size_t size) {
    if ((num == 0) || (size == 0)) {
        num = size = 1;
    }

    void* ptr = pvPortMalloc(num * size);
    if (ptr) {
        memset(ptr, 0, num * size);
    }

    return ptr;
}

void* __wrap_zalloc(size_t size) {
    return __wrap_calloc(1, size);
}

void* __wrap_realloc(void* ptr, size_t size) {
    return remalloc(ptr, size);
}

void __wrap_free(void* ptr) {
    vPortFree(ptr);
}

// mind the 'reent': no linker aliases
void* __wrap__malloc_r(void* reent, size_t size) {
    (void)reent;
    return pvPortMalloc(size);
}

void* __wrap__calloc_r(void* reent, size_t num, size_t size) {
    (void)reent;
    return __wrap_calloc(num, size);
}

void* __wrap__realloc_r(void* reent, void* ptr, size_t size) {
    (void)reent;
    return remalloc(ptr, size);
}

void __wrap__free_r(void* reent, void* ptr) {
    (void)reent;
    vPortFree(ptr);
}
