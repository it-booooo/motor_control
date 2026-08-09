#include "motor_control.h"
#include "platform_port.h"
#include "protocol.h"
#include <math.h>
#include <stdbool.h>
#include <string.h>

#define CMD_SIZE 36u
#define HEARTBEAT_SIZE 16u
#define CONFIG_SIZE 40u
#define TELEMETRY_SIZE 88u
#define MIT_MODE 1u
#define AK10_PROFILE 1u
#define MIT_MODE_ID 0x08u

typedef struct
{
    uint32_t sequence;
    uint64_t host_ns;
    float p, v, kp, kd, t;
} command_t;
typedef struct
{
    uint8_t motor_id;
    uint32_t rate_hz;
    float torque_limit, current_limit, temp_limit;
    uint32_t heartbeat_ms, command_ms, feedback_ms;
} config_t;
static protocol_parser_t parser;
static config_t cfg;
static command_t command;
static bool configured, have_command, have_feedback, fault_latched;
static uint64_t last_heartbeat_us, last_command_us, last_feedback_us, last_can_tx_us, first_can_tx_us, next_can_tx_us;
static float fb_p, fb_v, fb_i, fb_temp;
static uint32_t motor_error, tx_count, rx_count, tx_error, rx_error, bus_off_count, last_error, telemetry_seq;

