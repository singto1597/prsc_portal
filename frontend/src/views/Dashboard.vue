<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { RouterLink } from 'vue-router';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';
import { Line } from 'vue-chartjs';
import Swal from 'sweetalert2';
import { getDashboardSummary, type DashboardSummary, type MainCategoryDashboard } from '@/services/dashboard';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend, Filler);

const data = ref<DashboardSummary | null>(null);
const isLoading = ref(true);

onMounted(async () => {
  try {
    data.value = await getDashboardSummary();
  } catch (e) {
    const msg = e instanceof Error ? e.message : 'เกิดข้อผิดพลาด';
    Swal.fire({ icon: 'error', title: 'ไม่สามารถโหลด Dashboard', text: msg });
  } finally {
    isLoading.value = false;
  }
});

// ===== 🎨 ธีมสี/ไอคอนของ 3 หมวดหลัก (สีแบรนด์แดง ใช้กับหมวด 'แจ้งเหตุ', ที่เหลือแยกสี) =====
interface CategoryTheme {
  icon: string;
  iconBg: string;
  countColor: string;
  barColor: string;
  headerBg: string;
}

const CATEGORY_THEMES: Record<string, CategoryTheme> = {
  suggestion: {
    icon: 'bi-lightbulb',
    iconBg: 'bg-blue-500',
    countColor: 'text-blue-600',
    barColor: 'bg-blue-500',
    headerBg: 'bg-blue-50/60 border-b border-blue-100',
  },
  wellbeing: {
    icon: 'bi-heart-pulse',
    iconBg: 'bg-emerald-500',
    countColor: 'text-emerald-600',
    barColor: 'bg-emerald-500',
    headerBg: 'bg-emerald-50/60 border-b border-emerald-100',
  },
  report: {
    icon: 'bi-megaphone',
    iconBg: 'bg-red-500',
    countColor: 'text-red-600',
    barColor: 'bg-red-500',
    headerBg: 'bg-red-50/60 border-b border-red-100',
  },
};

const DEFAULT_THEME: CategoryTheme = {
  icon: 'bi-collection',
  iconBg: 'bg-gray-500',
  countColor: 'text-gray-700',
  barColor: 'bg-gray-500',
  headerBg: 'bg-gray-50 border-b border-gray-200',
};

function themeFor(code: string): CategoryTheme {
  return CATEGORY_THEMES[code] ?? DEFAULT_THEME;
}

// ===== 🎛️ Stat cards หลัก =====
const statCards = computed(() => [
  { label: 'เรื่องทั้งหมด', value: data.value?.total_issues ?? 0, icon: 'bi-files', color: 'text-red-600 bg-red-50' },
  { label: 'รอรับเรื่อง', value: data.value?.pending ?? 0, icon: 'bi-hourglass-top', color: 'text-yellow-600 bg-yellow-50' },
  { label: 'กำลังดำเนินการ', value: data.value?.in_progress ?? 0, icon: 'bi-gear', color: 'text-blue-600 bg-blue-50' },
  { label: 'ส่งต่อระดับบน', value: data.value?.escalated ?? 0, icon: 'bi-arrow-up-circle', color: 'text-orange-600 bg-orange-50' },
  { label: 'แก้ไขเสร็จ', value: data.value?.resolved ?? 0, icon: 'bi-check-circle', color: 'text-green-600 bg-green-50' },
  { label: 'งานเกินเวลา', value: data.value?.overdue ?? 0, icon: 'bi-alarm', color: 'text-red-700 bg-red-100' },
  { label: 'นักเรียนในระบบ', value: data.value?.total_students ?? 0, icon: 'bi-people', color: 'text-purple-600 bg-purple-50' },
  { label: 'ห้องเรียน', value: data.value?.total_rooms ?? 0, icon: 'bi-door-closed', color: 'text-cyan-600 bg-cyan-50' },
]);

