"""
Migration Rehearsal — จำลอง Production DB ทดสอบรัน migration 008 reconcile
==========================================================================
เป้า: ประเมินว่า UPDATE reconcile (comment_count / vote_count) ที่แก้ counter
ที่ drift ไว้ ใช้เวลานานแค่ไหน + วิเคราะห์ lock window (กัน deploy จริงแล้ว
Postgres lock ค้างจน request อื่นติด)

ขนาดจำลอง (จริงจังระดับ prod):
- piri_boards            5,000  บอร์ด
- piri_board_comments  100,000  คอมเมนต์ (1% ถูกซ่อน)
- piri_vote_choices     20,000  ตัวเลือกโหวต
- piri_votes           200,000  เสียงโหวต (5% soft-deleted)
- users                1,000    (FK ของ votes)

รัน: E2E_DATABASE_URL=... venv/bin/python backend/scripts/migration_rehearsal.py
"""
import asyncio
import os
import sys
import time

import asyncpg

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

DB = os.environ.get("REHEARSAL_DATABASE_URL", "postgresql://test_admin:test_password@localhost:5435/rehearsal_piri_db")

N_BOARDS = int(os.environ.get("REHEARSAL_BOARDS", 5000))
N_COMMENTS = int(os.environ.get("REHEARSAL_COMMENTS", 100_000))
N_CHOICES = int(os.environ.get("REHEARSAL_CHOICES", 20_000))
N_VOTES = int(os.environ.get("REHEARSAL_VOTES", 200_000))
N_USERS = 1000


def fmt_ms(s: float) -> str:
    return f"{s * 1000:.0f} ms" if s < 1 else f"{s:.2f} s"


