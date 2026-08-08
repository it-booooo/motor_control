# AK10-9 V3.0 馬達特性化測試台

這是一套以 PySide6 製作的桌面 GUI，用來操作 CubeMars AK10-9 V3.0 馬達測試台。
程式整合 CAN 馬達控制、序列埠 Load cell、同步 CSV 記錄、即時遙測、五種實驗、
模擬資料與離線分析。

本程式會實際送出馬達扭力或速度命令。使用前必須完成機械固定、機械限位與實體
E-stop；GUI 的安全上限與停止按鈕不能取代硬體保護。

## 主要功能

- 編輯 CAN、Load cell、力臂與安全限制，不需手動修改程式碼。
- 測試 CAN 馬達回授與 Load cell 序列資料是否正常。
- 執行縮放驗證、Kt 校正、正反向不對稱、反驅阻力與熱衰減實驗。
- 在背景執行量測，GUI 保持可操作，並顯示進度與即時數值／曲線。
- 監控馬達錯誤、電流、溫度及 CAN／Load cell 資料新鮮度。
- 緊急停止時立即將馬達切回 idle，並保留已完成寫入的部分 CSV。
- 產生四組模擬 CSV，不接硬體也能測試分析流程。
- 從 GUI 選擇 CSV、執行分析並預覽 PNG 圖表。
- 使用 PyInstaller 建立單一 Windows 執行檔。

## 安裝與啟動

### 從原始碼執行

建議使用 Python 3.10 以上版本。專案目前以 Python 3.12 驗證。

```bash
python -m pip install -r requirements.txt
python __main__.py
```

根目錄的 `__main__.py` 是唯一 GUI 入口，負責建立 `QApplication`、套用樣式並顯示
`MainWindow`。

### 使用 Windows EXE

已建置的程式位於：

```text
dist/MotorControl.exe
```

EXE 包含 Python、GUI 與分析套件，但不會包含 CAN 轉接器的廠商驅動。PCAN、Vector、
Kvaser 或其他介面仍須先在電腦安裝對應驅動。

## 使用前安全檢查

開始任何實驗前，至少確認：

1. 馬達底座已鎖固在工作台，而不是只放在桌面。
2. 力臂兩側有機械限位，失控時不能完整旋轉。
3. 力臂、Load cell 與接頭能承受預計的最大負載。
4. 旋轉範圍內沒有手、工具、線材或其他物品。
5. 馬達電源的實體開關或 E-stop 在伸手可及的位置。
6. 第一次測試先將「安全扭力」設為 **3 N·m**，確認方向與數值後再逐步提高。

GUI 在「開始實驗」前會要求勾選三項確認，並再顯示一次安全對話框。這些步驟只是
操作確認，不是硬體安全迴路。

## GUI 版面

主視窗左側有兩個設定頁籤，右側為即時遙測及分析區。

### 硬體與安全

此頁的設定會套用到下一次連線測試或實驗。設定不會回寫 `config.py`，重新啟動程式後
會重新載入 `config.py` 的預設值。

「安全扭力」與各實驗頁的「最大扭力／固定扭力」是不同欄位，不會彼此自動同步。
修改安全扭力後也要檢查實驗參數；實驗扭力高於安全扭力時，程式會拒絕開始。

