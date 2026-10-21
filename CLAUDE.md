# 易潛企業開發信系統 — Claude 專案說明

> 這份文件是給 Claude 看的。不管是哪個帳號、哪次對話，讀完這份文件就能立刻接手這個專案。

> ⚠️ **開工前先讀 [AGENTS.md](AGENTS.md)** —— 那是所有 AI 共用的工作規範（鐵則、標準流程、上版方式）。
> 本文件（CLAUDE.md）負責「專案是什麼、技術細節、存取設定」；AGENTS.md 負責「做事的規矩」。

---

## 專案是什麼

「易潛企業開發信系統」是一套供業務人員寫開發信、發送行銷郵件的內部平台。
部署在公司 QNAP NAS（192.168.3.200:8000），只供公司內網使用。

主要功能：
- AI 輔助寫信（GPT-4o，可對話式修改）
- SMTP 批量發送（支援 Gmail、阿里企業信箱）
- 發送記錄追蹤
- 排程自動發送
- 多帳號權限管理

---

## 使用者與部門

共 5 個部門，每個有獨立的 AI 寫信人設：

| 部門 | 業務類型 |
|------|---------|
| 創意種籽 | 國際潛水品牌台灣總代理（Cressi, Seac, Alpha Oceano） |
| DRT SHOW | 亞洲潛水產業展覽平台 |
| EZDIVE | 潛水產業媒體與內容平台 |
| DIWA | 潛水教育認證機構 |
| GOGOSCUBA | 潛水器材與通路平台 |

---

## 技術架構

| 項目 | 技術 |
|------|------|
| 後端 | Python 3.11 + FastAPI 0.95.2 |
| 前端 | Vue.js 3（CDN，無 build step） |
| 資料庫 | SQLite（Docker named volume: mailer_data） |
| AI | OpenAI GPT-4o（openai==1.30.1 + httpx==0.27.2） |
| 認證 | JWT + passlib pbkdf2_sha256 |
| 部署 | Docker + QNAP NAS TS-431X2（ARM32v7） |

---

## 檔案結構

```
業務信件開發軟體/
├── app/
│   ├── backend/
│   │   ├── main.py        # FastAPI 主程式、所有 API endpoint
│   │   ├── database.py    # SQLite 初始化、資料表結構
│   │   ├── auth.py        # JWT 認證、passlib 密碼雜湊
│   │   ├── mailer.py      # SMTP 發送邏輯
│   │   ├── directmail.py  # 阿里雲 DirectMail（暫時停用，ARM32 相容性問題）
│   │   ├── scheduler.py   # APScheduler 排程
│   │   ├── crypto.py      # SMTP 密碼加密（XOR+base64）
│   │   └── requirements.txt
│   └── frontend/
│       └── index.html     # Vue.js 3 SPA（單一 HTML 檔）
├── Dockerfile             # python:3.11-slim-bullseye，無 gcc
├── docker-compose.yml     # named volume: mailer_data
├── .env                   # OPENAI_API_KEY + SECRET_KEY（不進 git）
├── .env.example           # 範本
└── CLAUDE.md              # 本文件
```

---

## 已知問題與特殊決定

- **ARM32 相容性**：NAS 是 ARM32v7，apt-get/apk 在舊核心上容易崩潰。解法：Dockerfile 完全不裝 gcc，用 `--prefer-binary` 只裝預編譯 wheel。
- **alibabacloud-dm 暫停**：此套件的依賴（cryptography → cffi）在 ARM32 無預編譯版，暫時移除。directmail.py 已加 try/except，不影響啟動。
- **httpx 鎖版**：openai 1.30.1 需要 httpx<0.28，requirements.txt 鎖定 httpx==0.27.2。
- **pydantic v1**：用 pydantic==1.10.13（v1），避免 pydantic-core Rust 編譯問題。
- **密碼雜湊**：用 passlib pbkdf2_sha256 取代 bcrypt（bcrypt 4.x 需 Rust）。
- **Docker named volume**：資料庫用 `mailer_mailer_data` named volume，不用 bind mount（QNAP 路徑權限問題）。

