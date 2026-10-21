#!/bin/bash
# ─────────────────────────────────────────────────────────────
# 一鍵上版：把程式碼送到 NAS、重建容器，並記錄到 GitHub。
# 用法：
#   ./deploy.sh "這次改了什麼"
# 例：
#   ./deploy.sh "修好排程時間顯示錯誤"
#
# 給 AI：收到需求、改完程式、更新 CHANGELOG.md 後，執行這支就完成上版。
# 換部署環境（新 NAS / 新路徑）只要改下面「設定」區塊。
# ─────────────────────────────────────────────────────────────
set -euo pipefail

# ── 設定（換環境時改這裡）──────────────────────────────────────
NAS_HOST="admin@192.168.3.200"
NAS_PATH="/share/homes/admin/mailer"
IMAGE="ezdive/mailer:latest"
DOCKER_BIN="/share/CACHEDEV2_DATA/.qpkg/container-station/bin"
URL="http://192.168.3.200:8000"
# ──────────────────────────────────────────────────────────────

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

MSG="${1:-}"
if [ -z "$MSG" ]; then
  echo "❌ 請加上這次的修改說明，例如："
  echo "   ./deploy.sh \"修好排程時間顯示錯誤\""
  exit 1
fi

echo "[1/4] 檢查能不能連到 NAS ..."
if ! ssh -o ConnectTimeout=8 -o BatchMode=yes "$NAS_HOST" "echo ok" >/dev/null 2>&1; then
  echo "❌ 連不到 NAS（$NAS_HOST）。"
  echo "   這台電腦可能還沒設定好免密碼 SSH。"
  echo "   請看 CLAUDE.md 的「新電腦接手」章節設定後再試。"
  exit 1
fi

echo "[2/4] 送程式碼到 NAS ..."
scp -r app Dockerfile docker-compose.yml "$NAS_HOST:$NAS_PATH/"

echo "[3/4] 在 NAS 上重建並啟動容器（約 15-30 秒）..."
ssh "$NAS_HOST" "export PATH=$DOCKER_BIN:\$PATH && cd $NAS_PATH && docker build -t $IMAGE . && docker compose up -d"

echo "[4/4] 記錄到 GitHub ..."
if [ -n "$(git status --porcelain)" ]; then
  git add -A
  git commit -m "$MSG"
  if git push 2>/dev/null; then
    echo "   已推送到 GitHub。"
  else
    echo "   ⚠️ git push 失敗（可能是這台電腦還沒登入 GitHub）。"
    echo "      程式已上線，但沒推到 GitHub。請看 CLAUDE.md「新電腦接手」。"
  fi
else
  echo "   （沒有程式碼變動，略過 git）"
fi

echo ""
echo "✅ 完成！系統已更新：$URL"
echo "   這次：$MSG"