// ===== 📊 สีสถานะ (semantic — ไม่ทับกับสีหมวด) =====
const STATUS_DOT: Record<string, string> = {
  pending: 'bg-yellow-500',
  in_progress: 'bg-blue-500',
  escalated: 'bg-orange-500',
  resolved: 'bg-green-500',
  cancelled: 'bg-gray-400',
};
const STATUS_BAR: Record<string, string> = {
  pending: 'bg-yellow-400',
  in_progress: 'bg-blue-500',
  escalated: 'bg-orange-500',
  resolved: 'bg-green-500',
  cancelled: 'bg-gray-300',
};
const STATUS_BADGE: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-700',
  in_progress: 'bg-blue-100 text-blue-700',
  escalated: 'bg-orange-100 text-orange-700',
  resolved: 'bg-green-100 text-green-700',
  cancelled: 'bg-gray-200 text-gray-500',
};

function statusDot(s: string): string {
  return STATUS_DOT[s] ?? 'bg-gray-400';
}
function statusBar(s: string): string {
  return STATUS_BAR[s] ?? 'bg-gray-300';
}
function statusBadge(s: string): string {
  return STATUS_BADGE[s] ?? 'bg-gray-100 text-gray-600';
}

// ===== 🧮 ตัวช่วยเปอร์เซ็นต์ =====
function percent(part: number, total: number): number {
  if (!total) return 0;
  return Math.round((part / total) * 100);
}

function resolvedRate(cat: MainCategoryDashboard): number {
  const resolved = cat.by_status.find((s) => s.status === 'resolved')?.count ?? 0;
  return percent(resolved, cat.total);
}

