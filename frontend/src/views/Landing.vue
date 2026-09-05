<!-- eslint-disable vue/multi-word-component-names -- ชื่อ Landing ตาม spec (หน้าแรก) -->
<script setup lang="ts">
/**
 * 🏠 Landing.vue — หน้าแรกของ PIRIvoice
 * เสียงจากชาวพิริยาลัย · สภานักเรียน โรงเรียนพิริยาลัยจังหวัดแพร่
 *
 * หลักการ: ไม่มี Mock Data — ทุกข้อมูลดึงจาก Public API ( /api/v1/public/* )
 * ทุก section ที่ใช้ข้อมูลมี Loading Skeleton + Error Handling + Retry
 *
 * v3 (Ultra-Professional / Enterprise SaaS Redesign):
 * - Clean UI/UX: เน้น Whitespace, ลบ Gradient ที่ไม่จำเป็น, ใช้ Solid Colors
 * - Refined Shadows: ใช้เงาซ้อน (Layered Shadows) ให้มิติดูพรีเมียม
 * - Data Visualization: ปรับ Bento Grid และกราฟให้ดูเหมือน Dashboard ระดับโลก
 * - Pipeline Workflow: ออกแบบ UI สายงานใหม่ให้เห็นการเชื่อมต่อ (Connected Nodes)
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
    block: 'start'
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

function formatStatValue(v: number, decimals = 0): string {
  const factor = 10 ** decimals;
  const rounded = Math.round((v ?? 0) * factor) / factor;
  return new Intl.NumberFormat('th-TH', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(rounded);
}

/* ============================================================
 * 🎞️ Count-up & Interactions
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
    const duration = 1200;
    const start = performance.now();
    const step = (now: number) => {
      const p = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - p, 3); // easeOutCubic
      el.textContent = formatStatValue(target * eased, decimals);
      if (p < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  });
}

// Spotlight effect on cards
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
      icon: 'bi-arrow-right-circle',
      label: 'กำลังดำเนินการ',
      target: s.routed_issues,
      decimals: 0,
      iconCls: 'text-amber-500 bg-amber-50 ring-1 ring-amber-100',
    },
    {
      key: 'resolved',
      icon: 'bi-check2-circle',
      label: 'ปิดสำเร็จแล้ว',
      target: s.resolved_issues,
      decimals: 0,
      iconCls: 'text-emerald-500 bg-emerald-50 ring-1 ring-emerald-100',
    },
    {
      key: 'avg',
      icon: 'bi-stopwatch',
      label: 'เวลาเฉลี่ย (ชม.)',
      target: s.avg_resolve_hours,
      decimals: 1,
      iconCls: 'text-blue-500 bg-blue-50 ring-1 ring-blue-100',
    },
    {
      key: 'talk',
      icon: 'bi-chat-dots',
      label: 'PIRI Talk (กระทู้)',
      target: s.active_talk_threads,
      decimals: 0,
      iconCls: 'text-indigo-500 bg-indigo-50 ring-1 ring-indigo-100',
    },
    {
      key: 'votes',
      icon: 'bi-patch-check',
      label: 'PIRI Vote (เสียง)',
      target: s.active_votes,
      decimals: 0,
      iconCls: 'text-rose-500 bg-rose-50 ring-1 ring-rose-100',
    },
  ];
});

/* ============================================================
 * 📈 Sparkline (Enterprise style)
 * ============================================================ */
const SPARK_W = 400;
const SPARK_H = 100;
const SPARK_PAD = 8;

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
const hasUrgent = computed(() => announcements.value.some(a => a.priority === 'urgent'));

function priorityBadge(p: AnnouncementPriority) {
  if (p === 'urgent') return { cls: 'bg-rose-50 text-rose-700 border-rose-200', dot: 'bg-rose-500' };
  if (p === 'high') return { cls: 'bg-amber-50 text-amber-700 border-amber-200', dot: 'bg-amber-500' };
  return { cls: 'bg-slate-50 text-slate-600 border-slate-200', dot: 'bg-slate-400' };
}

const marqueeDuration = computed(() => `${Math.max(20, announcements.value.length * 8)}s`);

/* ============================================================
 * 💡 The Impact
 * ============================================================ */
const featuredCase = computed<ResolvedCase | null>(() => {
  if (resolvedCases.value.length === 0) return null;
  return [...resolvedCases.value].sort((a, b) => b.impact_score - a.impact_score)[0] ?? null;
});
const latestCase = computed<ResolvedCase | null>(() => resolvedCases.value[0] ?? null);
const recentCases = computed<ResolvedCase[]>(() =>
  resolvedCases.value.filter((c) => c.id !== featuredCase.value?.id).slice(0, 3)
);

/* ============================================================
 * 🪜 Static content
 * ============================================================ */
const navLinks = [
  { label: 'แดชบอร์ดสถิติ', id: 'stats' },
  { label: 'ระบบสายงาน', id: 'flow' },
  { label: 'ผลลัพธ์การแก้ไข', id: 'impact' },
  { label: 'PIRI Ecosystem', id: 'ecosystem' },
];

const workflowSteps = [
  {
    title: 'ส่งเรื่องเข้าระบบ',
    desc: 'นักเรียนแจ้งเรื่องราวหรือข้อคิดเห็นผ่านแพลตฟอร์มได้ตลอด 24 ชั่วโมง โดยสามารถเลือกปกปิดตัวตนได้',
    icon: 'bi-send',
  },
  {
    title: 'กลั่นกรองโดยตัวแทนห้อง',
    desc: 'หัวหน้าห้องและรอง 4 ฝ่าย จะเป็นด่านแรกในการรับรู้ปัญหาและจัดการเบื้องต้นภายในห้องเรียน',
    icon: 'bi-filter-circle',
  },
  {
    title: 'ส่งต่อประธานระดับ',
    desc: 'หากเรื่องมีผลกระทบกว้าง หรือเกินอำนาจหัวหน้าห้อง ระบบจะส่งต่อให้ประธานระดับชั้นอัตโนมัติ',
    icon: 'bi-diagram-2',
  },
  {
    title: 'วินิจฉัยโดยสภานักเรียน',
    desc: 'สภานักเรียนจะเข้ามารับช่วงต่อสำหรับวาระสำคัญ เพื่อประสานงานกับคณะครูและติดตามจนจบกระบวนการ',
    icon: 'bi-flag',
  },
];

/* ============================================================
 * 🔄 Lifecycle
 * ============================================================ */
function onWindowScroll() {
  isScrolled.value = window.scrollY > 20;
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
    if (statsGridRef.value) animateStatNumbers(statsGridRef.value);
  });
});
</script>

