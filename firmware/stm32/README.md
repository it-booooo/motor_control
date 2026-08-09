# STM32 motor communication firmware contract

此目錄定義 Python 與 STM32 之間的 motor-only application protocol。STM32 韌體需：

1. 驗證 packet version、length 與 CRC32。
2. 接收 backend configuration、heartbeat 與 motor command。
3. 依 motor profile/control mode 編碼 CAN frame。
4. 固定頻率傳送命令並解析馬達 CAN feedback。
5. 回傳 motor telemetry、CAN statistics 與 MCU/CAN timestamps。
6. 在 host heartbeat、motor command 或 CAN feedback timeout 時進入 Motor Idle。

這份專案不定義或接收外部感測器資料。完整 wire layout 見 `protocol.md`。