// ===== 🕐 เวลาไทย Asia/Bangkok =====
function fmtDate(iso: string | null): string {
  if (!iso) return '-';
  const d = new Date(iso);
  return d.toLocaleString('th-TH', { timeZone: 'Asia/Bangkok', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
}

function fmtDay(iso: string): string {
  const d = new Date(iso + 'T00:00:00Z');
  return d.toLocaleDateString('th-TH', { timeZone: 'UTC', day: 'numeric', month: 'short' });
}

// ===== 📈 Trend chart (7 วัน) =====
const trendChart = computed(() => ({
  labels: (data.value?.trend || []).map((t) => fmtDay(t.date)),
  datasets: [
    {
      label: 'จำนวนเรื่อง/วัน',
      data: (data.value?.trend || []).map((t) => t.count),
      borderColor: '#dc2626',
      backgroundColor: 'rgba(220,38,38,0.08)',
      fill: true,
      tension: 0.3,
      pointBackgroundColor: '#dc2626',
    },
  ],
}));

const chartOptions = { responsive: true, maintainAspectRatio: false };
</script>

<template>
  <div>
    <!-- Header -->
    <div class="flex flex-wrap items-center justify-between gap-3 mb-5">
      <h1 class="text-2xl font-bold text-gray-900"><i class="bi bi-bar-chart mr-1"></i> แดชบอร์ด</h1>
      <div v-if="data && data.scope === 'level'"
        class="flex items-center gap-2 px-3.5 py-1.5 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 text-sm">
        <i class="bi bi-funnel"></i>
        กำลังแสดงสถิติเฉพาะระดับชั้น <b class="ml-0.5">{{ data.scope_label }}</b>
      </div>
      <div v-else-if="data && data.scope === 'none'"
        class="flex items-center gap-2 px-3.5 py-1.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-sm">
        <i class="bi bi-exclamation-triangle"></i>
        ยังไม่ได้กำหนดระดับชั้นที่รับผิดชอบ — ข้อมูลทั้งหมดเป็น 0
      </div>
      <div v-else-if="data" class="px-3.5 py-1.5 rounded-xl bg-gray-100 text-gray-600 text-sm">
        <i class="bi bi-globe2 mr-1"></i> ภาพรวมทั้งโรงเรียน
      </div>
    </div>

    <!-- Loading -->
    <div v-if="isLoading" class="flex justify-center py-20">
      <div class="animate-spin w-10 h-10 border-4 border-red-600 border-t-transparent rounded-full"></div>
    </div>

    <div v-else-if="data" class="space-y-6">
      <!-- Stat cards -->
      <div class="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-8 gap-3">
        <div v-for="s in statCards" :key="s.label" class="bg-white rounded-xl shadow-sm p-4 card-hover">
          <div class="w-9 h-9 rounded-lg flex items-center justify-center mb-2" :class="s.color">
            <i class="bi" :class="s.icon"></i>
          </div>
          <p class="text-2xl font-bold text-gray-900">{{ s.value }}</p>
          <p class="text-xs text-gray-500">{{ s.label }}</p>
        </div>
      </div>

      <!-- 🗂️ 3 หมวดหลัก — แยกการ์ดชัดเจน -->
      <section
        v-for="cat in data.main_categories"
        :key="cat.code"
        class="bg-white rounded-2xl shadow-sm overflow-hidden"
      >
        <!-- Header band -->
        <div class="flex items-center justify-between px-5 py-4" :class="themeFor(cat.code).headerBg">
          <div class="flex items-center gap-3">
            <div class="w-11 h-11 rounded-xl flex items-center justify-center text-xl text-white shadow-sm shrink-0"
              :class="themeFor(cat.code).iconBg">
              <i class="bi" :class="themeFor(cat.code).icon"></i>
            </div>
            <div>
              <h2 class="text-lg font-bold text-gray-900">{{ cat.label }}</h2>
              <p class="text-xs text-gray-500">เรื่องทั้งหมด {{ cat.total }} · แก้ไขเสร็จ {{ resolvedRate(cat) }}%</p>
            </div>
          </div>
          <div class="text-right shrink-0">
            <p class="text-3xl font-black leading-none" :class="themeFor(cat.code).countColor">{{ cat.total }}</p>
            <p class="text-xs text-gray-500 mt-1">เรื่อง</p>
          </div>
        </div>

        <!-- Body: 3 คอลัมน์ -->
        <div class="p-5 grid md:grid-cols-3 gap-6">
          <!-- คอลัมน์ 1: สถานะการดำเนินการ -->
          <div>
            <h3 class="text-sm font-semibold text-gray-700 mb-3">
              <i class="bi bi-activity mr-1"></i> สถานะการดำเนินการ
            </h3>
            <div class="space-y-2.5">
              <div v-for="s in cat.by_status" :key="s.status" class="flex items-center gap-2">
                <span class="w-2.5 h-2.5 rounded-full shrink-0" :class="statusDot(s.status)"></span>
                <span class="flex-1 text-sm text-gray-600 truncate">{{ s.label }}</span>
                <span class="text-sm font-bold text-gray-800 shrink-0">{{ s.count }}</span>
                <div class="w-16 h-1.5 bg-gray-100 rounded-full overflow-hidden shrink-0">
                  <div class="h-full rounded-full" :class="statusBar(s.status)"
                    :style="{ width: percent(s.count, cat.total) + '%' }"></div>
                </div>
              </div>
            </div>
          </div>

          <!-- คอลัมน์ 2: หัวข้อย่อยยอดนิยม -->
          <div>
            <h3 class="text-sm font-semibold text-gray-700 mb-3">
              <i class="bi bi-tags mr-1"></i> หัวข้อย่อยที่แจ้งเยอะสุด
            </h3>
            <div v-if="cat.top_subcategories.length" class="space-y-3">
              <div v-for="sc in cat.top_subcategories" :key="sc.category">
                <div class="flex items-center justify-between text-sm mb-1">
                  <span class="text-gray-600 truncate">{{ sc.label }}</span>
                  <span class="font-bold text-gray-800 ml-2 shrink-0">{{ sc.count }}</span>
                </div>
                <div class="h-2 bg-gray-100 rounded-full overflow-hidden">
                  <div class="h-full rounded-full" :class="themeFor(cat.code).barColor"
                    :style="{ width: percent(sc.count, cat.total) + '%' }"></div>
                </div>
              </div>
            </div>
            <p v-else class="text-sm text-gray-400 py-4 text-center">ยังไม่มีข้อมูลในหมวดนี้</p>
          </div>

          <!-- คอลัมน์ 3: เรื่องล่าสุด + ดูทั้งหมด -->
          <div>
            <div class="flex items-center justify-between mb-3">
              <h3 class="text-sm font-semibold text-gray-700">
                <i class="bi bi-clock-history mr-1"></i> เรื่องล่าสุด
              </h3>
              <RouterLink
                :to="{ name: 'received-issues', query: { main_category: cat.code } }"
                class="text-xs font-medium text-red-600 hover:text-red-700 hover:underline inline-flex items-center gap-1">
                ดูทั้งหมด <i class="bi bi-arrow-right"></i>
              </RouterLink>
            </div>
            <div v-if="cat.recent_issues.length" class="space-y-1">
              <RouterLink
                v-for="r in cat.recent_issues"
                :key="r.id"
                :to="{ name: 'issue-detail', params: { id: r.id } }"
                class="flex items-center gap-2.5 p-2.5 rounded-xl hover:bg-gray-50 transition group"
              >
                <span class="w-2 h-2 rounded-full shrink-0" :class="statusDot(r.status)"></span>
                <div class="flex-1 min-w-0">
                  <p class="text-sm text-gray-800 truncate group-hover:text-gray-900">{{ r.title }}</p>
                  <p class="text-[11px] text-gray-400">
                    {{ r.category_label }} · {{ r.room_name || 'ไม่ระบุห้อง' }} · {{ fmtDate(r.created_at) }}
                  </p>
                </div>
                <span class="px-2 py-0.5 text-[11px] font-medium rounded-full shrink-0" :class="statusBadge(r.status)">
                  {{ r.status === 'pending' ? 'รอรับ' : r.status === 'in_progress' ? 'กำลังทำ' : r.status === 'escalated' ? 'ส่งต่อ' : r.status === 'resolved' ? 'เสร็จ' : 'ยกเลิก' }}
                </span>
              </RouterLink>
            </div>
            <p v-else class="text-sm text-gray-400 py-4 text-center">ยังไม่มีเรื่องล่าสุด</p>
          </div>
        </div>
      </section>

      <!-- ภาพรวมเสริม: แนวโน้ม + การเข้าใช้งาน -->
      <div class="grid lg:grid-cols-3 gap-4">
        <div class="lg:col-span-2 bg-white rounded-xl shadow-sm p-4">
          <h3 class="font-semibold text-gray-800 mb-3"><i class="bi bi-graph-up mr-1"></i> แนวโน้มเรื่องที่แจ้ง (7 วัน)</h3>
          <div class="h-64"><Line :data="trendChart" :options="chartOptions" /></div>
        </div>

        <div class="bg-white rounded-xl shadow-sm p-4">
          <h3 class="font-semibold text-gray-800 mb-3"><i class="bi bi-people mr-1"></i> การเข้าใช้งาน</h3>
          <p class="text-3xl font-black text-gray-900">{{ data.usage_count }}</p>
          <p class="text-xs text-gray-500 mb-3">ครั้ง (ยอดสะสม)</p>
          <div v-if="data.recent_logins.length" class="space-y-2 border-t border-gray-100 pt-3">
            <div v-for="(lg, idx) in data.recent_logins.slice(0, 5)" :key="idx" class="flex items-center justify-between text-xs">
              <span class="text-gray-600 truncate">{{ lg.actor }}</span>
              <span class="text-gray-400 ml-2 shrink-0">{{ fmtDate(lg.at) }}</span>
            </div>
          </div>
          <p v-else class="text-sm text-gray-400 py-3">ยังไม่มีข้อมูลการเข้าใช้งาน</p>
        </div>
      </div>
    </div>
  </div>
</template>