| 欄位 | 用途 | 預設值 |
|---|---|---:|
| CAN 介面 | `python-can` backend，可輸入或選擇 `socketcan`、`pcan`、`slcan`、`virtual` | `socketcan` |
| CAN 通道 | 介面使用的通道名稱 | `can0` |
| CAN bitrate | CAN 匯流排速度 | `1,000,000` bit/s |
| 馬達 ID | CubeMars 驅動器 ID | `1` |
| 指令頻率 | 背景執行緒重送 MIT 命令的頻率 | `200` Hz |
| Load cell 埠 | Arduino／ESP32 的序列埠，可按「重新掃描」更新 | `/dev/ttyUSB0` |
| Load cell baud | 序列埠 baud rate | `115200` |
| Load cell 方向 | 將量測方向乘上 `+1` 或 `-1` | `+1` |
| 力臂長度 | 馬達中心到 Load cell 受力點的實測距離 | `0.1500` m |
| 安全扭力 | GUI 允許的最大實驗扭力 | `20.00` N·m |
| 安全電流 | 回授相電流超過此值便停止 | `25.00` A |
| 安全溫度 | 驅動板溫度超過此值便停止 | `70.0` °C |
| 記錄頻率 | CSV 快照頻率 | `200` Hz |
| 資料目錄 | 實驗 CSV 的儲存位置 | 程式同層的 `data/` |

數字欄位右側的上下按鈕可依欄位 step 增減；按住按鈕會自動連續調整。

#### 測試 CAN 與 Load cell

「測試 CAN 與 Load cell」會依序：

1. 開啟 CAN。
2. 等待最多 3 秒的馬達回授。
3. 顯示目前位置與驅動板溫度。
4. 關閉 CAN。
5. 開啟 Load cell 序列埠並確認收到樣本。
6. 顯示目前公克數與牛頓數。

此功能會同時測試兩項硬體；其中任何一項失敗都會回報錯誤。
縮放常數驗證本身不需要 Load cell，因此即使完整連線測試停在 Load cell 階段，仍可在
確認 CAN 回授正常後單獨執行縮放驗證。

### 實驗設定

選擇實驗後，只會顯示該實驗可調整的參數。

#### 0. 縮放常數驗證

| 參數 | 預設值 | 可調範圍 |
|---|---:|---:|
| 測試速度 | `2.0` rad/s | `0.1–10.0` rad/s |
| 取樣時間 | `3.0` s | `1–30` s |

此實驗只使用 CAN，不開啟 Load cell，也不產生 CSV。

執行流程：

1. 馬達保持 idle，記錄起始位置。
2. GUI 要求使用者手動將輸出軸轉動約 `+90°`。
3. 比較前後位置，判斷回授是輸出軸角度或馬達端角度。
4. GUI 要求拆下力臂並清空旋轉範圍。
5. 馬達以設定速度旋轉並收集樣本。
6. 比較位置微分速度與 eRPM 換算速度，回報建議的 `POLE_PAIRS`。

#### 1. 扭力常數校正

| 參數 | 預設值 | 可調範圍 |
|---|---:|---:|
| 最大扭力 | 等於「安全扭力」 | `0.01–65.00` N·m |
| 階數 | `10` | `3–100` |
| 每階保持 | `3.0` s | `0.01–3600` s |
| 階間休息 | `5.0` s | `0.01–3600` s |

程式先記錄 2 秒零點，再由低到高執行正扭力階梯。每階保持後切回 idle，完成休息時間
再進入下一階。CSV 名稱結尾為 `_kt_calib.csv`。

分析內容包括輸出端／馬達端 Kt、相對標稱值的偏差、線性區 R²、飽和起點與指令準確度。

#### 2. 正反向不對稱

| 參數 | 預設值 | 可調範圍 |
|---|---:|---:|
| 最大 \|扭力\| | 等於「安全扭力」 | `0.01–65.00` N·m |
| 每方向階數 | `8` | `1–100` |
| 每階保持 | `3.0` s | `0.01–3600` s |
| 階間休息 | `4.0` s | `0.01–3600` s |

每個扭力大小依序執行正向、反向，再提高下一階，避免先做完整正向再做反向所造成的
溫度漂移偏差。CSV 名稱結尾為 `_direction_asym.csv`。

分析會輸出正反向實測曲線、各扭力的不對稱百分比、平均值與最大值。

#### 3. 反驅阻力

| 參數 | 預設值 | 可調範圍 |
|---|---:|---:|
| 記錄時間 | `60.0` s | `1–3600` s |

