# Healthy Work App 健康工作提醒工具

[English](README.en.md)

Healthy Work App 是一個 Windows 桌面小工具，用來幫助你維持比較健康的工作節奏。它可以進行工作倒數、提醒休息、記錄休息與喝水量，並在一天結束時產生簡單的健康工作報告。

這個專案使用 Python、PyQt5、本機 JSON 儲存，以及透過 PyQtWebEngine 播放的 Lottie 動畫。資料都存在使用者自己的電腦，不需要雲端帳號，也不使用 AI API。

## 功能

- 可調整休息提醒間隔的工作倒數計時器。
- 支援暫停、重新開始倒數、提前休息、延後提醒，以及結束今天。
- 倒數時間到時顯示主動休息提醒視窗。
- 休息期間自動計時，休息結束後可儲存休息紀錄。
- 單次休息紀錄最多計入 60 分鐘，避免忘記回到工作時污染統計。
- 可記錄喝水量與休息備註。
- 今日統計包含工作時間、休息時間、休息次數、喝水總量、目前休息時間與上次休息時間。
- 結束今天後產生健康工作報告與規則式建議。
- 記錄工作區段，用來判斷是否有連續工作過久的情況。
- 依照狀態播放不同貓咪動畫，優先使用 Lottie JSON，必要時退回 GIF。
- 使用本機 JSON 儲存資料，並具備基本資料驗證與壞檔備份機制。

## 下載與使用

一般使用者建議下載 Windows 免安裝 ZIP 版本。

1. 打開本專案的 **Releases** 頁面。
2. 下載最新版本的 Windows `.zip` 檔。
3. 先完整解壓縮 ZIP，不要直接在壓縮檔裡執行。
4. 雙擊解壓後資料夾中的 `.exe`。
5. 請保持整個資料夾內容完整，執行檔需要同資料夾內的 runtime 與動畫資源。

ZIP 版本不需要安裝。若要移除，關閉 App 後刪除整個解壓縮資料夾即可。

未簽章的 Windows 執行檔可能會出現 SmartScreen 提醒。這不一定代表程式有問題，只是代表它尚未經過可信任發行者的程式碼簽章。

## 從原始碼執行

在專案根目錄執行：

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m app.main
```

如果你的全域 Python 環境已經安裝好相依套件，也可以直接執行：

```powershell
python -m app.main
```

## 健康評分規則

健康評分使用本機規則式邏輯，不依賴雲端或 AI。

- 工作資料足夠時才會顯示正式分數。
- 如果今天尚未記錄工作，報告會顯示 `今天尚未工作`。
- 如果記錄工作未滿 30 分鐘，報告會顯示 `資料較少，暫不評分`。
- 工作時間達 30 分鐘以上時，報告會顯示一般的 `X / 100` 分數。
- 喝水目標會依照已記錄的工作時間等比例計算，而不是套用固定全天門檻。
- 基本喝水目標為 `1500 ml / 16 小時清醒時間`，約每工作小時 94 ml。
- 理想喝水目標為 `2000 ml / 16 小時清醒時間`，約每工作小時 125 ml。
- 目標沒有每日上限；如果工作時間更長，目標會繼續等比例提高。
- 休息節奏的核心目標是避免連續工作超過 60 分鐘。
- 休息總量是次要目標，建議每工作 1 小時至少休息 5 分鐘。
- 單次休息超過 60 分鐘時，App 會提醒本次休息紀錄將以 60 分鐘計算，今日統計與報告也會使用這個上限後的時間。
- 舊資料即使保存了數字分數，報告仍會優先套用目前顯示規則，避免在資料不足時顯示誤導性的分數。

## 動畫資源

主視窗倒數卡片會依照狀態播放不同動畫：

- 尚未開始：`paws animation`
- 工作中：`rolling cat animation`
- 已暫停：`Loading Cat`
- 提醒時間到：`Le Petit Chat _Cat_ Noir`
- 休息中：`Cat playing animation`
- 今日已結束：`Cat is sleeping and rolling`

App 會優先播放 `gif/json` 裡的 Lottie JSON 檔。若 PyQtWebEngine、本機 `lottie.min.js` 或 JSON 動畫不可用，會退回使用 `gif` 資料夾中的 GIF。

動畫素材與 Lottie 播放函式庫的來源、作者與授權資訊記錄在 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 資料儲存

從原始碼執行時，資料會存在：

```text
data/daily_records.json
```

打包成 Windows 免安裝版後，資料會存在執行檔旁邊：

```text
HealthyWork/data/daily_records.json
```

儲存內容包含：

- App 設定。
- 休息紀錄。
- 工作區段紀錄。
- 每日摘要。
- 每日工作分鐘數。

`daily_records.json` 會包含使用者活動資料，不應提交到 GitHub。版本庫只保留 `data/.gitkeep`，用來讓資料夾存在。

## 打包注意事項

第一版公開發佈建議使用 PyInstaller 的 `onedir` 模式產生 Windows 免安裝資料夾，再壓成 ZIP。正式確認資源路徑與資料保存都沒問題前，不建議優先使用 `onefile`。

打包成品需要包含：

- 執行檔。
- PyQt5 與 PyQtWebEngine runtime。
- 完整的 `gif/` 資料夾。
- `gif/json/lottie.min.js`。
- 所有 Lottie JSON 檔。
- 所有 GIF fallback 檔。

發佈前請確認：

- 雙擊執行檔可以開啟 App。
- PyQtWebEngine 可用時能播放 Lottie 動畫。
- Lottie 不可用時能退回 GIF。
- 工作倒數、暫停、提醒、延後提醒、休息與結束今天流程正常。
- 關閉並重新開啟後，休息紀錄與喝水紀錄能保留。
- 結束今天報告能開啟，並顯示友善文字，而不是 `N/A`。

GitHub repository 應保存原始碼；打包後的 ZIP 應放在 **GitHub Releases**。不要把 `.exe`、`.zip`、本機使用者資料、虛擬環境或 Python cache 檔提交到版本庫。

## 開發

安裝相依套件：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

執行測試：

```powershell
.\.venv\Scripts\python.exe -m pytest
```

目前測試涵蓋 timer 狀態轉換、資料儲存、統計、評分規則、提醒流程、動畫 fallback，以及主要 UI 的保存流程。

## 專案結構

```text
app/
  main.py
  ui/
    animation.py
    main_window.py
    reminder_dialog.py
    report_dialog.py
  core/
    timer.py
    scoring.py
    statistics.py
  data/
    models.py
    storage.py
data/
  .gitkeep
gif/
  json/
tests/
README.md
README.en.md
requirements.txt
```

## 平台說明

目前專案是在 Windows 環境下開發與打包。只要 PyQt5 與 PyQtWebEngine 安裝正確，原始碼理論上可能在 macOS 或 Linux 執行，但這兩個平台的打包成品尚未驗證。若要公開支援不同作業系統，建議每個平台各自打包並實機測試。
