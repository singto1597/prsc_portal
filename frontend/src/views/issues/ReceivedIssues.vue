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
  type Issue,
  type MainCategory,
} from '@/types/issue';
import { useAuthStore } from '@/stores/auth';

const authStore = useAuthStore();
const route = useRoute();
const router = useRouter();
const issues = ref<Issue[]>([]);
const isLoading = ref(true);
const error = ref('');
const statusFilter = ref('not_resolved');  // default: ซ่อนเรื่องที่เสร็จแล้ว (ดูเฉพาะยังไม่เสร็จ)
const levelFilter = ref('');   // '' = ทุกระดับที่มองเห็น, room/level/council
const mainCategoryFilter = ref('');  // '' = ทุกหมวด, suggestion/wellbeing/report
const subcategoryFilter = ref('');   // '' = ทุกหมวดย่อย, academic/physical_health/...

// สถานะ "ยังไม่เสร็จ" = pending + in_progress + escalated (ให้ server กรอง — กันหน้าว่างตอน 100 เรื่องแรกเสร็จหมด)
const NOT_RESOLVED_STATUSES = 'pending,in_progress,escalated';

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

// URL เป็น source of truth: แก้ URL เอง / back-forward → ปรับ filter ตาม URL
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
    // "not_resolved" = ส่งสถานะที่ยังไม่เสร็จให้ server กรอง (ไม่โหลดทุกสถานะแล้วตัด client
    // — เดิมถ้า 100 เรื่องแรกเสร็จหมดจะเห็นหน้าว่างทั้งที่ยังมีเรื่องค้างอยู่)
    const raw = statusFilter.value === 'not_resolved';
    issues.value = await listIssues({
      received: true,
      status: raw ? NOT_RESOLVED_STATUSES : (statusFilter.value || undefined),
      level: levelFilter.value || undefined,
      main_category: mainCategoryFilter.value || undefined,
      category: subcategoryFilter.value || undefined,
    });
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'โหลดข้อมูลไม่สำเร็จ';
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
      <select v-model="mainCategoryFilter" @change="onMainCategoryChange"
        class="px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white">
        <option value="">ทุกหมวดหลัก</option>
        <option v-for="mc in mainCategoryOptions" :key="mc.value" :value="mc.value">{{ mc.label }}</option>
      </select>
      <select v-model="subcategoryFilter" @change="onSubcategoryChange"
        :disabled="!mainCategoryFilter"
        class="px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white disabled:bg-gray-50 disabled:text-gray-400">
        <option value="">
          {{ mainCategoryFilter ? 'ทุกหมวดย่อย' : 'เลือกหมวดหลักก่อน' }}
        </option>
        <option v-for="sc in availableSubcategories" :key="sc.value" :value="sc.value">{{ sc.label }}</option>
      </select>
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