<template>
  <div class="relative min-h-screen overflow-x-clip bg-slate-50 font-sans text-slate-900 selection:bg-rose-500/20 selection:text-rose-900">
    
    <!-- ⚡ =============================================== -->
    <!-- 1. Enterprise Navbar                             -->
    <!-- ⚡ =============================================== -->
    <header
      class="fixed top-0 left-0 right-0 z-50 transition-all duration-300 border-b"
      :class="isScrolled ? 'bg-white/80 backdrop-blur-xl border-slate-200/80 shadow-[0_1px_3px_0_rgb(0,0,0,0.02)]' : 'bg-transparent border-transparent'"
    >
      <nav class="mx-auto flex h-16 max-w-[88rem] items-center justify-between px-4 sm:px-6 lg:px-8">
        <!-- Logo & Brand -->
        <div class="flex items-center gap-3.5 cursor-pointer" @click="scrollToId('hero')">
          <div class="flex -space-x-1.5">
            <img src="/logos/school-logo.png" alt="" class="h-8 w-8 rounded-[9px] border-2 border-white shadow-sm object-cover bg-white" />
            <img src="/logos/council-logo.png" alt="" class="h-8 w-8 rounded-[9px] border-2 border-white shadow-sm object-cover bg-white" />
          </div>
          <div class="flex flex-col justify-center">
            <span class="text-[17px] font-black tracking-tight text-slate-900 leading-none">
              PIRI<span class="text-rose-600">voice</span>
            </span>
            <span class="text-[9.5px] font-bold tracking-[0.02em] text-slate-400 mt-0.5 uppercase">
              Student Council
            </span>
          </div>
        </div>

        <!-- Desktop Menu -->
        <div class="hidden lg:flex items-center gap-1.5 bg-white/50 backdrop-blur-md border border-slate-200/60 rounded-full px-1.5 py-1.5 shadow-sm">
          <button
            v-for="link in navLinks"
            :key="link.id"
            @click="scrollToId(link.id)"
            class="px-4 py-1.5 text-[13px] font-bold text-slate-600 rounded-full transition-colors hover:text-slate-900 hover:bg-slate-100/80"
          >
            {{ link.label }}
          </button>
        </div>

        <!-- Login CTA -->
        <div class="flex items-center">
          <button
            @click="goLogin"
            class="group inline-flex items-center justify-center gap-2 rounded-xl bg-slate-900 px-4 py-2 text-sm font-bold text-white transition-all hover:bg-slate-800 hover:shadow-md hover:shadow-slate-900/10 active:scale-95"
          >
            เข้าสู่ระบบ
            <i class="bi bi-arrow-right text-[11px] opacity-70 transition-transform group-hover:translate-x-0.5"></i>
          </button>
        </div>
      </nav>
    </header>

    <main class="relative pt-16">
      
      <!-- 🌟 =============================================== -->
      <!-- 2. HERO — Crisp, SaaS Typography Focus           -->
      <!-- 🌟 =============================================== -->
      <section id="hero" class="relative overflow-hidden pt-12 pb-20 lg:pt-24 lg:pb-32">
        <!-- Abstract Clean Background Mesh -->
        <div class="absolute inset-0 pointer-events-none overflow-hidden flex justify-center">
          <div class="absolute -top-40 w-[1200px] h-[600px] bg-gradient-to-b from-rose-100/40 via-slate-100/20 to-transparent rounded-[100%] blur-3xl opacity-80"></div>
          <div class="absolute top-[20%] right-[-10%] w-[600px] h-[600px] bg-blue-50/40 rounded-full blur-3xl opacity-60"></div>
          <!-- Fine Grid overlay -->
          <div class="absolute inset-0 bg-[linear-gradient(to_right,#80808008_1px,transparent_1px),linear-gradient(to_bottom,#80808008_1px,transparent_1px)] bg-[size:32px_32px] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,#000_70%,transparent_100%)]"></div>
        </div>

        <div class="relative mx-auto max-w-[88rem] px-4 sm:px-6 lg:px-8">
          <div class="grid lg:grid-cols-[1.1fr_0.9fr] gap-12 lg:gap-8 items-center">
            
            <!-- Left: Copy -->
            <div class="max-w-2xl mx-auto text-center lg:text-left lg:mx-0">
              
              <!-- Announcement Pill -->
              <div class="animate-slide-up-fade flex justify-center lg:justify-start min-h-[32px]">
                <div v-if="isLoadingAnnouncements" class="skeleton-shimmer h-8 w-48 rounded-full border border-slate-200/60 bg-white"></div>
                <button
                  v-else-if="heroAnnouncement"
                  @click="scrollToId('announce')"
                  class="group inline-flex items-center gap-2 rounded-full border border-slate-200/80 bg-white/60 backdrop-blur-sm py-1 pl-1.5 pr-3 text-[12px] font-semibold text-slate-600 shadow-sm transition-all hover:border-slate-300 hover:bg-white"
                >
                  <span class="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider" :class="priorityBadge(heroAnnouncement.priority).cls">
                    <span class="h-1.5 w-1.5 rounded-full mr-1.5" :class="priorityBadge(heroAnnouncement.priority).dot"></span>
                    ประกาศ
                  </span>
                  <span class="truncate max-w-[200px] sm:max-w-xs">{{ heroAnnouncement.message }}</span>
                  <i class="bi bi-chevron-right text-[10px] text-slate-400 group-hover:text-slate-600 transition-transform group-hover:translate-x-0.5"></i>
                </button>
              </div>

              <!-- Headline -->
              <h1 class="animate-slide-up-fade mt-8 text-[2.5rem] leading-[1.1] tracking-tight font-black text-slate-900 sm:text-5xl lg:text-6xl xl:text-[4rem]" style="animation-delay: 80ms">
                แพลตฟอร์มรับฟังเสียง
                <br class="hidden sm:block" />
                เพื่อเปลี่ยนโรงเรียน
                <span class="relative inline-block mt-2 lg:mt-0">
                  <span class="relative z-10 text-rose-600">ให้ดีขึ้น</span>
                  <span class="absolute bottom-1.5 left-0 right-0 h-3 bg-rose-100/80 -z-10 -rotate-1 rounded-sm"></span>
                </span>
              </h1>

              <p class="animate-slide-up-fade mt-6 text-base sm:text-lg text-slate-500 leading-relaxed font-medium" style="animation-delay: 160ms">
                ระบบจัดการข้อคิดเห็นและปัญหาอัจฉริยะสำหรับนักเรียนพิริยาลัย แจ้งเรื่องง่าย ไต่ระดับสายงานอัตโนมัติ ติดตามสถานะโปร่งใสแบบเรียลไทม์
              </p>

              <!-- CTAs -->
              <div class="animate-slide-up-fade mt-8 flex flex-col sm:flex-row items-center gap-3.5 justify-center lg:justify-start" style="animation-delay: 240ms">
                <button
                  @click="goLogin"
                  class="w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-xl bg-rose-600 px-7 py-3.5 text-[15px] font-bold text-white shadow-[0_1px_2px_rgba(0,0,0,0.1),inset_0_1px_0_rgba(255,255,255,0.2)] transition-all hover:bg-rose-700 hover:shadow-lg hover:shadow-rose-600/20 active:scale-95"
                >
                  <i class="bi bi-pencil-square text-lg"></i>
                  แจ้งเรื่องเลย
                </button>
                <button
                  @click="goStats"
                  class="w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-7 py-3.5 text-[15px] font-bold text-slate-700 shadow-sm transition-all hover:bg-slate-50 hover:border-slate-300 active:scale-95"
                >
                  <i class="bi bi-bar-chart text-lg text-slate-400"></i>
                  ดูแดชบอร์ดสถิติ
                </button>
              </div>

              <!-- Social Proof / Trust -->
              <div class="animate-slide-up-fade mt-10 pt-8 border-t border-slate-200/60 flex flex-wrap items-center justify-center lg:justify-start gap-x-6 gap-y-3" style="animation-delay: 320ms">
                <div class="flex items-center gap-2">
                  <div class="flex items-center justify-center w-6 h-6 rounded-full bg-emerald-100 text-emerald-600"><i class="bi bi-check text-sm font-black"></i></div>
                  <span class="text-sm font-semibold text-slate-600">โปร่งใสตรวจสอบได้</span>
                </div>
                <div class="flex items-center gap-2">
                  <div class="flex items-center justify-center w-6 h-6 rounded-full bg-blue-100 text-blue-600"><i class="bi bi-stopwatch text-[11px] font-black"></i></div>
                  <span class="text-sm font-semibold text-slate-600">แก้ไขอย่างมีกรอบเวลา</span>
                </div>
                <div class="flex items-center gap-2">
                  <div class="flex items-center justify-center w-6 h-6 rounded-full bg-indigo-100 text-indigo-600"><i class="bi bi-incognito text-[11px] font-black"></i></div>
                  <span class="text-sm font-semibold text-slate-600">รองรับการปิดบังตัวตน</span>
                </div>
              </div>
            </div>

            <!-- Right: Enterprise Dashboard / Phone Mockup -->
            <div class="animate-slide-up-fade relative w-full max-w-[440px] mx-auto lg:mx-0 lg:ml-auto perspective-[1000px]" style="animation-delay: 200ms">
              <div class="absolute -bottom-8 left-1/2 -translate-x-1/2 w-3/4 h-12 bg-slate-900/10 blur-xl rounded-[100%] tilt-shadow"></div>
              
              <div class="phone-tilt relative bg-white border-[6px] border-slate-900 rounded-[2.5rem] shadow-2xl overflow-hidden aspect-[9/19]">
                <!-- Status bar -->
                <div class="absolute top-0 inset-x-0 h-6 flex items-center justify-between px-6 z-20 bg-white/80 backdrop-blur-sm text-[9px] font-bold text-slate-900">
                  <span>9:41</span>
                  <div class="flex gap-1">
                    <i class="bi bi-reception-4"></i>
                    <i class="bi bi-wifi"></i>
                    <i class="bi bi-battery-full text-[11px]"></i>
                  </div>
                </div>

                <!-- Internal App UI (Clean SaaS Look) -->
                <div class="pt-10 px-4 pb-4 h-full bg-slate-50 flex flex-col gap-3">
                  <!-- Top bar -->
                  <div class="flex items-center justify-between">
                    <div class="w-8 h-8 rounded-lg bg-slate-900 text-white flex items-center justify-center text-[10px] font-black">ณ</div>
                    <div class="w-8 h-8 rounded-lg border border-slate-200 bg-white flex items-center justify-center text-slate-500"><i class="bi bi-bell"></i></div>
                  </div>

                  <!-- Greeting -->
                  <div>
                    <p class="text-[10px] font-bold text-slate-500 uppercase tracking-wide">ภาพรวมวันนี้</p>
                    <p class="text-sm font-black text-slate-800">แดชบอร์ดส่วนตัว</p>
                  </div>

                  <!-- Quick Stats (Real Data inside mockup) -->
                  <div class="grid grid-cols-2 gap-2">
                    <div class="bg-white border border-slate-200/80 rounded-xl p-3 shadow-sm">
                      <div class="w-6 h-6 rounded-full bg-amber-50 text-amber-500 flex items-center justify-center mb-2"><i class="bi bi-arrow-repeat text-[10px]"></i></div>
                      <p class="text-[9px] font-semibold text-slate-500">กำลังดำเนินการ</p>
                      <p v-if="!isLoadingStats && stats" class="text-lg font-black text-slate-900 tabular-nums">{{ stats.routed_issues }}</p>
                      <div v-else class="h-6 w-8 bg-slate-100 rounded mt-1"></div>
                    </div>
                    <div class="bg-white border border-slate-200/80 rounded-xl p-3 shadow-sm">
                      <div class="w-6 h-6 rounded-full bg-emerald-50 text-emerald-500 flex items-center justify-center mb-2"><i class="bi bi-check2 text-[12px]"></i></div>
                      <p class="text-[9px] font-semibold text-slate-500">ปิดสำเร็จแล้ว</p>
                      <p v-if="!isLoadingStats && stats" class="text-lg font-black text-slate-900 tabular-nums">{{ stats.resolved_issues }}</p>
                      <div v-else class="h-6 w-8 bg-slate-100 rounded mt-1"></div>
                    </div>
                  </div>

                  <!-- Recent Ticket -->
                  <div class="bg-white border border-slate-200/80 rounded-xl p-3 shadow-sm flex-1">
                    <div class="flex items-center justify-between mb-2 pb-2 border-b border-slate-100">
                      <p class="text-[10px] font-bold text-slate-800">เรื่องล่าสุดในระบบ</p>
                      <span class="px-1.5 py-0.5 bg-slate-100 text-slate-500 text-[8px] font-bold rounded-full">อัปเดตสด</span>
                    </div>
                    <template v-if="!isLoadingCases && latestCase">
                      <div class="flex gap-2">
                        <div class="w-1.5 h-1.5 rounded-full bg-emerald-500 mt-1 shrink-0"></div>
                        <div>
                          <p class="text-[11px] font-bold text-slate-800 leading-tight line-clamp-2">{{ latestCase.title }}</p>
                          <p class="text-[9px] font-medium text-slate-400 mt-1">{{ latestCase.department_in_charge }}</p>
                        </div>
                      </div>
                    </template>
                    <div v-else class="space-y-1 mt-1">
                      <div class="h-2 w-full bg-slate-100 rounded"></div>
                      <div class="h-2 w-2/3 bg-slate-100 rounded"></div>
                    </div>
                  </div>

                  <!-- Fake Bottom Nav -->
                  <div class="h-12 bg-white border border-slate-200/80 rounded-xl shadow-sm flex items-center justify-around px-2 text-slate-400">
                    <div class="w-8 h-8 rounded-lg bg-slate-50 text-slate-800 flex items-center justify-center"><i class="bi bi-house-door-fill"></i></div>
                    <div class="w-8 h-8 flex items-center justify-center"><i class="bi bi-grid"></i></div>
                    <div class="w-10 h-10 -mt-4 bg-rose-600 text-white rounded-full flex items-center justify-center shadow-md shadow-rose-600/30 border-2 border-slate-50"><i class="bi bi-plus-lg"></i></div>
                    <div class="w-8 h-8 flex items-center justify-center"><i class="bi bi-chat-text"></i></div>
                    <div class="w-8 h-8 flex items-center justify-center"><i class="bi bi-person"></i></div>
                  </div>
                </div>
              </div>

              <!-- Floating UI Elements -->
              <div class="animate-float absolute -left-6 top-1/4 z-30 flex items-center gap-2.5 rounded-xl border border-slate-200/80 bg-white/95 px-3 py-2 shadow-lg backdrop-blur-md">
                <div class="flex h-6 w-6 items-center justify-center rounded-md bg-rose-50 text-rose-600"><i class="bi bi-inbox text-[10px]"></i></div>
                <div class="flex flex-col">
                  <span class="text-[8px] font-bold text-slate-400 uppercase tracking-wider">เรื่องเข้าสู่ระบบ</span>
                  <span v-if="stats" class="text-xs font-black text-slate-800 leading-none tabular-nums">{{ numberFmt.format(stats.total_issues) }}</span>
                  <span v-else class="h-3 w-8 bg-slate-100 rounded mt-0.5"></span>
                </div>
              </div>

              <div class="animate-float animation-delay-1500 absolute -right-4 bottom-1/4 z-30 flex items-center gap-2.5 rounded-xl border border-slate-200/80 bg-white/95 px-3 py-2 shadow-lg backdrop-blur-md">
                <div class="flex h-6 w-6 items-center justify-center rounded-md bg-indigo-50 text-indigo-600"><i class="bi bi-patch-check text-[10px]"></i></div>
                <div class="flex flex-col">
                  <span class="text-[8px] font-bold text-slate-400 uppercase tracking-wider">เสียงบน PIRI Vote</span>
                  <span v-if="stats" class="text-xs font-black text-slate-800 leading-none tabular-nums">{{ numberFmt.format(stats.active_votes) }}</span>
                  <span v-else class="h-3 w-8 bg-slate-100 rounded mt-0.5"></span>
                </div>
              </div>
            </div>

          </div>
        </div>
      </section>

      <!-- 📣 =============================================== -->
      <!-- 3. Ticker Announcements                          -->
      <!-- 📣 =============================================== -->
      <div id="announce" class="relative z-20 mx-auto max-w-[88rem] px-4 sm:px-6 lg:px-8 -mt-6">
        <div class="rounded-2xl border border-slate-200/80 bg-white shadow-sm overflow-hidden flex items-center h-12">
          
          <div v-if="isLoadingAnnouncements" class="w-full flex items-center px-4 gap-3">
            <div class="w-16 h-5 rounded-full bg-slate-100 skeleton-shimmer"></div>
            <div class="flex-1 h-3 rounded bg-slate-50 skeleton-shimmer"></div>
          </div>

          <div v-else-if="hasAnnouncementsError" class="w-full flex items-center justify-between px-4">
            <span class="text-[13px] font-medium text-slate-500 flex items-center gap-2">
              <i class="bi bi-wifi-off"></i> โหลดประกาศไม่สำเร็จ
            </span>
            <button @click="fetchAnnouncements" class="text-[11px] font-bold text-slate-600 hover:text-slate-900 bg-slate-100 px-2 py-1 rounded">ลองใหม่</button>
          </div>

          <template v-else-if="announcements.length > 0">
            <div class="flex items-center h-full pl-3 pr-2 bg-slate-50 border-r border-slate-100 shrink-0 z-10">
              <span class="flex items-center gap-1.5 px-2.5 py-1 bg-white border border-slate-200 rounded-full text-[10px] font-black uppercase tracking-wider text-slate-600 shadow-sm">
                <i class="bi bi-megaphone-fill text-slate-400"></i> ประกาศ
              </span>
            </div>
            
            <div class="flex-1 overflow-hidden relative h-full flex items-center bg-white mask-edges">
              <div class="marquee-track flex whitespace-nowrap" :style="{ animationDuration: marqueeDuration }">
                <div v-for="copy in 2" :key="copy" class="flex items-center" :aria-hidden="copy === 2 ? 'true' : 'false'">
                  <template v-for="a in announcements" :key="a.id">
                    <div class="flex items-center mx-4">
                      <span class="w-1.5 h-1.5 rounded-full mr-2" :class="priorityBadge(a.priority).dot"></span>
                      <a v-if="a.link" :href="a.link" target="_blank" rel="noopener" tabindex="-1" class="text-[13px] font-medium text-slate-600 hover:text-rose-600 transition-colors flex items-center gap-1">
                        {{ a.message }} <i class="bi bi-arrow-up-right text-[10px] opacity-50"></i>
                      </a>
                      <span v-else class="text-[13px] font-medium text-slate-600">{{ a.message }}</span>
                    </div>
                    <span class="w-1 h-1 rounded-full bg-slate-200 mx-2 last:hidden"></span>
                  </template>
                </div>
              </div>
            </div>
          </template>
        </div>
      </div>

      <!-- 📊 =============================================== -->
      <!-- 4. LIVE STATISTICS — Clean Dashboard Layout      -->
      <!-- 📊 =============================================== -->
      <section id="stats" class="py-20 lg:py-28 relative">
        <div class="mx-auto max-w-[88rem] px-4 sm:px-6 lg:px-8">
          
          <div class="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-10">
            <div class="max-w-xl">
              <div class="inline-flex items-center gap-1.5 rounded-full border border-emerald-200/60 bg-emerald-50 px-2.5 py-1 text-[10px] font-bold uppercase tracking-widest text-emerald-600 mb-4">
                <span class="relative flex h-1.5 w-1.5">
                  <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span class="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-500"></span>
                </span>
                Real-time Sync
              </div>
              <h2 class="text-3xl lg:text-4xl font-black tracking-tight text-slate-900">
                ข้อมูลสถานะการทำงาน
              </h2>
              <p class="mt-3 text-[15px] text-slate-500 font-medium">
                ตัวเลขสถิติดึงตรงจากฐานข้อมูลจริงอย่างโปร่งใส เพื่อให้ทุกคนเห็นความคืบหน้าของทุกเสียงสะท้อนที่ส่งเข้ามา
              </p>
            </div>
          </div>

          <!-- Loading State -->
          <div v-if="isLoadingStats" class="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-4">
            <div class="md:col-span-2 lg:col-span-2 bg-white rounded-2xl border border-slate-200/80 p-6 h-[280px] skeleton-shimmer"></div>
            <div v-for="i in 4" :key="i" class="bg-white rounded-2xl border border-slate-200/80 p-6 h-[132px] skeleton-shimmer"></div>
          </div>

          <!-- Error State -->
          <div v-else-if="hasStatsError" class="bg-white rounded-2xl border border-slate-200 border-dashed py-16 flex flex-col items-center">
            <div class="w-12 h-12 bg-slate-100 rounded-full flex items-center justify-center text-slate-400 mb-3"><i class="bi bi-x-octagon"></i></div>
            <p class="text-slate-600 font-semibold text-sm">ไม่สามารถโหลดข้อมูลสถิติได้</p>
            <button @click="fetchStats" class="mt-3 text-[13px] font-bold text-slate-900 bg-slate-100 px-4 py-2 rounded-lg hover:bg-slate-200 transition">ลองใหม่</button>
          </div>

          <!-- Bento Grid -->
          <div v-else ref="statsGridRef" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            
            <!-- Hero Stat (Spans 2 cols, 2 rows) -->
            <div class="bento-glow bg-white rounded-2xl border border-slate-200/80 p-6 sm:col-span-2 row-span-2 flex flex-col shadow-sm transition-shadow hover:shadow-md" @mousemove="onCardGlow">
              <div class="flex items-start justify-between">
                <div class="w-10 h-10 rounded-xl bg-slate-900 text-white flex items-center justify-center shadow-sm">
                  <i class="bi bi-bar-chart-fill text-lg"></i>
                </div>
                <span class="text-[10px] font-bold bg-slate-100 text-slate-500 px-2 py-1 rounded-md uppercase tracking-wider">Total Issues</span>
              </div>
              
              <div class="mt-8">
                <h3 class="text-sm font-semibold text-slate-500">เรื่องที่ส่งเข้าระบบทั้งหมด</h3>
                <div class="flex items-baseline gap-2 mt-1">
                  <span class="text-[4rem] leading-none font-black text-slate-900 tracking-tighter tabular-nums" :data-target="heroStat" data-decimals="0">
                    {{ formatStatValue(heroStat) }}
                  </span>
                  <span class="text-sm font-bold text-slate-400 mb-1">เรื่อง</span>
                </div>
              </div>

              <!-- Refined Sparkline -->
              <div class="mt-auto pt-8 relative">
                <template v-if="!isLoadingTrend && sparkTrend && sparkDot">
                  <div class="flex justify-between items-end mb-2">
                    <span class="text-[11px] font-bold text-slate-400 uppercase tracking-wider">แนวโน้ม 14 วันย้อนหลัง</span>
                    <span class="text-[11px] font-bold text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded"><i class="bi bi-arrow-up-right"></i> {{ sparkTrend.total }}</span>
                  </div>
                  <div class="relative h-20 w-full border-b border-slate-100 pb-1">
                    <svg viewBox="0 0 400 100" class="w-full h-full overflow-visible" preserveAspectRatio="none">
                      <defs>
                        <linearGradient id="sparkGradient" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stop-color="#0f172a" stop-opacity="0.1"></stop>
                          <stop offset="100%" stop-color="#0f172a" stop-opacity="0"></stop>
                        </linearGradient>
                      </defs>
                      <polygon :points="sparkTrend.area" fill="url(#sparkGradient)"></polygon>
                      <polyline :points="sparkTrend.line" fill="none" stroke="#0f172a" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke"></polyline>
                    </svg>
                    <!-- Live Dot -->
                    <span class="absolute w-2 h-2 bg-slate-900 rounded-full shadow-[0_0_0_4px_rgba(15,23,42,0.1)] -translate-x-1/2 -translate-y-1/2" :style="{ left: sparkDot.left + '%', top: sparkDot.top + '%' }"></span>
                  </div>
                </template>
                <div v-else-if="isLoadingTrend" class="h-28 w-full bg-slate-50 rounded-xl skeleton-shimmer"></div>
              </div>
            </div>

            <!-- Small Stats Loop -->
            <div 
              v-for="card in smallStats" 
              :key="card.key"
              class="bento-glow bg-white rounded-2xl border border-slate-200/80 p-5 shadow-sm transition-shadow hover:shadow-md flex flex-col justify-between"
              @mousemove="onCardGlow"
            >
              <div class="flex items-center justify-between mb-4">
                <div class="w-9 h-9 rounded-lg flex items-center justify-center text-[15px]" :class="card.iconCls">
                  <i :class="['bi', card.icon]"></i>
                </div>
                <i class="bi bi-arrow-up-right text-slate-300 text-[10px]"></i>
              </div>
              <div>
                <p class="text-[11px] font-bold text-slate-500 uppercase tracking-wide">{{ card.label }}</p>
                <p class="mt-1 flex items-baseline gap-1.5">
                  <span class="text-3xl font-black text-slate-900 tracking-tight tabular-nums" :data-target="card.target" :data-decimals="card.decimals">
                    {{ formatStatValue(card.target, card.decimals) }}
                  </span>
                  <span v-if="card.suffix" class="text-xs font-bold text-slate-400 mb-1">{{ card.suffix }}</span>
                </p>
              </div>
            </div>

            <!-- Join CTA Card -->
            <div class="bento-glow bg-slate-900 rounded-2xl border border-slate-800 p-6 shadow-md sm:col-span-2 lg:col-span-3 flex flex-col sm:flex-row sm:items-center justify-between gap-4" @mousemove="onCardGlow">
              <div>
                <h3 class="text-[15px] font-bold text-white flex items-center gap-2">
                  ระบบขับเคลื่อนด้วยเสียงของคุณ <i class="bi bi-stars text-rose-400"></i>
                </h3>
                <p class="text-[13px] font-medium text-slate-400 mt-1">ล็อกอินด้วยบัญชีโรงเรียน เพื่อแจ้งเรื่องหรือร่วมโหวตประเด็นต่างๆ</p>
              </div>
              <button @click="goLogin" class="shrink-0 bg-white text-slate-900 px-5 py-2.5 rounded-xl text-[13px] font-bold hover:bg-slate-100 transition-colors active:scale-95">
                เข้าระบบตอนนี้
              </button>
            </div>

          </div>
        </div>
      </section>

      <!-- 🪜 =============================================== -->
      <!-- 5. SMART WORKFLOW — Pipeline Layout              -->
      <!-- 🪜 =============================================== -->
      <section id="flow" class="py-20 lg:py-28 bg-white border-t border-slate-200/80">
        <div class="mx-auto max-w-[88rem] px-4 sm:px-6 lg:px-8">
          
          <div class="text-center max-w-2xl mx-auto mb-16">
            <h2 class="text-sm font-black uppercase tracking-widest text-slate-400 mb-2">Smart Workflow</h2>
            <p class="text-3xl font-black text-slate-900 tracking-tight">ขั้นตอนการทำงานแบบไต่ระดับ</p>
            <p class="mt-4 text-[15px] font-medium text-slate-500">
              ทุกเรื่องถูกออกแบบให้มีการส่งต่อ (Escalation) เป็นทอดๆ ขึ้นไปตามลำดับสายงาน เพื่อให้มั่นใจว่าปัญหานั้นๆ จะไปถึงผู้ที่มีอำนาจจัดการโดยตรง
            </p>
          </div>

          <!-- Pipeline Layout (Enterprise Step Component) -->
          <div class="relative max-w-4xl mx-auto">
            <!-- Connecting Line (Desktop: Horizontal, Mobile: Vertical) -->
            <div class="absolute left-[27px] top-0 bottom-0 w-px bg-slate-100 md:hidden"></div>
            <div class="hidden md:block absolute top-[27px] left-0 right-0 h-px bg-slate-100"></div>

            <div class="grid grid-cols-1 md:grid-cols-4 gap-8 md:gap-4 relative z-10">
              <div v-for="(step, i) in workflowSteps" :key="i" class="relative pl-14 md:pl-0 md:pt-14">
                
                <!-- Node Marker -->
                <div class="absolute left-0 top-0 md:left-auto md:top-0 w-14 h-14 md:w-14 md:h-14 bg-white border border-slate-200 rounded-2xl flex items-center justify-center text-slate-700 shadow-sm z-10">
                  <i :class="['bi', step.icon, 'text-xl']"></i>
                  <!-- Step Number -->
                  <span class="absolute -top-2 -right-2 w-5 h-5 bg-slate-900 text-white text-[9px] font-black rounded-full flex items-center justify-center ring-2 ring-white">
                    {{ i + 1 }}
                  </span>
                </div>

                <!-- Content -->
                <div class="pt-2 md:pt-4">
                  <h3 class="text-[15px] font-bold text-slate-900 leading-tight">{{ step.title }}</h3>
                  <p class="mt-2 text-[13px] font-medium text-slate-500 leading-relaxed">{{ step.desc }}</p>
                </div>

              </div>
            </div>
          </div>

        </div>
      </section>

      <!-- 💥 =============================================== -->
      <!-- 6. THE IMPACT — Split Case Study Layout          -->
      <!-- 💥 =============================================== -->
      <section id="impact" class="py-20 lg:py-28 bg-slate-50 border-t border-slate-200/80 overflow-hidden">
        <div class="mx-auto max-w-[88rem] px-4 sm:px-6 lg:px-8">
          
          <div class="flex flex-col lg:flex-row lg:items-end justify-between gap-6 mb-12">
            <div>
              <h2 class="text-3xl font-black text-slate-900 tracking-tight">ผลลัพธ์การแก้ไขจริง</h2>
              <p class="mt-3 text-[15px] font-medium text-slate-500 max-w-xl">
                ทุกตัวอักษรที่พิมพ์ส่งเข้ามา คือจุดเริ่มต้นของการเปลี่ยนแปลง นี่คือตัวอย่างเรื่องราวที่ได้รับการแก้ไขผ่านระบบของเรา
              </p>
            </div>
          </div>

          <div v-if="isLoadingCases" class="h-[400px] w-full bg-white border border-slate-200/80 rounded-2xl skeleton-shimmer"></div>
          
          <div v-else-if="!featuredCase" class="bg-white border border-slate-200 border-dashed rounded-2xl py-20 flex flex-col items-center justify-center text-center">
             <i class="bi bi-box-seam text-3xl text-slate-300 mb-3"></i>
             <p class="text-[15px] font-bold text-slate-600">ยังไม่มีประวัติการแก้ไขสำเร็จ</p>
             <p class="text-[13px] text-slate-400 mt-1">เรื่องแรกที่เสร็จสิ้นจะถูกนำมาแสดงที่นี่</p>
          </div>

          <div v-else class="grid lg:grid-cols-[1fr_320px] gap-6">
            
            <!-- Featured Case (Split Layout) -->
            <div class="bg-white rounded-[2rem] border border-slate-200/80 p-2 sm:p-3 shadow-sm">
              <!-- Meta Header -->
              <div class="px-5 py-4 flex items-center justify-between border-b border-slate-100">
                <span class="inline-flex items-center gap-1.5 px-2.5 py-1 bg-slate-100 text-slate-600 rounded-md text-[11px] font-bold tracking-wide">
                  <i class="bi bi-tag-fill text-[10px]"></i> {{ featuredCase.category }}
                </span>
                <span class="text-[11px] font-bold text-slate-400"><i class="bi bi-calendar3"></i> ปิดงานเมื่อ {{ formatThaiDate(featuredCase.resolved_at) }}</span>
              </div>

              <!-- Split Container -->
              <div class="relative grid md:grid-cols-2 gap-2 mt-2">
                
                <!-- Center Connector Arrow (Desktop) -->
                <div class="hidden md:flex absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-10 w-10 h-10 bg-white border border-slate-200 rounded-full items-center justify-center shadow-sm text-slate-400">
                  <i class="bi bi-arrow-right"></i>
                </div>

                <!-- Before -->
                <div class="bg-slate-50/80 rounded-[1.5rem] p-6 sm:p-8">
                  <div class="flex items-center gap-2 mb-4">
                    <span class="w-2 h-2 rounded-full bg-slate-400"></span>
                    <span class="text-[11px] font-black uppercase tracking-widest text-slate-500">ปัญหาที่ได้รับแจ้ง</span>
                  </div>
                  <h3 class="text-lg sm:text-xl font-black text-slate-900 leading-snug mb-3">"{{ featuredCase.title }}"</h3>
                  <div class="flex items-center gap-2 text-[12px] font-medium text-slate-500">
                    <div class="w-6 h-6 rounded-full bg-white border border-slate-200 flex items-center justify-center text-[10px] text-slate-400"><i class="bi bi-person-fill"></i></div>
                    แจ้งโดย {{ featuredCase.reporter_mask }}
                  </div>
                </div>

                <!-- Center Connector Down (Mobile) -->
                <div class="flex md:hidden justify-center -my-3 relative z-10">
                   <div class="w-8 h-8 bg-white border border-slate-200 rounded-full flex items-center justify-center text-slate-400 shadow-sm"><i class="bi bi-arrow-down"></i></div>
                </div>

                <!-- After -->
                <div class="bg-[#F0FDF4] rounded-[1.5rem] p-6 sm:p-8 border border-[#DCFCE7]">
                  <div class="flex items-center gap-2 mb-4">
                    <span class="w-2 h-2 rounded-full bg-emerald-500"></span>
                    <span class="text-[11px] font-black uppercase tracking-widest text-emerald-700">ผลลัพธ์การแก้ไข</span>
                  </div>
                  <p class="text-[15px] font-medium text-emerald-950 leading-relaxed mb-6">
                    {{ featuredCase.solution_summary }}
                  </p>
                  
                  <div class="mt-auto pt-4 border-t border-emerald-200/50 flex flex-wrap gap-4">
                    <div class="text-[11px] font-bold text-emerald-800">
                      <span class="block text-emerald-600/70 uppercase text-[9px] mb-0.5">รับผิดชอบโดย</span>
                      <i class="bi bi-building"></i> {{ featuredCase.department_in_charge }}
                    </div>
                    <div class="text-[11px] font-bold text-emerald-800" v-if="featuredCase.duration_hours">
                      <span class="block text-emerald-600/70 uppercase text-[9px] mb-0.5">ใช้เวลาแก้ไข</span>
                      <i class="bi bi-stopwatch"></i> {{ formatDuration(featuredCase.duration_hours) }}
                    </div>
                  </div>
                </div>

              </div>
            </div>

            <!-- Recent list Sidebar -->
            <div class="flex flex-col gap-3">
              <h3 class="text-[12px] font-bold text-slate-400 uppercase tracking-widest px-1">เรื่องที่เพิ่งปิดล่าสุด</h3>
              <div class="flex flex-col gap-2">
                <div v-for="c in recentCases" :key="c.id" class="bg-white border border-slate-200/80 rounded-2xl p-4 shadow-sm hover:border-slate-300 transition-colors cursor-default">
                  <div class="flex gap-3">
                    <div class="w-8 h-8 rounded-full bg-slate-50 border border-slate-100 flex items-center justify-center shrink-0 text-[10px] font-black text-slate-500">
                      {{ reporterInitial(c.reporter_mask) }}
                    </div>
                    <div class="min-w-0">
                      <p class="text-[13px] font-bold text-slate-800 truncate">{{ c.title }}</p>
                      <p class="text-[11px] font-medium text-slate-400 mt-0.5 truncate">{{ c.department_in_charge }}</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>

          </div>
        </div>
      </section>

      <!-- 🚀 =============================================== -->
      <!-- 7. ECOSYSTEM — Ultra Dark SaaS Look              -->
      <!-- 🚀 =============================================== -->
      <section id="ecosystem" class="py-24 bg-slate-950 text-white relative overflow-hidden">
        <!-- Subtle Grid & Spotlight -->
        <div class="absolute inset-0 bg-[linear-gradient(to_right,#ffffff05_1px,transparent_1px),linear-gradient(to_bottom,#ffffff05_1px,transparent_1px)] bg-[size:40px_40px]"></div>
        <div class="absolute top-0 right-0 w-[600px] h-[600px] bg-rose-500/10 rounded-full blur-[120px] pointer-events-none"></div>
        <div class="absolute bottom-0 left-0 w-[500px] h-[500px] bg-blue-500/10 rounded-full blur-[100px] pointer-events-none"></div>

        <div class="relative mx-auto max-w-[88rem] px-4 sm:px-6 lg:px-8 grid lg:grid-cols-2 gap-16 items-center">
          
          <!-- Left: Copy -->
          <div>
            <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/5 border border-white/10 text-[11px] font-bold tracking-widest text-slate-300 uppercase mb-6">
              <i class="bi bi-boxes"></i> PIRI Ecosystem
            </div>
            <h2 class="text-3xl sm:text-4xl lg:text-5xl font-black tracking-tight leading-tight">
              ไม่ใช่แค่แจ้งปัญหา<br>
              แต่คือพื้นที่ <span class="text-transparent bg-clip-text bg-gradient-to-r from-rose-400 to-rose-200">สร้างความโปร่งใส</span>
            </h2>
            <p class="mt-6 text-[15px] font-medium text-slate-400 leading-relaxed max-w-lg">
              เราสร้างเครื่องมือเสริมเพื่อเปลี่ยนเสียงสะท้อนให้เป็นพลังขับเคลื่อน นอกจากการรับแจ้งเรื่องแล้ว เรายังมีพื้นที่สำหรับการโหวตและการสนทนาสาธารณะ
            </p>

            <div class="mt-10 grid sm:grid-cols-2 gap-4">
              <!-- Feature 1 -->
              <div class="bg-white/5 border border-white/10 rounded-2xl p-5 hover:bg-white/10 transition-colors">
                <div class="w-10 h-10 rounded-xl bg-white/10 flex items-center justify-center text-slate-300 mb-4"><i class="bi bi-chat-square-text"></i></div>
                <h3 class="text-sm font-bold text-white">PIRI Talk</h3>
                <p class="mt-1.5 text-[12px] text-slate-400 font-medium">กระดานสนทนาสาธารณะสำหรับแลกเปลี่ยนความเห็นอย่างอิสระ ภายใต้การดูแลของสภานักเรียน</p>
              </div>
              <!-- Feature 2 -->
              <div class="bg-white/5 border border-white/10 rounded-2xl p-5 hover:bg-white/10 transition-colors">
                <div class="w-10 h-10 rounded-xl bg-white/10 flex items-center justify-center text-slate-300 mb-4"><i class="bi bi-bar-chart-steps"></i></div>
                <h3 class="text-sm font-bold text-white">PIRI Vote</h3>
                <p class="mt-1.5 text-[12px] text-slate-400 font-medium">ระบบลงคะแนนเพื่อหาฉันทามติ นำเสียงส่วนใหญ่มาประกอบการตัดสินใจนโยบายโรงเรียน</p>
              </div>
            </div>
          </div>

          <!-- Right: Sleek Dashboard Mockup -->
          <div class="relative w-full max-w-[540px] mx-auto perspective-[1200px]">
            <div class="mockup-tilt bg-slate-900 border border-slate-700 rounded-[1.5rem] shadow-[0_20px_50px_rgba(0,0,0,0.5)] overflow-hidden">
              
              <!-- Window Controls -->
              <div class="h-10 bg-slate-900 border-b border-slate-800 flex items-center px-4 gap-2">
                <div class="w-3 h-3 rounded-full bg-slate-700"></div>
                <div class="w-3 h-3 rounded-full bg-slate-700"></div>
                <div class="w-3 h-3 rounded-full bg-slate-700"></div>
                <div class="ml-2 text-[10px] font-bold text-slate-500 tracking-wider">PIRI Console</div>
              </div>

              <div class="flex h-[340px]">
                <!-- Sidebar -->
                <div class="w-16 border-r border-slate-800 flex flex-col items-center py-4 gap-4">
                  <div class="w-8 h-8 rounded-lg bg-rose-500/20 text-rose-400 flex items-center justify-center"><i class="bi bi-grid-fill"></i></div>
                  <div class="w-8 h-8 rounded-lg text-slate-600 flex items-center justify-center"><i class="bi bi-inbox"></i></div>
                  <div class="w-8 h-8 rounded-lg text-slate-600 flex items-center justify-center"><i class="bi bi-people"></i></div>
                </div>
                
                <!-- Content -->
                <div class="flex-1 p-5 flex flex-col gap-4">
                   <div class="flex gap-4">
                     <div class="flex-1 bg-slate-800/50 border border-slate-700/50 rounded-xl p-3">
                        <div class="text-[9px] font-bold text-slate-500 uppercase tracking-widest">Active Issues</div>
                        <div class="text-xl font-black text-white mt-1">1,248</div>
                     </div>
                     <div class="flex-1 bg-slate-800/50 border border-slate-700/50 rounded-xl p-3">
                        <div class="text-[9px] font-bold text-slate-500 uppercase tracking-widest">Resolution Rate</div>
                        <div class="text-xl font-black text-white mt-1">94%</div>
                     </div>
                   </div>

                   <!-- Abstract Graph -->
                   <div class="flex-1 bg-slate-800/50 border border-slate-700/50 rounded-xl p-4 flex flex-col justify-end gap-1.5 relative overflow-hidden">
                      <div class="absolute top-3 left-4 text-[9px] font-bold text-slate-500 uppercase tracking-widest">Weekly Traffic</div>
                      <div class="flex items-end justify-between h-20 px-2">
                        <div class="w-6 bg-slate-700 rounded-t-sm h-[30%]"></div>
                        <div class="w-6 bg-slate-700 rounded-t-sm h-[50%]"></div>
                        <div class="w-6 bg-slate-700 rounded-t-sm h-[40%]"></div>
                        <div class="w-6 bg-slate-700 rounded-t-sm h-[70%]"></div>
                        <div class="w-6 bg-rose-500 rounded-t-sm h-[90%] shadow-[0_0_15px_rgba(244,63,94,0.4)]"></div>
                        <div class="w-6 bg-slate-700 rounded-t-sm h-[60%]"></div>
                      </div>
                   </div>
                </div>
              </div>
            </div>

            <!-- Floating Badge -->
            <div class="absolute -right-6 bottom-12 bg-white text-slate-900 border border-slate-200 rounded-xl px-4 py-3 shadow-xl flex items-center gap-3 transform translate-z-10 animate-float">
              <div class="w-8 h-8 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center"><i class="bi bi-shield-check"></i></div>
              <div>
                <div class="text-[10px] font-black uppercase text-slate-400">Security</div>
                <div class="text-xs font-bold">ข้อมูลถูกเข้ารหัส</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- 🎬 =============================================== -->
      <!-- 8. FINAL CTA                                     -->
      <!-- 🎬 =============================================== -->
      <section class="py-24 bg-white text-center">
        <div class="mx-auto max-w-3xl px-4">
          <h2 class="text-3xl sm:text-4xl font-black text-slate-900 tracking-tight">ทุกเสียงมีความหมาย<br>ทุกเสียงพาพิริลัย ก้าวไปด้วยกัน</h2>
          <p class="mt-5 text-[15px] font-medium text-slate-500 leading-relaxed">
            เริ่มต้นใช้งานแพลตฟอร์มได้ทันทีผ่านบัญชี Google Workspace ของโรงเรียน การเสนอแนะสามารถตั้งค่าปกปิดตัวตนได้
          </p>
          <div class="mt-8 flex justify-center">
            <button
              @click="goLogin"
              class="inline-flex items-center gap-2 bg-slate-900 text-white px-8 py-4 rounded-xl font-bold text-[15px] hover:bg-slate-800 transition-colors shadow-sm active:scale-95"
            >
              เข้าสู่ระบบเพื่อเริ่มต้น
              <i class="bi bi-arrow-right"></i>
            </button>
          </div>
        </div>
      </section>

    </main>

    <!-- 🦶 =============================================== -->
    <!-- 9. FOOTER                                          -->
    <!-- 🦶 =============================================== -->
    <footer class="border-t border-slate-200 bg-slate-50 pt-16 pb-8">
      <div class="mx-auto max-w-[88rem] px-4 sm:px-6 lg:px-8">
        
        <div class="flex flex-col md:flex-row items-center justify-between gap-6 mb-16">
          <div class="flex items-center gap-3">
            <img src="/logos/council-logo.png" alt="" class="h-10 w-10 grayscale opacity-50" />
            <div class="h-8 w-px bg-slate-300"></div>
            <img src="/logos/school-logo.png" alt="" class="h-10 w-10 grayscale opacity-50" />
            <div class="ml-2">
              <div class="text-[15px] font-black text-slate-700">PIRI<span class="text-slate-400">voice</span></div>
              <div class="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Student Council</div>
            </div>
          </div>
        </div>

        <div class="border-t border-slate-200 pt-8 flex flex-col md:flex-row items-center justify-between gap-4 text-[12px] font-medium text-slate-400">
          <p>&copy; 2026 PIRIvoice Platform. All rights reserved.</p>
          <a
            href="https://www.singto1597.xyz/"
            target="_blank"
            rel="noopener noreferrer"
            class="hover:text-slate-700 transition-colors flex items-center gap-1.5"
          >
            <i class="bi bi-code-square"></i> Architected by <span class="font-bold">นายพัฒนพล สุธรรม</span>
          </a>
        </div>
      </div>
    </footer>
  </div>
