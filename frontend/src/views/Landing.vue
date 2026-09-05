<!-- eslint-disable vue/multi-word-component-names -- ชื่อ Landing ตาม spec (หน้าแรก) -->
<script setup lang="ts">
/**
 * 🏠 Landing.vue — หน้าแรกของ PIRIvoice
 * เสียงจากชาวพิริยาลัย · สภานักเรียน โรงเรียนพิริยาลัยจังหวัดแพร่
 *
 * หลักการ: ไม่มี Mock Data — ทุกข้อมูลดึงจาก Public API ( /api/v1/public/* )
 * ทุก section ที่ใช้ข้อมูลมี Loading Skeleton + Error Handling + Retry
 *
 * v2 (UX/UI redesign - Human Crafted):
 * - เน้นความสะอาดตา (Clean UI) ลด Gradient ที่ฉูดฉาดเพื่อความน่าเชื่อถือ
 * - ใช้ Solid Colors และ Subtle Shadows ให้ดูพรีเมียมเหมือน SaaS ระดับโลก
 * - เปลี่ยนกรอบความคิดเป็น "แจ้งเรื่อง" แทนการใช้คำเชิงลบ
 */
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue';
import { useRouter } from 'vue-router';
import api from '@/services/api';

/* ============================================================
 * 📐 TypeScript Interfaces — Public API Contract
 * ============================================================ */
interface SystemStats {
  total_issues: number;
  resolved_issues: number;
  routed_issues: number;
  resolved_rate_percent: number;
  avg_resolve_hours: number;
  active_talk_threads: number;
  active_votes: number;
}

interface StatTrendPoint {
  date: string;
  count: number;
}

interface ResolvedCase {
  id: string;
  title: string;
  category: string;
  reporter_mask: string;
  resolved_at: string;
  solution_summary: string;
  department_in_charge: string;
  impact_score: number;
  duration_hours?: number;
}

type AnnouncementPriority = 'normal' | 'high' | 'urgent';

interface Announcement {
  id: string;
  message: string;
  priority: AnnouncementPriority;
  link?: string;
}

/* ============================================================
 * 🗂️ State
 * ============================================================ */
const router = useRouter();

// ── ข้อมูลจาก API ──
const stats = ref<SystemStats | null>(null);
const statsTrend = ref<StatTrendPoint[]>([]);
const resolvedCases = ref<ResolvedCase[]>([]);
const announcements = ref<Announcement[]>([]);

// ── Loading / Error ──
const isLoadingStats = ref(true);
const isLoadingTrend = ref(true);
const isLoadingCases = ref(true);
const isLoadingAnnouncements = ref(true);

const hasStatsError = ref(false);
const hasTrendError = ref(false);
const hasCasesError = ref(false);
const hasAnnouncementsError = ref(false);

// ── UI: Navbar ──
const isScrolled = ref(false);

// ── DOM refs ──
const statsGridRef = ref<HTMLElement | null>(null);

/* ============================================================
 * 📡 API Calls
 * ============================================================ */
async function fetchStats() {
  isLoadingStats.value = true;
  hasStatsError.value = false;
  try {
    const res = (await api.get('/api/v1/public/stats')) as SystemStats;
    stats.value = res;
  } catch {
    hasStatsError.value = true;
  } finally {
    isLoadingStats.value = false;
  }
}

async function fetchStatsTrend() {
  isLoadingTrend.value = true;
  hasTrendError.value = false;
  try {
    const res = (await api.get('/api/v1/public/stats/trend', {
      params: { days: 14 },
    })) as StatTrendPoint[];
    statsTrend.value = Array.isArray(res) ? res : [];
  } catch {
    hasTrendError.value = true;
  } finally {
    isLoadingTrend.value = false;
  }
}

async function fetchResolvedCases() {
  isLoadingCases.value = true;
  hasCasesError.value = false;
  try {
    const res = (await api.get('/api/v1/public/resolved-cases', {
      params: { limit: 5 },
    })) as ResolvedCase[];
    resolvedCases.value = Array.isArray(res) ? res : [];
  } catch {
    hasCasesError.value = true;
  } finally {
    isLoadingCases.value = false;
  }
}

async function fetchAnnouncements() {
  isLoadingAnnouncements.value = true;
  hasAnnouncementsError.value = false;
  try {
    const res = (await api.get('/api/v1/public/announcements')) as Announcement[];
    announcements.value = Array.isArray(res) ? res : [];
  } catch {
    hasAnnouncementsError.value = true;
  } finally {
    isLoadingAnnouncements.value = false;
  }
}

/* ============================================================
 * 🛠️ Helpers
 * ============================================================ */
const numberFmt = new Intl.NumberFormat('th-TH');