async def main() -> None:
    print(f"🚀 Rehearsal DB: {DB} | boards={N_BOARDS} comments={N_COMMENTS} choices={N_CHOICES} votes={N_VOTES}")

    pool = await asyncpg.create_pool(DB, min_size=1, max_size=2)
    try:
        # 1) schema เต็ม (init_db + migrations ทั้งหมด — migration 008 ถูก apply ไปแล้วบนตารางว่าง)
        print("\n[1/5] init_db (schema + migrations 001-009)…")
        t = time.perf_counter()
        from core import init_db
        await init_db.init_db(pool)
        print(f"      init_db done in {fmt_ms(time.perf_counter() - t)}")

        # 2) seed ข้อมูลจำลอง (set-based เร็ว)
        print(f"[2/5] seed {N_BOARDS} boards + {N_COMMENTS} comments + {N_CHOICES} choices + {N_VOTES} votes…")
        t = time.perf_counter()
        async with pool.acquire() as conn:
            await conn.execute("TRUNCATE piri_boards, piri_board_comments, piri_vote_choices, piri_votes RESTART IDENTITY CASCADE")
            # users (FK ของ votes) + room
            await conn.execute("TRUNCATE users, students RESTART IDENTITY CASCADE")
            await conn.execute(
                "INSERT INTO rooms (room_code, room_name, level) VALUES ('ม.99/99','ม.99/99','ม.99')"
            )
            await conn.execute(
                """
                INSERT INTO users (id, username, password_hash, full_name)
                SELECT g, 'reh' || g, 'x', 'Rehearsal ' || g
                FROM generate_series(1, $1) g
                """,
                N_USERS
            )
            await conn.execute(
                """
                INSERT INTO piri_boards (id, board_type, title, description, status, comment_count, view_count)
                SELECT g, CASE WHEN g % 2 = 0 THEN 'vote' ELSE 'talk' END,
                       'Board ' || g, 'desc ' || g, 'active', 0, 0
                FROM generate_series(1, $1) g
                """,
                N_BOARDS
            )
            # คอมเมนต์: กระจายทั่ว board, 1% is_hidden_by_admin (เทียบกับ comment_count ที่นับเฉพาะไม่ซ่อน)
            await conn.execute(
                """
                INSERT INTO piri_board_comments (board_id, user_id, body, is_hidden_by_admin)
                SELECT (g % $1) + 1, NULL, 'comment ' || g, (g % 100 = 0)
                FROM generate_series(1, $2) g
                """,
                N_BOARDS, N_COMMENTS
            )
            # vote_choices: กระจายทั่ว board
            await conn.execute(
                """
                INSERT INTO piri_vote_choices (board_id, choice_text, sort_order)
                SELECT (g % $1) + 1, 'choice ' || g, g % 4
                FROM generate_series(1, $2) g
                """,
                N_BOARDS, N_CHOICES
            )
            # votes: กระจายทั่ว choice, 5% soft-deleted
            # (board,user) distinct ตามคอนสตรัคชัน — user = g//N_BOARDS → ต่อ board มี user ไม่ซ้ำ
            # (กันชน partial unique uq_piri_votes_board_user_active)
            await conn.execute(
                """
                INSERT INTO piri_votes (board_id, choice_id, user_id, deleted_at)
                SELECT (g % $1) + 1, (g % $2) + 1, ((g / $1) % $3) + 1,
                       CASE WHEN g % 20 = 0 THEN NOW() ELSE NULL END
                FROM generate_series(1, $4) g
                """,
                N_BOARDS, N_CHOICES, N_USERS, N_VOTES
            )
            # ปั่น counter ให้ drift (จำลองของเก่าที่ไม่เคยลด)
            await conn.execute("UPDATE piri_boards SET comment_count = id * 3 + 7")
            await conn.execute("UPDATE piri_vote_choices SET vote_count = id % 50")
        print(f"      seeded in {fmt_ms(time.perf_counter() - t)}")

        # 3) ตรวจค่า drift ก่อน reconcile
        async with pool.acquire() as conn:
            b0 = await conn.fetchval("SELECT comment_count FROM piri_boards ORDER BY id LIMIT 1")
            v0 = await conn.fetchval("SELECT vote_count FROM piri_vote_choices ORDER BY id LIMIT 1")
            print(f"      drift ก่อน: board#1 comment_count={b0} (ควรเป็น 0 หลัง fix) | choice#1 vote_count={v0}")

        # 4) ⏱️ รัน migration 008 reconcile — อันที่ user อยากรู้ว่าใช้เวลานานไหม
        # (แบบ aggregate+JOIN — เวอร์ชันปัจจุบันของ migration 008 หลัง rehearsal เจอว่า correlated
        #  subquery ช้า ~100 เท่า → lock ค้างนาน)
        print("\n[4/5] ⏱️  รัน migration 008 reconcile (aggregate+JOIN — comment_count + vote_count)…")
        async with pool.acquire() as conn:
            t = time.perf_counter()
            await conn.execute("""
                UPDATE piri_boards b
                SET comment_count = COALESCE(cnt.c, 0), updated_at = NOW()
                FROM (
                    SELECT pb.id AS bid, agg.c
                    FROM piri_boards pb
                    LEFT JOIN (
                        SELECT board_id, COUNT(*) AS c
                        FROM piri_board_comments
                        WHERE deleted_at IS NULL AND is_hidden_by_admin = FALSE
                        GROUP BY board_id
                    ) agg ON agg.board_id = pb.id
                ) cnt
                WHERE cnt.bid = b.id
            """)
            t_comment = time.perf_counter() - t

            t = time.perf_counter()
            await conn.execute("""
                UPDATE piri_vote_choices vc
                SET vote_count = COALESCE(cnt.c, 0), updated_at = NOW()
                FROM (
                    SELECT vc2.id AS cid, agg.c
                    FROM piri_vote_choices vc2
                    LEFT JOIN (
                        SELECT choice_id, COUNT(*) AS c
                        FROM piri_votes
                        WHERE deleted_at IS NULL
                        GROUP BY choice_id
                    ) agg ON agg.choice_id = vc2.id
                ) cnt
                WHERE cnt.cid = vc.id
            """)
            t_vote = time.perf_counter() - t

        print(f"      ✅ comment_count reconcile: {fmt_ms(t_comment)}  (อัปเดต {N_BOARDS} แถว)")
        print(f"      ✅ vote_count reconcile:     {fmt_ms(t_vote)}  (อัปเดต {N_CHOICES} แถว)")

        # 5) verify ค่าตรง
        async with pool.acquire() as conn:
            expected = await conn.fetchval(
                "SELECT COUNT(*) FROM piri_board_comments WHERE board_id = 1 AND deleted_at IS NULL AND is_hidden_by_admin = FALSE"
            )
            got = await conn.fetchval("SELECT comment_count FROM piri_boards WHERE id = 1")
            print(f"\n[5/5] verify board#1 comment_count = {got} (ตรงกับจริง {expected}) ✓" if got == expected else f"      ✗ MISMATCH {got} != {expected}")

        print("\n" + "=" * 70)
        print("📊 สรุป lock window:")
        print(f"  - comment_count UPDATE กินเวลารวม {fmt_ms(t_comment)} — ในช่วงนี้ Postgres ถือ ROW EXCLUSIVE")
        print("    lock บน piri_boards (ทุกแถวถูกอัปเดต) → ใคร INSERT/UPDATE piri_boards พร้อมกันจะรอ")
        print(f"  - vote_count UPDATE กินเวลารวม {fmt_ms(t_vote)} — lock ROW EXCLUSIVE บน piri_vote_choices")
        print(f"  - รวม reconcile ทั้งหมด {fmt_ms(t_comment + t_vote)}")
        print("  - การอ่าน (SELECT) ไม่โดน lock นี้ (MVCC) — มีผลกับ writer ของตารางนั้นเท่านั้น")
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
