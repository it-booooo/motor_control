#ifndef PLATFORM_PORT_H
#define PLATFORM_PORT_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

uint64_t platform_time_us(void);
bool platform_serial_write(const uint8_t *data, size_t length);
bool platform_can_send_extended(uint32_t extended_id, const uint8_t data[8]);
void platform_can_reconfigure(uint32_t bitrate);
void platform_emergency_output(bool asserted);

#endif
