# STM32 application protocol v1

Multi-byte values are little-endian. Every packet is:

```text
magic[2] = A5 5A
version:u8 = 1
type:u8
payload_length:u16
payload
crc32:u32  # CRC over header + payload
```

## Packet types

### 1 MotorCommand

```text
sequence:u32
control_mode:u8
reserved[3]
t_host_command_ns:u64
position_rad:f32
velocity_rads:f32
kp:f32
kd:f32
torque_nm:f32
```

### 2 MotorTelemetry

```text
sequence:u32
t_mcu_us:u64
t_host_command_ns:u64
t_mcu_rx_us:u64
t_can_tx_us:u64
t_can_rx_us:u64
position_rad:f32
velocity_rads:f32
current_a:f32
temperature_c:f32
motor_error:u32
can_tx_count:u32
can_rx_count:u32
can_tx_error:u32
can_rx_error:u32
bus_off_count:u32
last_error_code:u32
```

Unknown unsigned values use all bits set. MotorTelemetry contains only feedback produced by the motor/CAN path.

### 3 Heartbeat

```text
sequence:u32
t_host_ns:u64
last_command_sequence:u32
```

### 4 BackendConfiguration

```text
sequence:u32
motor_id:u8
control_mode:u8
motor_profile:u8
reserved:u8
can_bitrate:u32
command_rate_hz:u32
safe_torque_nm:f32
safe_current_a:f32
safe_temperature_c:f32
host_watchdog_ms:u32
motor_command_timeout_ms:u32
can_feedback_timeout_ms:u32
```

## Timing

- MCU queue/encode delay: `t_can_tx_us - t_mcu_rx_us`
- CAN response delay: `t_can_rx_us - t_can_tx_us`

Host and MCU clocks must not be subtracted unless they are explicitly synchronized.

## Safety behavior

STM32 must command Motor Idle when heartbeat, motor command, or CAN feedback exceeds its configured timeout. It must also reject commands beyond configured motor safety limits. Software behavior does not replace a hardware emergency stop.
