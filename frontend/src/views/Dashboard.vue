<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { RouterLink } from 'vue-router';
import Swal from 'sweetalert2';
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
import { getDashboardSummary, type DashboardSummary, type MainCategoryDashboard } from '@/services/dashboard';
import StatusStackedBar from '@/components/StatusStackedBar.vue';
import { STATUS_DOT, STATUS_BADGE, statusShort } from '@/constants/status';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend, Filler);

// ===== ข้อมูล + การโหลด =====
const data = ref<DashboardSummary | null>(null);
const isLoading = ref(true);
const error = ref('');
const lastUpdated = ref<string | null>(null);

async function loadDashboard() {
  isLoading.value = true;
  error.value = '';
  try {
    data.value = await getDashboardSummary();
    lastUpdated.value = new Date().toISOString();
  } catch (e) {
    const msg = e instanceof Error ? e.message : 'เกิดข้อผิดพลาด';
    error.value = msg;
    Swal.fire({
      icon: 'error',
      title: data.value ? 'รีเฟรชไม่สำเร็จ' : 'ไม่สามารถโหลด Dashboard',
      text: msg,
    });
  } finally {
    isLoading.value = false;
  }
}

onMounted(loadDashboard);

// ===== 🎨 ธีมสีของ 3 หมวดหลัก (accent — ไม่ทับสีสถานะ semantic) =====
interface CategoryTheme {
  icon: string;
  iconBg: string;
  countColor: string;
  barColor: string;
  headerBg: string;
  rowHover: string;
  leaderHighlight: string; // bg+ring ของแถวอันดับ 1
  chevron: string;
}

const CATEGORY_THEMES: Record<string, CategoryTheme> = {
  suggestion: {
    icon: 'bi-lightbulb',
    iconBg: 'bg-blue-500',
    countColor: 'text-blue-600',
    barColor: 'bg-blue-500',
    headerBg: 'bg-blue-50/60 border-b border-blue-100',
    rowHover: 'hover:bg-blue-50/40',
    leaderHighlight: 'bg-blue-50/50 ring-1 ring-blue-200',
    chevron: 'group-hover:text-blue-600',
  },
  wellbeing: {
    icon: 'bi-heart-pulse',
    iconBg: 'bg-emerald-500',
    countColor: 'text-emerald-600',
    barColor: 'bg-emerald-500',
    headerBg: 'bg-emerald-50/60 border-b border-emerald-100',
    rowHover: 'hover:bg-emerald-50/40',
    leaderHighlight: 'bg-emerald-50/50 ring-1 ring-emerald-200',
    chevron: 'group-hover:text-emerald-600',
  },
  report: {
    icon: 'bi-megaphone',
    iconBg: 'bg-red-500',
    countColor: 'text-red-600',
    barColor: 'bg-red-500',
    headerBg: 'bg-red-50/60 border-b border-red-100',
    rowHover: 'hover:bg-red-50/40',
    leaderHighlight: 'bg-red-50/60 ring-1 ring-red-200',
    chevron: 'group-hover:text-red-600',
  },
};

const DEFAULT_THEME: CategoryTheme = {
  icon: 'bi-collection',
  iconBg: 'bg-gray-500',
  countColor: 'text-gray-700',
  barColor: 'bg-gray-500',
  headerBg: 'bg-gray-50 border-b border-gray-200',
  rowHover: 'hover:bg-gray-50',
  leaderHighlight: 'bg-gray-50 ring-1 ring-gray-200',
  chevron: 'group-hover:text-gray-600',
};

function themeFor(code: string): CategoryTheme {
  return CATEGORY_THEMES[code] ?? DEFAULT_THEME;
}

// ===== 🎛️ KPI (6 ตัว เน้น "อะไรเยอะที่สุด/อะไรค้าง") =====
const statCards = computed(() => [
  { label: 'เรื่องทั้งหมด', value: data.value?.total_issues ?? 0, dot: 'bg-red-500' },
  { label: 'รอรับเรื่อง', value: data.value?.pending ?? 0, dot: 'bg-yellow-500' },
  { label: 'กำลังดำเนินการ', value: data.value?.in_progress ?? 0, dot: 'bg-blue-500' },
  { label: 'ส่งต่อระดับบน', value: data.value?.escalated ?? 0, dot: 'bg-orange-500' },
  { label: 'แก้ไขเสร็จ', value: data.value?.resolved ?? 0, dot: 'bg-green-500' },
  { label: 'งานเกินเวลา', value: data.value?.overdue ?? 0, dot: 'bg-red-600', alert: true },
]);

