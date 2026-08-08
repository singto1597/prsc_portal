#!/bin/bash
# ปล่อยโค้ดขึ้น Git remote ทั้งหมด (เหมือนโปรเจคเก่า)
set -e

git add .
git commit -m "$1"
git push origin $(git branch --show-current)

echo "✅ Push เรียบร้อย!"
