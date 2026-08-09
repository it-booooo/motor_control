#include "protocol.h"
#include <string.h>

uint16_t protocol_read_u16(const uint8_t *p) { return (uint16_t)p[0] | ((uint16_t)p[1] << 8); }
uint32_t protocol_read_u32(const uint8_t *p) { return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24); }
uint64_t protocol_read_u64(const uint8_t *p) { return (uint64_t)protocol_read_u32(p) | ((uint64_t)protocol_read_u32(p + 4) << 32); }
float protocol_read_f32(const uint8_t *p)
{
    uint32_t raw = protocol_read_u32(p);
    float value;
    memcpy(&value, &raw, 4);
    return value;
}
void protocol_write_u16(uint8_t *p, uint16_t v)
{
    p[0] = (uint8_t)v;
    p[1] = (uint8_t)(v >> 8);
}
void protocol_write_u32(uint8_t *p, uint32_t v)
{
    p[0] = (uint8_t)v;
    p[1] = (uint8_t)(v >> 8);
    p[2] = (uint8_t)(v >> 16);
    p[3] = (uint8_t)(v >> 24);
}
void protocol_write_u64(uint8_t *p, uint64_t v)
{
    protocol_write_u32(p, (uint32_t)v);
    protocol_write_u32(p + 4, (uint32_t)(v >> 32));
}
void protocol_write_f32(uint8_t *p, float v)
{
    uint32_t raw;
    memcpy(&raw, &v, 4);
    protocol_write_u32(p, raw);
}

uint32_t protocol_crc32(const uint8_t *data, size_t length)
{
    uint32_t crc = 0xFFFFFFFFu;
    size_t i;
    unsigned bit;
    for (i = 0; i < length; i++)
    {
        crc ^= data[i];
        for (bit = 0; bit < 8; bit++)
            crc = (crc >> 1) ^ (0xEDB88320u & (0u - (crc & 1u)));
    }
    return crc ^ 0xFFFFFFFFu;
}

void protocol_parser_init(protocol_parser_t *p) { memset(p, 0, sizeof(*p)); }
static void resync(protocol_parser_t *p)
{
    size_t i;
    for (i = 1; i + 1 < p->length; i++)
        if (p->bytes[i] == PROTOCOL_MAGIC_0 && p->bytes[i + 1] == PROTOCOL_MAGIC_1)
        {
            memmove(p->bytes, p->bytes + i, p->length - i);
            p->length -= i;
            p->expected = 0;
            return;
        }
    if (p->length && p->bytes[p->length - 1] == PROTOCOL_MAGIC_0)
    {
        p->bytes[0] = PROTOCOL_MAGIC_0;
        p->length = 1;
    }
    else
        p->length = 0;
    p->expected = 0;
}
void protocol_parser_feed(protocol_parser_t *p, uint8_t b, protocol_frame_callback_t cb, void *ctx)
{
    uint16_t n;
    uint32_t crc;
    if (p->length == 0 && b != PROTOCOL_MAGIC_0)
        return;
    if (p->length == 1 && b != PROTOCOL_MAGIC_1)
    {
        p->length = (b == PROTOCOL_MAGIC_0) ? 1u : 0u;
        return;
    }
    if (p->length >= sizeof(p->bytes))
        resync(p);
    p->bytes[p->length++] = b;
    if (p->length == 6)
    {
        n = protocol_read_u16(p->bytes + 4);
        if (p->bytes[2] != PROTOCOL_VERSION || n > PROTOCOL_MAX_PAYLOAD)
        {
            resync(p);
            return;
        }
        p->expected = 6u + n + 4u;
    }
    if (p->expected && p->length == p->expected)
    {
        n = protocol_read_u16(p->bytes + 4);
        crc = protocol_read_u32(p->bytes + 6 + n);
        if (protocol_crc32(p->bytes, 6u + n) == crc)
        {
            cb(p->bytes[3], p->bytes + 6, n, ctx);
            p->length = 0;
            p->expected = 0;
        }
        else
            resync(p);
    }
}
size_t protocol_build_frame(uint8_t type, const uint8_t *payload, uint16_t n, uint8_t *out, size_t cap)
{
    size_t total = 6u + n + 4u;
    if (n > PROTOCOL_MAX_PAYLOAD || cap < total)
        return 0;
    out[0] = PROTOCOL_MAGIC_0;
    out[1] = PROTOCOL_MAGIC_1;
    out[2] = PROTOCOL_VERSION;
    out[3] = type;
    protocol_write_u16(out + 4, n);
    if (n)
        memcpy(out + 6, payload, n);
    protocol_write_u32(out + 6 + n, protocol_crc32(out, 6u + n));
    return total;
}
