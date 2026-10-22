# PROJECT_STATUS.md — 專案現況與接手指南

> 這份是「現在到哪了、新接手人怎麼上手」。給 AI 看、也給管理者看。
> 做事規矩看 [AGENTS.md](AGENTS.md)；專案技術細節看 [CLAUDE.md](CLAUDE.md)。

---

## 一句話現況（2026-10-22）

系統**已上線、正常運作**，全公司使用中：http://192.168.3.200:8000
目前正在**交接**：原負責人 Tony 即將離職，改由新管理者（老闆娘）接手維護。

- 正式區（NAS）：最新版、健康檢查正常。
- GitHub 備份：https://github.com/ezdivemagazine-del/mailer （與正式區同步）。
- 工作方式已打包進專案：管理者只要「講需求」，AI 會自己改 → 記錄 → 上版。

---

## 🆕 第一次接手設定（ONBOARDING）— AI 請照這段執行

> 當新管理者說類似「我是新的負責人，請幫我做第一次設定、確認能連到正式區」時，
> **一步步帶他做完下面六步，並在每一步回報結果。遇到只有人能做的動作（輸入密碼、瀏覽器授權），
> 就停下來用白話請管理者操作，不要跳過、也不要自己亂填。**

### 開始前，先跟管理者確認手上有這四樣（沒有就先去拿，大多要向 Tony 要）
1. **專案資料夾**已經在這台電腦上（通常是連到公司 NAS 共用區看到的同一個資料夾），而且你現在就在這個資料夾裡工作。
2. 資料夾裡有 **`.env`** 檔，且 `OPENAI_API_KEY` 有填（這是 AI 寫信的金鑰）。
3. **NAS 的 admin 密碼**（設定免密碼連線時要輸入一次）。
4. 能登入 **GitHub 帳號 `ezdivemagazine-del`**（Tony 交接，或請他把你加為協作者）。

---

### 第 1 步：確認基本工具都在
```bash
git --version        # 沒有 → 執行 xcode-select --install 裝一下
ssh -V               # macOS 內建，應該直接有
```
若要能一行上版，還需要 `gh`（GitHub CLI）。沒有的話第 3 步會裝。

### 第 2 步：確認在正確的資料夾、而且 .env 在
```bash
ls AGENTS.md deploy.sh .env        # 三個都列得出來，代表位置正確
```
若 `.env` 不存在：照 `.env.example` 複製一份並填入 `OPENAI_API_KEY`、`SECRET_KEY`（向 Tony 要）。

### 第 3 步：設定連到 NAS（免密碼 SSH）
```bash
ls ~/.ssh/id_ed25519.pub || ssh-keygen -t ed25519 -N ""   # 沒金鑰就產生一把
ssh-copy-id admin@192.168.3.200                            # ← 這裡會問一次 NAS admin 密碼
```
> `ssh-copy-id` 若不存在，改用這行（效果一樣）：
> ```bash
> cat ~/.ssh/id_ed25519.pub | ssh admin@192.168.3.200 "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
> ```

### 第 4 步：登入 GitHub（用來自動備份程式）
```bash
command -v gh || (command -v brew || /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"; brew install gh)
gh auth login && gh auth setup-git
```
`gh auth login` 的選項依序：**GitHub.com → HTTPS → Yes → Login with a web browser**，
畫面會給一組 8 碼 code，照終端機指示在瀏覽器輸入，**並確認登入的是 `ezdivemagazine-del` 帳號**再授權。

### 第 5 步：驗證能連到正式區 ✅（最重要）
```bash
ssh -o ConnectTimeout=8 admin@192.168.3.200 "echo NAS_OK"      # 應印出 NAS_OK（且不再問密碼）
curl -s http://192.168.3.200:8000/health                       # 應印出 {"status":"ok"}
git fetch origin && git status -sb                             # 應顯示與 origin/main 同步
```
三個都過 → **這台電腦已經可以維護專案了**。

### 第 6 步：回報
用白話告訴管理者：三項驗證都過了沒、還缺什麼。全過就說明：
> 「設定完成。以後你只要跟我講需求，我會自己改、自己記錄、再用 `./deploy.sh` 上線。」

---

## 日常怎麼用（設定完成後）

管理者直接講需求，例如「排程清單想顯示建立者名字」。AI 就會：
理解 → 改程式 → 更新 [CHANGELOG.md](CHANGELOG.md) → 執行 `./deploy.sh "說明"`（自動上 NAS + 推 GitHub）→ 回報。

---

## 相關文件
- [AGENTS.md](AGENTS.md) — AI 工作規範（鐵則、流程）
- [CLAUDE.md](CLAUDE.md) — 專案技術細節、存取資訊
- [HANDOVER.md](HANDOVER.md) — Tony 離職前要交接的帳號 / 金鑰清單
- [CHANGELOG.md](CHANGELOG.md) — 歷次改了什麼
- `易潛企業開發信系統-操作手冊.docx` — 給全公司使用者看的系統操作手冊

_最後更新：2026-10-22_
