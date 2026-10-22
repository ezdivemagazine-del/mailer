# Changelog — 易潛企業開發信系統

每次上版都要在這裡記一筆（最新的放最上面）。接手的 AI 從最新一筆往下讀就懂現況。
記錄格式見 [AGENTS.md](AGENTS.md) 第 3 節。

---

## 2026-10-22｜交接：新增一句話接手流程（PROJECT_STATUS.md）

### 改了什麼
- 新增 **[PROJECT_STATUS.md](PROJECT_STATUS.md)**：專案現況 + 「第一次接手設定（ONBOARDING）」六步流程，AI 可照著帶新管理者在新電腦上設定並驗證能連到正式區。
- `AGENTS.md` 開頭加上 onboarding 觸發段，認得「我是新負責人，請幫我做第一次設定」這類話。

### 為什麼
- 未來維護改在老闆娘的電腦進行。要讓她只跟 AI（如 Codex）說一句話，就能自動完成接手設定。

### 要注意的
- 新電腦仍需要人做一次性動作：輸入 NAS 密碼、GitHub 瀏覽器授權、確認 .env 有金鑰。這些 AI 會引導，但不能代替。

---

## 2026-10-21｜交接：把工作流程打包進專案

### 改了什麼
- 新增 **[AGENTS.md](AGENTS.md)**：所有 AI（Claude Code / Codex / Cursor…）共用的工作規範——鐵則、標準流程、上版方式。
- 新增 **[deploy.sh](deploy.sh)**：一行上版（送 NAS → 重建容器 → git commit/push）。
- 新增 **[HANDOVER.md](HANDOVER.md)**：Tony 離職前要交接的帳號 / 金鑰清單。
- `CLAUDE.md` 加上「本地啟動」「新電腦接手」說明，並在開頭指向 AGENTS.md。

### 為什麼
- Tony（PM）約一個月後離職，專案交給業務同事用 AI 繼續維護。
- 要讓「業務只講需求，AI 自己改 → 記錄 → 上版」成為固定流程，不依賴特定人或特定 AI。

### 要注意的
- 換電腦接手時，務必先照 CLAUDE.md「新電腦接手」打通 NAS SSH 與 GitHub 存取，`deploy.sh` 才能運作。

---

## 2026-06-18｜v1.0 初次部署 + 首批 Bug 修正

### 完成事項
- **系統首次部署**到 QNAP NAS TS-431X2（ARM32v7），網址：http://192.168.3.200:8000
- **GitHub 建立**：https://github.com/ezdivemagazine-del/mailer（private）
- **SSH 免密碼連線**設定完成（Mac → NAS，可直接遠端操控）

### Bug 修正
| # | 問題 | 原因 | 解法 |
|---|------|------|------|
| 1 | Docker build 失敗（libz 對齊錯誤） | Bookworm base image 與 ARM32 舊核心不相容 | 改用 `python:3.11-slim-bullseye` |
| 2 | pip install 失敗（cffi/bcrypt 無法編譯） | bcrypt 4.x 需要 Rust；cffi 無 ARM32 wheel | 改用 `passlib==1.7.4`（純 Python），移除 gcc |
| 3 | pip install 失敗（cffi 被 alibabacloud 拉進來） | alibabacloud-dm → cryptography → cffi | 暫時移除 alibabacloud-dm，directmail.py 加 try/except |
| 4 | openai TypeError: unexpected keyword 'proxies' | httpx 0.28+ 移除 proxies 參數 | 鎖定 `httpx==0.27.2` |
| 5 | 容器啟動失敗（unable to open database file） | QNAP bind mount 路徑權限問題 | 改用 Docker named volume `mailer_mailer_data` |
| 6 | 部門選擇按鈕（藥丸）登入後不顯示 | `doLogin()` 後未呼叫 `loadPersonas()` | 在 doLogin 成功後加上 `loadPersonas()` |

### 目前已知限制
- **DirectMail 停用**：阿里雲套件 ARM32 相容性問題，待後續解決
- **pydantic 降版**：用 v1（1.10.13），避免 pydantic-core Rust 編譯問題

---

## 上版指令（快速參考）

```bash
# 從 Mac 一鍵上版到 NAS（約 20 秒）
cd "/Volumes/AI/業務信件開發軟體"
scp -r app/ admin@192.168.3.200:/share/homes/admin/mailer/
ssh admin@192.168.3.200 "export PATH=/share/CACHEDEV2_DATA/.qpkg/container-station/bin:\$PATH && cd /share/homes/admin/mailer && docker build -t ezdive/mailer:latest . && docker compose up -d"

# 推到 GitHub
git add . && git commit -m "說明改了什麼" && git push
```
