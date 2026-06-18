#!/bin/bash
# 多架構映像檔打包腳本
# 用途：在有 Docker Desktop 的 Mac 或 x86 Linux 上執行，產出同時支援 ARM32v7 與 amd64 的映像檔
# 執行前提：已登入 Docker Hub（docker login）

set -e

IMAGE_NAME="ezdive/mailer"
TAG="${1:-latest}"

echo "=== 易潛企業開發信系統 — 多架構打包 ==="
echo "映像名稱：${IMAGE_NAME}:${TAG}"
echo ""

# 確認 buildx 可用
echo "[1/4] 初始化 buildx 建置器..."
docker buildx rm multiarch-builder 2>/dev/null || true
docker buildx create --name multiarch-builder --use
docker buildx inspect --bootstrap

# 建立並推送多架構映像
echo ""
echo "[2/4] 開始建置（amd64 + arm/v7）..."
echo "      這個步驟需要幾分鐘，請耐心等待..."
docker buildx build \
  --platform linux/amd64,linux/arm/v7 \
  --tag "${IMAGE_NAME}:${TAG}" \
  --push \
  .

echo ""
echo "[3/4] 驗證映像架構..."
docker buildx imagetools inspect "${IMAGE_NAME}:${TAG}"

echo ""
echo "[4/4] 完成！"
echo ""
echo "✅ 映像已推送到 Docker Hub："
echo "   ${IMAGE_NAME}:${TAG}"
echo ""
echo "在 QNAP NAS 上執行以下指令拉取並啟動："
echo "   docker-compose pull"
echo "   docker-compose up -d"
