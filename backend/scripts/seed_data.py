"""
Seed Data สำหรับ PRSC Portal — สร้างข้อมูลตัวอย่างสำหรับนำเสนอ

วิธีรัน:
    cd backend
    DATABASE_URL=postgresql://... ./venv/bin/python -m scripts.seed_data

หรือผ่าน docker:
    docker compose -f docker-compose.test.yml ... (สำหรับเทส DB)

สร้าง:
  - ห้องเรียน 3 ห้อง (ม.4/1, ม.4/2, ม.5/1)
  - นักเรียน 10 คน/ห้อง พร้อมตำแหน่ง (หัวหน้าห้อง, รองวิชาการ, รองวินัย, รองกิจกรรม, รองปฏิคม)
  - ประธานระดับ + สภานักเรียน + ประธานสภา (Admin)
  - ปัญหา/ข้อเสนอแนะ ตัวอย่าง ~15 เรื่อง (หลากหลาย topic/category/status)
  - รหัสผ่านเริ่มต้น = เลขรหัสนักเรียน (เช่น 41001 → 41001/41001)
"""
import asyncio
import sys
import os
import json
from datetime import datetime, timedelta, timezone

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import settings
from services import auth_service
from services.issue_service import accept_issue, escalate_issue, add_step, complete_step, resolve_issue

# 🔑 รหัสผ่านเริ่มต้น = เลขรหัสนักเรียน (เช่น 47001 → 47001/47001)
# (กันใช้รหัสเดียวกันหมด — ตามที่ครูกำหนด)

# ข้อมูลตัวอย่าง: (student_id, ห้อง, เลขที่, ชื่อ, นามสกุล, ตำแหน่ง)
STUDENTS = [
    # ม.4/1
    ("41001", "ม.4/1", 1, "สมชาย", "ใจดี", "หัวหน้าห้อง"),
    ("41002", "ม.4/1", 2, "สมหญิง", "สวยงาม", "รองวิชาการ"),
    ("41003", "ม.4/1", 3, "อนุชา", "มีสุข", "รองวินัย"),
    ("41004", "ม.4/1", 4, "ปิยะ", "รักเรียน", "รองกิจกรรม"),
    ("41005", "ม.4/1", 5, "นภา", "สดใส", "รองปฏิคม"),
    ("41006", "ม.4/1", 6, "กิตติ", "มาเรียน", "นักเรียน"),
    ("41007", "ม.4/1", 7, "สุภาพร", "ขยัน", "นักเรียน"),
    ("41008", "ม.4/1", 8, "วีระ", "ตั้งใจ", "นักเรียน"),
    ("41009", "ม.4/1", 9, "มานะ", "เพียรพยายาม", "นักเรียน"),
    ("41010", "ม.4/1", 10, "จันทร์", "แจ่มใส", "นักเรียน"),
    # ม.4/2
    ("42001", "ม.4/2", 1, "ธนกฤต", "สุวรรณ", "หัวหน้าห้อง"),
    ("42002", "ม.4/2", 2, "พรพิมล", "ทองดี", "รองวิชาการ"),
    ("42003", "ม.4/2", 3, "ศักดิ์สิทธิ์", "มีชัย", "รองวินัย"),
    ("42004", "ม.4/2", 4, "กาญจนา", "งามสง่า", "รองกิจกรรม"),
    ("42005", "ม.4/2", 5, "อภิชาต", "เก่งกล้า", "รองปฏิคม"),
    ("42006", "ม.4/2", 6, "รัตนา", "สดสวย", "นักเรียน"),
    ("42007", "ม.4/2", 7, "พิชัย", "มั่นคง", "นักเรียน"),
    ("42008", "ม.4/2", 8, "อรทัย", "เบิกบาน", "นักเรียน"),
    ("42009", "ม.4/2", 9, "ชัยวัฒน์", "ก้าวหน้า", "นักเรียน"),
    ("42010", "ม.4/2", 10, "บุญญา", "รุ่งเรือง", "นักเรียน"),
    # ม.5/1
    ("51001", "ม.5/1", 1, "ณัฐพล", "แสงดาว", "หัวหน้าห้อง"),
    ("51002", "ม.5/1", 2, "วิภาดา", "หอมหวาน", "รองวิชาการ"),
    ("51003", "ม.5/1", 3, "ประเสริฐ", "กล้าหาญ", "รองวินัย"),
    ("51004", "ม.5/1", 4, "สุธิดา", "น่ารัก", "รองกิจกรรม"),
    ("51005", "ม.5/1", 5, "คมสัน", "แข็งแรง", "รองปฏิคม"),
    ("51006", "ม.5/1", 6, "นฤมล", "สดชื่น", "นักเรียน"),
    ("51007", "ม.5/1", 7, "ทวี", "ศักดิ์", "นักเรียน"),
    ("51008", "ม.5/1", 8, "เพ็ญศรี", "แจ่มจ้า", "นักเรียน"),
    ("51009", "ม.5/1", 9, "เอกพล", "มั่งมี", "นักเรียน"),
    ("51010", "ม.5/1", 10, "ลัดดา", "ละมุน", "นักเรียน"),
]