</template>

<style scoped>
/* ============================================================
 * Animations & Micro-Interactions
 * ============================================================ */
@keyframes slideUpFade {
  from { opacity: 0; transform: translateY(16px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-8px); }
}

@keyframes marquee {
  from { transform: translateX(0); }
  to { transform: translateX(-50%); }
}

/* Isometric Mockup Specifics */
@keyframes floatTilt {
  0%, 100% { transform: rotateX(12deg) rotateY(-14deg) rotateZ(1deg) translateY(0); }
  50% { transform: rotateX(12deg) rotateY(-14deg) rotateZ(1deg) translateY(-12px); }
}
@keyframes floatTiltDark {
  0%, 100% { transform: rotateX(15deg) rotateY(-8deg) translateY(0); }
  50% { transform: rotateX(15deg) rotateY(-8deg) translateY(-10px); }
}
@keyframes shadowSquash {
  0%, 100% { transform: translateX(-50%) scaleX(1); opacity: 0.15; }
  50% { transform: translateX(-50%) scaleX(0.85); opacity: 0.08; }
}

.animate-slide-up-fade {
  opacity: 0;
  animation: slideUpFade 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}

.animate-float {
  animation: float 5s ease-in-out infinite;
}

.animation-delay-1500 {
  animation-delay: 1.5s;
}

