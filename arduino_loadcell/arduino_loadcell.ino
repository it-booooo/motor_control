/*
 * arduino_loadcell.ino
 *
 * HX711 + S 型 load cell → USB 序列埠
 * 輸出格式（每行一筆）：  <毫秒>,<原始讀值>,<公克>
 *
 * 需要函式庫：Arduino IDE → 程式庫管理員 → 搜尋 "HX711 Arduino Library"
 *             (bogde/HX711)
 *
 * 接線（以 Arduino Uno / Nano 為例）：
 *   HX711 VCC → 5V        HX711 GND → GND
 *   HX711 DT  → D2        HX711 SCK → D3
 *   Load cell 四線接 HX711 的 E+ E- A+ A-（照 load cell 的線色表接）
 *
 * ★ 建議用 ESP32 而不是 Uno：ESP32 有硬體浮點、序列埠更快，
 *   而且之後你要加溫度感測器（多顆 NTC）時腳位比較夠。
 *   換 ESP32 只要改 DOUT/SCK 腳位定義。
 */

#include "HX711.h"

const int PIN_DOUT = 2;
const int PIN_SCK  = 3;

// ★ CALIBRATION_FACTOR 必須用砝碼實測校正，不能用猜的。
//   校正步驟：
//     1. 先把這個值設成 1.0，燒錄，記下空載時的 raw 讀值 R0
//     2. 掛一個已知重量 W（用電子秤量過的東西，越接近你的量測範圍越好）
//        記下 raw 讀值 R1
//     3. CALIBRATION_FACTOR = (R1 - R0) / W
//     4. 填回來，重新燒錄，再掛同一個重量驗證讀出來是不是 W
//   ★ 這一步做不確實，你後面所有扭力數據都是錯的。
const float CALIBRATION_FACTOR = 420.0;   // ← 換成你自己量出來的

HX711 scale;

void setup() {
  Serial.begin(115200);
  scale.begin(PIN_DOUT, PIN_SCK);
  scale.set_scale(CALIBRATION_FACTOR);
  scale.tare();                 // 開機歸零（Python 端還會再歸零一次）

  // HX711 有 10 SPS 和 80 SPS 兩種速率，由模組上的 RATE 腳決定。
  // 做動態量測請務必改成 80 SPS（把 RATE 腳拉到 VCC，或剪掉板上的 10SPS 短路）。
  // 10 SPS 對「抬重物」這種秒級動作來說太慢，會抓不到峰值。
}

void loop() {
  if (scale.is_ready()) {
    long raw = scale.read();
    float grams = (raw - scale.get_offset()) / CALIBRATION_FACTOR;
    Serial.print(millis());
    Serial.print(',');
    Serial.print(raw);
    Serial.print(',');
    Serial.println(grams, 2);
  }
}