# ระดับชั้นบน: ประธานระดับ + สภา
COUNCIL = [
    ("99001", "ม.5/2", 1, "ประธาน", "สภานักเรียน", "ประธานสภา"),
    ("99002", "ม.5/2", 2, "รอง", "สภานักเรียน", "สภานักเรียน"),
    ("99003", "ม.5/2", 3, "เลขา", "สภานักเรียน", "สภานักเรียน"),
    # ประธานระดับ ม.4 (รับเรื่องที่ escalate มาจากห้อง ม.4)
    ("99401", "ม.4/1", 11, "ประธาน", "ระดับ ม.4", "ประธานระดับ"),
]

# ตัวอย่างปัญหา: (reporter_index, main_category, category, title, desc, anonymous)
# หมวดหลัก: suggestion (เสนอความคิดเห็น) / wellbeing (สุขภาวะทางกายและใจ) / report (แจ้งเหตุ)
SAMPLE_ISSUES = [
    (6, "report", "complaint", "เสียงดังรบกวนเวลานอนพักกลางวัน", "มีนักเรียนส่งเสียงดังบริเวณหน้าห้องตอนพักกลางวัน รบกวนการนอน/พักผ่อนของเพื่อนในห้อง", False),
    (7, "report", "complaint", "ห้องน้ำชั้น 3 ไม่มีน้ำใช้", "ห้องน้ำชายชั้น 3 เปิดก๊อกแล้วไม่มีน้ำไหล ต้องไปใช้ห้องน้ำชั้นอื่นไกลมาก", False),
    (8, "report", "complaint", "พัดลมในห้องเสียงดัง", "พัดลมตัวหลังของห้องส่งเสียงดังมากตอนเปิด เบลทสั่น อยากให้ช่วยตรวจสอบ", False),
    (9, "suggestion", "activity", "อยากให้มีกีฬาสีของระดับชั้น", "อยากเสนอให้ทางสภานักเรียนจัดกิจกรรมกีฬาสีระดับชั้น ม.4 เพื่อสร้างความสามัคคี", False),
    (10, "report", "complaint", "ห้องสมุดเปิดช้าเกินไป", "ห้องสมุดเปิดตอน 9 โมง อยากให้เปิดก่อนเข้าเรียน เพื่อให้ยืม-คืนหนังสือได้ทัน", False),
    (11, "report", "complaint", "โต๊ะเรียนชำรุด", "โต๊ะของเพื่อนเลขที่ 12 ขาโยก เวลานั่งเขียนหนังสือไม่มั่นคง อยากให้เปลี่ยน/ซ่อม", True),
    (12, "report", "complaint", "สนามบาสหลังเลิกเรียนไฟไม่พอ", "สนามบาสไฟส่องสว่างน้อยมาก ตอนเย็นหลังเลิกเรียนเล่นไม่เห็นลูกบอล", False),
    (13, "suggestion", "discipline", "อยากให้ปรับเวลาลงโทษมาสาย", "มาสายทีถูกตัดคะแนนเยอะเกินไป อยากเสนอให้ลดโทษ หรือมี grace period", False),
    (14, "report", "complaint", "ถังขยะหน้าห้องเต็มทุกวัน", "ถังขยะหน้าห้องเต็มเร็วมาก มีขยะล้นเกลื่อนทุกช่วงบ่าย อยากให้เพิ่มรอบเก็บ", False),
    (15, "report", "complaint", "เครื่องทำน้ำเย็นพัง", "เครื่องทำน้ำเย็นชั้น 4 ไม่เย็นแล้ว น้ำอุ่น อยากให้ซ่อม/เปลี่ยน", True),
    (16, "report", "grievance", "ครูบางวิชาไม่ส่งการบ้านคืน", "การบ้านวิชาหนึ่งส่งไปแล้ว 2 อาทิตย์ ยังไม่ได้คืน อยากให้ตรวจแล้วส่งคืนเร็วขึ้น", False),
    (17, "suggestion", "activity", "อยากได้รางวัลตอบแทนคนช่วยงานสภา", "เพื่อนๆ ที่มาช่วยงานกิจกรรมของสภานักเรียนทุ่มเทมาก อยากเสนอให้มีรางวัล/ชื่นชม", False),
    (18, "report", "complaint", "มอเตอร์ไซค์หน้าประตูจอดบังทางเข้า", "มีมอเตอร์ไซค์จอดกีดขวางทางเข้าโรงเรียนหน้าประตู 3 ทุกเช้า อยากให้จัดการ", False),
    (19, "report", "complaint", "ขยะในสนามหลังอาคารเยอะ", "สนามหลังอาคาร 1 มีขยะเยอะมาก ไม่มีใครเก็บมานาน อยากให้ช่วยจัดเก็บ", True),
    (20, "suggestion", "academic", "อยากได้ไฟล์สรุปบทเรียนจากครู", "อยากเสนอให้ครูแต่ละวิชาแชร์ไฟล์สรุปบทเรียนหลังจบชั่วโมง เพื่อทบทวน", False),
    (21, "wellbeing", "mental_health", "เพื่อนเครียดจากสอบปลายภาค", "มีเพื่อนในห้องเครียดมากช่วงใกล้สอบ นอนไม่หลับ อยากให้มีกิจกรรมผ่อนคลาย", True),
    (22, "wellbeing", "physical_health", "ป่วยระหว่างเรียน ไม่มีที่พักฟื้น", "เวลาป่วยระหว่างเรียนไม่มีห้องพักสำหรับนอนพัก ต้องนั่งรอผู้ปกครองในโรงอาหาร", False),
    (23, "wellbeing", "physical_health", "อาหารกลางวันเหลือน้อยตอนพักสาย", "ห้องเรียนที่กินช่วงพักสายได้อาหารเหลือน้อย อยากให้จัดสรรให้ทั่วถึง", False),
    (24, "suggestion", "democracy", "อยากให้ประกาศผลเลือกตั้งสภาฯ โปร่งใส", "เสนอให้ประกาศคะแนนเลือกตั้งสภานักเรียนแบบเปิดเผยรายห้อง เพื่อความโปร่งใส", False),
]


