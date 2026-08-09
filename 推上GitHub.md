# 把這個資料夾推上 GitHub

全部在你的 Mac「終端機」App 裡做。從上到下貼，一段一段跑。

---

## 步驟 1：先確認 git 裝了、也認得你

```bash
git --version
```

沒反應或說找不到指令 → 跑 `xcode-select --install`，裝完再回來。

```bash
git config --global user.name "Tung Chang"
git config --global user.email "joshuachang1319@gmail.com"
```

---

## 步驟 2：把程式複製到一個正常的位置

現在檔案在 Claude 的暫存輸出資料夾，路徑很深而且之後可能被清掉。
先搬到 `~/projects`：

```bash
mkdir -p ~/projects
cp -R "$(ls -dt ~/Library/Application\ Support/Claude/local-agent-mode-sessions/*/*/*/outputs/motor_dyno | head -1)" ~/projects/motor_dyno
cd ~/projects/motor_dyno
ls
```

**如果上面那行 `cp` 失敗**（路徑有變動），最簡單的做法是：
在 Claude 的檔案卡片上點開資料夾 → 用 Finder 直接把 `motor_dyno` 資料夾拖到
`~/projects` 底下 → 然後 `cd ~/projects/motor_dyno`。

跑完 `ls` 應該看到：`README.md  LICENSE  config.py  ak_can.py  ...`

---

## 步驟 3：清掉我建的 git 紀錄，重新開一份乾淨的

我在沙箱裡建的 `.git` 有一些權限造成的殘留檔，直接重來比較乾淨：

```bash
rm -rf .git __pycache__
rm -rf data/*.csv                    # 暫存資料不用進版控

git init -b main
git add -A
git status --short                    # ★ 檢查一下：不該有任何 .csv
git commit -m "Motor communication console: STM32/CAN command and feedback"
```

`git status --short` 那行如果看到 `.csv` 檔，代表 `.gitignore` 沒生效，先停下來別 commit。

---

## 步驟 4：在 GitHub 上建一個空 repo

1. 打開 <https://github.com/new>
2. **Repository name**：`ak10-9-motor-dyno`
3. **Description**：`Low-cost dynamometer and characterization toolkit for CubeMars AK10-9 V3.0 QDD actuators`
4. 選 **Public**
5. ⚠️ **下面三個勾選框（Add a README / .gitignore / license）全部不要勾** ——
   我們本地已經有了，勾了會衝突
6. 按 **Create repository**

---

## 步驟 5：推上去

把下面的 `你的帳號` 換成你的 GitHub 使用者名稱：

```bash
git remote add origin https://github.com/你的帳號/ak10-9-motor-dyno.git
git push -u origin main
```

**第一次推會要求登入。** 注意 GitHub 從 2021 年起就不接受帳號密碼了，
要用 Personal Access Token 當密碼：

1. 到 <https://github.com/settings/tokens> → **Generate new token (classic)**
2. Note 填 `motor-dyno`，Expiration 選 90 days
3. 勾選 **repo**（整個大項打勾就好）
4. 按 Generate，**把那串 `ghp_...` 複製起來**（只會顯示這一次）
5. 終端機問 Username 就填你的帳號，問 Password 就貼那串 token

> 更省事的替代方案：裝 [GitHub Desktop](https://desktop.github.com/)，
> 用圖形介面登入一次，之後終端機的 git 也會沿用那組憑證。

---

## 步驟 6：你的分享連結

```
https://github.com/你的帳號/ak10-9-motor-dyno
```

推完打開這個網址，應該會看到 README 完整渲染出來（表格、badge 都會顯示）。

---

## 之後改了東西要更新

```bash
cd ~/projects/motor_dyno
git add -A
git commit -m "說明你改了什麼"
git push
```

---

## 兩個建議

**加 Topics 讓別人搜得到。** 進 repo 頁面 → 右上齒輪 → Topics 填：
`robotics` `humanoid-robot` `actuator` `cubemars` `dynamometer` `motor-characterization` `qdd`

**量測資料不要進版控。** `.gitignore` 已經擋掉 `data/*.csv` 了。
熱實驗一次就 14 MB，推上去 repo 會變得又肥又慢。
如果之後想公開資料集，用 [Zenodo](https://zenodo.org/) 或 GitHub Releases 附檔案，
那也是論文引用資料集的標準做法（Zenodo 會給你一個 DOI）。
