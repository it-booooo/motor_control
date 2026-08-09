#include "protocol.h"
#include <assert.h>
#include <string.h>

static int calls;
static void received(uint8_t type, const uint8_t *payload, uint16_t length, void *context)
{
    (void)context;
    assert(type == PACKET_HEARTBEAT);
    assert(length == 3);
    assert(payload[0] == 1 && payload[1] == 2 && payload[2] == 3);
    calls++;
}
int main(void)
{
    static const uint8_t check[] = "123456789";
    uint8_t frame[PROTOCOL_MAX_FRAME];
    protocol_parser_t parser;
    size_t n, i;
    assert(protocol_crc32(check, 9) == 0xCBF43926u);
    n = protocol_build_frame(PACKET_HEARTBEAT, (const uint8_t *)"\x01\x02\x03", 3, frame, sizeof(frame));
    assert(n == 13);
    protocol_parser_init(&parser);
    protocol_parser_feed(&parser, 0x00, received, 0);
    for (i = 0; i < n; i++)
        protocol_parser_feed(&parser, frame[i], received, 0);
    assert(calls == 1);
    return 0;
}