.phone-tilt {
  transform-style: preserve-3d;
  animation: floatTilt 6s ease-in-out infinite;
}

.mockup-tilt {
  transform-style: preserve-3d;
  animation: floatTiltDark 7s ease-in-out infinite;
}

.tilt-shadow {
  animation: shadowSquash 6s ease-in-out infinite;
}

.marquee-track {
  width: max-content;
  animation: marquee linear infinite;
}
.marquee-track:hover {
  animation-play-state: paused;
}

.mask-edges {
  mask-image: linear-gradient(to right, transparent, black 5%, black 95%, transparent);
}

/* ============================================================
 * Bento Glow (Spotlight effect)
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
}
/* White mode glow */
.bg-white.bento-glow::before {
  background: radial-gradient(400px circle at var(--mx, 50%) var(--my, 50%), rgba(0, 0, 0, 0.02), transparent 40%);
}
/* Dark mode glow */
.bg-slate-900.bento-glow::before, .bg-slate-800.bento-glow::before {
  background: radial-gradient(400px circle at var(--mx, 50%) var(--my, 50%), rgba(255, 255, 255, 0.04), transparent 40%);
}
.bento-glow:hover::before {
  opacity: 1;
}

/* ============================================================
 * Skeletons
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
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.5), transparent);
  animation: shimmer 1.5s infinite;
}
@keyframes shimmer {
  100% { transform: translateX(100%); }
}

/* ============================================================
 * Accessibility
 * ============================================================ */
@media (prefers-reduced-motion: reduce) {
  .animate-slide-up-fade, .animate-float, .phone-tilt, .mockup-tilt, .tilt-shadow, .marquee-track, .skeleton-shimmer::after {
    animation: none !important;
  }
  .phone-tilt, .mockup-tilt { transform: none !important; }
  .tilt-shadow { transform: translateX(-50%) !important; }
  .animate-slide-up-fade { opacity: 1 !important; }
}

button:focus-visible, a:focus-visible {
  outline: 2px solid rgba(15, 23, 42, 0.65);
  outline-offset: 2px;
}
</style>