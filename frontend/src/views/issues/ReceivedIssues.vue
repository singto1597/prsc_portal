<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { RouterLink } from 'vue-router';
import { listIssues } from '@/services/issue';
import { MAIN_CATEGORY_LABELS, subcategoryLabel, STATUS_LABELS, LEVEL_LABELS, type Issue } from '@/types/issue';
import { useAuthStore } from '@/stores/auth';

const authStore = useAuthStore();
const issues = ref<Issue[]>([]);
const isLoading = ref(true);
const error = ref('');
const statusFilter = ref('not_resolved');  // default: ซ่อนเรื่องที่เสร็จแล้ว (ดูเฉพาะยังไม่เสร็จ)
const levelFilter = ref('');   // '' = ทุกระดับที่มองเห็น, room/level/council

// ระดับสูงสุดของผู้ใช้ (สำหรับจำกัด dropdown ระดับที่เห็น)
const myLevel = computed(() => {
  const roleLevels: Record<string, string> = {
    class_president: 'room', vice_academic: 'room', vice_discipline: 'room',
    vice_activity: 'room', vice_reception: 'room',
    level_president: 'level',
    council_member: 'council', council_president: 'council',
  };
  let best = 'student';
  for (const r of authStore.roles) {
    const lv = roleLevels[r.role || ''] || 'student';
    const rank = { student: 0, room: 1, level: 2, council: 3 };
    if (rank[lv as keyof typeof rank] > rank[best as keyof typeof rank]) best = lv;
  }
  return best;
});

// ระดับที่มองเห็นได้ (ตั้งแต่ล่างสุด ถึงระดับตัวเอง)
const visibleLevels = computed(() => {
  const all = ['room', 'level', 'council'] as const;
  const rank = { student: 0, room: 1, level: 2, council: 3 };
  const myRank = rank[myLevel.value as keyof typeof rank] || 0;
  return all.filter((l) => rank[l] <= myRank);
});

onMounted(load);

async function load() {
  isLoading.value = true;
  error.value = '';
  try {
    // "not_resolved" = โหลดทุกสถานะแล้วกรองฝั่ง client (ตัด resolved/cancelled)
    const raw = statusFilter.value === 'not_resolved';
    issues.value = await listIssues({
      received: true,
      status: raw ? undefined : (statusFilter.value || undefined),
      level: levelFilter.value || undefined,
    });
    if (raw) {
      issues.value = issues.value.filter((i) => {
        const s: string = i.status;
        return s !== 'resolved' && s !== 'cancelled';
      });
    }
  } catch (e: any) {
    error.value = e.message || 'โหลดข้อมูลไม่สำเร็จ';
  } finally {
    isLoading.value = false;
  }
}

function statusColor(s: string) {
  return {
    pending: 'bg-yellow-100 text-yellow-700',
    in_progress: 'bg-blue-100 text-blue-700',
    resolved: 'bg-green-100 text-green-700',
    escalated: 'bg-orange-100 text-orange-700',
    cancelled: 'bg-gray-200 text-gray-500',
  }[s] || 'bg-gray-100 text-gray-600';
}
</script>

<template>
  <div>
    <div class="flex items-center justify-between mb-5">
      <h1 class="text-2xl font-bold text-gray-900"><i class="bi bi-inbox mr-1"></i> เรื่องที่รับ / ระดับฉัน</h1>
    </div>

    <!-- Filters -->
    <div class="flex flex-wrap gap-3 mb-4">
      <select v-model="levelFilter" @change="load"
        class="px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white">
        <option value="">ทุกระดับที่ฉันมองเห็น</option>
        <option v-for="lv in visibleLevels" :key="lv" :value="lv">
          ระดับ{{ lv === 'room' ? 'ห้อง (หัวหน้าห้อง / รอง)' : lv === 'level' ? 'ชั้น (ประธานระดับ)' : 'สภานักเรียน' }}
        </option>
      </select>
      <select v-model="statusFilter" @change="load"
        class="px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white">
        <option value="not_resolved">ยังไม่เสร็จ (ค่าเริ่มต้น)</option>
        <option value="">ทุกสถานะ (รวมเสร็จแล้ว)</option>
        <option value="pending">รอรับ</option>
        <option value="in_progress">กำลังดำเนินการ</option>
        <option value="escalated">ส่งต่อ</option>
        <option value="resolved">เสร็จแล้ว</option>
        <option value="cancelled">ถูกยกเลิก</option>
      </select>
      <span class="self-center text-sm text-gray-400">
        แสดง {{ issues.length }} เรื่อง
      </span>
    </div>

    <div v-if="isLoading" class="flex justify-center py-16">
      <div class="animate-spin w-10 h-10 border-4 border-red-600 border-t-transparent rounded-full"></div>
    </div>
    <div v-else-if="error" class="text-red-500 text-center py-10">{{ error }}</div>

    <div v-else-if="!issues.length" class="bg-white rounded-xl p-10 text-center text-gray-400">
      <div class="text-4xl mb-2"><i class="bi bi-inbox"></i></div>
      <p>ไม่พบเรื่องในเงื่อนไขที่เลือก</p>
    </div>

    <TransitionGroup v-else name="list" tag="div" class="grid gap-3">
      <RouterLink
        v-for="i in issues"
        :key="i.id"
        :to="{ name: 'issue-detail', params: { id: i.id } }"
        class="bg-white rounded-xl shadow-sm p-4 hover:shadow-md transition block"
      >
        <div class="flex items-start justify-between gap-3">
          <div class="flex-1 min-w-0">
            <div class="flex flex-wrap gap-2 mb-1.5">
              <span class="px-2 py-0.5 bg-red-100 text-red-700 text-xs rounded-full">{{ MAIN_CATEGORY_LABELS[i.main_category] }}</span>
              <span class="px-2 py-0.5 bg-purple-100 text-purple-700 text-xs rounded-full">{{ subcategoryLabel(i.main_category, i.category) }}</span>
              <span class="px-2 py-0.5 rounded-full text-xs"
                :class="{
                  'bg-emerald-100 text-emerald-700': i.current_level === 'room',
                  'bg-amber-100 text-amber-700': i.current_level === 'level',
                  'bg-rose-100 text-rose-700': i.current_level === 'council',
                }">
                {{ LEVEL_LABELS[i.current_level] }}
              </span>
            </div>
            <h3 class="font-semibold text-gray-900 truncate">{{ i.title }}</h3>
            <div class="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500 mt-1">
              <span><i class="bi bi-building mr-1"></i> {{ i.room_name }}</span>
              <span v-if="i.reporter_name"><i class="bi bi-person mr-1"></i> {{ i.reporter_name }}</span>
              <span v-else><i class="bi bi-eye-slash mr-1"></i> ไม่ระบุชื่อ</span>
              <span v-if="i.current_assignee_name"><i class="bi bi-person-badge mr-1"></i> {{ i.current_assignee_name }}</span>
            </div>
          </div>
          <div class="text-right shrink-0">
            <span class="px-2.5 py-1 text-xs font-medium rounded-full whitespace-nowrap" :class="statusColor(i.status)">
              {{ STATUS_LABELS[i.status] }}
            </span>
          </div>
        </div>
      </RouterLink>
    </TransitionGroup>
  </div>
</template>

<style scoped>
/* list animation */
.list-enter-active, .list-leave-active { transition: all 0.25s ease; }
.list-enter-from { opacity: 0; transform: translateY(10px); }
.list-leave-to { opacity: 0; transform: translateY(-6px); }
</style>
