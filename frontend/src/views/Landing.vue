<!-- eslint-disable vue/multi-word-component-names -- ชื่อ Landing ตาม spec (หน้าแรก) -->
<script setup lang="ts">
/**
 * 🏠 Landing.vue — หน้าแรกของ PIRIvoice
 * เสียงจากชาวพิริยาลัย · สภานักเรียน โรงเรียนพิริยาลัยจังหวัดแพร่
 *
 * หลักการ: ไม่มี Mock Data — ทุกข้อมูลดึงจาก Public API ( /api/v1/public/* )
 * ทุก section ที่ใช้ข้อมูลมี Loading Skeleton + Error Handling + Retry
 */
import { ref, computed, onMounted, onBeforeUnmount } from 'vue';
import { useRouter } from 'vue-router';
import api from '@/services/api';

/* ============================================================
 * 📐 TypeScript Interfaces — Public API Contract
 * ============================================================ */
interface SystemStats {
  total_issues: number;
  resolved_rate_percent: number;
  avg_resolve_hours: number;
  active_talk_threads: number;
  active_votes: number;
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
  /** ใช้เวลาตั้งแต่รับเรื่องจนปิดงาน (ชั่วโมง) — กันไว้ เผื่อ API ใส่มาทีหลัง */
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
const resolvedCases = ref<ResolvedCase[]>([]);
const announcements = ref<Announcement[]>([]);

// ── Loading / Error แยก per-endpoint (โหลดคู่กันโดยไม่รบกวนกัน) ──
const isLoadingStats = ref(true);
const isLoadingCases = ref(true);
const isLoadingAnnouncements = ref(true);

const hasStatsError = ref(false);
const hasCasesError = ref(false);
const hasAnnouncementsError = ref(false);

// ── UI: Navbar ──
const isScrolled = ref(false);
const isMobileMenuOpen = ref(false);

/* ============================================================
 * 📡 API Calls (ทุกตัวมี try...catch + loading + error flag)
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

async function fetchResolvedCases() {
  isLoadingCases.value = true;
  hasCasesError.value = false;
  try {
    const res = (await api.get('/api/v1/public/resolved-cases', {
      params: { limit: 5 },
    })) as ResolvedCase[];
    resolvedCases.value = Array.isArray(res) ? res : [];
    // เริ่ม auto-slide ทันทีที่โหลดข้อมูลเสร็จ (เผื่อข้อมูลมาทีหลัง mount)
    // กัน timer ถูก re-arm หลัง unmount (fetch ยังค้างอยู่ตอนกดออกจากหน้า)
    if (isComponentMounted) {
      activeIndex.value = 0;
      startCarousel();
    }
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
 * 🎠 Carousel — Resolved Cases (auto-slide + dot control)
 * ============================================================ */
const activeIndex = ref(0);
const carouselPaused = ref(false);
let carouselTimer: ReturnType<typeof setInterval> | null = null;
// flag ป้องกัน timer leak: fetch ที่ค้างอยู่ตอน unmount ต้องไม่ re-arm interval
let isComponentMounted = true;

const safeIndex = computed(() =>
  resolvedCases.value.length === 0 ? 0 : activeIndex.value % resolvedCases.value.length,
);
const activeCase = computed(() => resolvedCases.value[safeIndex.value] ?? null);

function prefersReducedMotion(): boolean {
  return typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

function startCarousel() {
  stopCarousel();
  if (!isComponentMounted) return;
  if (prefersReducedMotion()) return; // เคารพผู้ใช้ที่ปิดแอนิเมชัน (WCAG 2.2.2)
  if (resolvedCases.value.length < 2) return;
  carouselTimer = setInterval(() => {
    if (carouselPaused.value) return;
    activeIndex.value = (activeIndex.value + 1) % resolvedCases.value.length;
  }, 5500);
}

function stopCarousel() {
  if (carouselTimer !== null) {
    clearInterval(carouselTimer);
    carouselTimer = null;
  }
}

function goToSlide(i: number) {
  activeIndex.value = i;
  startCarousel();
}

function onCarouselHover() {
  carouselPaused.value = true;
}
function onCarouselLeave() {
  carouselPaused.value = false;
  startCarousel();
}

/* ============================================================
 * 🛠️ Helpers — formatting / navigation
 * ============================================================ */
const numberFmt = new Intl.NumberFormat('th-TH');

const goLogin = () => {
  isMobileMenuOpen.value = false;
  router.push({ name: 'login' });
};

function scrollToId(id: string) {
  isMobileMenuOpen.value = false;
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
    hour: '2-digit',
    minute: '2-digit',
  }).format(d);
}

function formatDuration(hours: number): string {
  const h = hours ?? 0;
  if (h < 1) return `${Math.max(1, Math.round(h * 60))} นาที`;
  if (h < 24) return `${h.toFixed(1).replace(/\.0$/, '')} ชม.`;
  const days = Math.floor(h / 24);
  const rest = Math.round(h % 24);
  return rest ? `${days} วัน ${rest} ชม.` : `${days} วัน`;
}

function impactLabel(score: number): { label: string; cls: string } {
  if (score >= 8) return { label: 'สูงมาก', cls: 'bg-red-50 text-red-600 border-red-100' };
  if (score >= 5) return { label: 'ปานกลาง', cls: 'bg-amber-50 text-amber-600 border-amber-100' };
  return { label: 'ทั่วไป', cls: 'bg-slate-50 text-slate-500 border-slate-100' };
}

/* ============================================================
 * 🧮 Computed — Stats cards
 * ============================================================ */
const statCards = computed(() => {
  if (!stats.value) return [];
  const s = stats.value;
  return [
    {
      icon: 'bi-inbox-fill',
      label: 'เรื่องที่รับแจ้งทั้งหมด',
      value: numberFmt.format(s.total_issues ?? 0),
      hint: 'สะสมตั้งแต่เปิดระบบ',
      tint: 'bg-rose-50 text-rose-600 border-rose-100',
    },
    {
      icon: 'bi-check2-circle',
      label: 'อัตราการแก้ไขสำเร็จ',
      value: `${(s.resolved_rate_percent ?? 0).toFixed(1)}%`,
      hint: 'เทียบกับเรื่องทั้งหมด',
      tint: 'bg-emerald-50 text-emerald-600 border-emerald-100',
    },
    {
      icon: 'bi-stopwatch',
      label: 'เวลาเฉลี่ยต่อเรื่อง',
      value: `${(s.avg_resolve_hours ?? 0).toFixed(1)} ชม.`,
      hint: 'ตั้งแต่รับเรื่องจนปิดงาน',
      tint: 'bg-amber-50 text-amber-600 border-amber-100',
    },
    {
      icon: 'bi-chat-dots',
      label: 'กระทู้พูดคุยที่เปิดอยู่',
      value: numberFmt.format(s.active_talk_threads ?? 0),
      hint: 'บน PIRI Talk',
      tint: 'bg-rose-50 text-rose-600 border-rose-100',
    },
    {
      icon: 'bi-people',
      label: 'เสียงโหวตสะสม',
      value: numberFmt.format(s.active_votes ?? 0),
      hint: 'บน PIRI Vote',
      tint: 'bg-rose-50 text-rose-600 border-rose-100',
    },
  ];
});