async def main():
    pool = await __import__("asyncpg").create_pool(settings.DATABASE_URL, min_size=1, max_size=5)
    try:
        from core.init_db import init_db
        await init_db(pool)

        user_ids = {}  # student_id -> user_id
        room_ids = {}  # room_code -> room_id
        student_role = {}  # student_id -> role

        print("🚀 สร้างนักเรียน + ห้องเรียน...")
        async with pool.acquire() as conn:
            async with conn.transaction():
                for sid, room_code, no, first, last, role_label in STUDENTS:
                    # room
                    room = await conn.fetchval("SELECT id FROM rooms WHERE room_code=$1 AND deleted_at IS NULL", room_code)
                    if not room:
                        level = room_code.split("/")[0] if "/" in room_code else room_code
                        room = await conn.fetchval(
                            "INSERT INTO rooms (room_code, room_name, level, room_number) VALUES ($1,$2,$3,NULL) RETURNING id",
                            room_code, room_code, level
                        )
                    room_ids[room_code] = room

                    from services.student_service import map_role_label
                    role = map_role_label(role_label)
                    student_role[sid] = role

                    # user
                    user = await conn.fetchval("SELECT id FROM users WHERE username=$1", sid)
                    if not user:
                        user = await conn.fetchval(
                            "INSERT INTO users (username, password_hash, full_name) VALUES ($1,$2,$3) RETURNING id",
                            sid, auth_service.hash_password(sid), f"{first} {last}"
                        )
                    user_ids[sid] = user

                    # permissions + is_admin ตาม roles.json (ครูสภา/แอดมิน = is_admin)
                    role_perms = auth_service.get_role_permissions(role)
                    role_is_admin = auth_service.get_role_is_admin(role)
                    staff_level = level if role == "teacher" else None  # ครูทั่วไป → ระดับชั้น

                    # student
                    existing = await conn.fetchval(
                        "SELECT id FROM students WHERE room_id=$1 AND student_id=$2", room, sid
                    )
                    if existing:
                        await conn.execute(
                            """
                            UPDATE students SET user_id=$1, first_name=$2, last_name=$3,
                                class_role=$4, staff_level=$5, is_admin=$6, permissions=$7, status='active'
                            WHERE id=$8
                            """,
                            user, first, last, role, staff_level, role_is_admin,
                            json.dumps(role_perms), existing
                        )
                    else:
                        await conn.execute(
                            """
                            INSERT INTO students (room_id, user_id, student_id, student_no, prefix,
                                first_name, last_name, class_role, staff_level, is_admin, permissions, status)
                            VALUES ($1,$2,$3,$4,'', $5,$6,$7,$8,$9,$10,'active')
                            """,
                            room, user, sid, no, first, last, role, staff_level,
                            role_is_admin, json.dumps(role_perms)
                        )

                # สภานักเรียน (สร้าง room ม.5/2)
                for sid, room_code, no, first, last, role_label in COUNCIL:
                    room = await conn.fetchval("SELECT id FROM rooms WHERE room_code=$1 AND deleted_at IS NULL", room_code)
                    if not room:
                        room = await conn.fetchval(
                            "INSERT INTO rooms (room_code, room_name, level, room_number) VALUES ($1,$2,$3,NULL) RETURNING id",
                            room_code, room_code, "ม.5"
                        )
                    role = {
                        "ประธานสภา": "council_president",
                        "ประธานระดับ": "level_president",
                    }.get(role_label, "council_member")
                    is_admin_flag = auth_service.get_role_is_admin(role)  # ตาม roles.json
                    user = await conn.fetchval("SELECT id FROM users WHERE username=$1", sid)
                    if not user:
                        user = await conn.fetchval(
                            "INSERT INTO users (username, password_hash, full_name) VALUES ($1,$2,$3) RETURNING id",
                            sid, auth_service.hash_password(sid), f"{first} {last}"
                        )
                    existing = await conn.fetchval(
                        "SELECT id FROM students WHERE room_id=$1 AND student_id=$2", room, sid
                    )
                    if existing:
                        await conn.execute(
                            "UPDATE students SET user_id=$1, first_name=$2, last_name=$3, class_role=$4, is_admin=$5, permissions=$6, status='active' WHERE id=$7",
                            user, first, last, role, is_admin_flag,
                            json.dumps(auth_service.get_role_permissions(role)), existing
                        )
                    else:
                        await conn.execute(
                            "INSERT INTO students (room_id, user_id, student_id, student_no, prefix, first_name, last_name, class_role, is_admin, permissions, status) VALUES ($1,$2,$3,$4,'', $5,$6,$7,$8,$9,'active')",
                            room, user, sid, no, first, last, role, is_admin_flag,
                            json.dumps(auth_service.get_role_permissions(role))
                        )
                    user_ids[sid] = user

                # 👨‍🏫 STAFF: ครูสภา (school-wide) / ครูทั่วไป (ระดับชั้น) / แอดมิน (school-wide)
                # (sid, room_code หรือ None, ชื่อ, นามสกุล, ตำแหน่งใน Excel)
                STAFF = [
                    ("88001", None, "ครู", "ที่ปรึกษาสภา", "ครูสภา"),
                    ("88002", None, "ครู", "ที่ปรึกษารอง", "ครูสภา"),
                    ("88003", "ม.4/1", "ครู", "ประจำชั้น ม.4", "ครูทั่วไป"),
                    ("88004", "ม.5/1", "ครู", "ประจำชั้น ม.5", "ครูทั่วไป"),
                    ("99000", None, "แอดมิน", "ระบบ", "แอดมิน"),
                ]
                for sid, room_code, first, last, role_label in STAFF:
                    role = map_role_label(role_label)
                    room = None
                    staff_level = None
                    if room_code:
                        room = await conn.fetchval("SELECT id FROM rooms WHERE room_code=$1 AND deleted_at IS NULL", room_code)
                        staff_level = await conn.fetchval("SELECT level FROM rooms WHERE id=$1", room)
                    role_perms = auth_service.get_role_permissions(role)
                    role_is_admin = auth_service.get_role_is_admin(role)

                    user = await conn.fetchval("SELECT id FROM users WHERE username=$1", sid)
                    if not user:
                        user = await conn.fetchval(
                            "INSERT INTO users (username, password_hash, full_name) VALUES ($1,$2,$3) RETURNING id",
                            sid, auth_service.hash_password(sid), f"{first} {last}"
                        )
                    user_ids[sid] = user

                    # admin/ครูสภา: room_id = NULL (ไม่ผูกห้อง — school-wide)
                    existing = await conn.fetchval(
                        """
                        SELECT id FROM students
                        WHERE student_id=$1 AND room_id IS NOT DISTINCT FROM $2 AND deleted_at IS NULL
                        """, sid, room
                    )
                    if existing:
                        await conn.execute(
                            """
                            UPDATE students SET user_id=$1, first_name=$2, last_name=$3,
                                class_role=$4, staff_level=$5, is_admin=$6, permissions=$7, status='active'
                            WHERE id=$8
                            """,
                            user, first, last, role, staff_level, role_is_admin,
                            json.dumps(role_perms), existing
                        )
                    else:
                        await conn.execute(
                            """
                            INSERT INTO students (room_id, user_id, student_id, student_no, prefix,
                                first_name, last_name, class_role, staff_level, is_admin, permissions, status)
                            VALUES ($1,$2,$3,0,'', $4,$5,$6,$7,$8,$9,'active')
                            """,
                            room, user, sid, first, last, role, staff_level,
                            role_is_admin, json.dumps(role_perms)
                        )

        print("✅ นักเรียน + ห้องเรียน สร้างเสร็จ")

        # สร้างตัวอย่างปัญหา
        print("🚀 สร้างตัวอย่างปัญหา...")
        from services import issue_service

        # ใช้ session: แต่ละเรื่องสร้างโดย student แล้วให้หัวหน้าห้องรับ
        issue_ids = []
        # SAMPLE_ISSUES[0] คือ index ใน STUDENTS ของผู้รายงาน
        for reporter_index, main_category, category, title, desc, anonymous in SAMPLE_ISSUES:
            if reporter_index >= len(STUDENTS):
                continue
            reporter_sid = STUDENTS[reporter_index][0]  # student_id จาก index ใน STUDENTS
            reporter_user = user_ids.get(reporter_sid)
            if not reporter_user:
                continue

            # วนรอบผู้รายงาน — ใช้ reporter_sid เป็น student ต้นเรื่อง
            room_id = None
            # หาห้องของผู้รายงาน
            async with pool.acquire() as conn:
                room_id = await conn.fetchval(
                    "SELECT room_id FROM students WHERE user_id=$1 AND status='active'", reporter_user
                )

            issue_id = await issue_service.create_issue(
                pool, reporter_user, main_category, category, title, desc, anonymous, room_id
            )
            issue_ids.append(issue_id)

        # ให้หัวหน้าห้องรับเรื่อง + เพิ่มขั้นตอน + บางเรื่อง resolve / escalate
        print("🚀 กำหนดสถานะตัวอย่าง (รับเรื่อง/ขั้นตอน/ปิดเรื่อง/ส่งต่อ)...")
        # หา user_id ของหัวหน้าห้อง ม.4/1 (41001)
        head_user = user_ids.get("41001")
        head_5 = user_ids.get("51001")
        council_president = user_ids.get("99001")

        # เรื่องแรก (index 0) — กำลังดำเนินการ (มีขั้นตอน)
        if issue_ids and head_user:
            await accept_issue(pool, head_user, issue_ids[0], 3)
            await add_step(pool, head_user, issue_ids[0], "ตรวจสอบพื้นที่", "ลงพื้นที่ดูสถานที่เกิดเหตุ")
            await add_step(pool, head_user, issue_ids[0], "แจ้งผู้ที่เกี่ยวข้อง", "ได้แจ้งเวรประจำชั้นแล้ว")
            await add_step(pool, head_user, issue_ids[0], "ดำเนินการแก้ไข", "กำลังดำเนินการ")
            await complete_step(pool, head_user, issue_ids[0], (await _get_step_ids(pool, issue_ids[0]))[0])

        # เรื่องที่ 2 — resolve (เสร็จแล้ว)
        if len(issue_ids) > 1 and head_user:
            await accept_issue(pool, head_user, issue_ids[1], 2)
            await add_step(pool, head_user, issue_ids[1], "แจ้งช่างซ่อม", "แจ้งช่างประจำอาคารแล้ว")
            await resolve_issue(pool, head_user, issue_ids[1], "ช่างซ่อมแล้ว น้ำไหลปกติ")

        # เรื่องที่ 3 — escalate ครบ chain: room → level → council (พัดลมห้อง ม.4/1)
        # รับเรื่องโดยหัวหน้าห้อง ม.4/1 (41001) → ส่งต่อประธานระดับ (99401) → ประธานสภา (99001)
        level_president = user_ids.get("99401")
        if len(issue_ids) > 2 and head_user:
            await accept_issue(pool, head_user, issue_ids[2], 3)
            await escalate_issue(pool, head_user, issue_ids[2], "เกินความสามารถของระดับห้อง ต้องใช้ผู้เชี่ยวชาญ")
            # ประธานระดับรับ (ระดับ level)
            if level_president:
                await accept_issue(pool, level_president, issue_ids[2], 5)
                await escalate_issue(pool, level_president, issue_ids[2], "ต้องประสานงานข้ามสายงานระดับโรงเรียน")
                # ประธานสภารับ (ระดับ council)
                if council_president:
                    await accept_issue(pool, council_president, issue_ids[2], 7)
                    await add_step(pool, council_president, issue_ids[2], "ประสานงานฝ่ายอาคารสถานที่", "ได้ประสานงานกับฝ่ายอาคารสถานที่แล้ว")

        # บันทึก login audit สำหรับ dashboard (จำลอง)
        async with pool.acquire() as conn:
            for sid, uid in user_ids.items():
                if sid in ("41001", "41002", "99001", "41006", "51001"):
                    await conn.execute(
                        """
                        INSERT INTO audit_logs (action, actor_identifier, client_source, service_name, user_id)
                        VALUES ('login', $1, 'web', 'auth_service', $2)
                        """,
                        sid, uid
                    )

        print("🎉 Seed Data เสร็จสมบูรณ์!")
        print("   รหัสนักเรียนตัวอย่าง: 41001 (หัวหน้าห้อง ม.4/1), 41002 (รองวิชาการ), 99001 (ประธานสภา)")
        print("   รหัสผ่าน: 1234 ทุกบัญชี")

    finally:
        await pool.close()


async def _get_step_ids(pool, issue_id):
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT id FROM issue_steps WHERE issue_id=$1 ORDER BY step_order", issue_id)
    return [r["id"] for r in rows]


if __name__ == "__main__":
    asyncio.run(main())
