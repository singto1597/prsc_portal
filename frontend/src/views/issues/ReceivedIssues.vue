<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue';
import { RouterLink, useRoute, useRouter } from 'vue-router';
import { listIssues } from '@/services/issue';
import {
  MAIN_CATEGORIES,
  MAIN_CATEGORY_LABELS,
  subcategoryLabel,
  STATUS_LABELS,
  LEVEL_LABELS,
  DESTINATION_LABELS,
  type Issue,
  type MainCategory,
} from '@/types/issue';
import { STATUS_BADGE } from '@/constants/status';
import { useAuthStore } from '@/stores/auth';
import IssueListToolbar from '@/components/IssueListToolbar.vue';
import PaginationBar from '@/components/PaginationBar.vue';
import ApproveBoardModal from '@/components/boards/ApproveBoardModal.vue';

const authStore = useAuthStore();
const route = useRoute();
const router = useRouter();
const issues = ref<Issue[]>([]);
const total = ref(0); // จำนวนทั้งหมดที่ตรงเงื่อนไข (จาก envelope)
const isLoading = ref(true);
const error = ref('');
// 🏛️ อนุมัติเผยแพร่ PIRI Board (สภานักเรียน/แอดมิน) — modal ตั้งค่าตัวเลือกโหวต/คอมเมนต์
const approveTarget = ref<Issue | null>(null);
const approveOpen = ref(false);

// สภานักเรียน/แอดมิน อนุมัติเรื่องที่ขอเผยแพร่ (vote/talk) และยังไม่ถูกอนุมัติ/ปิด
function canApprove(i: Issue): boolean {
  if (!authStore.isCouncilAuthority) return false
  if (i.requested_destination === 'normal') return false
  if (i.published_board_id) return false
  return !['resolved', 'cancelled', 'rejected'].includes(i.status)
}

function openApprove(i: Issue) {
  approveTarget.value = i
  approveOpen.value = true
}

function onApproved(boardId: number) {
  router.push({ name: 'board-detail', params: { id: boardId } })
}
const q = ref('');           // คำค้นหา
const sort = ref<'asc' | 'desc'>('desc'); // ใหม่ไปเก่า (default)
const page = ref(1);
const pageSize = 20;
const statusFilter = ref('not_resolved');  // default: ซ่อนเรื่องที่เสร็จแล้ว (ดูเฉพาะยังไม่เสร็จ)
const levelFilter = ref('');   // '' = ทุกระดับที่มองเห็น, room/level/council
const mainCategoryFilter = ref('');  // '' = ทุกหมวด, suggestion/wellbeing/report
const subcategoryFilter = ref('');   // '' = ทุกหมวดย่อย, academic/physical_health/...

// สถานะ "ยังไม่เสร็จ" = pending + in_progress + escalated (ให้ server กรอง — กันหน้าว่างตอน 100 เรื่องแรกเสร็จหมด)
const NOT_RESOLVED_STATUSES = 'pending,in_progress,escalated';

// จำนวนตัวกรองที่ active (badge บนปุ่ม filter) — ไม่นับ default 'not_resolved'
const activeFilters = computed(
  () =>
    (statusFilter.value !== 'not_resolved' ? 1 : 0) +
    (levelFilter.value ? 1 : 0) +
    (mainCategoryFilter.value ? 1 : 0) +
    (subcategoryFilter.value ? 1 : 0),
);

// หาหมวดหลักของหมวดย่อย (แต่ละหมวดย่อยอยู่ใต้หมวดหลักเดียว)
function mainOfCategory(cat: string): string {
  for (const mc of Object.keys(MAIN_CATEGORIES) as MainCategory[]) {
    if (MAIN_CATEGORIES[mc].subcategories[cat]) return mc;
  }
  return '';
}

// ตั้งค่าเริ่มต้นจาก URL (คลิกจาก Dashboard → มาเจอหมวด/หมวดย่อยนั้นเลย)
const initMainCat = typeof route.query.main_category === 'string' ? route.query.main_category : '';
const initCat = typeof route.query.category === 'string' ? route.query.category : '';

// URL มีแค่ ?category= (ไม่มี main_category) → หาหมวดหลักให้เอง เพื่อให้ dropdown ตรงกัน
const effectiveMain = initMainCat || mainOfCategory(initCat);
if (effectiveMain) mainCategoryFilter.value = effectiveMain;