/* ============================================================
 * 📣 Computed — Announcement bar (theme ตาม priority สูงสุด)
 * ============================================================ */
const topPriority = computed<AnnouncementPriority>(() => {
  const order: Record<AnnouncementPriority, number> = { normal: 0, high: 1, urgent: 2 };
  return announcements.value.reduce<AnnouncementPriority>(
    (acc, a) => (order[a.priority] > order[acc] ? a.priority : acc),
    'normal',
  );
});

const announcementTheme = computed(() => {
  const p = topPriority.value;
  if (p === 'urgent')
    return {
      bar: 'bg-gradient-to-r from-red-600 to-red-700',
      badge: 'bg-red-700/60 text-red-50 border-red-300/30',
      item: 'text-red-50 hover:text-white',
      icon: 'text-red-100',
    };
  if (p === 'high')
    return {
      bar: 'bg-gradient-to-r from-rose-600 to-rose-700',
      badge: 'bg-rose-700/60 text-rose-50 border-rose-300/30',
      item: 'text-rose-50 hover:text-white',
      icon: 'text-rose-100',
    };
  return {
    bar: 'bg-gradient-to-r from-rose-500 to-rose-600',
    badge: 'bg-rose-600/60 text-rose-50 border-rose-200/40',
    item: 'text-rose-50 hover:text-white',
    icon: 'text-rose-100',
  };
});

// ความเร็ว marquee ตามจำนวนประกาศ — กันข้อความเดียวไหลช้ามาก (1 รายการ ≈ 16s)
const marqueeDuration = computed(() => {
  const n = Math.max(announcements.value.length, 1);
  return `${Math.max(16, n * 7)}s`;
});

/* ============================================================
 * 🪜 Static content — Workflow / Ecosystem / Nav
 * ============================================================ */
const navLinks = [
  { label: 'ผลการดำเนินงาน', id: 'stats' },
  { label: 'ขั้นตอนการทำงาน', id: 'flow' },
  { label: 'ระบบนิเวศ', id: 'ecosystem' },
];

const workflowSteps = [
  {
    icon: 'bi-megaphone',
    title: 'นักเรียนแจ้งเรื่อง',
    desc: 'ส่งข้อคิดเห็น / ปัญหา เข้าระบบได้ตลอด 24 ชม.',
    hover: 'group-hover:border-slate-300 group-hover:bg-slate-50 group-hover:text-slate-600 group-hover:shadow-slate-100',
  },
  {
    icon: 'bi-person-lines-fill',
    title: 'หัวหน้าห้อง',
    desc: 'รวบรวม กลั่นกรอง และนำเรื่องเข้าสู่ระบบรับเรื่อง',
    hover: 'group-hover:border-red-300 group-hover:bg-red-50 group-hover:text-red-600 group-hover:shadow-red-100',
  },
  {
    icon: 'bi-diagram-3',
    title: 'สภานักเรียน',
    desc: 'ประเมิน วินิจฉัย และมอบหมายหน่วยงานที่รับผิดชอบ',
    hover: 'group-hover:border-rose-300 group-hover:bg-rose-50 group-hover:text-rose-600 group-hover:shadow-rose-100',
  },
  {
    icon: 'bi-check2-circle',
    title: 'ปิดงานและประเมินผล',
    desc: 'บันทึกผลการแก้ไขอย่างโปร่งใส พร้อมประเมินความพึงพอใจ',
    hover: 'group-hover:border-emerald-300 group-hover:bg-emerald-50 group-hover:text-emerald-600 group-hover:shadow-emerald-100',
  },
];

/** ตัวเลขสมมติของกราฟหน้าตาราง mock (ภาพประกอบ UI เท่านั้น — ไม่ใช่ข้อมูล) */
const chartHeights = [42, 66, 52, 80, 60, 92, 70, 56];

/* ============================================================
 * 🔄 Lifecycle
 * ============================================================ */
function onWindowScroll() {
  isScrolled.value = window.scrollY > 12;
}

onMounted(() => {
  // ดึงข้อมูลทุกส่วนพร้อมกัน (โหลดคู่กัน ไม่ต้องรอเรียงกัน)
  fetchStats();
  fetchResolvedCases();
  fetchAnnouncements();
  startCarousel();
  window.addEventListener('scroll', onWindowScroll, { passive: true });
});

onBeforeUnmount(() => {
  isComponentMounted = false;
  stopCarousel();
  window.removeEventListener('scroll', onWindowScroll);
});
</script>

