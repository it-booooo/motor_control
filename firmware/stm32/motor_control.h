#ifndef MOTOR_CONTROL_H
#define MOTOR_CONTROL_H
#include <stdint.h>
void mc_init(void);
void mc_serial_rx_byte(uint8_t byte);
void mc_can_rx(uint32_t extended_id, const uint8_t data[8]);
void mc_can_error(uint32_t error_code, int bus_off);
void mc_poll(void);
#endif
