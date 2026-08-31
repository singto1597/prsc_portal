import { defineStore } from 'pinia';
import { ref } from 'vue';
import { getUnreadCounts, markRead } from '@/services/notification';
import type { MarkReadPayload } from '@/types/notification';

// 🔔 Unread badge state — poll ทุก 30 วิ (pattern เดียวกับ ImportStudents.vue)
//   MainLayout เรียก startPolling() → badge บนเมนู + กระดิ่งอัปเดตเอง

const POLL_INTERVAL_MS = 30_000;
const POLL_FAIL_LIMIT = 3;

export const useNotificationsStore = defineStore('notifications', () => {
  const counts = ref<Record<string, number>>({});
  const total = ref(0);

  async function fetchCounts() {
    try {
      const res = await getUnreadCounts();
      counts.value = res.counts;
      total.value = res.total;
    } catch {
      // best-effort: badge เงียบตอน error (ไม่เด้ง error ให้ผู้ใช้)
    }
  }

  // mark อ่าน แล้ว refetch ทันที (badge ลดทันทีไม่ต้องรอ poll รอบหน้า)
  // กลืน error เอง → caller ใช้ `void read(...)` ได้ปลอดภัย (ไม่เกิด unhandled rejection)
  async function read(payload: MarkReadPayload) {
    try {
      await markRead(payload);
    } catch {
      // best-effort: badge จะอัปเดตเองตอน poll รอบหน้า
    }
    await fetchCounts();
  }

  // ---- polling ----
  let timer: number | null = null;
  let inFlight = false;
  let failStreak = 0;

  function startPolling() {
    if (timer !== null) return;
    void fetchCounts();
    timer = window.setInterval(async () => {
      if (inFlight) return;
      inFlight = true;
      try {
        await fetchCounts();
        failStreak = 0;
      } catch {
        failStreak += 1;
        if (failStreak >= POLL_FAIL_LIMIT) stopPolling();
      } finally {
        inFlight = false;
      }
    }, POLL_INTERVAL_MS);
  }

  function stopPolling() {
    if (timer !== null) {
      window.clearInterval(timer);
      timer = null;
    }
  }

  return { counts, total, fetchCounts, read, startPolling, stopPolling };
});