<template>
  <div
    class="relative min-h-screen overflow-x-hidden bg-[#FAFAFC] font-sans text-slate-900 selection:bg-rose-500/30 selection:text-rose-900"
  >
    <!-- ⚡ =============================================== -->
    <!-- 1. STICKY NAVBAR (Glassmorphism)                 -->
    <!-- ⚡ =============================================== -->
    <header
      class="sticky top-0 z-50 border-b backdrop-blur-xl transition-all duration-300"
      :class="
        isScrolled
          ? 'border-white/60 bg-white/80 shadow-[0_10px_30px_-15px_rgba(225,29,72,0.15)]'
          : 'border-white/30 bg-white/50'
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
              PIRI<span class="bg-gradient-to-r from-red-600 to-rose-600 bg-clip-text text-transparent">voice</span>
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
            class="rounded-lg px-3.5 py-2 text-sm font-semibold text-slate-600 transition-colors hover:bg-rose-50 hover:text-rose-600"
          >
            {{ link.label }}
          </button>
          <div class="mx-2 h-5 w-px bg-slate-200"></div>
          <button
            @click="goLogin"
            class="group relative flex items-center gap-2 overflow-hidden rounded-xl bg-gradient-to-r from-red-600 via-rose-500 to-red-600 bg-[length:200%_auto] px-4 py-2.5 text-sm font-bold text-white shadow-lg shadow-rose-500/30 transition-all duration-300 hover:bg-right hover:shadow-rose-500/50 active:scale-[0.97]"
          >
            <i class="bi bi-box-arrow-in-right text-base"></i>
            เข้าสู่ระบบ
          </button>
        </div>

        <!-- Hamburger (mobile) -->
        <button
          class="flex h-10 w-10 items-center justify-center rounded-xl border border-slate-200 bg-white/80 text-slate-700 shadow-sm lg:hidden"
          :aria-expanded="isMobileMenuOpen"
          aria-controls="mobile-menu"
          :aria-label="isMobileMenuOpen ? 'ปิดเมนู' : 'เปิดเมนู'"
          @click="isMobileMenuOpen = !isMobileMenuOpen"
        >
          <i :class="isMobileMenuOpen ? 'bi bi-x-lg text-lg' : 'bi bi-list text-2xl'"></i>
        </button>
      </nav>

      <!-- เมนูมือถือ -->
      <Transition name="menu-drop">
        <div
          v-if="isMobileMenuOpen"
          id="mobile-menu"
          class="border-t border-slate-100 bg-white/95 px-4 py-4 backdrop-blur-xl lg:hidden"
        >
          <div class="flex flex-col gap-1">
            <button
              v-for="link in navLinks"
              :key="link.id"
              @click="scrollToId(link.id)"
              class="flex items-center justify-between rounded-xl px-4 py-3 text-left text-sm font-semibold text-slate-700 transition-colors hover:bg-rose-50 hover:text-rose-600"
            >
              {{ link.label }}
              <i class="bi bi-chevron-right text-slate-300"></i>
            </button>
            <button
              @click="goLogin"
              class="mt-2 flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-red-600 to-rose-600 px-4 py-3 text-sm font-bold text-white shadow-lg shadow-rose-500/30"
            >
              <i class="bi bi-box-arrow-in-right text-base"></i>
              เข้าสู่ระบบ
            </button>
          </div>
        </div>
      </Transition>
    </header>

    <main class="relative">
      <!-- 🌟 =============================================== -->
      <!-- 2. HERO (Split Layout + Live Resolved Carousel)   -->
      <!-- 🌟 =============================================== -->
      <section id="hero" class="relative overflow-hidden">
        <!-- 🎨 พื้นหลัง: Animated Glow Orbs -->
        <div class="pointer-events-none absolute inset-0">
          <div
            class="animate-blob absolute -right-[8%] -top-[14%] h-[720px] w-[720px] rounded-full bg-gradient-to-b from-red-200/60 via-rose-100/30 to-transparent opacity-70 blur-[110px] max-md:h-[400px] max-md:w-[400px] max-md:blur-[80px]"
          ></div>
          <div
            class="animate-blob animation-delay-2000 absolute -left-[10%] top-[30%] h-[560px] w-[560px] rounded-full bg-gradient-to-tr from-blue-200/40 via-sky-100/20 to-transparent opacity-60 blur-[100px] max-md:h-[400px] max-md:w-[400px] max-md:blur-[80px]"
          ></div>
          <div
            class="animate-blob animation-delay-4000 absolute -bottom-[20%] right-[20%] h-[480px] w-[480px] rounded-full bg-gradient-to-tl from-rose-200/50 to-transparent opacity-60 blur-[110px] max-md:h-[400px] max-md:w-[400px] max-md:blur-[80px]"
          ></div>
          <div
            class="absolute inset-0 opacity-60 [mask-image:linear-gradient(to_bottom,white,transparent)] [background-image:url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAiIGhlaWdodD0iMjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGNpcmNsZSBjeD0iMSIgY3k9IjEiIHI9IjEiIGZpbGw9InJnYmEoMCwgMCwgMCwgMC4wNCkiLz48L3N2Zz4=')]"
          ></div>
        </div>

        <div class="relative mx-auto grid max-w-7xl grid-cols-1 items-center gap-14 px-4 pb-20 pt-14 lg:grid-cols-2 lg:gap-16 lg:px-8 lg:pb-28 lg:pt-20">
          <!-- ฝั่งซ้าย: Typography & CTA -->
          <div class="text-center lg:text-left">
            <div class="animate-slide-up-fade inline-flex items-center gap-2 rounded-full border border-red-100 bg-white/80 px-4 py-1.5 text-sm font-bold text-red-700 shadow-sm backdrop-blur">
              <i class="bi bi-award text-base text-red-500"></i>
              Official Platform 2569
            </div>

            <h1 class="animate-slide-up-fade mt-6 text-4xl font-black leading-[1.15] tracking-normal text-slate-900 sm:text-5xl xl:text-[3.6rem]" style="animation-delay: 80ms">
              ให้ทุกเสียงของคุณ
              <br class="hidden sm:block" />
              <span
                class="bg-gradient-to-r from-red-600 via-rose-500 to-red-600 bg-clip-text text-transparent drop-shadow-sm"
              >
                เปลี่ยนโรงเรียนให้ดีขึ้น
              </span>
            </h1>

            <p class="animate-slide-up-fade mx-auto mt-6 max-w-xl text-base font-medium leading-relaxed text-slate-500 sm:text-lg lg:mx-0" style="animation-delay: 160ms">
              แจ้งข้อคิดเห็นหรือปัญหา แล้วระบบจะไต่ระดับตามสายงานอย่างโปร่งใส
              จากหัวหน้าห้อง สู่สภานักเรียน พร้อมติดตามความคืบหน้าและผลการแก้ไขได้แบบเรียลไทม์
            </p>

            <!-- CTA -->
            <div class="animate-slide-up-fade mt-8 flex flex-col items-center gap-3 sm:flex-row sm:justify-center lg:justify-start" style="animation-delay: 240ms">
              <button
                @click="goLogin"
                class="group relative flex w-full items-center justify-center gap-2 overflow-hidden rounded-2xl bg-gradient-to-r from-red-600 via-rose-500 to-red-600 bg-[length:200%_auto] px-8 py-4 text-base font-bold text-white shadow-xl shadow-rose-500/30 transition-all duration-300 hover:bg-right hover:shadow-rose-500/50 active:scale-[0.97] sm:w-auto"
              >
                <i class="bi bi-megaphone-fill text-lg transition-transform group-hover:-rotate-12"></i>
                แจ้งปัญหา
                <i class="bi bi-arrow-right transition-transform group-hover:translate-x-1"></i>
              </button>
              <button
                @click="scrollToId('stats')"
                class="flex w-full items-center justify-center gap-2 rounded-2xl border border-slate-200 bg-white/80 px-8 py-4 text-base font-bold text-slate-700 shadow-sm backdrop-blur transition-all duration-300 hover:border-rose-200 hover:bg-rose-50 hover:text-rose-600 active:scale-[0.97] sm:w-auto"
              >
                <i class="bi bi-graph-up-arrow text-lg text-rose-500"></i>
                ดูผลการดำเนินงาน
              </button>
            </div>

            <!-- Trust line -->
            <div class="animate-slide-up-fade mt-8 flex flex-wrap items-center justify-center gap-x-5 gap-y-2 text-sm font-semibold text-slate-400 lg:justify-start" style="animation-delay: 320ms">
              <span class="inline-flex items-center gap-1.5"><i class="bi bi-shield-check text-emerald-500"></i> โปร่งใสตรวจสอบได้</span>
              <span class="inline-flex items-center gap-1.5"><i class="bi bi-lightning-charge-fill text-amber-500"></i> แก้ไขอย่างมีเวลา</span>
              <span class="inline-flex items-center gap-1.5"><i class="bi bi-chat-dots text-cyan-500"></i> ทุกเสียงถูกฟัง</span>
            </div>
          </div>

          <!-- ฝั่งขวา: Live Resolved Cases Carousel -->
          <div class="animate-slide-up-fade relative mx-auto w-full max-w-[560px]" style="animation-delay: 200ms">
            <!-- การ์ดซ้อนด้านหลัง -->
            <div
              class="absolute inset-0 -z-10 -translate-y-4 scale-[0.96] rounded-[2.5rem] bg-gradient-to-br from-rose-100/70 to-white shadow-2xl shadow-rose-200/60"
            ></div>

            <!-- หัวของการ์ด: LIVE badge -->
            <div class="mb-4 flex items-center justify-between px-1">
              <div class="inline-flex items-center gap-2 rounded-full border border-emerald-100 bg-emerald-50/90 px-3 py-1 text-xs font-bold text-emerald-700">
                <span class="relative flex h-2.5 w-2.5">
                  <span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75"></span>
                  <span class="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-500"></span>
                </span>
                ปิดงานล่าสุด · อัปเดตเรียลไทม์
              </div>
              <button
                @click="fetchResolvedCases"
                :disabled="isLoadingCases"
                class="flex h-10 w-10 items-center justify-center rounded-lg border border-slate-200 bg-white/80 text-slate-500 shadow-sm transition-colors hover:bg-rose-50 hover:text-rose-600 disabled:opacity-50"
                aria-label="โหลดผลการดำเนินงานใหม่"
                title="โหลดใหม่"
              >
                <i :class="isLoadingCases ? 'bi bi-arrow-repeat animate-spin' : 'bi bi-arrow-clockwise'"></i>
              </button>
            </div>

            <!-- ⏳ Skeleton ขณะโหลด -->
            <div
              v-if="isLoadingCases"
              class="skeleton-shimmer relative min-h-[460px] overflow-hidden rounded-[2rem] border border-slate-100 bg-white/80 p-6 shadow-xl sm:min-h-[440px] sm:p-8"
            >
              <div class="flex items-center justify-between gap-3">
                <div class="h-6 w-24 rounded-full bg-slate-200"></div>
                <div class="h-6 w-20 rounded-full bg-slate-100"></div>
              </div>
              <div class="mt-6 h-6 w-4/5 rounded-lg bg-slate-200"></div>
              <div class="mt-2 h-4 w-3/5 rounded-lg bg-slate-200"></div>
              <div class="mt-5 h-24 w-full rounded-2xl bg-slate-100"></div>
              <div class="mt-5 h-4 w-2/3 rounded-lg bg-slate-200"></div>
              <div class="mt-3 h-4 w-1/2 rounded-lg bg-slate-200"></div>
            </div>

            <!-- ⚠️ Error -->
            <div
              v-else-if="hasCasesError && resolvedCases.length === 0"
              class="rounded-[2rem] border border-rose-100 bg-white/80 p-8 text-center shadow-xl"
            >
              <div class="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-rose-50 text-rose-500">
                <i class="bi bi-wifi-off text-2xl"></i>
              </div>
              <h3 class="mt-4 text-base font-bold text-slate-800">ไม่สามารถโหลดผลการดำเนินงานได้</h3>
              <p class="mt-1 text-sm text-slate-500">กรุณาตรวจสอบการเชื่อมต่อ หรือลองอีกครั้ง</p>
              <button
                @click="fetchResolvedCases"
                class="mt-5 inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-red-600 to-rose-600 px-5 py-2.5 text-sm font-bold text-white shadow-lg shadow-rose-500/30 transition hover:opacity-90"
              >
                <i class="bi bi-arrow-clockwise"></i>
                ลองใหม่
              </button>
            </div>

            <!-- 📭 ยังไม่มีข้อมูล -->
            <div
              v-else-if="resolvedCases.length === 0"
              class="rounded-[2rem] border border-slate-100 bg-white/80 p-10 text-center shadow-xl"
            >
              <div class="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-50 text-slate-400">
                <i class="bi bi-folder2-open text-2xl"></i>
              </div>
              <h3 class="mt-4 text-base font-bold text-slate-700">ยังไม่มีผลการดำเนินงานที่เปิดเผย</h3>
              <p class="mt-1 text-sm text-slate-400">เรื่องที่ปิดงานแล้วจะแสดงที่นี่ทันที</p>
            </div>

            <!-- 🎠 Carousel -->
            <template v-else>
              <div
                class="group relative min-h-[460px] overflow-hidden rounded-[2rem] border border-white/70 bg-white/75 shadow-xl backdrop-blur-xl sm:min-h-[440px]"
                @mouseenter="onCarouselHover"
                @mouseleave="onCarouselLeave"
              >
                <!-- Glow ด้านหลังการ์ด -->
                <div class="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-rose-200/40 blur-3xl"></div>
                <div class="pointer-events-none absolute -bottom-16 -left-16 h-48 w-48 rounded-full bg-blue-200/40 blur-3xl"></div>

                <!-- วาง slide แบบ absolute + ความสูงคงที่ → สลับแบบ crossfade ไม่กระโดด -->
                <Transition name="case">
                  <div v-if="activeCase" :key="activeCase.id" class="absolute inset-0 p-6 sm:p-8">
                    <!-- แถวบน: หมวดหมู่ + ความรุนแรง -->
                    <div class="flex items-center justify-between gap-3">
                      <span
                        class="inline-flex items-center gap-1.5 rounded-full border border-rose-100 bg-rose-50 px-3 py-1 text-xs font-bold text-rose-600"
                      >
                        <i class="bi bi-tag-fill text-[10px]"></i>
                        {{ activeCase.category }}
                      </span>
                      <span
                        class="inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-bold"
                        :class="impactLabel(activeCase.impact_score).cls"
                      >
                        <i class="bi bi-fire"></i>
                        ผลกระทบ: {{ impactLabel(activeCase.impact_score).label }}
                      </span>
                    </div>

                    <!-- ชื่อเรื่อง -->
                    <h3 class="mt-5 line-clamp-2 text-xl font-black leading-snug text-slate-900 sm:text-2xl">
                      {{ activeCase.title }}
                    </h3>

                    <!-- ผู้แจ้ง + หน่วยงาน -->
                    <div class="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm font-medium text-slate-500">
                      <span class="inline-flex items-center gap-1.5">
                        <i class="bi bi-person-badge text-rose-400"></i>
                        ผู้แจ้ง: {{ activeCase.reporter_mask }}
                      </span>
                      <span class="inline-flex items-center gap-1.5">
                        <i class="bi bi-building text-slate-400"></i>
                        {{ activeCase.department_in_charge }}
                      </span>
                    </div>

                    <!-- สรุปวิธีแก้ไข -->
                    <div class="mt-5 rounded-2xl border border-slate-100 bg-slate-50/80 p-4">
                      <p class="flex items-start gap-2 text-sm leading-relaxed text-slate-600">
                        <i class="bi bi-check-circle-fill mt-0.5 shrink-0 text-emerald-500"></i>
                        <span class="line-clamp-3">“{{ activeCase.solution_summary }}”</span>
                      </p>
                    </div>

                    <!-- ท้าย: เวลาปิดงาน + ระยะเวลาดำเนินการ -->
                    <div class="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4 text-xs font-semibold text-slate-500">
                      <span class="inline-flex items-center gap-1.5">
                        <i class="bi bi-check2-circle text-emerald-500"></i>
                        ปิดงานเมื่อ {{ formatThaiDate(activeCase.resolved_at) }}
                      </span>
                      <span
                        v-if="activeCase.duration_hours != null"
                        class="inline-flex items-center gap-1.5 rounded-full bg-rose-50 px-2.5 py-1 text-rose-600"
                      >
                        <i class="bi bi-stopwatch"></i>
                        ดำเนินการ {{ formatDuration(activeCase.duration_hours) }}
                      </span>
                    </div>
                  </div>
                </Transition>
              </div>

              <!-- Dot indicators (hit-area ใหญ่ขึ้นสำหรับมือถือ) -->
              <div class="mt-5 flex items-center justify-center gap-1">
                <button
                  v-for="(c, i) in resolvedCases"
                  :key="c.id"
                  @click="goToSlide(i)"
                  class="group flex h-9 w-9 items-center justify-center rounded-full transition-colors hover:bg-rose-100/70"
                  :aria-label="`ดูเรื่องที่ ${i + 1}`"
                  :aria-current="i === safeIndex ? 'true' : undefined"
                >
                  <span
                    class="block h-2.5 rounded-full transition-all duration-300"
                    :class="i === safeIndex ? 'w-7 bg-rose-600' : 'w-2.5 bg-slate-300 group-hover:bg-rose-300'"
                  ></span>
                </button>
              </div>
            </template>
          </div>
        </div>
      </section>

      <!-- 📣 =============================================== -->
      <!-- 3. DYNAMIC ANNOUNCEMENT BAR                       -->
      <!-- 📣 =============================================== -->
      <div class="relative z-10 mx-auto max-w-7xl px-4 lg:px-8">
        <!-- Skeleton ประกาศ -->
        <div
          v-if="isLoadingAnnouncements"
          class="skeleton-shimmer relative h-12 overflow-hidden rounded-2xl border border-slate-100 bg-white/70 shadow-sm"
        ></div>

        <!-- Error ประกาศ -->
        <div
          v-else-if="hasAnnouncementsError"
          class="flex h-12 items-center justify-between rounded-2xl border border-rose-100 bg-rose-50/80 px-4 shadow-sm"
        >
          <span class="inline-flex items-center gap-2 text-sm font-semibold text-rose-500">
            <i class="bi bi-exclamation-triangle-fill"></i>
            ไม่สามารถโหลดประกาศได้
          </span>
          <button
            @click="fetchAnnouncements"
            class="inline-flex min-h-[34px] items-center gap-1.5 rounded-lg bg-white px-3.5 py-2 text-xs font-bold text-rose-600 shadow-sm transition hover:bg-rose-100"
          >
            <i class="bi bi-arrow-clockwise"></i>
            ลองใหม่
          </button>
        </div>

        <!-- Marquee ประกาศ -->
        <div
          v-else-if="announcements.length > 0"
          :class="[announcementTheme.bar, 'relative overflow-hidden rounded-2xl shadow-lg shadow-rose-500/10']"
        >
          <div class="flex h-12 items-center px-3">
            <span
              class="inline-flex shrink-0 items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-black uppercase tracking-wide backdrop-blur"
              :class="announcementTheme.badge"
            >
              <i :class="['bi bi-megaphone-fill', announcementTheme.icon]"></i>
              ประกาศ
            </span>
            <div class="marquee ml-3 min-w-0 flex-1 overflow-hidden">
              <div class="marquee-track" :style="{ animationDuration: marqueeDuration }">
                <div
                  v-for="copy in 2"
                  :key="copy"
                  class="flex shrink-0 items-center"
                  :aria-hidden="copy === 2 ? 'true' : 'false'"
                >
                  <template v-for="a in announcements" :key="a.id">
                    <a
                      v-if="a.link"
                      :href="a.link"
                      :target="a.link?.startsWith('http') ? '_blank' : undefined"
                      :rel="a.link?.startsWith('http') ? 'noopener noreferrer' : undefined"
                      :class="[announcementTheme.item, 'inline-flex items-center whitespace-nowrap px-4 text-sm font-semibold transition-colors']"
                    >
                      <i class="bi bi-dot -ml-2 text-lg"></i>
                      {{ a.message }}
                      <i class="bi bi-box-arrow-up-right ml-1.5 text-[10px] opacity-70"></i>
                    </a>
                    <span
                      v-else
                      :class="[announcementTheme.item, 'inline-flex items-center whitespace-nowrap px-4 text-sm font-semibold']"
                    >
                      <i class="bi bi-dot -ml-2 text-lg"></i>
                      {{ a.message }}
                    </span>
                  </template>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 📊 =============================================== -->
      <!-- 4. LIVE STATISTICS (#stats)                        -->
      <!-- 📊 =============================================== -->
      <section id="stats" class="relative scroll-mt-20 py-20 lg:py-28">
        <div class="mx-auto max-w-7xl px-4 lg:px-8">
          <!-- Header -->
          <div class="mx-auto max-w-2xl text-center">
            <span
              class="inline-flex items-center gap-2 rounded-full border border-emerald-100 bg-emerald-50 px-3.5 py-1.5 text-xs font-black uppercase tracking-wider text-emerald-600 shadow-sm"
            >
              <span class="relative flex h-2 w-2">
                <span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75"></span>
                <span class="relative inline-flex h-2 w-2 rounded-full bg-emerald-500"></span>
              </span>
              Live · Real-time
            </span>
            <h2 class="mt-4 text-3xl font-black tracking-normal text-slate-900 sm:text-4xl">
              ผลการดำเนินงานแบบ <span class="bg-gradient-to-r from-red-600 to-rose-600 bg-clip-text text-transparent">Real-time</span>
            </h2>
            <p class="mt-4 font-medium leading-relaxed text-slate-500">
              ตัวเลขจากระบบจริง อัปเดตตลอดเวลา เพื่อให้เห็นภาพรวมว่าความเห็นของนักเรียน
              กำลังถูกเปลี่ยนให้กลายเป็นการแก้ไขจริงมากแค่ไหน
            </p>
          </div>

          <!-- Grid การ์ด -->
          <div class="mt-12">
            <!-- Skeleton -->
            <div v-if="isLoadingStats" class="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
              <div v-for="i in 5" :key="i" class="skeleton-shimmer relative overflow-hidden rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
                <div class="h-12 w-12 rounded-xl bg-slate-100"></div>
                <div class="mt-5 h-4 w-24 rounded-lg bg-slate-200"></div>
                <div class="mt-2 h-8 w-20 rounded-lg bg-slate-200"></div>
                <div class="mt-3 h-3 w-28 rounded-lg bg-slate-100"></div>
              </div>
            </div>

            <!-- Error -->
            <div v-else-if="hasStatsError && !stats" class="rounded-2xl border border-rose-100 bg-white p-10 text-center shadow-sm">
              <div class="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-rose-50 text-rose-500">
                <i class="bi bi-wifi-off text-2xl"></i>
              </div>
              <h3 class="mt-4 text-base font-bold text-slate-800">ไม่สามารถโหลดสถิติได้</h3>
              <p class="mt-1 text-sm text-slate-500">กรุณาตรวจสอบการเชื่อมต่อ หรือลองอีกครั้ง</p>
              <button
                @click="fetchStats"
                class="mt-5 inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-red-600 to-rose-600 px-5 py-2.5 text-sm font-bold text-white shadow-lg shadow-rose-500/30 transition hover:opacity-90"
              >
                <i class="bi bi-arrow-clockwise"></i>
                ลองใหม่
              </button>
            </div>

            <!-- การ์ดจริง -->
            <div
              v-else
              class="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5"
            >
              <div
                v-for="card in statCards"
                :key="card.label"
                class="group relative overflow-hidden rounded-2xl border border-slate-100 bg-white p-6 shadow-sm transition-all duration-300 hover:-translate-y-1.5 hover:border-rose-100 hover:shadow-xl hover:shadow-rose-100/60"
              >
                <!-- Glow ตามเมาส์ -->
                <div
                  class="pointer-events-none absolute -right-10 -top-10 h-28 w-28 rounded-full bg-rose-100/0 blur-2xl transition-colors duration-300 group-hover:bg-rose-100/50"
                ></div>
                <div
                  class="flex h-12 w-12 items-center justify-center rounded-xl border text-xl transition-transform duration-300 group-hover:scale-110"
                  :class="card.tint"
                >
                  <i :class="['bi', card.icon]"></i>
                </div>
                <p class="mt-5 text-sm font-semibold text-slate-500">{{ card.label }}</p>
                <p class="mt-1.5 text-3xl font-black tracking-tight text-slate-900">{{ card.value }}</p>
                <p class="mt-1.5 text-xs font-medium text-slate-400">{{ card.hint }}</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- 🪜 =============================================== -->
      <!-- 5. WORKFLOW (#flow)                                -->
      <!-- 🪜 =============================================== -->
      <section id="flow" class="relative scroll-mt-20 border-t border-slate-200/60 bg-white/70 py-20 backdrop-blur-sm lg:py-28">
        <div class="mx-auto max-w-7xl px-4 lg:px-8">
          <div class="mx-auto max-w-2xl text-center">
            <span class="inline-flex items-center gap-2 rounded-full border border-rose-100 bg-rose-50 px-3.5 py-1.5 text-xs font-black uppercase tracking-wider text-rose-600 shadow-sm">
              <i class="bi bi-diagram-3"></i>
              Escalation Pyramid
            </span>
            <h2 class="mt-4 text-3xl font-black tracking-normal text-slate-900 sm:text-4xl">
              ระบบไต่ระดับสายงานที่ชัดเจน
            </h2>
            <p class="mt-4 font-medium leading-relaxed text-slate-500">
              ทุกเรื่องมีเส้นทางดำเนินการที่โปร่งใส มีเจ้าของงานชัดเจน และไม่มีเสียงไหนถูกทิ้งไว้
            </p>
          </div>

          <!-- Steps -->
          <div class="relative mx-auto mt-16 max-w-5xl">
            <!-- เส้นเชื่อมด้านหลัง (desktop) -->
            <div
              class="absolute left-[12%] right-[12%] top-9 hidden h-[3px] rounded-full bg-gradient-to-r from-slate-200 via-rose-300 to-emerald-300 md:block"
            ></div>

            <div class="grid grid-cols-1 gap-12 md:grid-cols-4 md:gap-6">
              <div
                v-for="(step, idx) in workflowSteps"
                :key="step.title"
                class="group relative flex flex-col items-center text-center"
              >
                <!-- ไอคอนขั้นตอน -->
                <div
                  class="relative z-10 flex h-[4.5rem] w-[4.5rem] items-center justify-center rounded-2xl border-2 border-slate-200 bg-white text-3xl text-slate-400 shadow-sm transition-all duration-300 hover:-translate-y-1.5"
                  :class="step.hover"
                >
                  <i :class="['bi', step.icon]"></i>
                  <span
                    class="absolute -right-2 -top-2 flex h-7 w-7 items-center justify-center rounded-xl bg-slate-900 text-xs font-black text-white shadow-md ring-2 ring-white transition-colors group-hover:bg-rose-600"
                  >
                    {{ idx + 1 }}
                  </span>
                </div>
                <h3 class="mt-6 text-base font-bold text-slate-900">{{ step.title }}</h3>
                <p class="mt-2 max-w-[220px] text-sm leading-relaxed text-slate-500">{{ step.desc }}</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- 🚀 =============================================== -->
      <!-- 6. ECOSYSTEM (Dark) — PIRI Talk & PIRI Vote        -->
      <!-- 🚀 =============================================== -->
      <section id="ecosystem" class="relative scroll-mt-20 overflow-hidden bg-slate-900 py-20 text-white lg:py-28">
        <!-- Grid pattern -->
        <div class="bg-grid-dark pointer-events-none absolute inset-0"></div>
        <!-- Glow -->
        <div class="pointer-events-none absolute -left-24 top-10 h-[420px] w-[420px] rounded-full bg-cyan-500/20 blur-[130px] max-lg:h-[300px] max-lg:w-[300px] max-lg:blur-[90px]"></div>
        <div class="pointer-events-none absolute -right-24 bottom-0 h-[420px] w-[420px] rounded-full bg-rose-500/20 blur-[130px] max-lg:h-[300px] max-lg:w-[300px] max-lg:blur-[90px]"></div>

        <div class="relative mx-auto grid max-w-7xl grid-cols-1 items-center gap-16 px-4 lg:grid-cols-2 lg:gap-20 lg:px-8">
          <!-- ฝั่งซ้าย: คำอธิบายระบบนิเวศ -->
          <div>
            <span class="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3.5 py-1.5 text-xs font-black uppercase tracking-wider text-cyan-300 backdrop-blur">
              <i class="bi bi-asterisk"></i>
              PIRI Ecosystem
            </span>
            <h2 class="mt-5 text-3xl font-black leading-tight tracking-normal sm:text-4xl">
              มากกว่าแค่ “แจ้งปัญหา”
              <br />
              <span class="bg-gradient-to-r from-cyan-400 via-sky-400 to-rose-400 bg-clip-text text-transparent">
                ขับเคลื่อนด้วยเสียงของนักเรียน
              </span>
            </h2>
            <p class="mt-5 max-w-lg font-medium leading-relaxed text-slate-400">
              PIRIvoice ไม่ใช่แค่ระบบร้องเรียน — คือระบบนิเวศที่เปิดพื้นที่ให้ทุกคนมีส่วนร่วม
              ทั้งเสนอ วิพากษ์ และตัดสินใจร่วมกันบนข้อมูลที่โปร่งใส
            </p>

            <!-- PIRI Talk -->
            <div class="group mt-8 flex gap-4 rounded-2xl border border-white/10 bg-white/[0.03] p-5 backdrop-blur transition-all duration-300 hover:border-cyan-400/40 hover:bg-white/[0.06]">
              <div class="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-cyan-400/20 bg-cyan-500/10 text-xl text-cyan-300">
                <i class="bi bi-chat-dots-fill"></i>
              </div>
              <div>
                <h3 class="flex flex-wrap items-center gap-2 text-base font-bold">
                  PIRI Talk
                  <span class="rounded-full border border-cyan-400/20 bg-cyan-500/10 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-cyan-300">กระดานสนทนาสาธารณะ</span>
                </h3>
                <p class="mt-1.5 text-sm leading-relaxed text-slate-400">
                  พื้นที่พูดคุย แลกเปลี่ยนความเห็น และโหวตเห็นด้วยกับข้อเสนอของเพื่อนๆ
                  ทีมสภานักเรียนคอยกลั่นกรองเนื้อหาให้พื้นที่ปลอดภัยและสร้างสรรค์
                </p>
              </div>
            </div>

            <!-- PIRI Vote -->
            <div class="group mt-4 flex gap-4 rounded-2xl border border-white/10 bg-white/[0.03] p-5 backdrop-blur transition-all duration-300 hover:border-rose-400/40 hover:bg-white/[0.06]">
              <div class="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-rose-400/20 bg-rose-500/10 text-xl text-rose-300">
                <i class="bi bi-patch-check-fill"></i>
              </div>
              <div>
                <h3 class="flex flex-wrap items-center gap-2 text-base font-bold">
                  PIRI Vote
                  <span class="rounded-full border border-rose-400/20 bg-rose-500/10 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-rose-300">ระบบฉันทามติ</span>
                </h3>
                <p class="mt-1.5 text-sm leading-relaxed text-slate-400">
                  ลงคะแนนเสียงเห็นด้วยต่อประเด็นหรือข้อเสนอต่าง ๆ ให้คนส่วนใหญ่ตัดสินใจร่วมกัน
                  ผลโหวตสะท้อนเป็นข้อมูลจริงบน Dashboard อย่างโปร่งใส
                </p>
              </div>
            </div>
          </div>

          <!-- ฝั่งขวา: Mockup Dashboard แบบ High-tech -->
          <div class="relative mx-auto w-full max-w-[520px]">
            <div class="absolute -inset-10 rounded-[3rem] bg-gradient-to-tr from-cyan-500/25 via-transparent to-rose-500/25 blur-3xl"></div>

            <div class="relative overflow-hidden rounded-2xl border border-white/10 bg-slate-900/80 shadow-2xl backdrop-blur-xl">
              <!-- Title bar -->
              <div class="flex items-center gap-2 border-b border-white/10 bg-white/[0.03] px-4 py-3">
                <span class="h-3 w-3 rounded-full bg-red-400/80"></span>
                <span class="h-3 w-3 rounded-full bg-amber-400/80"></span>
                <span class="h-3 w-3 rounded-full bg-emerald-400/80"></span>
                <span class="ml-3 inline-flex items-center gap-1.5 text-[11px] font-semibold text-slate-400">
                  <i class="bi bi-graph-up text-cyan-400"></i>
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
                  <span class="flex h-9 w-9 items-center justify-center rounded-xl border border-cyan-400/30 bg-cyan-500/15 text-sm text-cyan-300"><i class="bi bi-grid-1x2"></i></span>
                  <span class="flex h-9 w-9 items-center justify-center rounded-xl text-sm text-slate-500 transition-colors hover:bg-white/5 hover:text-slate-300"><i class="bi bi-inbox"></i></span>
                  <span class="flex h-9 w-9 items-center justify-center rounded-xl text-sm text-slate-500 transition-colors hover:bg-white/5 hover:text-slate-300"><i class="bi bi-bar-chart"></i></span>
                  <span class="flex h-9 w-9 items-center justify-center rounded-xl text-sm text-slate-500 transition-colors hover:bg-white/5 hover:text-slate-300"><i class="bi bi-people"></i></span>
                  <span class="flex h-9 w-9 items-center justify-center rounded-xl text-sm text-slate-500 transition-colors hover:bg-white/5 hover:text-slate-300"><i class="bi bi-gear"></i></span>
                </div>

                <!-- Main -->
                <div class="flex-1 p-4 sm:p-5">
                  <!-- Stat chips -->
                  <div class="grid grid-cols-3 gap-2">
                    <div class="rounded-xl border border-white/10 bg-white/[0.03] p-2.5">
                      <p class="text-[10px] font-semibold text-slate-500">เรื่องทั้งหมด</p>
                      <p class="mt-0.5 text-base font-black text-white">2,4xx</p>
                    </div>
                    <div class="rounded-xl border border-white/10 bg-white/[0.03] p-2.5">
                      <p class="text-[10px] font-semibold text-slate-500">อัตราสำเร็จ</p>
                      <p class="mt-0.5 text-base font-black text-emerald-400">92%</p>
                    </div>
                    <div class="rounded-xl border border-white/10 bg-white/[0.03] p-2.5">
                      <p class="text-[10px] font-semibold text-slate-500">เสียงโหวต</p>
                      <p class="mt-0.5 text-base font-black text-cyan-400">8.1k</p>
                    </div>
                  </div>

                  <!-- Chart -->
                  <div class="mt-3 rounded-xl border border-white/10 bg-white/[0.03] p-3">
                    <div class="flex items-center justify-between text-[11px] font-semibold text-slate-400">
                      <span class="inline-flex items-center gap-1.5"><i class="bi bi-activity text-cyan-400"></i> ภาพรวมการแก้ไขปัญหา</span>
                      <span class="inline-flex items-center gap-1 text-emerald-400"><i class="bi bi-arrow-up-right"></i> +23%</span>
                    </div>
                    <div class="mt-3 flex h-24 items-end gap-1.5">
                      <div
                        v-for="(h, i) in chartHeights"
                        :key="i"
                        class="mock-bar flex-1 rounded-t-md"
                        :class="i % 2 === 0 ? 'bg-gradient-to-t from-cyan-600 to-cyan-400' : 'bg-gradient-to-t from-rose-600 to-rose-400'"
                        :style="{ height: h + '%', animationDelay: i * 70 + 'ms' }"
                      ></div>
                    </div>
                  </div>

                  <!-- Row ล่าสุด -->
                  <div class="mt-3 flex items-center justify-between rounded-xl border border-white/10 bg-white/[0.03] p-3">
                    <div class="flex items-center gap-2.5">
                      <span class="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-400"><i class="bi bi-check2"></i></span>
                      <div>
                        <p class="text-[11px] font-bold text-slate-200">ปิดงานล่าสุด 4 รายการ</p>
                        <p class="text-[10px] text-slate-500">ห้องน้ำหญิง ชั้น 2 · แอร์ห้องประชุม</p>
                      </div>
                    </div>
                    <i class="bi bi-chevron-right text-slate-500"></i>
                  </div>
                </div>
              </div>
            </div>

            <!-- Floating card: เรื่องที่ปิดสำเร็จ -->
            <div class="animate-float absolute -right-3 -top-5 flex items-center gap-2 rounded-xl border border-white/15 bg-slate-800/90 px-3.5 py-2.5 text-xs font-bold text-slate-100 shadow-2xl backdrop-blur">
              <span class="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-500/15 text-emerald-400"><i class="bi bi-check-circle-fill"></i></span>
              1,2xx เรื่องที่แก้ไขสำเร็จ
            </div>
            <!-- Floating card: เสียงโหวตใหม่ -->
            <div class="animate-float animation-delay-1500 absolute -bottom-5 -left-3 flex items-center gap-2 rounded-xl border border-white/15 bg-slate-800/90 px-3.5 py-2.5 text-xs font-bold text-slate-100 shadow-2xl backdrop-blur">
              <span class="flex h-7 w-7 items-center justify-center rounded-lg bg-rose-500/15 text-rose-400"><i class="bi bi-people-fill"></i></span>
              3 เสียงใหม่บน PIRI Vote
            </div>
          </div>
        </div>
      </section>
    </main>

    <!-- 🦶 =============================================== -->
    <!-- 7. FOOTER                                          -->
    <!-- 🦶 =============================================== -->
    <footer class="relative border-t border-slate-200 bg-white">
      <div class="mx-auto max-w-7xl px-4 py-12 lg:px-8">
        <div class="flex flex-col items-center gap-4 text-center">
          <div class="flex items-center gap-3">
            <img src="/logos/council-logo.png" alt="โลโก้สภานักเรียน" class="h-12 w-12 object-contain opacity-60 grayscale" />
            <div class="h-10 w-px bg-slate-200"></div>
            <img src="/logos/school-logo.png" alt="โลโก้โรงเรียน" class="h-12 w-12 object-contain opacity-60 grayscale" />
          </div>
          <div>
            <p class="text-lg font-black tracking-tight text-slate-800">
              PIRI<span class="bg-gradient-to-r from-red-600 to-rose-600 bg-clip-text text-transparent">voice</span>
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
            class="group inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-slate-500 transition-colors hover:bg-rose-50 hover:text-rose-600"
          >
            <i class="bi bi-code-slash text-sm opacity-70"></i>
            Core System Architect &amp; Developed by
            <span class="font-bold underline decoration-rose-200 decoration-2 underline-offset-2 group-hover:decoration-rose-400">
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

/* Blob — วงกลมพื้นหลังลอย */
@keyframes blob {
  0% {
    transform: translate(0px, 0px) scale(1);
  }
  33% {
    transform: translate(30px, -50px) scale(1.05);
  }
  66% {
    transform: translate(-20px, 20px) scale(0.95);
  }
  100% {
    transform: translate(0px, 0px) scale(1);
  }
}

/* Float — การ์ดลอยเบา ๆ */
@keyframes float {
  0%,
  100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-12px);
  }
}