// หมวดย่อยต้อง belong กับหมวดหลักที่เลือก → ถ้าไม่ (เช่น แก้ URL มือ) ให้ตัดทิ้ง เหมือนที่ watch ทำ
if (initCat && mainOfCategory(initCat) === effectiveMain) {
  subcategoryFilter.value = initCat;
}

// หมวดย่อยที่เลือกได้ (ตามหมวดหลักที่เลือกอยู่)
const availableSubcategories = computed(() => {
  if (!mainCategoryFilter.value) return [];
  const info = MAIN_CATEGORIES[mainCategoryFilter.value as MainCategory];
  if (!info) return [];
  return Object.entries(info.subcategories).map(([value, label]) => ({ value, label }));
});

// URL เป็น source of truth: แก้ URL เอง / back-forward → ปรับ filter ตาม URL (กลับหน้า 1)
watch(
  () => [route.query.main_category, route.query.category],
  ([mc, cat]) => {
    const mainV = typeof mc === 'string' ? mc : '';
    const catV = typeof cat === 'string' ? cat : '';
    const mainChanged = mainV !== mainCategoryFilter.value;
    const catChanged = catV !== subcategoryFilter.value;
    if (mainChanged || catChanged) {
      // หมวดย่อยต้อง belong กับหมวดหลักที่เลือก → ถ้าไม่ (เช่น แก้ URL มือ) ให้ตัดทิ้ง
      let validCat = '';
      if (mainV && catV) {
        validCat = mainOfCategory(catV) === mainV ? catV : '';
      }
      mainCategoryFilter.value = mainV;
      subcategoryFilter.value = validCat;
      page.value = 1;
      load();
    }
  },
);

// เลือกหมวดจาก dropdown → เขียนกลับไปที่ URL (refresh/แชร์ URL แล้วได้ข้อมูลตรงกัน)
function onMainCategoryChange() {
  // เปลี่ยนหมวดหลัก → หมวดย่อยเดิมอยู่คนละหมวด → เคลียร์
  subcategoryFilter.value = '';
  const query = { ...route.query };
  if (mainCategoryFilter.value) {
    query.main_category = mainCategoryFilter.value;
  } else {
    delete query.main_category;
  }
  delete query.category;
  router.replace({ query });
  page.value = 1;
  load();
}

function onSubcategoryChange() {
  const query = { ...route.query };
  if (subcategoryFilter.value) {
    query.category = subcategoryFilter.value;
  } else {
    delete query.category;
  }
  router.replace({ query });
  page.value = 1;
  load();
}

// เปลี่ยน filter ฝั่ง dropdown (ระดับ/สถานะ) → กลับหน้า 1 แล้วโหลด
function onFilterChange() {
  page.value = 1;
  load();
}

// search / sort เปลี่ยน (จาก Toolbar) → กลับหน้า 1 แล้วโหลด
function onToolbarChange() {
  page.value = 1;
  load();
}

// เปลี่ยนหน้า (จาก Pagination)
function onPageChange(n: number) {
  page.value = n;
  load();
}

// ตัวเลือกหมวดหลัก (จาก types/issue.ts)
const mainCategoryOptions = [
  { value: 'suggestion', label: MAIN_CATEGORY_LABELS.suggestion },
  { value: 'wellbeing', label: MAIN_CATEGORY_LABELS.wellbeing },
  { value: 'report', label: MAIN_CATEGORY_LABELS.report },
];

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
    // "not_resolved" = ส่งสถานะที่ยังไม่เสร็จให้ server กรอง (ไม่โหลดทุกสถานะแล้วตัด client)
    const raw = statusFilter.value === 'not_resolved';
    const res = await listIssues({
      received: true,
      status: raw ? NOT_RESOLVED_STATUSES : (statusFilter.value || undefined),
      level: levelFilter.value || undefined,
      main_category: mainCategoryFilter.value || undefined,
      category: subcategoryFilter.value || undefined,
      q: q.value.trim() || undefined,
      sort: sort.value,
      limit: pageSize,
      offset: (page.value - 1) * pageSize,
    });
    issues.value = res.items;
    total.value = res.total;
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'โหลดข้อมูลไม่สำเร็จ';
  } finally {
    isLoading.value = false;
  }
}
</script>

