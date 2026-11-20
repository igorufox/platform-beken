/*
 * The configuration of mbedTLS 3.6.6 on the BK7231N (MBEDTLS_CONFIG_FILE "tls_config.h" of sdk/build.py; this
 * folder is before the BDK's on the include path). One mbedTLS on the three chips (owner 2026-11-17, code/libraries.ini):
 * the package framework-mbedtls replaces the BDK's 2.6.0, so the BDK's 2.x config (mbedtls-port/inc/tls_config.h) is
 * not used any more; this is it in 3.x names, the same choices: the TLS 1.2 client of ESPurna (libs/tls_mbedtls.h,
 * module tls), RSA key exchange, P-256 / P-384 certificates, the hashes of libs/hash.h.
 * The BK7231N's Wi-Fi supplicant (libsupplicant_bk7231n.a, closed) has no mbedtls calls and no SAE: nothing of WPA
 * goes through here.
 */

#ifndef ESPURNA_BEKEN_TLS_CONFIG_H
#define ESPURNA_BEKEN_TLS_CONFIG_H

#include <stddef.h>

/* --- system: the BDK's heap (bdk/port/mbedtls_beken.c), the TRNG of the chip (core_beken.cpp) ------------------- */

#define MBEDTLS_PLATFORM_C
#define MBEDTLS_PLATFORM_MEMORY
void *tls_mbedtls_mem_calloc(size_t n, size_t size);
void tls_mbedtls_mem_free(void *ptr);
#define MBEDTLS_PLATFORM_STD_CALLOC tls_mbedtls_mem_calloc
#define MBEDTLS_PLATFORM_STD_FREE   tls_mbedtls_mem_free

#define MBEDTLS_HAVE_ASM
#define MBEDTLS_ENTROPY_HARDWARE_ALT
#define MBEDTLS_NO_PLATFORM_ENTROPY
/* (the glue of LibreTiny: more entropy sources than the BDK's 2) */
#define MBEDTLS_ENTROPY_MAX_SOURCES 10

/* --- sizes of the BDK's config ----------------------------------------------------------------------------------- */

#define MBEDTLS_MPI_MAX_SIZE        384
#define MBEDTLS_MPI_WINDOW_SIZE     2
#define MBEDTLS_ECP_WINDOW_SIZE     2
#define MBEDTLS_ECP_FIXED_POINT_OPTIM 0
#define MBEDTLS_AES_ROM_TABLES

/* the BDK's 2.6 grew the record buffers by need (its MBEDTLS_SSL_DYNAMIC_CONTENT_LEN patch); 3.x: full buffers for
 * the handshake, cut to the negotiated record size after it */
#define MBEDTLS_SSL_VARIABLE_BUFFER_LENGTH
/* the buffer sizes of the ESP8266 (its sdkconfig): a whole record in, 4 KB records out */
#define MBEDTLS_SSL_IN_CONTENT_LEN  16384
#define MBEDTLS_SSL_OUT_CONTENT_LEN 4096

/* --- ciphers, curves, key exchange ------------------------------------------------------------------------------- */

#define MBEDTLS_CIPHER_MODE_CBC
#define MBEDTLS_ECP_DP_SECP256R1_ENABLED
#define MBEDTLS_ECP_DP_SECP384R1_ENABLED
#define MBEDTLS_ECP_NIST_OPTIM
#define MBEDTLS_KEY_EXCHANGE_RSA_ENABLED
#define MBEDTLS_PKCS1_V15

/* --- TLS 1.2 (3.x has no TLS 1.0 / 1.1) -------------------------------------------------------------------------- */

#define MBEDTLS_SSL_PROTO_TLS1_2
#define MBEDTLS_SSL_MAX_FRAGMENT_LENGTH
#define MBEDTLS_SSL_SERVER_NAME_INDICATION
#define MBEDTLS_SSL_KEEP_PEER_CERTIFICATE

/* --- modules ----------------------------------------------------------------------------------------------------- */

#define MBEDTLS_AES_C
#define MBEDTLS_ASN1_PARSE_C
#define MBEDTLS_ASN1_WRITE_C
#define MBEDTLS_BASE64_C
#define MBEDTLS_BIGNUM_C
#define MBEDTLS_CIPHER_C
#define MBEDTLS_CTR_DRBG_C
#define MBEDTLS_ECP_C
#define MBEDTLS_ENTROPY_C
#define MBEDTLS_MD_C
#define MBEDTLS_MD5_C
#define MBEDTLS_OID_C
#define MBEDTLS_PEM_PARSE_C
#define MBEDTLS_PK_C
#define MBEDTLS_PK_PARSE_C
#define MBEDTLS_RSA_C
#define MBEDTLS_SHA1_C
#define MBEDTLS_SHA224_C
#define MBEDTLS_SHA256_C
#define MBEDTLS_SSL_CLI_C
#define MBEDTLS_SSL_TLS_C
#define MBEDTLS_X509_CRT_PARSE_C
#define MBEDTLS_X509_USE_C

/* --- Matter: what the Matter library asks for (its matter_requirements.h; owner 2026-11-19: the parts only Matter
 * uses link into the matter module, the head keeps what it calls itself). PASE / CASE on P-256, session keys (HKDF,
 * AES-CCM), the DRBGs of its crypto layer, the CSR of the operational certificate. ECDSA_C also lets the head's TLS
 * verify ECDSA-signed certificates (pk). */
#define MBEDTLS_CCM_C
#define MBEDTLS_CIPHER_MODE_CTR
#define MBEDTLS_ECDH_C
#define MBEDTLS_ECDSA_C
#define MBEDTLS_ECDSA_DETERMINISTIC
#define MBEDTLS_HKDF_C
#define MBEDTLS_HMAC_DRBG_C
#define MBEDTLS_PKCS5_C
#define MBEDTLS_PK_WRITE_C
#define MBEDTLS_X509_CREATE_C
#define MBEDTLS_X509_CSR_PARSE_C
#define MBEDTLS_X509_CSR_WRITE_C

#endif /* ESPURNA_BEKEN_TLS_CONFIG_H */