馬達全程保持 idle，由使用者緩慢來回推動力臂。CSV 名稱結尾為 `_backdrive.csv`。

分析會計算反驅阻力中位數、95 百分位、庫倫摩擦與黏滯係數。若要可靠分離正反方向，
記錄期間必須有足夠的正向與反向移動樣本。

#### 4. 熱衰減

| 參數 | 預設值 | 可調範圍 |
|---|---:|---:|
| 固定扭力 | 安全扭力的 50% | `-65.00–65.00` N·m |
| 升溫記錄 | `600.0` s | `1–86400` s |
| 降溫記錄 | `300.0` s | `0–86400` s |
| 固定座標籤 | `stock` | 可自行輸入 |

內建標籤選項為 `stock`、`pla`、`alu`、`alu_fin`、`alu_paste`。

程式先記錄 10 秒基準，再輸出固定扭力完成升溫段，最後切回 idle 記錄降溫段。CSV 名稱
結尾為 `_thermal_<固定座標籤>.csv`。

分析會以指數模型估計穩態溫度與熱時間常數，並輸出扭力隨時間及溫度的衰減。

### 開始、進度與停止

「開始實驗」只有在以下三項全部勾選後才可使用：

- 治具已鎖固，力臂兩側已有機械限位。
- 實體電源／E-stop 在伸手可及處。
- 旋轉範圍已清空，現場人員已知悉。

開始前程式還會檢查：

- CAN 介面與通道不可空白。
- 除縮放驗證外，必須設定 Load cell 序列埠。
- 力臂長度必須大於 0。
- Kt、正反向與熱實驗扭力不得超過「安全扭力」。
- 實驗時間必須大於 0。

量測期間硬體設定與實驗設定會停用，避免中途修改。離線分析／模擬與硬體量測不能同時
執行，以免影響 200 Hz 記錄時序。

紅色「緊急停止 / Motor Idle」會設定停止旗標並立即將目前命令改為 idle。Worker 隨後
安全關閉 CSV、Load cell 與 CAN。若 Recorder 已建立，停止前的資料會保留，不會刪除。

### 即時遙測

GUI 顯示：

- 實驗階段
- 馬達位置（°）
- 輸出軸速度（rad/s）
- 相電流（A）
- 驅動板溫度（°C）
- Load cell 力（N）
- 實測扭力（N·m）
- 指令扭力（N·m）

曲線區同時繪製扭力、電流與溫度，最多保留最近 1200 個 GUI 更新點。量測迴圈仍依
「記錄頻率」寫入 CSV；GUI 遙測最多約 20 次／秒，以免繪圖拖慢量測。

如果沒有安裝 `pyqtgraph`，數字仍可顯示，但即時曲線會停用。

### 資料分析與模擬

此區提供：

- 選擇 CSV
- 執行分析
- 產生四組模擬資料
- 停止處理
- 文字記錄
- PNG 圖表預覽

「量測完成後自動分析」預設為開啟。使用者停止、安全保護觸發或實驗失敗時，不會自動
分析部分 CSV，但仍可稍後手動選擇該檔案。

模擬器會產生：

```text
data/sim_kt_calib.csv
data/sim_direction_asym.csv
data/sim_backdrive.csv
data/sim_thermal_pla.csv
```

原始碼模式的分析輸出位於專案的 `data/analysis/`。打包 EXE 模式則位於所選 CSV 同層的
`analysis/`。輸出包含一張 PNG 與一份 TXT 摘要，檔名後綴依實驗類型為 `_kt`、
`_asym`、`_backdrive` 或 `_thermal`。

## 自動安全保護

量測迴圈每次取樣都會檢查：

- 馬達回報的錯誤碼不是 0。
- 相電流超過「安全電流」。
- 驅動板溫度超過「安全溫度」。
- CAN 最新資料超過 `0.25` 秒沒有更新。
- Load cell 最新資料超過 `0.25` 秒沒有更新或完全沒有資料。