// ===== 🧮 ตัวช่วยตัวเลข/เปอร์เซ็นต์ =====
function fmtNum(n: number): string {
  return n.toLocaleString('en-US'); // ตัวเลขอาหรับ + คอมมา (กันไทย ๑๒๓ ที่อ่านยากใน data)
}

function percent(part: number, total: number): number {
  if (!total) return 0;
  return Math.round((part / total) * 100);
}

// แท่งสัดส่วนเทียบกับ max ในหมวด (อันดับ 1 เต็มรางเสมอ → เปรียบเทียบ "ใครใหญ่สุด" ได้ทันที)
function shareWidth(part: number, max: number): number {
  if (!max || !part) return 0;
  return Math.max(8, Math.min(100, Math.round((part / max) * 100)));
}

function maxSubCount(cat: MainCategoryDashboard): number {
  // หา max จริงๆ จากทุกหมวดย่อย (รวม "อื่นๆ" ที่ต่อท้าย) — ไม่ใช้ index 0 เฉยๆ
  // เพราะกรณีเรื่องทั้งหมดไปอยู่ _other → index 0 เป็นหมวดจริงที่ count=0
  return Math.max(0, ...cat.subcategories.map((s) => s.count));
}

function resolvedRate(cat: MainCategoryDashboard): number {
  const resolved = cat.by_status.find((s) => s.status === 'resolved')?.count ?? 0;
  return percent(resolved, cat.total);
}

// ===== 🏅 อันดับหมวดย่อย =====
function rankEmoji(n: number): string {
  return ['🥇', '🥈', '🥉'][n - 1] ?? '';
}

function rankCircle(idx: number): string {
  if (idx === 0) return 'bg-amber-100';
  if (idx === 1) return 'bg-gray-100';
  if (idx === 2) return 'bg-orange-50';
  return 'bg-transparent';
}