---

## 本地啟動（改完程式先在自己電腦測）

```bash
cd "/Volumes/AI/業務信件開發軟體"
pip3 install -r app/backend/requirements.txt   # 第一次才需要
PYTHONPATH=. python3 -m uvicorn app.backend.main:app --host 0.0.0.0 --port 8000
```

開瀏覽器到 http://localhost:8000 測試。測完按 Ctrl+C 停止（或 `pkill -f "uvicorn app.backend"`）。

---

## 上版流程（每次改完程式碼後）

**首選：一行搞定。**

```bash
./deploy.sh "這次改了什麼"
```

`deploy.sh` 會自動：送程式到 NAS → 重建容器 → `git commit` + `push`。
（換 NAS／路徑時，改 `deploy.sh` 最上面的「設定」區塊即可。）

<details>
<summary>手動步驟（deploy.sh 壞掉時的備援）</summary>

```bash
# 1. 傳修改的檔案到 NAS
scp -r app Dockerfile docker-compose.yml admin@192.168.3.200:/share/homes/admin/mailer/

# 2. 在 NAS 重新建置並啟動（約 15-30 秒）
ssh admin@192.168.3.200 "export PATH=/share/CACHEDEV2_DATA/.qpkg/container-station/bin:\$PATH && cd /share/homes/admin/mailer && docker build -t ezdive/mailer:latest . && docker compose up -d"

# 3. 推到 GitHub
git add -A && git commit -m "說明改了什麼" && git push
```

> requirements.txt 沒變的話，pip install 用快取，build 只需 15 秒。
</details>

---

## 新電腦接手（業務換電腦 / 新同事第一次設定）

新電腦只有「資料夾」還不夠，要先打通兩個存取權，`deploy.sh` 才能自動上版。
**這三樣東西要向 Tony（或前手）拿**：NAS admin 密碼、OpenAI 金鑰、GitHub 帳號存取權。

### 1. 連得到 NAS（免密碼 SSH）
```bash
# 若沒有 SSH key 先產生一把（一路按 Enter）
ls ~/.ssh/id_ed25519.pub || ssh-keygen -t ed25519

# 把公鑰裝到 NAS（會問一次 NAS 的 admin 密碼，之後就免密碼）
ssh-copy-id admin@192.168.3.200

# 測試：應該不再問密碼
ssh admin@192.168.3.200 "echo ok"
```

### 2. 推得上 GitHub
```bash
# 安裝 GitHub CLI 後登入（跟著畫面用瀏覽器授權一次）
gh auth login
```
Repo：https://github.com/ezdivemagazine-del/mailer （private，帳號 `ezdivemagazine-del`）

### 3. 金鑰在哪
- `OPENAI_API_KEY`、`SECRET_KEY` 都在專案根目錄的 **`.env`** 檔（**不在 git 裡**，所以換電腦時 `.env` 要一起帶過去，或照 `.env.example` 重填）。
- 這個資料夾如果是直接放在 NAS 共用區，`.env` 通常已經在裡面；確認一下 `cat .env` 有值即可。
- OpenAI 金鑰餘額／重辦：platform.openai.com（帳號資訊問 Tony）。

設定完這三項，之後只要「講需求 → AI 改 → `./deploy.sh`」就會自動上線。

---

## 環境設定（.env）

```
OPENAI_API_KEY=sk-proj-...
SECRET_KEY=任意字串（JWT 簽名用）
```

---

## NAS 資訊

- IP：192.168.3.200
- 機型：QNAP TS-431X2（ARM32v7，8GB RAM）
- SSH 帳號：admin
- 專案路徑：/share/homes/admin/mailer/
- Docker 路徑：/share/CACHEDEV2_DATA/.qpkg/container-station/bin/

---

## PM 聯絡人

Tony（易潛企業 PM，無開發背景，有 UI 美感）
GitHub：ezdivemagazine-del