任何條件成立都會觸發停止、切回 idle 並保留已寫入的 CSV。

CSV 另外記錄 `age_can` 與 `age_lc`。離線分析只保留兩者都小於 `0.05` 秒的資料列；
有效資料低於原始資料的 80% 時會顯示警告。

## CSV 格式

實驗 CSV 使用時間戳記命名：

```text
<資料目錄>/YYYYMMDD_HHMMSS_<實驗名稱>.csv
```

主要欄位如下：

| 欄位 | 說明 |
|---|---|
| `t` | Recorder 開始後的相對時間（s） |
| `phase` | 實驗階段名稱 |
| `cmd_torque` | 指令扭力（N·m） |
| `cmd_velocity` | 指令速度（rad/s） |
| `pos_deg` | 馬達位置回授（°） |
| `spd_rads` | 換算後輸出軸速度（rad/s） |
| `spd_erpm` | 原始電氣轉速（eRPM） |
| `current_a` | 相電流（A） |
| `temp_c` | 驅動板溫度（°C） |
| `error` | 馬達錯誤碼 |
| `force_n` | Load cell 力（N） |
| `torque_meas` | `force_n × lever_m`（N·m） |
| `lever_m` | 本次量測使用的力臂長度（m） |
| `age_can` | 馬達回授資料年齡（s） |
| `age_lc` | Load cell 資料年齡（s） |

## 硬體通訊

### 馬達 CAN

- CubeMars AK V3.0 MIT 模式，Control Mode ID 為 `0x08`。
- 預設 bitrate 為 1 Mbps。
- 命令順序依 V3.0 手冊實作為 KP、KD、位置、速度、扭力。
- 純扭力模式使用 `kp=0`、`kd=0`、`t_ff=<扭力>`。
- idle 使用位置、速度、增益及前饋扭力全部為 0。
- 命令由獨立背景執行緒持續重送，預設 200 Hz。

`config.py` 內的 `P_MIN/P_MAX`、`V_MIN/V_MAX`、`T_MIN/T_MAX`、`GEAR_RATIO` 與
`POLE_PAIRS` 仍屬協議／機械換算參數，GUI 不會修改它們。更換馬達型號或確認縮放範圍
後，必須直接更新 `config.py` 並重新啟動程式。

### Load cell

Arduino／ESP32 必須持續輸出：

```text
<MCU 毫秒>,<原始讀值>,<公克數>
```

程式開啟序列埠後會等待裝置重新啟動，最多等待 5 秒取得第一筆資料。每次會產生 CSV 的
實驗都會先執行約 2 秒 tare。tare 時請勿碰觸力臂；Load cell 方向應透過 GUI 的 `+1/-1`
設定調整。

Arduino 範例位於 `arduino_loadcell/arduino_loadcell.ino`。HX711 建議使用 80 SPS；
10 SPS 容易造成資料過舊並觸發保護。

## 建立 Windows EXE

安裝所有 requirements 後執行：

```bash
python build.py
```

`build.py` 會：

1. 確認 Windows 平台。
2. 檢查 PyInstaller、PySide6、pyqtgraph、python-can、pyserial、pandas、NumPy、
   Matplotlib 與 SciPy 是否可載入。
3. 確認舊的 `dist/MotorControl.exe` 沒有被執行中的程式鎖定。
4. 收集 Qt、Matplotlib、pyqtgraph、python-can backend 與必要 DLL。
5. 以根目錄 `__main__.py` 建立 windowed one-file EXE。
6. 驗證輸出檔存在且大小不為 0。

輸出：

```text
dist/MotorControl.exe
```

PyInstaller 掃描所有 python-can backend 時，可能警告未安裝 Vector、Kvaser、IXXAT、
SYSTEC 等廠商函式庫。若實際不使用這些介面，警告不影響建置；實際使用的 CAN backend
仍必須能載入對應驅動。

