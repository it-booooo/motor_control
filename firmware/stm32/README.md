# STM32 通用韌體核心（第一版）

這個目錄放置與 STM32 型號無關的馬達通訊核心。它已包含：

- PC serial packet 的 framing、CRC32 與串流重新同步
- AK10-9 V3.0 KV60 MIT command 編碼及 feedback 解碼
- 200 Hz 固定頻率 CAN command
- heartbeat、motor command、CAN feedback timeout
- torque、current、temperature 軟體保護
- MotorTelemetry 回傳

它刻意不直接 include `stm32xxxx_hal.h`。未知晶片型號時，CAN/FDCAN、UART/USB
CDC、timer 與腳位無法正確決定；這些差異全部收斂在 `platform_port.h` 的五個函式。

## 檔案

| 檔案 | 用途 |
|---|---|
| `protocol.h/.c` | PC 與 STM32 的 binary protocol、CRC32、stream parser |
| `motor_control.h/.c` | MIT CAN codec、安全邏輯、排程與 telemetry |
| `platform_port.h` | 需要用 CubeMX/HAL 實作的硬體介面 |
| `main_example.c` | 可移植到 CubeIDE `Core/Src/main.c` 的整合範例 |
| `protocol.md` | 完整 wire format |

## 移植到實際 STM32

1. 用 STM32CubeIDE 建立對應晶片的工程。
2. 設定一組 UART 115200 8-N-1 或 USB CDC。
3. 設定 Classic CAN 2.0B、1 Mbps、允許 extended ID。
4. 設定自由運行的 microsecond timer；計數需延伸成 64-bit。
5. 把本目錄的 `.c/.h` 加入工程。
6. 實作 `platform_port.h` 的函式，將 UART/CDC 收到的每個 byte 交給
   `mc_serial_rx_byte()`，CAN RX callback 則呼叫 `mc_can_rx()`。
7. 在無阻塞主迴圈持續呼叫 `mc_poll()`。

`main_example.c` 是整合範例，不應與 CubeMX 產生的 `main.c` 同時編譯。

## 安全限制

這是通用核心，尚未在實體 AK10-9 上驗證。第一次測試必須拆除負載、設置機械限位、
使用硬體急停，並把 torque limit 設成 3 N.m 以下。軟體 idle/watchdog 不能取代急停。