/* Marquee — ข้อความประกาศวิ่ง */
@keyframes marquee {
  from {
    transform: translateX(0);
  }
  to {
    transform: translateX(-50%);
  }
}

/* Bar chart — กราฟแท่งค่อย ๆ โผล่ (mockup) */
@keyframes growBar {
  from {
    transform: scaleY(0);
  }
  to {
    transform: scaleY(1);
  }
}

/* Fade-in หน้า */
@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

/* Slide-up + fade */
@keyframes slideUpFade {
  from {
    opacity: 0;
    transform: translateY(20px) scale(0.98);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.animate-blob {
  animation: blob 15s infinite alternate ease-in-out;
}
.animate-float {
  animation: float 6s ease-in-out infinite;
}
.animation-delay-2000 {
  animation-delay: 2s;
}
.animation-delay-4000 {
  animation-delay: 4s;
}
.animation-delay-1500 {
  animation-delay: 1.5s;
}
.animate-fade-in {
  animation: fadeIn 0.8s ease-out forwards;
}
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
 * Mock bar chart
 * ============================================================ */
.mock-bar {
  transform-origin: bottom;
  animation: growBar 1s cubic-bezier(0.16, 1, 0.3, 1) both;
}

/* ============================================================
 * Carousel transition — crossfade เฉพาะ opacity
 * (slide วาง absolute + ความสูงคงที่ → ไม่ blank flash / ไม่กระโดด)
 * ============================================================ */
.case-enter-active,
.case-leave-active {
  transition: opacity 0.5s ease;
}
.case-enter-from,
.case-leave-to {
  opacity: 0;
}

/* ============================================================
 * Skeleton — shimmer sweep (สวยกว่า opacity pulse)
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
  100% {
    transform: translateX(100%);
  }
}

/* ============================================================
 * Mobile menu drop
 * ============================================================ */
.menu-drop-enter-active,
.menu-drop-leave-active {
  transition:
    opacity 0.22s ease,
    transform 0.22s ease;
}
.menu-drop-enter-from,
.menu-drop-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

/* ============================================================
 * Dark ecosystem — grid pattern
 * ============================================================ */
.bg-grid-dark {
  background-image:
    linear-gradient(rgba(148, 163, 184, 0.07) 1px, transparent 1px),
    linear-gradient(90deg, rgba(148, 163, 184, 0.07) 1px, transparent 1px);
  background-size: 44px 44px;
  -webkit-mask-image: radial-gradient(ellipse 80% 70% at 50% 40%, black, transparent);
  mask-image: radial-gradient(ellipse 80% 70% at 50% 40%, black, transparent);
}

/* ============================================================
 * Accessibility — เคารพผู้ที่ปิดแอนิเมชัน
 * ============================================================ */
@media (prefers-reduced-motion: reduce) {
  .animate-blob,
  .animate-float,
  .animate-slide-up-fade,
  .animate-fade-in,
  .marquee-track,
  .mock-bar,
  .animate-ping,
  .animate-spin,
  .animate-pulse,
  .skeleton-shimmer::after {
    animation: none !important;
  }
  .animate-blob,
  .animate-float,
  .animate-slide-up-fade,
  .animate-fade-in,
  .skeleton-shimmer {
    opacity: 1 !important;
  }
  .case-enter-active,
  .case-leave-active,
  .menu-drop-enter-active,
  .menu-drop-leave-active {
    transition: none !important;
    opacity: 1 !important;
    transform: none !important;
  }
}

/* ============================================================
 * Keyboard focus — ring แดงตามธีม (เดิมไม่มี focus-visible)
 * ============================================================ */
button:focus-visible,
a:focus-visible {
  outline: 2px solid rgba(225, 29, 72, 0.65);
  outline-offset: 2px;
}
</style>