static uint32_t float_to_uint(float x, float lo, float hi, unsigned bits)
{
    uint32_t max = (1u << bits) - 1u;
    if (x < lo)
        x = lo;
    if (x > hi)
        x = hi;
    return (uint32_t)lroundf((x - lo) * (float)max / (hi - lo));
}
static void encode_mit(uint8_t d[8], const command_t *c)
{
    uint32_t p = float_to_uint(c->p, -12.56f, 12.56f, 16), v = float_to_uint(c->v, -33, 33, 12), kp = float_to_uint(c->kp, 0, 500, 12), kd = float_to_uint(c->kd, 0, 5, 12), t = float_to_uint(c->t, -65, 65, 12);
    d[0] = (uint8_t)(kp >> 4);
    d[1] = (uint8_t)((kp << 4) | (kd >> 8));
    d[2] = (uint8_t)kd;
    d[3] = (uint8_t)(p >> 8);
    d[4] = (uint8_t)p;
    d[5] = (uint8_t)(v >> 4);
    d[6] = (uint8_t)((v << 4) | (t >> 8));
    d[7] = (uint8_t)t;
}
static bool timed_out(uint64_t now, uint64_t then, uint32_t ms) { return then == 0 || now - then > (uint64_t)ms * 1000u; }
static bool safe_to_drive(uint64_t now)
{
    if (!configured || !have_command || fault_latched)
        return false;
    if (timed_out(now, last_heartbeat_us, cfg.heartbeat_ms) || timed_out(now, last_command_us, cfg.command_ms))
        return false;
    if (have_feedback && timed_out(now, last_feedback_us, cfg.feedback_ms))
        return false;
    if (!have_feedback && first_can_tx_us && timed_out(now, first_can_tx_us, cfg.feedback_ms))
        return false;
    return fabsf(command.t) <= cfg.torque_limit;
}
static void send_telemetry(uint64_t now)
{
    uint8_t p[TELEMETRY_SIZE] = {0}, frame[PROTOCOL_MAX_FRAME];
    size_t n;
    protocol_write_u32(p, telemetry_seq++);
    protocol_write_u64(p + 4, now);
    protocol_write_u64(p + 12, command.host_ns);
    protocol_write_u64(p + 20, last_command_us);
    protocol_write_u64(p + 28, last_can_tx_us);
    protocol_write_u64(p + 36, last_feedback_us);
    protocol_write_f32(p + 44, fb_p);
    protocol_write_f32(p + 48, fb_v);
    protocol_write_f32(p + 52, fb_i);
    protocol_write_f32(p + 56, fb_temp);
    protocol_write_u32(p + 60, motor_error);
    protocol_write_u32(p + 64, tx_count);
    protocol_write_u32(p + 68, rx_count);
    protocol_write_u32(p + 72, tx_error);
    protocol_write_u32(p + 76, rx_error);
    protocol_write_u32(p + 80, bus_off_count);
    protocol_write_u32(p + 84, last_error);
    n = protocol_build_frame(PACKET_MOTOR_TELEMETRY, p, sizeof(p), frame, sizeof(frame));
    if (n)
        (void)platform_serial_write(frame, n);
}
static void on_frame(uint8_t type, const uint8_t *p, uint16_t n, void *ctx)
{
    uint64_t now = platform_time_us();
    (void)ctx;
    if (type == PACKET_HEARTBEAT && n == HEARTBEAT_SIZE)
    {
        last_heartbeat_us = now;
        return;
    }
    if (type == PACKET_MOTOR_COMMAND && n == CMD_SIZE && p[4] == MIT_MODE)
    {
        command.sequence = protocol_read_u32(p);
        command.host_ns = protocol_read_u64(p + 8);
        command.p = protocol_read_f32(p + 16);
        command.v = protocol_read_f32(p + 20);
        command.kp = protocol_read_f32(p + 24);
        command.kd = protocol_read_f32(p + 28);
        command.t = protocol_read_f32(p + 32);
        have_command = true;
        last_command_us = now;
        if (!isfinite(command.p) || !isfinite(command.v) || !isfinite(command.kp) || !isfinite(command.kd) || !isfinite(command.t) || !configured || fabsf(command.t) > cfg.torque_limit)
        {
            fault_latched = true;
            last_error = 1;
        }
        return;
    }
    if (type == PACKET_CONFIGURATION && n == CONFIG_SIZE && p[5] == MIT_MODE && p[6] == AK10_PROFILE && protocol_read_u32(p + 8) == 1000000u)
    {
        cfg.motor_id = p[4];
        cfg.rate_hz = protocol_read_u32(p + 12);
        cfg.torque_limit = protocol_read_f32(p + 16);
        cfg.current_limit = protocol_read_f32(p + 20);
        cfg.temp_limit = protocol_read_f32(p + 24);
        cfg.heartbeat_ms = protocol_read_u32(p + 28);
        cfg.command_ms = protocol_read_u32(p + 32);
        cfg.feedback_ms = protocol_read_u32(p + 36);
        if (cfg.motor_id <= 55 && cfg.rate_hz >= 1 && cfg.rate_hz <= 1000 && cfg.torque_limit > 0 && cfg.current_limit > 0 && cfg.temp_limit > 0 && cfg.heartbeat_ms && cfg.command_ms && cfg.feedback_ms)
        {
            configured = true;
            fault_latched = false;
            platform_emergency_output(false);
            platform_can_reconfigure(1000000u);
        }
    }
}
void mc_init(void)
{
    memset(&cfg, 0, sizeof(cfg));
    memset(&command, 0, sizeof(command));
    protocol_parser_init(&parser);
    configured = have_command = have_feedback = fault_latched = false;
    first_can_tx_us = 0;
    next_can_tx_us = platform_time_us();
}
void mc_serial_rx_byte(uint8_t b) { protocol_parser_feed(&parser, b, on_frame, 0); }
void mc_can_rx(uint32_t id, const uint8_t d[8])
{
    int16_t pos, speed, current;
    if (!configured || id != cfg.motor_id)
        return;
    pos = (int16_t)(((uint16_t)d[0] << 8) | d[1]);
    speed = (int16_t)(((uint16_t)d[2] << 8) | d[3]);
    current = (int16_t)(((uint16_t)d[4] << 8) | d[5]);
    fb_p = (float)pos * 0.1f * 0.01745329252f;
    fb_v = (float)speed * 10.0f / 21.0f / 9.0f * 0.1047197551f;
    fb_i = (float)current * 0.01f;
    fb_temp = (float)(int8_t)d[6];
    motor_error = d[7];
    last_feedback_us = platform_time_us();
    have_feedback = true;
    rx_count++;
    if (motor_error || fabsf(fb_i) > cfg.current_limit || fb_temp > cfg.temp_limit)
    {
        fault_latched = true;
        last_error = motor_error ? motor_error : 2u;
        platform_emergency_output(true);
    }
    send_telemetry(last_feedback_us);
}
void mc_can_error(uint32_t error_code, int bus_off)
{
    rx_error++;
    last_error = error_code;
    if (bus_off)
    {
        bus_off_count++;
        fault_latched = true;
    }
}
void mc_poll(void)
{
    uint64_t now = platform_time_us();
    uint32_t period;
    command_t out = command;
    uint8_t d[8];
    if (!configured)
        return;
    period = 1000000u / cfg.rate_hz;
    if (now < next_can_tx_us)
        return;
    next_can_tx_us = now + period;
    if (!safe_to_drive(now))
        memset(&out, 0, sizeof(out));
    encode_mit(d, &out);
    last_can_tx_us = now;
    if (!first_can_tx_us)
        first_can_tx_us = now;
    if (platform_can_send_extended(((uint32_t)MIT_MODE_ID << 8) | cfg.motor_id, d))
        tx_count++;
    else
        tx_error++;
}