## 常見問題

### CAN 開啟成功但 3 秒內沒有回授

依序檢查 CAN 介面／通道、1 Mbps bitrate、馬達 ID、CAN_H／CAN_L、120 Ω 終端電阻、
轉接器驅動，以及 Linux socketcan 是否已啟用。

### Windows 使用預設值無法連線

預設 `socketcan/can0` 是 Linux 設定。使用 PCAN 時通常需將 CAN 介面改為 `pcan`，通道
改為裝置使用的名稱，例如 `PCAN_USBBUS1`。實際名稱以安裝的驅動與 python-can 文件為準。

### Load cell 序列埠不存在

按「重新掃描」，確認裝置管理員中的 COM 埠、序列埠沒有被其他程式占用，並確認 baud
與韌體設定一致。

### Load cell 一連線就觸發資料中斷

確認韌體持續輸出三欄 CSV 格式、HX711 使用足夠取樣率，並檢查 USB 線材、供電及接地。

### 無法開始實驗

確認三項安全核取方塊皆已勾選、扭力未超過安全扭力、必要欄位不為空，且目前沒有分析、
模擬或其他硬體工作正在執行。

### 分析後沒有圖

確認 CSV 含有可辨識的 `phase`，且 CAN／Load cell age 小於 0.05 秒的有效列數足夠。
縮放常數驗證不產生 CSV，因此不能使用一般資料分析功能。

### build.py 無法覆寫 EXE

關閉 `MotorControl.exe`，並在工作管理員確認沒有同名背景程序後重試。

## 專案結構

```text
motor_control/
├─ __main__.py                 # 唯一 GUI 入口
├─ build.py                    # PyInstaller one-file 建置
├─ config.py                   # 協議、機械與 GUI 預設參數
├─ ak_can.py                   # MIT 命令封包、CAN 收發與馬達狀態
├─ loadcell.py                 # 序列埠接收與 tare
├─ logger.py                   # 同步快照、CSV 與基礎安全類型
├─ analyze.py                  # CSV 分析、PNG 與 TXT
├─ simulate.py                 # 四種模擬資料
├─ experiments.py              # 原始 CLI 實驗流程（保留供診斷）
├─ arduino_loadcell/
│  └─ arduino_loadcell.ino
├─ src/
│  ├─ main_window.py           # MainWindow、選單與安全關閉
│  ├─ app_state.py             # GUI 啟動狀態
│  ├─ experiment_specs.py      # 實驗名稱、時間估算與輸入驗證
│  ├─ runtime.py               # 原始碼／EXE 的程式根目錄
│  ├─ application/
│  │  └─ composer.py           # 建立並串接 Panel 與 Controller
│  ├─ controllers/
│  │  ├─ experiment_controller.py
│  │  └─ analysis_controller.py
│  ├─ workers/
│  │  ├─ experiment_worker.py
│  │  └─ process_worker.py
│  └─ ui/
│     ├─ hardware_panel.py
│     ├─ experiment_panel.py
│     ├─ telemetry_panel.py
│     ├─ analysis_panel.py
│     ├─ spin_boxes.py
│     ├─ workspace_view.py
│     └─ style.py
└─ tests/
   ├─ test_experiment_specs.py
   └─ test_spinbox_controls.py
```

## 開發與測試

執行測試：

```bash
python -m unittest discover -s tests -v
```

不透過 GUI 的診斷入口仍保留：

```bash
python ak_can.py
python simulate.py
python analyze.py data/sim_kt_calib.csv
python experiments.py verify
python experiments.py kt
python experiments.py asym
python experiments.py backdrive
python experiments.py thermal
```

正式操作建議使用 GUI；`experiments.py` 使用終端互動且不包含 GUI 的按鈕、進度與互斥
控制。

## 授權

MIT License，詳見 `LICENSE`。
