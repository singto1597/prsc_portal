#!/bin/bash
# =====================================================================
# 🛡️ setup_traefik.sh — ติดตั้ง Traefik Proxy ตัวกลาง (1 เครื่อง 1 อัน)
#
# ติดตั้งครั้งเดียวต่อเครื่อง → หลังจากนี้ ทุกระบบ / หลายโปรเจค / หลาย
# environment (staging, production, ...) จะแชร์ Traefik ตัวเดียวกันนี้
# ผ่าน network "traefik-public" (setup.sh ของแต่ละโปรเจคแค่ใช้ ไม่ต้อง deploy ใหม่)
#
# ทำอะไรบ้าง:
#   1) เปิด Docker Swarm (ถ้ายังไม่เคยเปิด)
#   2) สร้าง network traefik-public (ถ้ายังไม่มี)
#   3) Deploy docker-compose.proxy.yml เป็น stack global_proxy (พอร์ต 80)
#
# รันซ้ำได้ (idempotent) — ถ้าติดตั้งแล้วจะข้ามไป
#
# ตัวเลือก:
#   ./setup_traefik.sh     # ติดตั้ง / ตรวจสอบ (รันซ้ำได้)
#   ./setup_traefik.sh --remove   # ถอด Traefik ออก (docker stack rm global_proxy)
# =====================================================================
set -euo pipefail

cd "$(dirname "$0")"

# ---------- helper ----------
red()    { printf "\033[1;31m%s\033[0m\n" "$*"; }
green()  { printf "\033[1;32m%s\033[0m\n" "$*"; }
yellow() { printf "\033[1;33m%s\033[0m\n" "$*"; }
cyan()   { printf "\033[1;36m%s\033[0m\n" "$*"; }
step()   { echo; cyan "▶ $*"; }

usage() {
    awk 'NR>=3 && /^# ===/ { exit } NR>=3 && /^#/ { gsub(/^# ?/, ""); print }' "$0"
    exit 0
}

# ---------- flags ----------
REMOVE=0
for arg in "$@"; do
    case "$arg" in
        --remove)  REMOVE=1 ;;
        -h|--help) usage ;;
        *)         yellow "⚠️  ไม่รู้จักตัวเลือก: $arg (ดู ./setup_traefik.sh --help)" ;;
    esac
done

if ! command -v docker >/dev/null 2>&1; then
    red "❌ ไม่พบคำสั่ง docker ในเครื่อง"
    exit 1
fi
if ! docker info >/dev/null 2>&1; then
    red "❌ Docker daemon ไม่ทำงาน — เปิด Docker ก่อน (เช่น systemctl start docker)"
    exit 1
fi

# ---------- ถอด Traefik ----------
if [ "$REMOVE" = "1" ]; then
    step "ถอด Traefik ออกจากเครื่อง"
    docker stack rm global_proxy || true
    green "   ✔ ถอด global_proxy แล้ว (network traefik-public คงไว้ — ระบบอื่นอาจใช้อยู่)"
    exit 0
fi

# =====================================================================
# 1) เปิด Docker Swarm (ถ้ายังไม่เคยเปิด)
# =====================================================================
step "1/3 ตรวจสอบ Docker Swarm"
if docker node ls >/dev/null 2>&1; then
    green "   ✔ Swarm เปิดอยู่แล้ว"
else
    echo "   ⏳ กำลังเปิดโหมด Swarm (docker swarm init)..."
    docker swarm init
    green "   ✔ Swarm พร้อมใช้แล้ว"
fi

# =====================================================================
# 2) สร้าง network traefik-public
# =====================================================================
step "2/3 สร้าง Network traefik-public"
if docker network ls --format '{{.Name}}' | grep -qx "traefik-public"; then
    green "   ✔ Network traefik-public มีอยู่แล้ว"
else
    echo "   ⏳ กำลังสร้าง Network traefik-public ..."
    docker network create --driver=overlay traefik-public
    green "   ✔ สร้าง Network traefik-public สำเร็จ"
fi

# =====================================================================
# 3) Deploy Traefik
# =====================================================================
step "3/3 Deploy Traefik (stack global_proxy)"
if docker stack ls --format '{{.Name}}' | grep -qx "global_proxy"; then
    green "   ✔ Traefik (global_proxy) รันอยู่แล้ว — พร้อมใช้ร่วมกับทุกระบบ"
else
    echo "   ⏳ กำลัง Deploy Traefik ..."
    docker stack deploy -c docker-compose.proxy.yml global_proxy
    green "   ✔ ติดตั้ง Traefik เสร็จแล้ว — ทุกระบบใช้ตัวกลางนี้ได้เลย (พอร์ต 80)"
fi

echo
green "✅ ============================================================"
green "✅ Traefik พร้อมใช้งานแล้ว (ครั้งเดียวต่อเครื่อง)"
green "✅ ============================================================"
echo
echo "   🛡️  รับทราฟฟิก:  port 80 (และ 443 ถ้าเปิด HTTPS ใน docker-compose.proxy.yml)"
echo "   🌐  ระบบอื่น/โปรเจคอื่น:  แค่ติด network \"traefik-public\" + label traefik.enable=true"
echo "      (setup.sh ของแต่ละโปรเจคทำให้อัตโนมัติ)"
echo
echo "   📌 เปลี่ยน config Traefik (เช่น เปิด HTTPS): แก้ docker-compose.proxy.yml → ./setup_traefik.sh ใหม่"