<template>
  <div>
    <!-- Editorial page header -->
    <div class="mb-6">
      <p class="mb-2 flex items-center gap-2 text-[11px] font-bold uppercase tracking-widest text-[#B91C1C]">
        <i class="bi bi-inbox text-[13px]"></i> Inbox &amp; My Level
      </p>
      <h1 class="text-2xl sm:text-3xl font-bold tracking-tight text-stone-900 leading-tight">เรื่องที่รับ / ระดับฉัน</h1>
      <p class="mt-2 text-sm text-stone-500">เรื่องที่รอคุณและทีมรับผิดชอบดำเนินการ</p>
    </div>

    <!-- Toolbar: ค้นหา + ปุ่ม filter (dropdown: ตัวกรอง + เรียงลำดับ) + จำนวน -->
    <IssueListToolbar
      v-model:q="q"
      v-model:sort="sort"
      :total="total"
      :count="issues.length"
      :active-filters="activeFilters"
      :loading="isLoading"
      @change="onToolbarChange"
    >
      <template #filters>
        <div class="space-y-3">
          <div>
            <label class="block text-xs font-semibold text-stone-500 mb-1.5">หมวดหลัก</label>
            <select v-model="mainCategoryFilter" @change="onMainCategoryChange"
              class="w-full px-3 py-2 border border-stone-300 rounded-xl text-sm bg-white">
              <option value="">ทุกหมวดหลัก</option>
              <option v-for="mc in mainCategoryOptions" :key="mc.value" :value="mc.value">{{ mc.label }}</option>
            </select>
          </div>
          <div>
            <label class="block text-xs font-semibold text-stone-500 mb-1.5">หมวดย่อย</label>
            <select v-model="subcategoryFilter" @change="onSubcategoryChange"
              :disabled="!mainCategoryFilter"
              class="w-full px-3 py-2 border border-stone-300 rounded-xl text-sm bg-white disabled:bg-stone-50 disabled:text-stone-400">
              <option value="">
                {{ mainCategoryFilter ? 'ทุกหมวดย่อย' : 'เลือกหมวดหลักก่อน' }}
              </option>
              <option v-for="sc in availableSubcategories" :key="sc.value" :value="sc.value">{{ sc.label }}</option>
            </select>
          </div>
          <div>
            <label class="block text-xs font-semibold text-stone-500 mb-1.5">ระดับ</label>
            <select v-model="levelFilter" @change="onFilterChange"
              class="w-full px-3 py-2 border border-stone-300 rounded-xl text-sm bg-white">
              <option value="">ทุกระดับที่ฉันมองเห็น</option>
              <option v-for="lv in visibleLevels" :key="lv" :value="lv">
                ระดับ{{ lv === 'room' ? 'ห้อง (หัวหน้าห้อง / รอง)' : lv === 'level' ? 'ชั้น (ประธานระดับ)' : 'สภานักเรียน' }}
              </option>
            </select>
          </div>
          <div>
            <label class="block text-xs font-semibold text-stone-500 mb-1.5">สถานะ</label>
            <select v-model="statusFilter" @change="onFilterChange"
              class="w-full px-3 py-2 border border-stone-300 rounded-xl text-sm bg-white">
              <option value="not_resolved">ยังไม่เสร็จ (รอรับ / กำลังทำ / ส่งต่อ)</option>
              <option value="">ทุกสถานะ (รวมเสร็จแล้ว)</option>
              <option value="pending">รอรับ</option>
              <option value="in_progress">กำลังดำเนินการ</option>
              <option value="escalated">ส่งต่อ</option>
              <option value="resolved">เสร็จแล้ว</option>
              <option value="cancelled">ถูกยกเลิก</option>
              <option value="rejected">ถูกปัดตก</option>
            </select>
          </div>
        </div>
      </template>
    </IssueListToolbar>

    <!-- โหลดข้อมูล: skeleton รายการ -->
    <div v-if="isLoading" class="animate-pulse rounded-2xl border border-stone-200 bg-white p-5">
      <div class="divide-y divide-stone-100">
        <div v-for="n in 5" :key="n" class="flex items-start gap-3 py-4">
          <div class="h-10 w-10 rounded-full bg-stone-100"></div>
          <div class="flex-1 space-y-2 pt-1">
            <div class="h-3 w-1/3 rounded bg-stone-100"></div>
            <div class="h-3 w-2/3 rounded bg-stone-100"></div>
          </div>
          <div class="h-6 w-16 rounded-full bg-stone-100"></div>
        </div>
      </div>
    </div>

    <!-- โหลดไม่สำเร็จ: inline error + retry -->
    <div
      v-else-if="error"
      class="flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-stone-200 py-20 text-center"
    >
      <i class="bi bi-wifi-off text-3xl text-stone-400 mb-3"></i>
      <p class="text-stone-600">{{ error }}</p>
      <button
        type="button"
        class="mt-4 rounded-lg bg-[#B91C1C] px-5 py-2 text-[13px] font-bold text-white hover:bg-[#991B1B]"
        @click="load"
      >
        ลองอีกครั้ง
      </button>
    </div>

    <!-- Empty state -->
    <div
      v-else-if="!issues.length"
      class="flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-stone-200 bg-white py-16 px-6 text-center"
    >
      <div class="text-4xl mb-2 text-stone-300"><i class="bi bi-inbox"></i></div>
      <p class="text-stone-600">ไม่พบเรื่องในเงื่อนไขที่เลือก</p>
    </div>

    <!-- Ledger-style list -->
    <TransitionGroup
      v-else
      name="list"
      tag="div"
      class="rounded-2xl border border-stone-200 overflow-hidden bg-white divide-y divide-stone-200"
    >
      <RouterLink
        v-for="i in issues"
        :key="i.id"
        :to="{ name: 'issue-detail', params: { id: i.id } }"
        class="flex items-start justify-between gap-3 px-5 py-4 hover:bg-stone-50 transition block"
      >
        <div class="flex-1 min-w-0">
          <div class="flex flex-wrap gap-2 mb-1.5">
            <span class="px-2 py-0.5 bg-stone-100 text-stone-600 text-xs rounded-full">{{ MAIN_CATEGORY_LABELS[i.main_category] }}</span>
            <span class="px-2 py-0.5 bg-stone-100 text-stone-600 text-xs rounded-full">{{ subcategoryLabel(i.main_category, i.category) }}</span>
            <span
              class="px-2 py-0.5 rounded-full text-xs"
              :class="{
                'bg-stone-100 text-stone-700': i.current_level === 'room',
                'bg-stone-200 text-stone-700': i.current_level === 'level',
                'bg-stone-300 text-stone-800': i.current_level === 'council',
              }"
            >
              {{ LEVEL_LABELS[i.current_level] }}
            </span>
            <span v-if="i.requested_destination && i.requested_destination !== 'normal'"
              class="px-2 py-0.5 bg-stone-100 text-stone-600 text-xs rounded-full">
              {{ DESTINATION_LABELS[i.requested_destination] }}
            </span>
          </div>
          <h3 class="font-semibold text-stone-900 truncate">{{ i.title }}</h3>
          <div class="flex flex-wrap gap-x-4 gap-y-1 text-xs text-stone-500 mt-1">
            <span><i class="bi bi-building mr-1"></i> {{ i.room_name }}</span>
            <span v-if="i.reporter_name"><i class="bi bi-person mr-1"></i> {{ i.reporter_name }}</span>
            <span v-else><i class="bi bi-eye-slash mr-1"></i> ไม่ระบุชื่อ</span>
            <span v-if="i.current_assignee_name"><i class="bi bi-person-badge mr-1"></i> {{ i.current_assignee_name }}</span>
          </div>
        </div>
        <div class="text-right shrink-0 flex flex-col items-end gap-2">
          <span
            class="px-2.5 py-1 text-xs font-medium rounded-full whitespace-nowrap"
            :class="STATUS_BADGE[i.status] || 'bg-stone-100 text-stone-500'"
          >
            {{ STATUS_LABELS[i.status] }}
          </span>
          <button
            v-if="canApprove(i)"
            @click.stop.prevent="openApprove(i)"
            class="px-3 py-1.5 bg-[#B91C1C] text-white text-xs font-medium rounded-lg hover:bg-[#991B1B] whitespace-nowrap"
          >
            <i class="bi bi-people-fill mr-1"></i> อนุมัติเผยแพร่
          </button>
        </div>
      </RouterLink>
    </TransitionGroup>

    <!-- แบ่งหน้า -->
    <PaginationBar :total="total" :page="page" :page-size="pageSize" :loading="isLoading" @page-change="onPageChange" />

    <!-- 🏛️ Modal อนุมัติเผยแพร่ PIRI Board -->
    <ApproveBoardModal :issue="approveTarget" v-model:open="approveOpen" @approved="onApproved" />
  </div>
</template>

<style scoped>
/* list animation */
.list-enter-active, .list-leave-active { transition: all 0.25s ease; }
.list-enter-from { opacity: 0; transform: translateY(10px); }
.list-leave-to { opacity: 0; transform: translateY(-6px); }
</style>