function prefersReducedMotion(): boolean {
  return typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

const goLogin = () => {
  router.push({ name: 'login' });
};

function scrollToId(id: string) {
  document.getElementById(id)?.scrollIntoView({
    behavior: prefersReducedMotion() ? 'auto' : 'smooth',
  });
}

function formatThaiDate(iso: string): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat('th-TH', {
    timeZone: 'Asia/Bangkok',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(d);
}

function formatDuration(hours: number): string {
  const h = hours ?? 0;
  if (h <= 0) return 'ทันที';
  if (h < 1) return `${Math.max(1, Math.round(h * 60))} นาที`;
  if (h < 24) return `${h.toFixed(1).replace(/\.0$/, '')} ชม.`;
  const days = Math.floor(h / 24);
  const rest = Math.round(h % 24);
  return rest ? `${days} วัน ${rest} ชม.` : `${days} วัน`;
}

function reporterInitial(mask: string): string {
  if (!mask) return '?';
  const cleaned = mask.replace(/^นักเรียน\s*/, '').trim();
  if (!cleaned || cleaned.includes('ไม่ประสงค์')) return '?';
  return cleaned.charAt(0);
}

function impactLabel(score: number): { label: string; cls: string } {
  if (score >= 8) return { label: 'ผลกระทบสูง', cls: 'bg-rose-50 text-rose-600 border-rose-100' };
  if (score >= 5) return { label: 'ผลกระทบกลาง', cls: 'bg-slate-100 text-slate-700 border-slate-200' };
  return { label: 'ผลกระทบทั่วไป', cls: 'bg-slate-50 text-slate-500 border-slate-100' };
}

function formatStatValue(v: number, decimals = 0): string {
  const factor = 10 ** decimals;
  const rounded = Math.round((v ?? 0) * factor) / factor;
  return new Intl.NumberFormat('th-TH', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(rounded);
}

/* ============================================================
 * 🎞️ Count-up
 * ============================================================ */
function animateStatNumbers(container: HTMLElement) {
  const els = container.querySelectorAll<HTMLElement>('[data-target]');
  if (prefersReducedMotion()) {
    els.forEach((el) => {
      el.textContent = formatStatValue(
        parseFloat(el.dataset.target ?? '0'),
        parseInt(el.dataset.decimals ?? '0', 10),
      );
    });
    return;
  }
  els.forEach((el) => {
    const target = parseFloat(el.dataset.target ?? '0');
    const decimals = parseInt(el.dataset.decimals ?? '0', 10);
    const duration = 1100;
    const start = performance.now();
    const step = (now: number) => {
      const p = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - p, 3);
      el.textContent = formatStatValue(target * eased, decimals);
      if (p < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  });
}

function onCardGlow(ev: MouseEvent) {
  const el = ev.currentTarget as HTMLElement;
  const rect = el.getBoundingClientRect();
  el.style.setProperty('--mx', `${ev.clientX - rect.left}px`);
  el.style.setProperty('--my', `${ev.clientY - rect.top}px`);
}

/* ============================================================
 * 📊 Computed
 * ============================================================ */
const heroStat = computed(() => (stats.value ? stats.value.total_issues : 0));

const smallStats = computed(() => {
  const s = stats.value;
  if (!s) return [];
  return [
    {
      key: 'routed',
      icon: 'bi-arrow-right-circle-fill',
      label: 'กำลังดำเนินการ',
      target: s.routed_issues,
      decimals: 0,
      hint: 'ส่งต่อฝ่ายที่เกี่ยวข้องแล้ว',
      iconCls: 'bg-rose-50 text-rose-600 border-rose-100',
    },
    {
      key: 'resolved',
      icon: 'bi-check2-circle-fill',
      label: 'ปิดสำเร็จแล้ว',
      target: s.resolved_issues,
      decimals: 0,
      hint: 'ทุกเรื่องถูกติดตามจนจบ',
      iconCls: 'bg-emerald-50 text-emerald-600 border-emerald-100',
    },
    {
      key: 'avg',
      icon: 'bi-stopwatch-fill',
      label: 'เวลาเฉลี่ยต่อเรื่อง',
      target: s.avg_resolve_hours,
      decimals: 1,
      suffix: ' ชม.',
      hint: 'ตั้งแต่รับเรื่องจนปิดงาน',
      iconCls: 'bg-slate-50 text-slate-600 border-slate-200',
    },
    {
      key: 'talk',
      icon: 'bi-chat-dots-fill',
      label: 'กระทู้บน PIRI Talk',
      target: s.active_talk_threads,
      decimals: 0,
      hint: 'กำลังเปิดพูดคุย',
      iconCls: 'bg-blue-50 text-blue-600 border-blue-100',
    },
    {
      key: 'votes',
      icon: 'bi-patch-check-fill',
      label: 'เสียงบน PIRI Vote',
      target: s.active_votes,
      decimals: 0,
      hint: 'สะสมจากการโหวต',
      iconCls: 'bg-slate-50 text-slate-600 border-slate-200',
    },
  ];
});

/* ============================================================
 * 📈 Sparkline
 * ============================================================ */
const SPARK_W = 320;
const SPARK_H = 84;
const SPARK_PAD = 6;

const sparkTrend = computed(() => {
  const pts = statsTrend.value;
  if (pts.length === 0) return null;
  const max = Math.max(...pts.map((p) => p.count), 1);
  const n = pts.length;
  const stepX = (SPARK_W - SPARK_PAD * 2) / (n - 1 || 1);
  const coords = pts.map((p, i) => ({
    x: SPARK_PAD + i * stepX,
    y: SPARK_H - SPARK_PAD - (p.count / max) * (SPARK_H - SPARK_PAD * 2),
  }));
  const line = coords.map((c) => `${c.x.toFixed(1)},${c.y.toFixed(1)}`).join(' ');
  const area = `${SPARK_PAD},${SPARK_H} ${line} ${(SPARK_W - SPARK_PAD).toFixed(1)},${SPARK_H}`;
  return {
    line,
    area,
    last: coords[coords.length - 1] ?? { x: SPARK_W - SPARK_PAD, y: SPARK_H - SPARK_PAD },
    total: pts.reduce((acc, p) => acc + p.count, 0),
    days: n,
  };
});

const sparkDot = computed(() => {
  const t = sparkTrend.value;
  if (!t) return null;
  return { left: (t.last.x / SPARK_W) * 100, top: (t.last.y / SPARK_H) * 100 };
});

/* ============================================================
 * 📣 Announcements
 * ============================================================ */
const heroAnnouncement = computed<Announcement | null>(() => announcements.value[0] ?? null);

const topPriority = computed<AnnouncementPriority>(() => {
  const order: Record<AnnouncementPriority, number> = { normal: 0, high: 1, urgent: 2 };
  return announcements.value.reduce<AnnouncementPriority>(
    (acc, a) => (order[a.priority] > order[acc] ? a.priority : acc),
    'normal',
  );
});

const hasUrgent = computed(() => topPriority.value === 'urgent');

function priorityDotCls(p: AnnouncementPriority): string {
  if (p === 'urgent') return 'bg-rose-600';
  if (p === 'high') return 'bg-orange-500';
  return 'bg-slate-400';
}

const marqueeDuration = computed(() => {
  const n = Math.max(announcements.value.length, 1);
  return `${Math.max(16, n * 7)}s`;
});

/* ============================================================
 * 💡 The Impact
 * ============================================================ */
const featuredCase = computed<ResolvedCase | null>(() => {
  if (resolvedCases.value.length === 0) return null;
  const top = [...resolvedCases.value].sort((a, b) => b.impact_score - a.impact_score)[0];
  return top ?? null;
});

const latestCase = computed<ResolvedCase | null>(() => resolvedCases.value[0] ?? null);

const recentCases = computed<ResolvedCase[]>(() =>
  resolvedCases.value.filter((c) => c.id !== featuredCase.value?.id).slice(0, 3),
);

/* ============================================================
 * 🪜 Static content
 * ============================================================ */
const navLinks = [
  { label: 'ผลการดำเนินงาน', id: 'stats' },
  { label: 'ขั้นตอนการทำงาน', id: 'flow' },
  { label: 'ผลลัพธ์จริง', id: 'impact' },
  { label: 'ระบบนิเวศ', id: 'ecosystem' },
];

const workflowTiers = [
  {
    name: 'ทุกเสียงของนักเรียน',
    desc: 'ส่งเรื่องราว / ข้อคิดเห็น เข้าระบบได้ตลอด 24 ชม. ผ่านมือถือหรือคอมพิวเตอร์',
    icon: 'bi-send-fill',
    width: 'max-w-3xl',
    num: '01',
    ring: 'border-slate-200 bg-white text-slate-900',
    iconCls: 'bg-slate-100 text-slate-600',
  },
  {
    name: 'หัวหน้าห้อง + รอง 4 ฝ่าย',
    desc: 'รวบรวม กลั่นกรอง และส่งต่อเรื่องที่เกินขอบเขตขึ้นไปตามสายงาน',
    icon: 'bi-person-lines-fill',
    width: 'max-w-2xl',
    num: '02',
    ring: 'border-slate-200 bg-white text-slate-900',
    iconCls: 'bg-slate-100 text-slate-700',
  },
  {
    name: 'ประธานระดับ',
    desc: 'รวบรวมเรื่องทั้งระดับชั้น ดูแลความสำคัญ และส่งต่อขึ้นสภาหากจำเป็น',
    icon: 'bi-people-fill',
    width: 'max-w-xl',
    num: '03',
    ring: 'border-rose-100 bg-white text-slate-900',
    iconCls: 'bg-rose-50 text-rose-600',
  },
  {
    name: 'สภานักเรียน · ประธานสภา',
    desc: 'รับช่วงต่อเรื่องสำคัญ มอบหมายหน่วยงานที่เกี่ยวข้อง และติดตามจนจบกระบวนการ',
    icon: 'bi-flag-fill',
    width: 'max-w-lg',
    num: '04',
    ring: 'border-rose-200 bg-rose-50/50 text-slate-900',
    iconCls: 'bg-rose-100 text-rose-700',
  },
];

const goStats = () => scrollToId('stats');

/* ============================================================
 * 🔄 Lifecycle
 * ============================================================ */
function onWindowScroll() {
  isScrolled.value = window.scrollY > 12;
}

onMounted(() => {
  fetchStats();
  fetchStatsTrend();
  fetchResolvedCases();
  fetchAnnouncements();
  window.addEventListener('scroll', onWindowScroll, { passive: true });
});

onBeforeUnmount(() => {
  window.removeEventListener('scroll', onWindowScroll);
});

watch([stats, isLoadingStats], () => {
  if (!stats.value || isLoadingStats.value) return;
  nextTick(() => {
    const grid = statsGridRef.value;
    if (grid) animateStatNumbers(grid);
  });
});
</script>

<template>
  <div
    class="relative min-h-screen overflow-x-clip bg-[#F8FAFC] font-sans text-slate-900 selection:bg-rose-500/20 selection:text-rose-900"
  >
    <!-- ⚡ =============================================== -->
    <!-- 1. STICKY NAVBAR (Clean Glassmorphism)           -->
    <!-- ⚡ =============================================== -->
    <header
      class="sticky top-0 z-50 border-b backdrop-blur-xl transition-all duration-300"
      :class="
        isScrolled
          ? 'border-slate-200/80 bg-white/80 shadow-sm'
          : 'border-transparent bg-transparent'
      "
    >
      <nav class="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 lg:px-8">
        <!-- ซ้าย: โลโก้ 2 ดวง + ตัวแบ่ง + Wordmark -->
        <div class="flex items-center gap-3">
          <div class="flex items-center gap-2">
            <div
              class="flex h-10 w-10 items-center justify-center rounded-xl border border-slate-200/70 bg-white p-1 shadow-sm transition-transform duration-300 hover:scale-105"
            >
              <img src="/logos/school-logo.png" alt="โลโก้โรงเรียนพิริยาลัย" class="h-full w-full object-contain" />
            </div>
            <div
              class="flex h-10 w-10 items-center justify-center rounded-xl border border-slate-200/70 bg-white p-1 shadow-sm transition-transform duration-300 hover:scale-105"
            >
              <img src="/logos/council-logo.png" alt="โลโก้สภานักเรียน" class="h-full w-full object-contain" />
            </div>
          </div>
          <div class="hidden h-6 w-px bg-slate-300 sm:block"></div>
          <button @click="scrollToId('hero')" class="group text-left">
            <span class="block text-xl font-black tracking-tight text-slate-900">
              PIRI<span class="text-rose-600">voice</span>
            </span>
            <span class="block text-[10px] font-semibold tracking-wide text-slate-500">
              สภานักเรียน · โรงเรียนพิริยาลัยฯ
            </span>
          </button>
        </div>

        <!-- ขวา: ลิงก์ + ปุ่มเข้าสู่ระบบ (desktop) -->
        <div class="hidden items-center gap-1 lg:flex">
          <button
            v-for="link in navLinks"
            :key="link.id"
            @click="scrollToId(link.id)"
            class="rounded-lg px-3.5 py-2 text-sm font-semibold text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900"
          >
            {{ link.label }}
          </button>
          <div class="mx-2 h-5 w-px bg-slate-200"></div>
          <button
            @click="goLogin"
            class="group relative flex items-center gap-2 overflow-hidden rounded-xl bg-rose-600 px-4 py-2.5 text-sm font-bold text-white shadow-sm transition-all duration-300 hover:bg-rose-700 hover:shadow-md active:scale-[0.97]"
          >
            <i class="bi bi-box-arrow-in-right text-base"></i>
            เข้าสู่ระบบ
          </button>
        </div>

        <!-- ปุ่มเข้าสู่ระบบ (mobile) -->
        <button
          @click="goLogin"
          aria-label="เข้าสู่ระบบ"
          class="flex h-10 w-10 items-center justify-center rounded-xl bg-rose-600 text-white shadow-sm transition-all duration-300 hover:bg-rose-700 active:scale-[0.97] sm:h-auto sm:w-auto sm:gap-2 sm:px-4 sm:py-2.5 lg:hidden"
        >
          <i class="bi bi-box-arrow-in-right text-lg sm:text-base"></i>
          <span class="hidden text-sm font-bold sm:inline">เข้าสู่ระบบ</span>
        </button>
      </nav>
    </header>

    <main class="relative">
      <!-- 🌟 =============================================== -->
      <!-- 2. HERO — Headline + Phone Mockup                 -->
      <!-- 🌟 =============================================== -->
      <section id="hero" class="relative overflow-hidden">
        <!-- 🎨 พื้นหลัง: Animated Glow Orbs (Subtle, Clean) -->
        <div class="pointer-events-none absolute inset-0">
          <div
            class="animate-blob absolute -right-[5%] -top-[10%] h-[600px] w-[600px] rounded-full bg-rose-100/50 blur-[100px] max-md:h-[400px] max-md:w-[400px] max-md:blur-[80px]"
          ></div>
          <div
            class="animate-blob animation-delay-2000 absolute -left-[5%] top-[20%] h-[500px] w-[500px] rounded-full bg-slate-200/50 blur-[90px] max-md:h-[300px] max-md:w-[300px] max-md:blur-[70px]"
          ></div>
          <div
            class="absolute inset-0 opacity-[0.03] [mask-image:linear-gradient(to_bottom,white,transparent)] [background-image:url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAiIGhlaWdodD0iMjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGNpcmNsZSBjeD0iMSIgY3k9IjEiIHI9IjEiIGZpbGw9InJnYmEoMCwgMCwgMCwgMC4wNCkiLz48L3N2Zz4=')]"
          ></div>
        </div>

        <div class="relative mx-auto grid max-w-7xl grid-cols-1 items-center gap-16 px-4 pb-24 pt-14 lg:grid-cols-[1.05fr_0.95fr] lg:gap-10 lg:px-8 lg:pb-32 lg:pt-20">
          <!-- ฝั่งซ้าย: Typography & CTA -->
          <div class="text-center lg:text-left">
            <!-- ประกาศล่าสุด -->
            <div class="animate-slide-up-fade flex min-h-[34px] justify-center lg:justify-start">
              <div v-if="isLoadingAnnouncements" class="skeleton-shimmer h-[30px] w-56 rounded-full border border-slate-200 bg-white/70"></div>
              <div v-else-if="hasAnnouncementsError" class="hidden"></div>
              <button
                v-else-if="heroAnnouncement"
                @click="scrollToId('announce')"
                class="group inline-flex max-w-full items-center gap-2 rounded-full border border-slate-200/80 bg-white/80 py-1.5 pl-2 pr-4 text-sm font-semibold text-slate-600 shadow-sm backdrop-blur transition-all duration-300 hover:border-rose-200 hover:text-rose-700"
              >
                <span class="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-slate-900 px-3 py-1 text-[11px] font-black uppercase tracking-wide text-white">
                  <i class="bi bi-megaphone-fill"></i>
                  ประกาศ
                </span>
                <span class="inline-flex min-w-0 items-center gap-1.5">
                  <span :class="['h-1.5 w-1.5 shrink-0 rounded-full', priorityDotCls(heroAnnouncement.priority)]"></span>
                  <span class="truncate">{{ heroAnnouncement.message }}</span>
                  <i class="bi bi-arrow-right shrink-0 text-xs text-slate-300 transition-transform group-hover:translate-x-0.5 group-hover:text-rose-500"></i>
                </span>
              </button>
            </div>

            <h1 class="animate-slide-up-fade mt-6 text-4xl font-black leading-[1.15] tracking-tight text-slate-900 sm:text-5xl xl:text-[3.6rem]" style="animation-delay: 80ms">
              ให้ทุกเสียงของคุณ
              <br class="hidden sm:block" />
              <span class="text-rose-600">
                เปลี่ยนโรงเรียนให้ดีขึ้น
              </span>
            </h1>

            <p class="animate-slide-up-fade mx-auto mt-6 max-w-xl text-base font-medium leading-relaxed text-slate-500 sm:text-lg lg:mx-0" style="animation-delay: 160ms">
              แจ้งเรื่องราว ข้อคิดเห็น หรือสิ่งที่อยากให้แก้ไข ระบบจะไต่ระดับตามสายงานอย่างอัตโนมัติ
              มีเจ้าของงานชัดเจน และคุณติดตามความคืบหน้าได้แบบเรียลไทม์
            </p>

            <!-- CTA -->
            <div class="animate-slide-up-fade mt-8 flex flex-col items-center gap-3 sm:flex-row sm:justify-center lg:justify-start" style="animation-delay: 240ms">
              <button
                @click="goLogin"
                class="group relative flex w-full items-center justify-center gap-2 overflow-hidden rounded-2xl bg-rose-600 px-8 py-4 text-base font-bold text-white shadow-md shadow-rose-600/20 transition-all duration-300 hover:bg-rose-700 hover:shadow-lg active:scale-[0.97] sm:w-auto"
              >
                <i class="bi bi-send-fill text-lg transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5"></i>
                แจ้งเรื่อง
              </button>
              <button
                @click="goStats"
                class="flex w-full items-center justify-center gap-2 rounded-2xl border border-slate-200 bg-white/80 px-8 py-4 text-base font-bold text-slate-700 shadow-sm backdrop-blur transition-all duration-300 hover:border-slate-300 hover:bg-slate-50 active:scale-[0.97] sm:w-auto"
              >
                <i class="bi bi-bar-chart-fill text-lg text-slate-400"></i>
                ดูผลการดำเนินงาน
              </button>
            </div>

            <!-- Trust line -->
            <div class="animate-slide-up-fade mt-9 flex flex-wrap items-center justify-center gap-x-5 gap-y-2 text-sm font-semibold text-slate-500 lg:justify-start" style="animation-delay: 320ms">
              <span class="inline-flex items-center gap-1.5"><i class="bi bi-shield-check text-slate-400"></i> โปร่งใสตรวจสอบได้</span>
              <span class="inline-flex items-center gap-1.5"><i class="bi bi-lightning-charge-fill text-slate-400"></i> รวดเร็วมีกำหนดเวลา</span>
              <span class="inline-flex items-center gap-1.5"><i class="bi bi-chat-dots text-slate-400"></i> ทุกเสียงถูกรับฟัง</span>
            </div>

            <p class="animate-slide-up-fade mt-4 flex items-center justify-center gap-1.5 text-xs font-medium text-slate-400 lg:justify-start" style="animation-delay: 380ms">
              <i class="bi bi-info-circle text-[13px]"></i>
              ใช้บัญชีนักเรียนของโรงเรียนเข้าสู่ระบบเพื่อเริ่มต้น
            </p>
          </div>

          <!-- ฝั่งขวา: Phone Mockup (Clean) -->
          <div class="animate-slide-up-fade relative mx-auto w-full max-w-[420px]" style="animation-delay: 200ms">
            <!-- เงาใต้โทรศัพท์ -->
            <div class="tilt-shadow pointer-events-none absolute -bottom-6 left-1/2 h-8 w-64 -translate-x-1/2 rounded-[100%] bg-slate-900/10 blur-md"></div>

            <div class="phone-tilt pointer-events-none relative select-none" aria-hidden="true">
              <!-- Glow หลังเครื่อง -->
              <div class="pointer-events-none absolute -inset-6 rounded-[3.5rem] bg-rose-200/30 blur-2xl"></div>

              <div class="relative mx-auto w-[min(290px,82vw)] rounded-[2.9rem] border-[6px] border-slate-900 bg-slate-900 shadow-2xl sm:w-[310px]">
                <!-- จอ -->
                <div class="relative overflow-hidden rounded-[2.4rem] bg-[#F8FAFC]">
                  <!-- กล้อง (notch) -->
                  <div class="absolute left-1/2 top-2 z-10 h-6 w-28 -translate-x-1/2 rounded-full bg-slate-900"></div>

                  <!-- Status bar -->
                  <div class="flex items-center justify-between px-6 pb-1 pt-2.5 text-[10px] font-bold text-slate-900">
                    <span>09:41</span>
                    <span class="flex items-center gap-1">
                      <i class="bi bi-signal text-[9px]"></i>
                      <i class="bi bi-wifi text-[10px]"></i>
                      <i class="bi bi-battery-full text-[11px]"></i>
                    </span>
                  </div>

                  <!-- App header -->
                  <div class="flex items-center justify-between px-5 pt-2">
                    <div class="flex items-center gap-2">
                      <span class="flex h-7 w-7 items-center justify-center rounded-lg border border-slate-200 bg-white shadow-sm">
                        <img src="/logos/school-logo.png" alt="" class="h-5 w-5 object-contain" />
                      </span>
                      <span class="text-sm font-black tracking-tight text-slate-900">
                        PIRI<span class="text-rose-600">voice</span>
                      </span>
                    </div>
                    <div class="flex items-center gap-2.5 text-slate-400">
                      <span class="relative">
                        <i class="bi bi-bell text-sm"></i>
                        <span class="absolute -right-0.5 -top-0.5 h-1.5 w-1.5 rounded-full bg-rose-500"></span>
                      </span>
                      <span class="flex h-6 w-6 items-center justify-center rounded-full bg-slate-800 text-[9px] font-black text-white">ณ</span>
                    </div>
                  </div>

                  <!-- การ์ดต้อนรับ -->
                  <div class="mx-4 mt-3 rounded-2xl bg-white p-4 shadow-sm border border-slate-100">
                    <p class="text-[11px] font-bold text-slate-500">สวัสดีชาวพิริยาลัย 👋</p>
                    <p class="mt-0.5 text-[13px] font-black text-slate-800">มีอะไรให้เราช่วยดูแลวันนี้?</p>
                  </div>

                  <!-- แบบฟอร์มแจ้งเรื่อง (ย่อ) -->
                  <div class="mx-4 mt-3 rounded-2xl border border-slate-200 bg-white p-3 shadow-sm">
                    <div class="flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-[11px] text-slate-400">
                      <i class="bi bi-chat-left-text text-slate-300"></i>
                      เล่าเรื่องให้เราฟังหน่อย…
                    </div>
                    <div class="mt-2 flex w-full items-center justify-center gap-1.5 rounded-xl bg-slate-900 py-2 text-[12px] font-bold text-white shadow-sm">
                      <i class="bi bi-send text-[11px]"></i>
                      ส่งเรื่อง
                    </div>
                  </div>

                  <!-- สถิติย่อ (ข้อมูลจริง) -->
                  <div class="mx-4 mt-3 grid grid-cols-2 gap-2">
                    <div class="rounded-xl border border-slate-100 bg-white p-2.5 shadow-sm">
                      <p class="text-[9px] font-semibold text-slate-400">กำลังดำเนินการ</p>
                      <template v-if="!isLoadingStats && stats">
                        <p class="mt-0.5 text-base font-black tabular-nums text-slate-800">{{ numberFmt.format(stats.routed_issues) }}</p>
                      </template>
                      <div v-else class="skeleton-shimmer mt-1 h-5 w-8 rounded bg-slate-100"></div>
                    </div>
                    <div class="rounded-xl border border-slate-100 bg-white p-2.5 shadow-sm">
                      <p class="text-[9px] font-semibold text-slate-400">ปิดสำเร็จแล้ว</p>
                      <template v-if="!isLoadingStats && stats">
                        <p class="mt-0.5 text-base font-black tabular-nums text-rose-600">{{ numberFmt.format(stats.resolved_issues) }}</p>
                      </template>
                      <div v-else class="skeleton-shimmer mt-1 h-5 w-8 rounded bg-slate-100"></div>
                    </div>
                  </div>

                  <!-- เรื่องล่าสุด -->
                  <div class="mx-4 mt-3 rounded-2xl border border-slate-200 bg-white p-3 shadow-sm">
                    <div class="flex items-center justify-between">
                      <p class="text-[10px] font-bold text-slate-500">เรื่องล่าสุด</p>
                      <span class="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-[9px] font-black text-slate-600">
                        <span class="h-1 w-1 animate-pulse rounded-full bg-emerald-500"></span>
                        ปิดสำเร็จ
                      </span>
                    </div>
                    <template v-if="!isLoadingCases && latestCase">
                      <p class="mt-1.5 line-clamp-1 text-[12px] font-bold text-slate-800">{{ latestCase.title }}</p>
                      <p class="mt-0.5 line-clamp-1 text-[10px] text-slate-400">{{ latestCase.solution_summary }}</p>
                    </template>
                    <div v-else-if="isLoadingCases" class="skeleton-shimmer mt-2 h-3 w-full rounded bg-slate-100"></div>
                    <p v-else class="mt-1.5 text-[11px] font-semibold text-slate-400">เรื่องที่ปิดงานแล้วจะโผล่ที่นี่</p>
                  </div>

                  <!-- Bottom nav -->
                  <div class="mt-3 flex items-center justify-around border-t border-slate-200 bg-white px-2 py-2.5 text-slate-300">
                    <span class="rounded-xl bg-slate-100 px-3 py-1 text-[13px] text-slate-800"><i class="bi bi-house-fill"></i></span>
                    <span class="text-[13px]"><i class="bi bi-grid"></i></span>
                    <span class="text-[13px]"><i class="bi bi-chat-dots"></i></span>
                    <span class="text-[13px]"><i class="bi bi-person"></i></span>
                  </div>
                </div>
              </div>

              <!-- Floating cards -->
              <div class="animate-float absolute -left-4 -top-3 z-30 flex items-center gap-2 rounded-xl border border-slate-200/80 bg-white/90 px-3.5 py-2.5 text-xs font-bold text-slate-700 shadow-lg backdrop-blur">
                <span class="flex h-7 w-7 items-center justify-center rounded-lg bg-slate-100 text-slate-600"><i class="bi bi-inbox-fill"></i></span>
                <template v-if="!isLoadingStats && stats">
                  เรื่องเข้าสู่ระบบ {{ numberFmt.format(stats.total_issues) }}
                </template>
                <div v-else class="skeleton-shimmer h-4 w-20 rounded bg-slate-100"></div>
              </div>
              <div class="animate-float animation-delay-1500 absolute -bottom-4 -right-3 z-30 flex items-center gap-2 rounded-xl border border-slate-200/80 bg-white/90 px-3.5 py-2.5 text-xs font-bold text-slate-700 shadow-lg backdrop-blur">
                <span class="flex h-7 w-7 items-center justify-center rounded-lg bg-rose-50 text-rose-600"><i class="bi bi-patch-check-fill"></i></span>
                <template v-if="!isLoadingStats && stats">
                  {{ numberFmt.format(stats.active_votes) }} เสียงบน PIRI Vote
                </template>
                <div v-else class="skeleton-shimmer h-4 w-20 rounded bg-slate-100"></div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- 📣 =============================================== -->
      <!-- 3. GLASSMORPHISM ANNOUNCEMENT TICKER              -->
      <!-- 📣 =============================================== -->
      <div id="announce" class="relative z-10 mx-auto max-w-7xl scroll-mt-20 px-4 lg:px-8">
        <div v-if="isLoadingAnnouncements" class="skeleton-shimmer h-14 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"></div>

        <div v-else-if="hasAnnouncementsError" class="flex h-14 items-center justify-between rounded-2xl border border-slate-200 bg-slate-50 px-4 shadow-sm">
          <span class="inline-flex items-center gap-2 text-sm font-semibold text-slate-500">
            <i class="bi bi-exclamation-triangle-fill"></i>
            ไม่สามารถโหลดประกาศได้
          </span>
          <button @click="fetchAnnouncements" class="inline-flex min-h-[34px] items-center gap-1.5 rounded-lg bg-white px-3.5 py-2 text-xs font-bold text-slate-600 shadow-sm transition hover:bg-slate-100">
            <i class="bi bi-arrow-clockwise"></i>
            ลองใหม่
          </button>
        </div>

        <div v-else-if="announcements.length > 0" class="relative overflow-hidden rounded-2xl border border-slate-200/80 bg-white/90 shadow-sm backdrop-blur-xl">
          <div class="flex h-14 items-center px-3">
            <span class="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-slate-900 px-3 py-1 text-[11px] font-black uppercase tracking-wide text-white shadow-sm">
              <i class="bi bi-megaphone-fill"></i>
              ประกาศ
            </span>
            <span v-if="hasUrgent" class="ml-2 inline-flex shrink-0 items-center gap-1 rounded-full border border-rose-200 bg-rose-50 px-2.5 py-1 text-[10px] font-black uppercase tracking-wide text-rose-600">
              <i class="bi bi-exclamation-circle-fill text-[11px]"></i>
              สำคัญ
            </span>

            <div class="marquee ml-3 min-w-0 flex-1 overflow-hidden">
              <div class="marquee-track" :style="{ animationDuration: marqueeDuration }">
                <div v-for="copy in 2" :key="copy" class="flex shrink-0 items-center" :aria-hidden="copy === 2 ? 'true' : 'false'">
                  <template v-for="a in announcements" :key="a.id">
                    <a v-if="a.link" :href="a.link" target="_blank" rel="noopener noreferrer" :tabindex="copy === 2 ? -1 : undefined" :aria-hidden="copy === 2 ? 'true' : undefined" class="inline-flex items-center whitespace-nowrap px-4 text-sm font-semibold text-slate-600 transition-colors hover:text-slate-900">
                      <span :class="['h-1.5 w-1.5 shrink-0 rounded-full', priorityDotCls(a.priority)]"></span>
                      <span class="ml-2">{{ a.message }}</span>
                      <i class="bi bi-box-arrow-up-right ml-1.5 text-[10px] text-slate-400"></i>
                    </a>
                    <span v-else class="inline-flex items-center whitespace-nowrap px-4 text-sm font-semibold text-slate-600">
                      <span :class="['h-1.5 w-1.5 shrink-0 rounded-full', priorityDotCls(a.priority)]"></span>
                      <span class="ml-2">{{ a.message }}</span>
                    </span>
                  </template>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 📊 =============================================== -->
      <!-- 4. LIVE STATISTICS — BENTO GRID (#stats)          -->
      <!-- 📊 =============================================== -->
      <section id="stats" class="relative scroll-mt-20 py-20 lg:py-28">
        <div class="mx-auto max-w-7xl px-4 lg:px-8">
          <!-- Header -->
          <div class="mx-auto max-w-2xl text-center">
            <span class="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3.5 py-1.5 text-xs font-black uppercase tracking-wider text-slate-600 shadow-sm">
              <span class="relative flex h-2 w-2">
                <span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75"></span>
                <span class="relative inline-flex h-2 w-2 rounded-full bg-emerald-500"></span>
              </span>
              Live · Real-time
            </span>
            <h2 class="mt-4 text-3xl font-black tracking-tight text-slate-900 sm:text-4xl">
              ระบบกำลังขยับ — ดูข้อมูลแบบเรียลไทม์
            </h2>
            <p class="mt-4 font-medium leading-relaxed text-slate-500">
              ตัวเลขทุกจุดมาจากระบบจริง อัปเดตต่อเนื่อง
              เพื่อให้เห็นว่าเสียงของเพื่อนๆ กำลังถูกดำเนินการอย่างโปร่งใส
            </p>
          </div>

          <!-- Bento Grid -->
          <div class="mt-12">
            <!-- Skeleton -->
            <div v-if="isLoadingStats" class="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
              <div class="skeleton-shimmer relative h-72 overflow-hidden rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:col-span-2 lg:col-span-2 lg:row-span-2">
                <div class="h-8 w-40 rounded-lg bg-slate-200"></div>
                <div class="mt-6 h-14 w-32 rounded-xl bg-slate-200"></div>
                <div class="mt-8 h-24 w-full rounded-2xl bg-slate-100"></div>
              </div>
              <div v-for="i in 4" :key="i" class="skeleton-shimmer h-40 overflow-hidden rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
                <div class="h-10 w-10 rounded-xl bg-slate-100"></div>
                <div class="mt-4 h-4 w-28 rounded-lg bg-slate-200"></div>
                <div class="mt-2 h-8 w-16 rounded-lg bg-slate-200"></div>
              </div>
              <div class="skeleton-shimmer h-40 overflow-hidden rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:col-span-2 lg:col-span-3">
                <div class="h-10 w-10 rounded-xl bg-slate-100"></div>
                <div class="mt-4 h-4 w-28 rounded-lg bg-slate-200"></div>
                <div class="mt-2 h-8 w-16 rounded-lg bg-slate-200"></div>
              </div>
            </div>

            <!-- Error -->
            <div v-else-if="hasStatsError && !stats" class="rounded-3xl border border-slate-200 bg-white p-10 text-center shadow-sm">
              <div class="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-100 text-slate-500">
                <i class="bi bi-wifi-off text-2xl"></i>
              </div>
              <h3 class="mt-4 text-base font-bold text-slate-800">ไม่สามารถโหลดสถิติได้</h3>
              <p class="mt-1 text-sm text-slate-500">กรุณาตรวจสอบการเชื่อมต่อ หรือลองอีกครั้ง</p>
              <button
                @click="fetchStats"
                class="mt-5 inline-flex items-center gap-2 rounded-xl bg-slate-900 px-5 py-2.5 text-sm font-bold text-white shadow-sm transition hover:bg-slate-800"
              >
                <i class="bi bi-arrow-clockwise"></i>
                ลองใหม่
              </button>
            </div>

            <!-- Bento จริง -->
            <div v-else ref="statsGridRef" class="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
              <!-- 🎯 การ์ดหลัก -->
              <div
                class="bento-glow group relative col-span-1 row-span-2 flex flex-col overflow-hidden rounded-3xl bg-slate-900 p-7 text-white shadow-xl sm:col-span-2 lg:col-span-2"
                @mousemove="onCardGlow"
              >
                <div class="bg-grid-dark pointer-events-none absolute inset-0 opacity-20"></div>

                <div class="relative flex items-center justify-between">
                  <span class="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] font-black uppercase tracking-wider text-slate-300 backdrop-blur">
                    <span class="relative flex h-1.5 w-1.5">
                      <span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75"></span>
                      <span class="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-400"></span>
                    </span>
                    Live ข้อมูลจริง
                  </span>
                  <i class="bi bi-activity text-xl text-slate-500 transition-transform duration-300 group-hover:scale-125"></i>
                </div>

                <p class="relative mt-6 text-sm font-medium text-slate-400">เรื่องที่เข้าสู่ระบบแล้ว</p>
                <p class="relative mt-1 text-5xl font-black tabular-nums tracking-tight sm:text-6xl">
                  <span :data-target="heroStat" data-decimals="0">{{ formatStatValue(heroStat, 0) }}</span>
                </p>
                <p class="relative mt-2 text-xs font-medium text-slate-500">สะสมตั้งแต่เปิดระบบ · ทุกเสียงถูกบันทึก</p>

                <!-- Sparkline -->
                <div class="relative mt-auto pt-5">
                  <template v-if="!isLoadingTrend && sparkTrend && sparkDot">
                    <div class="relative">
                      <svg viewBox="0 0 320 84" class="h-24 w-full" preserveAspectRatio="none" aria-hidden="true">
                        <polygon :points="sparkTrend.area" fill="url(#sparkFill)" opacity="0.15"></polygon>
                        <polyline :points="sparkTrend.line" fill="none" stroke="#e11d48" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke"></polyline>
                        <defs>
                          <linearGradient id="sparkFill" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stop-color="#e11d48" stop-opacity="0.8"></stop>
                            <stop offset="100%" stop-color="#e11d48" stop-opacity="0"></stop>
                          </linearGradient>
                        </defs>
                      </svg>
                      <span
                        class="absolute h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-white shadow ring-2 ring-rose-600"
                        :style="{ left: sparkDot.left + '%', top: sparkDot.top + '%' }"
                      ></span>
                    </div>
                    <span class="sr-only">แนวโน้มย้อนหลัง {{ sparkTrend.days }} วัน มีเรื่องเข้าสู่ระบบรวม {{ sparkTrend.total }} เรื่อง</span>
                  </template>
                  <div v-else-if="isLoadingTrend" class="skeleton-shimmer h-24 w-full rounded-2xl bg-white/5"></div>
                  <div v-else class="flex h-24 items-center justify-center rounded-2xl border border-dashed border-white/10 text-xs font-medium text-slate-500">
                    <i class="bi bi-graph-down mr-1.5"></i>
                    ไม่มีข้อมูลแนวโน้ม
                  </div>
                </div>
              </div>

              <!-- การ์ดย่อย -->
              <div
                v-for="card in smallStats.slice(0, 4)"
                :key="card.key"
                class="bento-glow group relative overflow-hidden rounded-3xl border border-slate-200 bg-white p-6 shadow-sm transition-all duration-300 hover:-translate-y-1 hover:border-slate-300 hover:shadow-md"
                @mousemove="onCardGlow"
              >
                <div
                  class="flex h-11 w-11 items-center justify-center rounded-xl border text-xl transition-transform duration-300 group-hover:-translate-y-0.5 group-hover:scale-110 group-hover:rotate-3"
                  :class="card.iconCls"
                >
                  <i :class="['bi', card.icon]"></i>
                </div>
                <p class="mt-4 text-sm font-medium text-slate-500">{{ card.label }}</p>
                <p class="mt-1 text-3xl font-black tabular-nums tracking-tight text-slate-900">
                  <span :data-target="card.target" :data-decimals="card.decimals">{{ formatStatValue(card.target, card.decimals) }}</span>
                  <span v-if="card.suffix" class="text-xl font-bold text-slate-400">{{ card.suffix }}</span>
                </p>
                <p class="mt-1.5 text-xs font-medium text-slate-400">{{ card.hint }}</p>
              </div>

              <!-- การ์ด PIRI Vote -->
              <div
                class="bento-glow group relative overflow-hidden rounded-3xl border border-slate-200 bg-white p-6 shadow-sm transition-all duration-300 hover:-translate-y-1 hover:border-slate-300 hover:shadow-md"
                @mousemove="onCardGlow"
              >
                <div
                  class="flex h-11 w-11 items-center justify-center rounded-xl border text-xl transition-transform duration-300 group-hover:-translate-y-0.5 group-hover:scale-110 group-hover:rotate-3"
                  :class="smallStats[4]?.iconCls"
                >
                  <i :class="['bi', smallStats[4]?.icon]"></i>
                </div>
                <p class="mt-4 text-sm font-medium text-slate-500">{{ smallStats[4]?.label }}</p>
                <p class="mt-1 text-3xl font-black tabular-nums tracking-tight text-slate-900">
                  <span :data-target="smallStats[4]?.target ?? 0" data-decimals="0">{{ formatStatValue(smallStats[4]?.target ?? 0, 0) }}</span>
                </p>
                <p class="mt-1.5 text-xs font-medium text-slate-400">{{ smallStats[4]?.hint }}</p>
              </div>

              <!-- การ์ด CTA -->
              <div
                class="bento-glow group relative flex flex-col items-stretch gap-4 overflow-hidden rounded-3xl border border-slate-200 bg-white p-6 shadow-sm transition-all duration-300 hover:-translate-y-1 hover:border-slate-300 hover:shadow-md sm:col-span-2 sm:flex-row sm:items-center sm:justify-between lg:col-span-3"
                @mousemove="onCardGlow"
              >
                <div class="relative">
                  <h3 class="text-base font-black text-slate-900">อยากเห็นตัวเลขเหล่านี้ขยับขึ้นอีกไหม?</h3>
                  <p class="mt-1 text-sm font-medium text-slate-500">
                    ทุกเรื่องราวที่ส่งเข้ามา คือข้อมูลที่ช่วยให้โรงเรียนตัดสินใจได้ตรงจุด
                  </p>
                </div>
                <button
                  @click="goLogin"
                  class="relative inline-flex shrink-0 items-center justify-center gap-2 rounded-xl bg-slate-900 px-6 py-3 text-sm font-bold text-white shadow-sm transition-all duration-300 hover:bg-slate-800 active:scale-[0.97] sm:w-auto"
                >
                  <i class="bi bi-send-fill"></i>
                  มีส่วนร่วมตอนนี้
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- 🪜 =============================================== -->
      <!-- 5. SMART WORKFLOW — พีระมิดจริง (#flow)           -->
      <!-- 🪜 =============================================== -->
      <section id="flow" class="relative scroll-mt-20 overflow-hidden border-t border-slate-200/80 bg-white py-20 lg:py-28">
        <div class="relative mx-auto max-w-7xl px-4 lg:px-8">
          <div class="mx-auto max-w-2xl text-center">
            <span class="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3.5 py-1.5 text-xs font-black uppercase tracking-wider text-slate-600 shadow-sm">
              <i class="bi bi-arrow-up-short"></i>
              Smart Workflow
            </span>
            <h2 class="mt-4 text-3xl font-black tracking-tight text-slate-900 sm:text-4xl">
              ระบบไต่ระดับสายงานอัจฉริยะ
            </h2>
            <p class="mt-4 font-medium leading-relaxed text-slate-500">
              ทุกเรื่องมีเจ้าของงานที่ชัดเจน และพร้อมไต่ระดับขึ้นไปเองเมื่อเกินขอบเขตอำนาจ
              จากหัวหน้าห้อง สู่สภานักเรียน — เพื่อให้มั่นใจว่าไม่มีเสียงไหนถูกทิ้งไว้
            </p>
          </div>

          <div class="relative mx-auto mt-16 flex max-w-3xl flex-col items-center gap-3">
            <template v-for="(tier, i) in [...workflowTiers].reverse()" :key="tier.num">
              <div v-if="i > 0" class="flex items-center gap-2 text-[11px] font-bold uppercase tracking-wider text-slate-400">
                <span class="h-px w-10 bg-gradient-to-r from-transparent to-slate-200"></span>
                <i class="bi bi-arrow-up-short text-base"></i>
                ส่งต่อขึ้นไป
                <span class="h-px w-10 bg-gradient-to-l from-transparent to-slate-200"></span>
              </div>

              <div
                class="bento-glow group relative w-full overflow-hidden rounded-2xl border p-5 shadow-sm transition-all duration-300 hover:-translate-y-1 hover:shadow-md sm:p-6"
                :class="[tier.width, tier.ring]"
                @mousemove="onCardGlow"
              >
                <div class="flex items-center gap-4">
                  <div
                    class="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl text-2xl transition-transform duration-300 group-hover:scale-110"
                    :class="tier.iconCls"
                  >
                    <i :class="['bi', tier.icon]"></i>
                  </div>
                  <div class="min-w-0 flex-1">
                    <p class="text-base font-black text-slate-900 sm:text-lg">{{ tier.name }}</p>
                    <p class="mt-1 text-sm font-medium leading-relaxed text-slate-500">{{ tier.desc }}</p>
                  </div>
                  <span class="hidden shrink-0 items-center gap-1 rounded-full border border-slate-200 bg-white/80 px-3 py-1 text-xs font-black text-slate-500 sm:inline-flex">
                    <i class="bi bi-shield-shaded text-[11px]"></i>
                    ระดับ {{ tier.num }}
                  </span>
                </div>
              </div>
            </template>
            <p class="mt-5 inline-flex items-center gap-2 text-sm font-semibold text-slate-400">
              <i class="bi bi-shuffle text-slate-400"></i>
              ถูกออกแบบมาให้มีการส่งต่อขึ้นไปเรื่อยๆ จนกว่าจะมีเจ้าภาพดูแล
            </p>
          </div>
        </div>
      </section>

      <!-- 💥 =============================================== -->
      <!-- 6. THE IMPACT — เคสจริง Before/After (#impact)    -->
      <!-- 💥 =============================================== -->
      <section id="impact" class="relative scroll-mt-20 border-t border-slate-200/80 bg-[#F8FAFC] py-20 lg:py-28">
        <div class="mx-auto max-w-7xl px-4 lg:px-8">
          <div class="mx-auto max-w-2xl text-center">
            <span class="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3.5 py-1.5 text-xs font-black uppercase tracking-wider text-slate-600 shadow-sm">
              <i class="bi bi-stars"></i>
              ผลลัพธ์จริง · The Impact
            </span>
            <h2 class="mt-4 text-3xl font-black tracking-tight text-slate-900 sm:text-4xl">
              เสียงหนึ่งเสียง ที่กลายเป็น
              <span class="text-rose-600">การเปลี่ยนแปลงจริง</span>
            </h2>
            <p class="mt-4 font-medium leading-relaxed text-slate-500">
              ไม่ใช่แค่รับเรื่องแล้วหายเงียบ — นี่คือตัวอย่างผลลัพธ์ที่เกิดขึ้นจริงจากการมีส่วนร่วมของทุกคน
            </p>
          </div>

          <div class="mt-12">
            <div v-if="isLoadingCases" class="grid gap-5 lg:grid-cols-3">
              <div class="skeleton-shimmer h-[380px] overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm lg:col-span-2"></div>
              <div class="skeleton-shimmer h-[380px] overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm"></div>
            </div>

            <div v-else-if="hasCasesError && resolvedCases.length === 0" class="rounded-3xl border border-slate-200 bg-white p-10 text-center shadow-sm">
              <div class="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-100 text-slate-500">
                <i class="bi bi-wifi-off text-2xl"></i>
              </div>
              <h3 class="mt-4 text-base font-bold text-slate-800">ไม่สามารถโหลดผลลัพธ์ได้</h3>
              <p class="mt-1 text-sm text-slate-500">กรุณาตรวจสอบการเชื่อมต่อ หรือลองอีกครั้ง</p>
              <button @click="fetchResolvedCases" class="mt-5 inline-flex items-center gap-2 rounded-xl bg-slate-900 px-5 py-2.5 text-sm font-bold text-white shadow-sm transition hover:bg-slate-800">
                <i class="bi bi-arrow-clockwise"></i> ลองใหม่
              </button>
            </div>

            <div v-else-if="!featuredCase" class="rounded-3xl border border-slate-200 bg-white p-10 text-center shadow-sm">
              <div class="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-100 text-slate-500">
                <i class="bi bi-lightbulb text-2xl"></i>
              </div>
              <h3 class="mt-4 text-base font-bold text-slate-800">เรื่องแรกที่ถูกปิดจะโผล่ตรงนี้</h3>
              <p class="mt-1 text-sm text-slate-500">ระบบกำลังทำงานอย่างเต็มที่ — รอชมผลลัพธ์จริงได้เลย</p>
            </div>

            <div v-else class="grid gap-5 lg:grid-cols-3">
              <!-- การ์ดใหญ่: Before/After -->
              <div class="bento-glow relative overflow-hidden rounded-3xl border border-slate-200 bg-white p-7 shadow-sm transition-all duration-300 hover:shadow-md lg:col-span-2" @mousemove="onCardGlow">
                <div class="flex flex-wrap items-center justify-between gap-3">
                  <span class="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-bold text-slate-600">
                    <i class="bi bi-tag-fill text-[10px]"></i>
                    {{ featuredCase.category }}
                  </span>
                  <span class="inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-bold" :class="impactLabel(featuredCase.impact_score).cls">
                    <i class="bi bi-fire"></i>
                    {{ impactLabel(featuredCase.impact_score).label }}
                  </span>
                </div>

                <div class="mt-6 flex gap-4">
                  <span class="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-500"><i class="bi bi-chat-text-fill"></i></span>
                  <div>
                    <p class="text-[11px] font-black uppercase tracking-wider text-slate-500">Before · เรื่องที่ถูกส่งเข้ามา</p>
                    <h3 class="mt-1 text-xl font-black leading-snug text-slate-900 sm:text-2xl">{{ featuredCase.title }}</h3>
                    <p class="mt-1.5 text-sm font-medium text-slate-500">
                      แจ้งโดย {{ featuredCase.reporter_mask }} · เมื่อ {{ formatThaiDate(featuredCase.resolved_at) }}
                    </p>
                  </div>
                </div>

                <div class="my-5 flex items-center gap-3 pl-12">
                  <span class="h-px flex-1 bg-gradient-to-r from-slate-200 to-emerald-200"></span>
                  <span class="flex h-8 w-8 items-center justify-center rounded-full bg-emerald-100 text-emerald-600"><i class="bi bi-arrow-down-short text-lg"></i></span>
                  <span class="h-px flex-1 bg-emerald-200"></span>
                </div>

                <div class="flex gap-4">
                  <span class="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600"><i class="bi bi-check-circle-fill"></i></span>
                  <div>
                    <p class="text-[11px] font-black uppercase tracking-wider text-emerald-600">After · ผลลัพธ์ที่เกิดขึ้นจริง</p>
                    <p class="mt-1.5 rounded-2xl border border-emerald-100 bg-emerald-50/50 p-4 text-base font-medium leading-relaxed text-slate-800">
                      {{ featuredCase.solution_summary }}
                    </p>
                    <p class="mt-2 text-xs font-medium text-slate-500">
                      บันทึกการแก้ไขจากทีมงาน {{ featuredCase.department_in_charge }}
                    </p>
                  </div>
                </div>

                <div class="mt-6 flex flex-wrap items-center gap-x-6 gap-y-2 border-t border-slate-100 pt-4 text-sm font-semibold text-slate-500">
                  <span class="inline-flex items-center gap-1.5"><i class="bi bi-building text-slate-400"></i> หน่วยงานรับผิดชอบ: {{ featuredCase.department_in_charge }}</span>
                  <span v-if="featuredCase.duration_hours != null" class="inline-flex items-center gap-1.5"><i class="bi bi-stopwatch text-slate-400"></i> ใช้เวลา {{ formatDuration(featuredCase.duration_hours) }}</span>
                </div>
              </div>

              <!-- คอลัมน์ขวา: เรื่องที่เพิ่งปิด -->
              <div class="flex flex-col gap-4">
                <h3 class="text-sm font-black uppercase tracking-wider text-slate-400">
                  <i class="bi bi-check2-all mr-1.5 text-slate-400"></i>
                  เรื่องที่เพิ่งดำเนินการสำเร็จ
                </h3>

                <template v-if="recentCases.length">
                  <div
                    v-for="c in recentCases"
                    :key="c.id"
                    class="group relative overflow-hidden rounded-2xl border border-slate-200 bg-white p-4 shadow-sm transition-all duration-300 hover:-translate-y-0.5 hover:shadow-md"
                  >
                    <div class="flex items-start gap-3">
                      <span class="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-100 text-[10px] font-black text-slate-600">{{ reporterInitial(c.reporter_mask) }}</span>
                      <div class="min-w-0 flex-1">
                        <p class="line-clamp-2 text-sm font-bold leading-snug text-slate-800">{{ c.title }}</p>
                        <p class="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px] font-medium text-slate-500">
                          <span>{{ c.category }}</span>
                          <span class="h-0.5 w-0.5 rounded-full bg-slate-300"></span>
                          <span>{{ c.reporter_mask }}</span>
                        </p>
                      </div>
                      <i class="bi bi-check-circle-fill mt-1 shrink-0 text-emerald-500"></i>
                    </div>
                  </div>
                </template>
                <div v-else class="flex h-full min-h-[140px] flex-col items-center justify-center gap-2 rounded-2xl border border-dashed border-slate-200 bg-white/60 p-6 text-center">
                  <i class="bi bi-inbox text-2xl text-slate-300"></i>
                  <p class="text-sm font-medium text-slate-500">ยังไม่มีเรื่องที่เพิ่งปิด — รอได้เลย</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- 🚀 =============================================== -->
      <!-- 7. ECOSYSTEM (Dark Mode Clean)                     -->
      <!-- 🚀 =============================================== -->
      <section id="ecosystem" class="relative scroll-mt-20 overflow-hidden bg-slate-900 py-20 text-white lg:py-28">
        <div class="bg-grid-dark pointer-events-none absolute inset-0 opacity-40"></div>

        <div class="relative mx-auto grid max-w-7xl grid-cols-1 items-center gap-16 px-4 lg:grid-cols-2 lg:gap-20 lg:px-8">
          <!-- ฝั่งซ้าย: คำอธิบาย -->
          <div>
            <span class="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/5 px-3.5 py-1.5 text-xs font-black uppercase tracking-wider text-slate-300 backdrop-blur">
              <i class="bi bi-asterisk"></i>
              PIRI Ecosystem
            </span>
            <h2 class="mt-5 text-3xl font-black leading-tight tracking-tight sm:text-4xl">
              มากกว่าแค่ “แจ้งเรื่อง”
              <br />
              <span class="text-white opacity-90">
                ขับเคลื่อนด้วยเสียงของทุกคน
              </span>
            </h2>
            <p class="mt-5 max-w-lg font-medium leading-relaxed text-slate-400">
              PIRIvoice ไม่ใช่แค่ระบบรับแจ้งเรื่อง — คือระบบนิเวศที่เปิดพื้นที่ให้ทุกคนมีส่วนร่วม ทั้งเสนอ วิพากษ์ และตัดสินใจร่วมกันบนข้อมูลที่โปร่งใส
            </p>

            <!-- PIRI Talk -->
            <div class="bento-glow group mt-8 flex gap-4 rounded-2xl border border-white/10 bg-white/5 p-5 backdrop-blur transition-all duration-300 hover:bg-white/10" @mousemove="onCardGlow">
              <div class="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-white/5 text-xl text-slate-300 transition-transform duration-300 group-hover:scale-110">
                <i class="bi bi-chat-dots-fill"></i>
              </div>
              <div>
                <h3 class="flex flex-wrap items-center gap-2 text-base font-bold">
                  PIRI Talk
                  <span class="rounded-full border border-white/10 bg-white/10 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-slate-300">กระดานสนทนาสาธารณะ</span>
                </h3>
                <p class="mt-1.5 text-sm font-medium leading-relaxed text-slate-400">
                  พื้นที่พูดคุย แลกเปลี่ยนความเห็นอย่างอิสระ ทีมสภานักเรียนคอยดูแลเพื่อสร้างพื้นที่ปลอดภัยและสร้างสรรค์
                </p>
              </div>
            </div>

            <!-- PIRI Vote -->
            <div class="bento-glow group mt-4 flex gap-4 rounded-2xl border border-white/10 bg-white/5 p-5 backdrop-blur transition-all duration-300 hover:bg-white/10" @mousemove="onCardGlow">
              <div class="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-white/5 text-xl text-slate-300 transition-transform duration-300 group-hover:scale-110">
                <i class="bi bi-patch-check-fill"></i>
              </div>
              <div>
                <h3 class="flex flex-wrap items-center gap-2 text-base font-bold">
                  PIRI Vote
                  <span class="rounded-full border border-white/10 bg-white/10 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-slate-300">ระบบฉันทามติ</span>
                </h3>
                <p class="mt-1.5 text-sm font-medium leading-relaxed text-slate-400">
                  ลงคะแนนเสียงสนับสนุนประเด็นที่เห็นด้วย เพื่อสะท้อนข้อมูลที่เป็นฉันทามติ นำไปสู่การตัดสินใจที่โปร่งใส
                </p>
              </div>
            </div>
          </div>

          <!-- ฝั่งขวา: Mockup Dashboard Isometric (Clean) -->
          <div class="relative mx-auto w-full max-w-[520px]">
            <div class="tilt-shadow pointer-events-none absolute -bottom-8 left-1/2 h-10 w-72 -translate-x-1/2 rounded-[100%] bg-black/50 blur-xl"></div>

            <div class="mockup-tilt pointer-events-none relative select-none" aria-hidden="true">
              <div class="relative overflow-hidden rounded-2xl border border-white/10 bg-slate-800 shadow-2xl backdrop-blur-xl">
                <!-- Title bar -->
                <div class="flex items-center gap-2 border-b border-white/10 bg-slate-900/50 px-4 py-3">
                  <span class="h-3 w-3 rounded-full bg-slate-600"></span>
                  <span class="h-3 w-3 rounded-full bg-slate-600"></span>
                  <span class="h-3 w-3 rounded-full bg-slate-600"></span>
                  <span class="ml-3 inline-flex items-center gap-1.5 text-[11px] font-semibold text-slate-400">
                    <i class="bi bi-graph-up text-slate-300"></i>
                    PIRIvoice Console
                  </span>
                  <span class="ml-auto inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-black text-emerald-400">
                    <span class="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400"></span>
                    LIVE
                  </span>
                </div>

                <div class="flex">
                  <!-- Sidebar -->
                  <div class="hidden flex-col gap-3 border-r border-white/10 p-3 sm:flex">
                    <span class="flex h-9 w-9 items-center justify-center rounded-xl border border-white/10 bg-white/5 text-sm text-white"><i class="bi bi-grid-1x2"></i></span>
                    <span class="flex h-9 w-9 items-center justify-center rounded-xl text-sm text-slate-500"><i class="bi bi-inbox"></i></span>
                    <span class="flex h-9 w-9 items-center justify-center rounded-xl text-sm text-slate-500"><i class="bi bi-bar-chart"></i></span>
                    <span class="flex h-9 w-9 items-center justify-center rounded-xl text-sm text-slate-500"><i class="bi bi-people"></i></span>
                    <span class="flex h-9 w-9 items-center justify-center rounded-xl text-sm text-slate-500"><i class="bi bi-gear"></i></span>
                  </div>

                  <!-- Main -->
                  <div class="flex-1 p-4 sm:p-5">
                    <!-- Stat chips -->
                    <div class="grid grid-cols-3 gap-2">
                      <div class="rounded-xl border border-white/10 bg-white/5 p-2.5">
                        <p class="text-[10px] font-semibold text-slate-400">เรื่องที่เข้าสู่ระบบ</p>
                        <template v-if="!isLoadingStats && stats">
                          <p class="mt-0.5 text-base font-black tabular-nums text-white">{{ numberFmt.format(stats.total_issues) }}</p>
                        </template>
                        <div v-else class="skeleton-shimmer mt-1 h-4 w-8 rounded bg-white/10"></div>
                      </div>
                      <div class="rounded-xl border border-white/10 bg-white/5 p-2.5">
                        <p class="text-[10px] font-semibold text-slate-400">กำลังดำเนินการ</p>
                        <template v-if="!isLoadingStats && stats">
                          <p class="mt-0.5 text-base font-black tabular-nums text-white">{{ numberFmt.format(stats.routed_issues) }}</p>
                        </template>
                        <div v-else class="skeleton-shimmer mt-1 h-4 w-8 rounded bg-white/10"></div>
                      </div>
                      <div class="rounded-xl border border-white/10 bg-white/5 p-2.5">
                        <p class="text-[10px] font-semibold text-slate-400">ปิดสำเร็จแล้ว</p>
                        <template v-if="!isLoadingStats && stats">
                          <p class="mt-0.5 text-base font-black tabular-nums text-emerald-400">{{ numberFmt.format(stats.resolved_issues) }}</p>
                        </template>
                        <div v-else class="skeleton-shimmer mt-1 h-4 w-8 rounded bg-white/10"></div>
                      </div>
                    </div>

                    <!-- Chart -->
                    <div class="mt-3 rounded-xl border border-white/10 bg-white/5 p-3">
                      <div class="flex items-center justify-between text-[11px] font-semibold text-slate-400">
                        <span class="inline-flex items-center gap-1.5"><i class="bi bi-activity text-slate-300"></i> เรื่องที่เข้าสู่ระบบ (14 วัน)</span>
                        <template v-if="sparkTrend">
                          <span class="inline-flex items-center gap-1 text-slate-300"><i class="bi bi-lightning-charge-fill"></i> {{ sparkTrend.total }} เรื่อง</span>
                        </template>
                      </div>
                      <div v-if="!isLoadingTrend && sparkTrend && sparkDot" class="relative mt-3 h-24 w-full">
                        <svg viewBox="0 0 320 84" class="h-24 w-full" preserveAspectRatio="none" aria-hidden="true">
                          <polygon :points="sparkTrend.area" fill="url(#sparkFillDark)" opacity="0.3"></polygon>
                          <polyline :points="sparkTrend.line" fill="none" stroke="#e2e8f0" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke"></polyline>
                          <defs>
                            <linearGradient id="sparkFillDark" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="0%" stop-color="#e2e8f0" stop-opacity="0.3"></stop>
                              <stop offset="100%" stop-color="#e2e8f0" stop-opacity="0"></stop>
                            </linearGradient>
                          </defs>
                        </svg>
                        <span class="absolute h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-white shadow" :style="{ left: sparkDot.left + '%', top: sparkDot.top + '%' }"></span>
                      </div>
                      <div v-else-if="isLoadingTrend" class="skeleton-shimmer mt-3 h-24 w-full rounded-lg bg-white/5"></div>
                      <div v-else class="mt-3 flex h-24 items-center justify-center rounded-lg border border-dashed border-white/10 text-[11px] text-slate-500">
                        ยังไม่มีข้อมูลแนวโน้ม
                      </div>
                    </div>

                    <div class="mt-3 flex items-center justify-between rounded-xl border border-white/10 bg-white/5 p-3">
                      <div class="flex items-center gap-2.5">
                        <span class="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-400"><i class="bi bi-check2"></i></span>
                        <div>
                          <p class="text-[11px] font-bold text-slate-300">เรื่องที่ถูกจัดการแล้ว</p>
                          <template v-if="!isLoadingCases && latestCase">
                            <p class="line-clamp-1 text-[10px] text-slate-500">{{ latestCase.title }}</p>
                          </template>
                          <p v-else class="text-[10px] text-slate-500">รอข้อมูลจากระบบ…</p>
                        </div>
                      </div>
                      <i class="bi bi-chevron-right text-slate-500"></i>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Floating cards -->
              <div class="animate-float absolute -right-3 -top-5 z-30 flex items-center gap-2 rounded-xl border border-white/10 bg-slate-900 px-3.5 py-2.5 text-xs font-bold text-white shadow-xl backdrop-blur">
                <span class="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-500/15 text-emerald-400"><i class="bi bi-check-circle-fill"></i></span>
                <template v-if="!isLoadingStats && stats">
                  {{ numberFmt.format(stats.resolved_issues) }} เรื่องที่ปิดสำเร็จ
                </template>
                <div v-else class="skeleton-shimmer h-4 w-20 rounded bg-slate-700"></div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- 🎬 =============================================== -->
      <!-- 8. CTA BAND — ปิดท้ายเชิญชวน                       -->
      <!-- 🎬 =============================================== -->
      <section class="relative overflow-hidden py-20 lg:py-24 bg-white">
        <div class="mx-auto max-w-5xl px-4 lg:px-8">
          <div class="relative overflow-hidden rounded-[2.5rem] bg-slate-900 px-6 py-16 text-center text-white shadow-xl sm:px-12">
            <!-- ตกแต่ง -->
            <div class="bg-grid-dark pointer-events-none absolute inset-0 opacity-40"></div>
            <div class="pointer-events-none absolute -left-20 -top-20 h-64 w-64 rounded-full bg-white/5 blur-3xl"></div>

            <div class="relative">
              <span class="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-1.5 text-xs font-black uppercase tracking-wider backdrop-blur">
                <i class="bi bi-stars text-slate-300"></i>
                ร่วมเป็นส่วนหนึ่งของการเปลี่ยนแปลง
              </span>
              <h2 class="mx-auto mt-6 max-w-3xl text-3xl font-black leading-tight tracking-tight sm:text-5xl">
                ทุกเสียงมีความหมาย
                <br class="hidden sm:block" />
                ทุกเสียงพาพิริลัย ก้าวไปด้วยกัน
              </h2>
              <p class="mx-auto mt-6 max-w-xl font-medium leading-relaxed text-slate-400">
                ส่งต่อเรื่องราวหรือข้อเสนอแนะของคุณได้ใน 1 นาที เข้าสู่ระบบด้วยบัญชีโรงเรียน 
                คุณสามารถเลือกที่จะไม่เปิดเผยตัวตนได้เสมอ แล้วระบบจะส่งต่อเนื้อหาไปยังผู้รับผิดชอบที่ตรงจุด
              </p>
              <div class="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
                <button
                  @click="goLogin"
                  class="group flex w-full items-center justify-center gap-2 rounded-2xl bg-white px-8 py-4 text-base font-black text-slate-900 shadow-md transition-all duration-300 hover:bg-slate-50 hover:shadow-lg active:scale-[0.97] sm:w-auto"
                >
                  <i class="bi bi-send-fill text-lg transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5"></i>
                  เข้าสู่ระบบ · เริ่มแจ้งเรื่อง
                </button>
                <button
                  @click="goStats"
                  class="flex w-full items-center justify-center gap-2 rounded-2xl border border-white/20 bg-white/5 px-8 py-4 text-base font-bold text-white backdrop-blur transition-all duration-300 hover:bg-white/10 active:scale-[0.97] sm:w-auto"
                >
                  <i class="bi bi-bar-chart-line text-lg"></i>
                  สำรวจตัวเลขก่อน
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>
    </main>

    <!-- 🦶 =============================================== -->
    <!-- 9. FOOTER                                          -->
    <!-- 🦶 =============================================== -->
    <footer class="relative border-t border-slate-200 bg-white">
      <div class="mx-auto max-w-7xl px-4 py-12 lg:px-8">
        <div class="flex flex-col items-center gap-4 text-center">
          <div class="flex items-center gap-3">
            <img src="/logos/council-logo.png" alt="โลโก้สภานักเรียน" class="h-12 w-12 object-contain grayscale opacity-70" />
            <div class="h-10 w-px bg-slate-200"></div>
            <img src="/logos/school-logo.png" alt="โลโก้โรงเรียน" class="h-12 w-12 object-contain grayscale opacity-70" />
          </div>
          <div>
            <p class="text-lg font-black tracking-tight text-slate-800">
              PIRI<span class="text-rose-600">voice</span>
            </p>
            <p class="mt-1 text-sm font-semibold text-slate-500">คณะกรรมการสภานักเรียน โรงเรียนพิริยาลัยจังหวัดแพร่</p>
          </div>
        </div>

        <div
          class="mt-10 flex flex-col items-center justify-between gap-4 border-t border-slate-100 pt-6 text-xs font-medium text-slate-400 sm:flex-row"
        >
          <p>© 2026 PIRIvoice · สงวนลิขสิทธิ์</p>
          <a
            href="https://www.singto1597.xyz/"
            target="_blank"
            rel="noopener noreferrer"
            class="group inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-slate-500 transition-colors hover:bg-slate-50 hover:text-slate-900"
          >
            <i class="bi bi-code-slash text-sm opacity-70"></i>
            Core System Architect &amp; Developed by
            <span class="font-bold underline decoration-slate-200 decoration-2 underline-offset-2 group-hover:decoration-slate-400">
              นายพัฒนพล สุธรรม
            </span>
          </a>
        </div>
      </div>
    </footer>
  </div>
</template>

<style scoped>
/* ============================================================
 * Animations
 * ============================================================ */
@keyframes blob {
  0% { transform: translate(0px, 0px) scale(1); }
  33% { transform: translate(30px, -50px) scale(1.05); }
  66% { transform: translate(-20px, 20px) scale(0.95); }
  100% { transform: translate(0px, 0px) scale(1); }
}

@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-12px); }
}

@keyframes marquee {
  from { transform: translateX(0); }
  to { transform: translateX(-50%); }
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slideUpFade {
  from { opacity: 0; transform: translateY(20px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

/* ============================================================
 * Isometric Mockups
 * ============================================================ */
@keyframes floatTilt {
  0%, 100% { transform: rotateX(14deg) rotateY(-16deg) rotateZ(2deg) translateY(0); }
  50% { transform: rotateX(14deg) rotateY(-16deg) rotateZ(2deg) translateY(-14px); }
}
@keyframes shadowSquash {
  0%, 100% { transform: translateX(-50%) scaleX(1); opacity: 0.3; }
  50% { transform: translateX(-50%) scaleX(0.88); opacity: 0.15; }
}
@keyframes floatTiltDark {
  0%, 100% { transform: rotateX(18deg) rotateY(-10deg) translateY(0); }
  50% { transform: rotateX(18deg) rotateY(-10deg) translateY(-12px); }
}

.phone-tilt {
  animation: floatTilt 7s ease-in-out infinite;
}
.mockup-tilt {
  animation: floatTiltDark 8s ease-in-out infinite;
}
.tilt-shadow {
  animation: shadowSquash 7s ease-in-out infinite;
}

/* ============================================================
 * Bento Glow
 * ============================================================ */
.bento-glow {
  position: relative;
}
.bento-glow::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.35s ease;
  background: radial-gradient(340px circle at var(--mx, 50%) var(--my, 50%), rgba(255, 255, 255, 0.1), transparent 45%);
}
.bento-glow:hover::before {
  opacity: 1;
}
/* เปลี่ยน Glow สำหรับ Light Mode */
.bg-white.bento-glow::before {
  background: radial-gradient(340px circle at var(--mx, 50%) var(--my, 50%), rgba(0, 0, 0, 0.03), transparent 45%);
}

.animate-blob { animation: blob 15s infinite alternate ease-in-out; }
.animate-float { animation: float 6s ease-in-out infinite; }
.animation-delay-2000 { animation-delay: 2s; }
.animation-delay-1500 { animation-delay: 1.5s; }
.animate-fade-in { animation: fadeIn 0.8s ease-out forwards; }
.animate-slide-up-fade {
  opacity: 0;
  animation: slideUpFade 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}

/* ============================================================
 * Marquee
 * ============================================================ */
.marquee-track {
  display: flex;
  width: max-content;
  animation: marquee 30s linear infinite;
}
.marquee:hover .marquee-track {
  animation-play-state: paused;
}

/* ============================================================
 * Skeleton
 * ============================================================ */
.skeleton-shimmer {
  position: relative;
  overflow: hidden;
}
.skeleton-shimmer::after {
  content: '';
  position: absolute;
  inset: 0;
  transform: translateX(-100%);
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.6), transparent);
  animation: shimmer 1.8s infinite;
}
@keyframes shimmer {
  100% { transform: translateX(100%); }
}

/* ============================================================
 * Dark sections
 * ============================================================ */
.bg-grid-dark {
  background-image:
    linear-gradient(rgba(148, 163, 184, 0.1) 1px, transparent 1px),
    linear-gradient(90deg, rgba(148, 163, 184, 0.1) 1px, transparent 1px);
  background-size: 44px 44px;
  -webkit-mask-image: radial-gradient(ellipse 80% 70% at 50% 40%, black, transparent);
  mask-image: radial-gradient(ellipse 80% 70% at 50% 40%, black, transparent);
}

/* ============================================================
 * Accessibility
 * ============================================================ */
@media (prefers-reduced-motion: reduce) {
  .animate-blob, .animate-float, .animate-slide-up-fade, .animate-fade-in,
  .phone-tilt, .mockup-tilt, .tilt-shadow, .marquee-track, .animate-ping,
  .animate-spin, .animate-pulse, .skeleton-shimmer::after {
    animation: none !important;
  }
  .phone-tilt, .mockup-tilt { transform: none !important; }
  .tilt-shadow { transform: translateX(-50%) !important; }
  .animate-blob, .animate-float, .animate-slide-up-fade, .animate-fade-in,
  .skeleton-shimmer { opacity: 1 !important; }
}

button:focus-visible, a:focus-visible {
  outline: 2px solid rgba(15, 23, 42, 0.65);
  outline-offset: 2px;
}
</style>