// ===== 🕐 เวลาไทย Asia/Bangkok =====
function fmtDateTime(iso: string | null): string {
  if (!iso) return '-';
  return new Date(iso).toLocaleString('th-TH', {
    timeZone: 'Asia/Bangkok',
    day: 'numeric', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

function fmtDate(iso: string | null): string {
  if (!iso) return '-';
  return new Date(iso).toLocaleString('th-TH', {
    timeZone: 'Asia/Bangkok',
    day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
  });
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
    <!-- ===== Header ===== -->
    <div class="flex flex-wrap items-center justify-between gap-3 mb-5">
      <div>
        <h1 class="text-xl sm:text-2xl font-bold text-gray-900 leading-tight"><i class="bi bi-bar-chart mr-1 text-red-500"></i> แดชบอร์ด</h1>
        <p v-if="lastUpdated" class="text-xs text-gray-400 mt-0.5">
          อัปเดตล่าสุด <span class="font-medium text-gray-500">{{ fmtDateTime(lastUpdated) }}</span>
        </p>
      </div>
      <div class="flex items-center gap-2">
        <div v-if="data && data.scope === 'level'"
          class="flex items-center gap-2 px-3.5 py-1.5 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 text-sm">
          <i class="bi bi-funnel"></i>
          กำลังแสดงสถิติเฉพาะระดับชั้น <b class="ml-0.5">{{ data.scope_label }}</b>
        </div>
        <div v-else-if="data && data.scope === 'none'"
          class="flex items-center gap-2 px-3.5 py-1.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-sm">
          <i class="bi bi-exclamation-triangle"></i>
          ยังไม่ได้กำหนดระดับชั้นที่รับผิดชอบ
        </div>
        <div v-else-if="data" class="px-3.5 py-1.5 rounded-xl bg-gray-100 text-gray-600 text-sm">
          <i class="bi bi-globe2 mr-1"></i> ภาพรวมทั้งโรงเรียน
        </div>
        <button
          type="button"
          @click="loadDashboard"
          :disabled="isLoading"
          title="รีเฟรชข้อมูล"
          class="w-9 h-9 rounded-xl bg-white border border-gray-200 text-gray-500 hover:text-red-600 hover:border-red-300 flex items-center justify-center transition disabled:opacity-50"
        >
          <i class="bi bi-arrow-clockwise" :class="{ 'animate-spin': isLoading }"></i>
        </button>
      </div>
    </div>

    <!-- ===== Loading: skeleton จำลองโครงสร้างจริง (กัน layout shift) ===== -->
    <div v-if="isLoading && !data" class="space-y-6">
      <div class="bg-white rounded-2xl shadow-sm overflow-hidden">
        <div class="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-px bg-gray-100">
          <div v-for="i in 6" :key="i" class="bg-white p-5">
            <div class="w-2 h-2 rounded-full bg-gray-200 animate-pulse mb-2"></div>
            <div class="h-7 w-16 bg-gray-200 animate-pulse rounded mb-1"></div>
            <div class="h-3 w-20 bg-gray-200 animate-pulse rounded"></div>
          </div>
        </div>
        <div class="px-5 pb-5">
          <div class="h-2 bg-gray-200 animate-pulse rounded-full mb-2"></div>
          <div class="h-3 w-64 bg-gray-200 animate-pulse rounded"></div>
        </div>
      </div>
      <div v-for="i in 3" :key="i" class="bg-white rounded-2xl shadow-sm p-5">
        <div class="flex items-center gap-3 mb-4">
          <div class="w-11 h-11 rounded-xl bg-gray-200 animate-pulse"></div>
          <div class="flex-1 space-y-1.5">
            <div class="h-4 w-40 bg-gray-200 animate-pulse rounded"></div>
            <div class="h-3 w-64 bg-gray-200 animate-pulse rounded"></div>
          </div>
        </div>
        <div class="grid lg:grid-cols-3 gap-4">
          <div class="lg:col-span-2 space-y-2.5">
            <div v-for="j in 3" :key="j" class="h-16 bg-gray-100 animate-pulse rounded-xl"></div>
          </div>
          <div class="space-y-2.5">
            <div v-for="j in 3" :key="j" class="h-9 bg-gray-100 animate-pulse rounded-xl"></div>
          </div>
        </div>
      </div>
    </div>

    <!-- ===== Error ครั้งแรก (ไม่มีข้อมูล) ===== -->
    <div v-else-if="error && !data" class="bg-white rounded-2xl shadow-sm p-12 text-center">
      <div class="text-5xl mb-3 text-red-300"><i class="bi bi-exclamation-triangle"></i></div>
      <h2 class="text-lg font-bold text-gray-800 mb-1">ไม่สามารถโหลดข้อมูล Dashboard</h2>
      <p class="text-sm text-gray-500 mb-5 max-w-md mx-auto">{{ error }}</p>
      <button
        type="button"
        @click="loadDashboard"
        class="px-5 py-2.5 bg-red-600 text-white rounded-xl hover:bg-red-700 text-sm font-medium transition"
      >
        <i class="bi bi-arrow-clockwise mr-1"></i> ลองใหม่
      </button>
    </div>

    <!-- ===== scope 'none': ครูยังไม่ตั้งระดับชั้น → แนะนำแทนเลข 0 ===== -->
    <div v-else-if="data && data.scope === 'none'" class="bg-white rounded-2xl shadow-sm p-12 text-center">
      <div class="text-5xl mb-3 text-gray-300"><i class="bi bi-person-gear"></i></div>
      <h2 class="text-lg font-bold text-gray-800 mb-2">ยังไม่ได้กำหนดระดับชั้นที่รับผิดชอบ</h2>
      <p class="text-sm text-gray-500 max-w-md mx-auto">
        ครูยังไม่ระบุระดับชั้น (เช่น ม.4 / ม.5) จึงยังไม่เห็นข้อมูลสถิติ
        <br />กรุณาติดต่อผู้ดูแลระบบเพื่อตั้งค่าระดับชั้นในบัญชีของคุณ
      </p>
    </div>

    <div v-else-if="data" class="space-y-6">
      <!-- ===== KPI band: 6 ตัว + แถบสัดส่วนสถานะรวมทั้งระบบ ===== -->
      <div class="bg-white rounded-2xl shadow-sm overflow-hidden">
        <div class="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-px bg-gray-100">
          <div
            v-for="s in statCards"
            :key="s.label"
            class="bg-white p-4 sm:p-5"
            :class="s.alert ? 'bg-red-50' : ''"
          >
            <div class="flex items-center gap-1.5 mb-1">
              <span class="w-2 h-2 rounded-full shrink-0" :class="s.dot"></span>
              <span class="text-xs text-gray-500 truncate">{{ s.label }}</span>
            </div>
            <p class="text-2xl font-black text-gray-900 tabular-nums" :class="s.alert ? 'text-red-700' : ''">
              {{ fmtNum(s.value) }}
            </p>
          </div>
        </div>
        <div class="px-4 sm:px-5 py-4">
          <StatusStackedBar :stats="data.by_status" :total="data.total_issues" heightClass="h-2" />
          <div class="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-xs text-gray-500">
            <span v-for="s in data.by_status" :key="s.status" class="inline-flex items-center gap-1.5">
              <span class="w-2.5 h-2.5 rounded-full" :class="STATUS_DOT[s.status] ?? 'bg-gray-300'"></span>
              {{ s.label }}
              <b class="text-gray-700 tabular-nums">{{ fmtNum(s.count) }}</b>
            </span>
          </div>
        </div>
      </div>

      <!-- ===== 3 หมวดหลัก — แยกการ์ดชัดเจน ===== -->
      <section
        v-for="cat in data.main_categories"
        :key="cat.code"
        class="bg-white rounded-2xl shadow-sm overflow-hidden"
      >
        <!-- Header band (ทั้งแถวคลิก → ดูทั้งหมดในหมวด) -->
        <RouterLink
          :to="{ name: 'received-issues', query: { main_category: cat.code } }"
          class="flex items-center justify-between gap-3 px-5 py-4 transition group"
          :class="themeFor(cat.code).headerBg"
        >
          <div class="flex items-center gap-3 min-w-0">
            <div
              class="w-11 h-11 rounded-xl flex items-center justify-center text-xl text-white shadow-sm shrink-0"
              :class="themeFor(cat.code).iconBg"
            >
              <i class="bi" :class="themeFor(cat.code).icon"></i>
            </div>
            <div class="min-w-0">
              <h2 class="text-lg font-bold text-gray-900 flex flex-wrap items-center gap-2">
                {{ cat.label }}
                <span
                  v-if="cat.overdue > 0"
                  class="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] font-semibold rounded-full bg-red-100 text-red-700"
                  title="งานที่เกินกำหนดเวลาในหมวดนี้"
                >
                  <i class="bi bi-alarm"></i> เกินเวลา {{ fmtNum(cat.overdue) }}
                </span>
              </h2>
              <p class="text-xs text-gray-500 truncate mt-0.5">{{ cat.description }}</p>
            </div>
          </div>
          <div class="text-right shrink-0">
            <p class="text-3xl font-black leading-none tabular-nums" :class="themeFor(cat.code).countColor">
              {{ fmtNum(cat.total) }}
            </p>
            <p class="text-[11px] text-gray-500 mt-1 inline-flex items-center gap-1">
              เรื่อง · เสร็จ {{ resolvedRate(cat) }}%
              <span class="text-red-600 font-medium group-hover:underline inline-flex items-center gap-0.5">
                ดูทั้งหมด <i class="bi bi-arrow-right"></i>
              </span>
            </p>
          </div>
        </RouterLink>

        <!-- แถบสถานะภายในหมวด (progress รวม) -->
        <div class="px-5 pt-3">
          <StatusStackedBar :stats="cat.by_status" :total="cat.total" heightClass="h-1.5" />
          <div class="flex flex-wrap gap-x-3 gap-y-1 mt-1.5 text-[11px] text-gray-500">
            <span v-for="s in cat.by_status" :key="s.status" class="inline-flex items-center gap-1">
              <span class="w-2 h-2 rounded-full" :class="STATUS_DOT[s.status] ?? 'bg-gray-300'"></span>
              {{ statusShort(s.status) }} <b class="text-gray-700 tabular-nums">{{ fmtNum(s.count) }}</b>
            </span>
          </div>
        </div>

        <!-- Body: leaderboard หมวดย่อย (2/3) + เรื่องล่าสุด (1/3) -->
        <div class="p-5 grid lg:grid-cols-3 gap-6">
          <div class="lg:col-span-2 min-w-0">
            <h3 class="text-sm font-semibold text-gray-700 mb-2.5">
              <i class="bi bi-trophy mr-1" :class="themeFor(cat.code).countColor"></i>
              หมวดย่อยที่แจ้งมากที่สุด
            </h3>
            <div v-if="cat.total > 0" class="space-y-1.5">
              <template v-for="(sc, idx) in cat.subcategories" :key="sc.category">
                <!-- แถวหมวดย่อย → คลิกดูเรื่องในหมวดนั้น (deep-link) -->
                <RouterLink
                  v-if="sc.category !== '_other'"
                  :to="{ name: 'received-issues', query: { main_category: cat.code, category: sc.category } }"
                  class="group flex flex-wrap items-center gap-3 rounded-xl p-3 transition focus-visible:ring-2 focus-visible:ring-red-500 focus-visible:outline-none"
                  :class="idx === 0 ? themeFor(cat.code).leaderHighlight : themeFor(cat.code).rowHover"
                >
                  <span
                    class="w-8 h-8 rounded-full flex items-center justify-center shrink-0"
                    :class="rankCircle(idx)"
                  >
                    <span v-if="idx < 3" class="text-base" role="img" :aria-label="`อันดับ ${idx + 1}`">
                      {{ rankEmoji(idx + 1) }}
                    </span>
                    <span v-else class="text-sm font-black text-gray-400" :aria-label="`อันดับ ${idx + 1}`">
                      {{ idx + 1 }}
                    </span>
                  </span>

                  <div class="flex-1 min-w-0">
                    <div class="flex items-center justify-between gap-2">
                      <p class="font-semibold text-gray-800 truncate">{{ sc.label }}</p>
                      <span class="text-lg font-black text-gray-900 shrink-0 tabular-nums">{{ fmtNum(sc.count) }}</span>
                    </div>
                    <p class="text-[11px] text-gray-400 truncate">{{ sc.description }}</p>
                    <div class="mt-1.5 flex items-center gap-2">
                      <div class="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                        <div
                          class="h-full rounded-full transition-all"
                          :class="themeFor(cat.code).barColor"
                          :style="{ width: shareWidth(sc.count, maxSubCount(cat)) + '%' }"
                        ></div>
                      </div>
                      <span class="text-[11px] text-gray-400 shrink-0 tabular-nums">
                        {{ percent(sc.count, cat.total) }}%
                      </span>
                    </div>
                    <div class="mt-1.5 flex flex-wrap gap-x-2.5 gap-y-1">
                      <span
                        v-for="s in sc.by_status.filter((x) => x.count > 0)"
                        :key="s.status"
                        class="inline-flex items-center gap-1 text-[11px] text-gray-500"
                        :title="`${s.label}: ${s.count} เรื่อง`"
                      >
                        <span class="w-2 h-2 rounded-full" :class="STATUS_DOT[s.status] ?? 'bg-gray-300'"></span>
                        {{ statusShort(s.status) }} <b class="text-gray-600 tabular-nums">{{ fmtNum(s.count) }}</b>
                      </span>
                      <span v-if="!sc.by_status.some((x) => x.count > 0)" class="text-[11px] text-gray-400">
                        ยังไม่มีเรื่อง
                      </span>
                    </div>
                  </div>

                  <i class="bi bi-chevron-right text-gray-300 shrink-0 transition" :class="themeFor(cat.code).chevron"></i>
                </RouterLink>

                <!-- หมวดย่อยนอกระบบ (อื่นๆ) → ไม่คลิก เน้นๆ ให้เห็นว่าไม่ใช่หมวดใน config -->
                <div v-else class="flex flex-wrap items-center gap-3 rounded-xl p-3 opacity-80">
                  <span class="w-8 h-8 rounded-full flex items-center justify-center shrink-0 text-sm font-black text-gray-400"
                    :aria-label="`อันดับ ${idx + 1}`">{{ idx + 1 }}</span>
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center justify-between gap-2">
                      <p class="font-semibold text-gray-500 truncate">{{ sc.label }}</p>
                      <span class="text-lg font-black text-gray-500 shrink-0 tabular-nums">{{ fmtNum(sc.count) }}</span>
                    </div>
                    <p class="text-[11px] text-gray-400 truncate">{{ sc.description }}</p>
                  </div>
                </div>
              </template>
            </div>
            <p v-else class="text-sm text-gray-400 py-8 text-center">
              <i class="bi bi-inbox mr-1"></i> ยังไม่มีเรื่องในหมวดนี้
            </p>
          </div>

          <!-- เรื่องล่าสุด → คลิกเข้าไปดูผลลัพธ์/ติดตามงาน -->
          <div class="lg:col-span-1 min-w-0">
            <div class="flex items-center justify-between mb-2">
              <h3 class="text-sm font-semibold text-gray-700">
                <i class="bi bi-clock-history mr-1"></i> เรื่องล่าสุด
              </h3>
            </div>
            <div v-if="cat.recent_issues.length" class="space-y-1">
              <RouterLink
                v-for="r in cat.recent_issues"
                :key="r.id"
                :to="{ name: 'issue-detail', params: { id: r.id } }"
                class="flex items-center gap-2.5 p-2 rounded-xl hover:bg-gray-50 transition group focus-visible:ring-2 focus-visible:ring-red-500 focus-visible:outline-none"
              >
                <span class="w-2 h-2 rounded-full shrink-0" :class="STATUS_DOT[r.status] ?? 'bg-gray-300'"></span>
                <div class="flex-1 min-w-0">
                  <p class="text-sm text-gray-800 truncate group-hover:text-gray-900">{{ r.title }}</p>
                  <p class="text-[11px] text-gray-400 truncate">
                    {{ r.category_label }} · {{ r.room_name || 'ไม่ระบุห้อง' }} · {{ fmtDate(r.created_at) }}
                  </p>
                </div>
                <span
                  class="px-2 py-0.5 text-[11px] font-medium rounded-full shrink-0"
                  :class="STATUS_BADGE[r.status] ?? 'bg-gray-100 text-gray-600'"
                >
                  {{ statusShort(r.status) }}
                </span>
              </RouterLink>
            </div>
            <p v-else class="text-sm text-gray-400 py-4 text-center">ยังไม่มีเรื่องล่าสุด</p>
          </div>
        </div>
      </section>

      <!-- ===== ภาพรวมเสริม: แนวโน้ม + สถิติระบบ ===== -->
      <div class="grid lg:grid-cols-3 gap-4">
        <div class="lg:col-span-2 bg-white rounded-2xl shadow-sm p-4 sm:p-5">
          <h3 class="font-semibold text-gray-800 mb-3"><i class="bi bi-graph-up mr-1"></i> แนวโน้มเรื่องที่แจ้ง (7 วัน)</h3>
          <div class="h-64"><Line :data="trendChart" :options="chartOptions" /></div>
        </div>

        <div class="bg-white rounded-2xl shadow-sm p-4 sm:p-5">
          <h3 class="font-semibold text-gray-800 mb-3"><i class="bi bi-building mr-1"></i> สถิติระบบ</h3>
          <div class="grid grid-cols-2 gap-3">
            <div class="bg-gray-50 rounded-xl p-3">
              <p class="text-2xl font-black text-gray-900 tabular-nums">{{ fmtNum(data.total_students) }}</p>
              <p class="text-xs text-gray-500"><i class="bi bi-people mr-1"></i> นักเรียนในระบบ</p>
            </div>
            <div class="bg-gray-50 rounded-xl p-3">
              <p class="text-2xl font-black text-gray-900 tabular-nums">{{ fmtNum(data.total_rooms) }}</p>
              <p class="text-xs text-gray-500"><i class="bi bi-door-closed mr-1"></i> ห้องเรียน</p>
            </div>
          </div>
          <div class="mt-3 pt-3 border-t border-gray-100">
            <div class="flex items-center justify-between">
              <p class="text-2xl font-black text-gray-900 tabular-nums">{{ fmtNum(data.usage_count) }}</p>
              <span class="text-xs text-gray-400">ครั้ง (ยอดสะสม)</span>
            </div>
            <p class="text-xs text-gray-500 mt-1 mb-2"><i class="bi bi-person-check mr-1"></i> การเข้าใช้งานล่าสุด</p>
            <div v-if="data.recent_logins.length" class="space-y-1.5">
              <div
                v-for="(lg, idx) in data.recent_logins.slice(0, 5)"
                :key="idx"
                class="flex items-center justify-between text-xs"
              >
                <span class="text-gray-600 truncate">{{ lg.actor }}</span>
                <span class="text-gray-400 ml-2 shrink-0">{{ fmtDate(lg.at) }}</span>
              </div>
            </div>
            <p v-else class="text-sm text-gray-400 py-2">ยังไม่มีข้อมูลการเข้าใช้งาน</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
