# Changelog — 易潛企業開發信系統

每次上版後記錄在這裡。未來接手的 Claude 請從最新一筆往下讀。

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
