#!/bin/bash

# 1. โหลดตัวแปรจากไฟล์ .env นอกสุด
if [ -f .env ]; then
    set -a
    . ./.env
    set +a
    echo "⚙️ โหลด Environment: $ENV_NAME"
else
    echo "❌ ไม่พบไฟล์ .env"
    exit 1
fi

CURRENT_BRANCH=$(git branch --show-current)
if [ -z "$CURRENT_BRANCH" ]; then
    echo "❌ ไม่สามารถหาชื่อ Branch ได้"
    exit 1
fi

# 2. ดึงโค้ดล่าสุดจาก Monorepo
echo "⬇️ กำลังดึงโค้ดล่าสุดจาก Monorepo..."
git fetch origin
git reset --hard origin/$CURRENT_BRANCH

# --- 📦 [NEW] ดึงไฟล์จริงจาก Git LFS (webp/pdf ของ P.R. Playbooks) ---
# git reset --hard จะได้ไฟล์เป็น LFS pointer (ไฟล์เล็กๆ) ไม่ใช่ไฟล์จริง
# ต้อง git lfs pull ก่อน build ไม่งั้น Docker COPY เอาตัวชี้ไปลง image → รูปไม่แสดง
#
# ⚠️ ใช้ absolute path ของ git-lfs (ไม่ใช่ command -v git-lfs) เพราะ script นี้
#    มักถูกรันแบบ non-interactive ซึ่ง ~/.local/bin ไม่อยู่ใน PATH → command -v หาไม่เจอ
#    และหลัง pull ต้องตรวจว่าไฟล์เป็นไฟล์จริง (ใหญ่พอ) ไม่ใช่ pointer 131 bytes
echo "📦 กำลังดึงไฟล์จริงจาก Git LFS..."
LFS_BIN=""
if command -v git-lfs >/dev/null 2>&1; then
    LFS_BIN="git-lfs"
elif [ -x "$HOME/.local/bin/git-lfs" ]; then
    LFS_BIN="$HOME/.local/bin/git-lfs"
fi

if [ -n "$LFS_BIN" ]; then
    "$LFS_BIN" pull
    # 🧪 ตรวจว่าได้ไฟล์จริง (webp ควรหลาย KB ขึ้นไป) — ถ้ายังเป็น pointer ให้หยุดทันที
    if [ -f frontend/public/playbooks/vol1/page-01.webp ]; then
        SIZE=$(stat -c%s frontend/public/playbooks/vol1/page-01.webp 2>/dev/null || echo 0)
        if [ "$SIZE" -lt 1000 ]; then
            echo "❌ ไฟล์ playbook ยังเป็น LFS pointer ($SIZE bytes) — git lfs pull ไม่สำเร็จ หยุด deploy"
            exit 1
        fi
    fi
    echo "✅ ไฟล์ LFS เป็นไฟล์จริงแล้ว"
else
    echo "❌ ไม่พบ git-lfs — ไฟล์ webp/pdf จะเป็น pointer (รูปไม่แสดง) หยุด deploy"
    exit 1
fi

# --- 🚀 [NEW] ดึงเลข Commit 7 หลักล่าสุดมาใช้เป็นชื่อ Image ---
export IMAGE_TAG=$(git rev-parse --short HEAD)
echo "🏷️ ตรวจพบ Commit ล่าสุด: ${IMAGE_TAG}"

# 3. เตรียมไฟล์ .env ให้ Frontend (Vite) ก่อน Build
# echo "📝 คัดลอก .env โยนให้ Frontend..."
# cp .env frontend/.env

# 4. Build Image (ใช้เลข Commit เป็น Tag แทน latest)
echo "🔨 กำลังสร้าง Docker Image เวอร์ชัน: ${IMAGE_TAG}..."
docker build -t pirivoice-${ENV_NAME}-backend:${IMAGE_TAG} ./backend
docker build --no-cache \
  --build-arg VITE_API_BASE_URL=${VITE_API_BASE_URL} \
  -t pirivoice-${ENV_NAME}-frontend:${IMAGE_TAG} ./frontend

# 5. Deploy อัปเดตระบบแบบ Zero Downtime
echo "🚀 กำลังสลับสวิตช์ระบบ $ENV_NAME แบบ Zero Downtime (เวอร์ชัน ${IMAGE_TAG})..."
docker stack deploy -c docker-compose.app.yml ${ENV_NAME}_app

echo "✅ อัปเดตเสร็จสมบูรณ์ ระบบทำงานต่อเนื่องไม่มีสะดุด!"
