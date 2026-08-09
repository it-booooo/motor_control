# STM32 application protocol v1

所有多位元組欄位皆為 little-endian，float 為 IEEE-754 binary32。每個 serial frame：

```text
magic[2] = A5 5A
version:u8 = 1
type:u8
payload_length:u16
payload
crc32:u32
```

CRC 使用標準 reflected CRC-32（polynomial `0xEDB88320`、初值與最後 XOR
皆為 `0xFFFFFFFF`），計算範圍為 header 加 payload；與 Python `zlib.crc32()` 相容。

## Packet types

### 1 MotorCommand（PC → STM32，36 bytes）

```text
sequence:u32, control_mode:u8, reserved[3], t_host_command_ns:u64,
position_rad:f32, velocity_rads:f32, kp:f32, kd:f32, torque_nm:f32
```

### 2 MotorTelemetry（STM32 → PC，88 bytes）

```text
sequence:u32, t_mcu_us:u64, t_host_command_ns:u64, t_mcu_rx_us:u64,
t_can_tx_us:u64, t_can_rx_us:u64, position_rad:f32, velocity_rads:f32,
current_a:f32, temperature_c:f32, motor_error:u32, can_tx_count:u32,
can_rx_count:u32, can_tx_error:u32, can_rx_error:u32, bus_off_count:u32,
last_error_code:u32
```

### 3 Heartbeat（PC → STM32，16 bytes）

```text
sequence:u32, t_host_ns:u64, last_command_sequence:u32
```

### 4 BackendConfiguration（PC → STM32，40 bytes）

```text
sequence:u32, motor_id:u8, control_mode:u8, motor_profile:u8, reserved:u8,
can_bitrate:u32, command_rate_hz:u32, safe_torque_nm:f32,
safe_current_a:f32, safe_temperature_c:f32, host_watchdog_ms:u32,
motor_command_timeout_ms:u32, can_feedback_timeout_ms:u32
```

目前只接受 `control_mode=1`（MIT）、`motor_profile=1`（AK10-9 V3.0 KV60）、
`can_bitrate=1000000`。配置與 heartbeat 未就緒時，韌體只會送 idle command。
