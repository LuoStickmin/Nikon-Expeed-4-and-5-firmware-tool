/*
 * K8 solver for Nikon Expeed 4/5 packaging-B DSLR containers.
 * See docs/k8-dslr.md.
 *
 * Model: K8 = raw[8] XOR keystream(T1[index], step)
 *   value = T1[index]; inc = 0x160*step
 *   repeat 8: value = (value + inc) & 0xFF; inc += step; out = value
 *
 * raw defaults to the shared 0x10000080 constant D319A081BBF520EF.
 * SHA-1 is finalised as SHA1(container[0x20:] || K8) == container[0:20].
 * The body is hashed once; only the tail (rem bytes + 8 key bytes) is
 * re-finalised per candidate.
 *
 * usage: k8_solve <firmware> <t1.bin> [raw-hex] [body-offset]
 */
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

static uint32_t rol(uint32_t v, int n) { return (v << n) | (v >> (32 - n)); }

static void sha1_block(uint32_t *h, const uint8_t *p)
{
    uint32_t w[80];
    int i;
    for (i = 0; i < 16; i++)
        w[i] = ((uint32_t)p[i * 4] << 24) | ((uint32_t)p[i * 4 + 1] << 16) |
               ((uint32_t)p[i * 4 + 2] << 8) | (uint32_t)p[i * 4 + 3];
    for (i = 16; i < 80; i++)
        w[i] = rol(w[i - 3] ^ w[i - 8] ^ w[i - 14] ^ w[i - 16], 1);

    uint32_t a = h[0], b = h[1], c = h[2], d = h[3], e = h[4];
    for (i = 0; i < 80; i++) {
        uint32_t f, k;
        if (i < 20)      { f = (b & c) | (~b & d);           k = 0x5A827999; }
        else if (i < 40) { f = b ^ c ^ d;                    k = 0x6ED9EBA1; }
        else if (i < 60) { f = (b & c) | (b & d) | (c & d);   k = 0x8F1BBCDC; }
        else             { f = b ^ c ^ d;                    k = 0xCA62C1D6; }
        uint32_t t = rol(a, 5) + f + e + k + w[i];
        e = d; d = c; c = rol(b, 30); b = a; a = t;
    }
    h[0] += a; h[1] += b; h[2] += c; h[3] += d; h[4] += e;
}

static void digest_from(const uint32_t *state, const uint8_t *rem, size_t rem_len,
                        const uint8_t *k8, uint64_t total_len, uint8_t out[20])
{
    uint32_t h[5];
    uint8_t buf[128];
    size_t n = 0;
    memcpy(h, state, sizeof h);
    memcpy(buf, rem, rem_len);
    n = rem_len;
    memcpy(buf + n, k8, 8);
    n += 8;
    uint64_t bits = (total_len + 8) * 8;
    buf[n++] = 0x80;
    while (n % 64 != 56) buf[n++] = 0;
    for (int i = 0; i < 8; i++) buf[n++] = (uint8_t)(bits >> (56 - 8 * i));
    for (size_t i = 0; i < n; i += 64) sha1_block(h, buf + i);
    for (int i = 0; i < 5; i++) {
        out[i * 4 + 0] = (uint8_t)(h[i] >> 24);
        out[i * 4 + 1] = (uint8_t)(h[i] >> 16);
        out[i * 4 + 2] = (uint8_t)(h[i] >> 8);
        out[i * 4 + 3] = (uint8_t)h[i];
    }
}

static uint8_t *read_file(const char *path, size_t *len)
{
    FILE *f = fopen(path, "rb");
    if (!f) { perror(path); exit(2); }
    fseek(f, 0, SEEK_END);
    long n = ftell(f);
    fseek(f, 0, SEEK_SET);
    uint8_t *p = malloc((size_t)n);
    if (!p || fread(p, 1, (size_t)n, f) != (size_t)n) { perror("read"); exit(2); }
    fclose(f);
    *len = (size_t)n;
    return p;
}

static int hexval(unsigned char c)
{
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

int main(int argc, char **argv)
{
    if (argc < 3) { fprintf(stderr, "usage: %s <firmware> <t1.bin> [raw-hex] [body-offset]\n", argv[0]); return 2; }
    size_t flen, tlen;
    uint8_t *fw = read_file(argv[1], &flen);
    uint8_t *t1 = read_file(argv[2], &tlen);
    if (tlen != 256) {
        /* accept a 256-byte table or its 512-hex-char text form */
        uint8_t *dec = malloc(256);
        int ok = (tlen >= 512);
        for (int i = 0; ok && i < 256; i++) {
            int hi = hexval(t1[2 * i]), lo = hexval(t1[2 * i + 1]);
            if (hi < 0 || lo < 0) ok = 0;
            else dec[i] = (uint8_t)((hi << 4) | lo);
        }
        if (!ok) { fprintf(stderr, "%s is neither 256 raw bytes nor 256 hex bytes\n", argv[2]); return 2; }
        t1 = dec;
        tlen = 256;
    }
    if (flen < 0x40) { fprintf(stderr, "firmware too short\n"); return 2; }

    static uint8_t RAW[8] = {0xD3, 0x19, 0xA0, 0x81, 0xBB, 0xF5, 0x20, 0xEF};
    if (argc >= 4) {
        const char *h = argv[3];
        if (strlen(h) != 16) { fprintf(stderr, "raw must be 16 hex chars\n"); return 2; }
        for (int i = 0; i < 8; i++) {
            unsigned v; if (sscanf(h + 2 * i, "%2x", &v) != 1) return 2;
            RAW[i] = (uint8_t)v;
        }
    }

    size_t body_off = 0x20;
    if (argc >= 5) body_off = (size_t)strtoul(argv[4], NULL, 0);
    if (flen <= body_off + 8) { fprintf(stderr, "firmware too short\n"); return 2; }

    const uint8_t *body = fw + body_off;
    size_t blen = flen - body_off;
    size_t full = blen / 64;
    const uint8_t *rem = body + full * 64;
    size_t rem_len = blen - full * 64;

    uint32_t st[5] = {0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476, 0xC3D2E1F0};
    for (size_t i = 0; i < full; i++) sha1_block(st, body + i * 64);

    uint8_t digest[20];
    printf("firmware  %s (%zu bytes, body %zu, rem %zu)\n", argv[1], flen, blen, rem_len);
    printf("header    ");
    for (int i = 0; i < 20; i++) printf("%02x", fw[i]);
    printf("\n");

    int hits = 0;
    for (int index = 0; index < 256; index++) {
        for (int s = 0; s < 256; s++) {
            uint8_t step = (uint8_t)s;
            uint8_t k8[8];
            int v = t1[index];
            int inc = 0x160 * step;
            for (int j = 0; j < 8; j++) {
                v = (v + inc) & 0xFF;
                inc += step;
                k8[j] = (uint8_t)v;
            }
            for (int j = 0; j < 8; j++) k8[j] ^= RAW[j];
            digest_from(st, rem, rem_len, k8, blen, digest);
            if (memcmp(digest, fw, 20) == 0) {
                hits++;
                printf("MATCH index=%02X step=%02X K8=", index, step);
                for (int j = 0; j < 8; j++) printf("%02X", k8[j]);
                printf("\n");
            }
        }
    }
    printf("matches: %d\n", hits);
    return hits ? 0 : 1;
}
