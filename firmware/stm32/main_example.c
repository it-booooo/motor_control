/* Integration example only. Do not compile beside CubeMX-generated main.c. */
#include "motor_control.h"
void application_init(void) { mc_init(); }
void application_serial_byte_received(unsigned char byte) { mc_serial_rx_byte(byte); }
void application_can_frame_received(unsigned long id, const unsigned char data[8]) { mc_can_rx((uint32_t)id, data); }
void application_forever(void)
{
    for (;;)
        mc_poll();
}
