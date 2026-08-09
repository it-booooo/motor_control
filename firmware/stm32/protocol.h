#ifndef STM32_PROTOCOL_H
#define STM32_PROTOCOL_H

#include <stddef.h>
#include <stdint.h>

#define PROTOCOL_MAGIC_0 0xA5u
#define PROTOCOL_MAGIC_1 0x5Au
#define PROTOCOL_VERSION 1u
#define PROTOCOL_MAX_PAYLOAD 96u
#define PROTOCOL_MAX_FRAME (6u + PROTOCOL_MAX_PAYLOAD + 4u)

enum protocol_packet_type
{
    PACKET_MOTOR_COMMAND = 1,
    PACKET_MOTOR_TELEMETRY = 2,
    PACKET_HEARTBEAT = 3,
    PACKET_CONFIGURATION = 4
};

typedef struct
{
    uint8_t bytes[PROTOCOL_MAX_FRAME];
    size_t length;
    size_t expected;
} protocol_parser_t;

typedef void (*protocol_frame_callback_t)(uint8_t type, const uint8_t *payload,
                                          uint16_t payload_length, void *context);

void protocol_parser_init(protocol_parser_t *parser);
void protocol_parser_feed(protocol_parser_t *parser, uint8_t byte,
                          protocol_frame_callback_t callback, void *context);
uint32_t protocol_crc32(const uint8_t *data, size_t length);
size_t protocol_build_frame(uint8_t type, const uint8_t *payload,
                            uint16_t payload_length, uint8_t *output, size_t output_capacity);
uint16_t protocol_read_u16(const uint8_t *p);
uint32_t protocol_read_u32(const uint8_t *p);
uint64_t protocol_read_u64(const uint8_t *p);
float protocol_read_f32(const uint8_t *p);
void protocol_write_u16(uint8_t *p, uint16_t value);
void protocol_write_u32(uint8_t *p, uint32_t value);
void protocol_write_u64(uint8_t *p, uint64_t value);
void protocol_write_f32(uint8_t *p, float value);

#endif
