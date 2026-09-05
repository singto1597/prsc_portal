<!-- eslint-disable vue/multi-word-component-names -->
<script setup lang="ts">
/**
 * 🏠 Landing.vue — PIRIvoice (Redesigned)
 * เสียงจากชาวพิริยาลัย · สภานักเรียน โรงเรียนพิริยาลัยจังหวัดแพร่
 * 
 * Design Concept: "Transparent, Minimal, and Human-Centric"
 * เน้นความสะอาดตา ข้อมูลชัดเจน ไม่ใช้เอฟเฟกต์ 3D ที่ดูปลอม 
 * ให้ความรู้สึกถึงแพลตฟอร์มที่โปร่งใสและพึ่งพาได้จริงๆ
 */
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue';
import { useRouter } from 'vue-router';
import api from '@/services/api';

/* ============================================================
 * 📐 TypeScript Interfaces
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
 * 🗂️ State Management
 * ============================================================ */
const router = useRouter();

const stats = ref<SystemStats | null>(null);
const statsTrend = ref<StatTrendPoint[]>([]);
const resolvedCases = ref<ResolvedCase[]>([]);
const announcements = ref<Announcement[]>([]);

const isLoading = ref({
  stats: true,
  trend: true,
  cases: true,
  announcements: true,
});

const errors = ref({
  stats: false,
  trend: false,
  cases: false,
  announcements: false,
});

const isScrolled = ref(false);
const statsGridRef = ref<HTMLElement | null>(null);

/* ============================================================
 * 📡 API Fetching
 * ============================================================ */
async function fetchStats() {
  isLoading.value.stats = true; errors.value.stats = false;
  try {
    stats.value = (await api.get('/api/v1/public/stats')) as SystemStats;
  } catch { errors.value.stats = true; } 
  finally { isLoading.value.stats = false; }
}

async function fetchStatsTrend() {
  isLoading.value.trend = true; errors.value.trend = false;
  try {
    const res = await api.get('/api/v1/public/stats/trend', { params: { days: 14 } });
    statsTrend.value = Array.isArray(res) ? res : [];
  } catch { errors.value.trend = true; } 
  finally { isLoading.value.trend = false; }
}

async function fetchResolvedCases() {
  isLoading.value.cases = true; errors.value.cases = false;
  try {
    const res = await api.get('/api/v1/public/resolved-cases', { params: { limit: 6 } });
    resolvedCases.value = Array.isArray(res) ? res : [];
  } catch { errors.value.cases = true; } 
  finally { isLoading.value.cases = false; }
}

async function fetchAnnouncements() {
  isLoading.value.announcements = true; errors.value.announcements = false;
  try {
    const res = await api.get('/api/v1/public/announcements');
    announcements.value = Array.isArray(res) ? res : [];
  } catch { errors.value.announcements = true; } 
  finally { isLoading.value.announcements = false; }
}

/* ============================================================
 * 🛠️ Helpers
 * ============================================================ */
function prefersReducedMotion() {
  return typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

const goLogin = () => router.push({ name: 'login' });

function scrollToId(id: string) {
  document.getElementById(id)?.scrollIntoView({
    behavior: prefersReducedMotion() ? 'auto' : 'smooth',
    block: 'start'
  });
}

function formatThaiDate(iso: string) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat('th-TH', { day: 'numeric', month: 'short', year: 'numeric' }).format(d);
}

function formatStatValue(v: number, decimals = 0) {
  const factor = 10 ** decimals;
  const rounded = Math.round((v ?? 0) * factor) / factor;
  return new Intl.NumberFormat('th-TH', { minimumFractionDigits: decimals, maximumFractionDigits: decimals }).format(rounded);
}

// Number Animation (Smoother logic)
function animateStatNumbers(container: HTMLElement) {
  if (prefersReducedMotion()) return;
  const els = container.querySelectorAll<HTMLElement>('[data-target]');
  
  els.forEach((el) => {
    const target = parseFloat(el.dataset.target ?? '0');
    const decimals = parseInt(el.dataset.decimals ?? '0', 10);
    const duration = 1500;
    const start = performance.now();
    
    const step = (now: number) => {
      const p = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - p, 4); // Quartic ease out
      el.textContent = formatStatValue(target * eased, decimals);
      if (p < 1) requestAnimationFrame(step);
      else el.textContent = formatStatValue(target, decimals);
    };
    requestAnimationFrame(step);
  });
}

/* ============================================================
 * 📊 Computed Properties
 * ============================================================ */
const heroAnnouncement = computed(() => announcements.value[0] ?? null);

const workflowSteps = [
  { id: '01', title: 'รับเรื่อง', desc: 'แจ้งปัญหาผ่านระบบออนไลน์ตลอด 24 ชม. เลือกไม่ประสงค์ออกนามได้', icon: 'bi-inbox' },
  { id: '02', title: 'ตรวจสอบ', desc: 'ตัวแทนห้องเรียนคัดกรองปัญหาและประเมินระดับความเร่งด่วน', icon: 'bi-search' },
  { id: '03', title: 'ส่งต่อ', desc: 'ส่งตรงถึงประธานระดับ หรือสภานักเรียน ตามสายงานที่ถูกต้อง', icon: 'bi-diagram-3' },
  { id: '04', title: 'แก้ไข', desc: 'ประสานงานกับคณะครู ติดตามผล และอัปเดตสถานะแบบเรียลไทม์', icon: 'bi-check-circle' },
];

/* ============================================================
 * 🔄 Lifecycle
 * ============================================================ */
const onScroll = () => { isScrolled.value = window.scrollY > 10; };

onMounted(() => {
  fetchStats(); fetchStatsTrend(); fetchResolvedCases(); fetchAnnouncements();
  window.addEventListener('scroll', onScroll, { passive: true });
});

onBeforeUnmount(() => window.removeEventListener('scroll', onScroll));

watch(() => isLoading.value.stats, (loading) => {
  if (!loading) nextTick(() => { if (statsGridRef.value) animateStatNumbers(statsGridRef.value); });
});
</script>

<template>
  <div class="min-h-screen bg-[#FAFAFA] font-sans text-slate-900 selection:bg-rose-200 selection:text-rose-900">
    
    <!-- 🌟 NAVBAR (Clean & Minimal) -->
    <header 
      class="fixed top-0 inset-x-0 z-50 transition-all duration-300 border-b"
      :class="isScrolled ? 'bg-white/85 backdrop-blur-lg border-slate-200 shadow-sm' : 'bg-transparent border-transparent'"
    >
      <div class="mx-auto flex h-16 max-w-7xl items-center justify-between px-6 lg:px-8">
        <div class="flex items-center gap-3 cursor-pointer" @click="scrollToId('hero')">
          <div class="flex -space-x-2">
            <img src="/logos/school-logo.png" class="h-8 w-8 rounded-full border-2 border-white bg-white object-cover shadow-sm" />
            <img src="/logos/council-logo.png" class="h-8 w-8 rounded-full border-2 border-white bg-white object-cover shadow-sm" />
          </div>
          <span class="text-lg font-bold tracking-tight text-slate-900">
            PIRI<span class="text-rose-600">voice</span>
          </span>
        </div>

        <nav class="hidden md:flex items-center gap-8">
          <button @click="scrollToId('stats')" class="text-sm font-medium text-slate-500 hover:text-slate-900 transition-colors">สถิติ</button>
          <button @click="scrollToId('flow')" class="text-sm font-medium text-slate-500 hover:text-slate-900 transition-colors">ขั้นตอนการทำงาน</button>
          <button @click="scrollToId('impact')" class="text-sm font-medium text-slate-500 hover:text-slate-900 transition-colors">ผลลัพธ์</button>
        </nav>

        <button @click="goLogin" class="rounded-full bg-slate-900 px-5 py-2 text-sm font-semibold text-white transition-all hover:bg-slate-800 hover:scale-105 active:scale-95">
          เข้าสู่ระบบ
        </button>
      </div>
    </header>

    <main class="relative pt-16">
      
      <!-- 🚀 HERO SECTION (Typography Focus, No 3D Gimmicks) -->
      <section id="hero" class="relative pt-24 pb-32 overflow-hidden">
        <!-- Subtle Glow Background -->
        <div class="absolute inset-0 z-0 flex justify-center opacity-40 pointer-events-none">
          <div class="w-[800px] h-[500px] bg-rose-100 rounded-full blur-3xl -translate-y-32"></div>
        </div>

        <div class="relative z-10 mx-auto max-w-7xl px-6 lg:px-8 text-center">
          
          <!-- Announcement (Elegant Pill) -->
          <div class="flex justify-center mb-8 h-8">
            <div v-if="isLoading.announcements" class="w-64 h-8 bg-slate-200/50 rounded-full animate-pulse"></div>
            <button v-else-if="heroAnnouncement" class="group flex items-center gap-2 rounded-full bg-white px-3 py-1.5 text-xs font-medium text-slate-600 shadow-sm ring-1 ring-slate-200 hover:bg-slate-50 transition-all">
              <span class="flex h-2 w-2 rounded-full" :class="heroAnnouncement.priority === 'urgent' ? 'bg-rose-500' : 'bg-emerald-500'"></span>
              <span class="truncate max-w-[250px] sm:max-w-md">{{ heroAnnouncement.message }}</span>
              <i class="bi bi-arrow-right text-slate-400 group-hover:translate-x-1 transition-transform"></i>
            </button>
          </div>

          <h1 class="text-4xl sm:text-6xl lg:text-7xl font-bold tracking-tight text-slate-900 leading-[1.1]">
            ส่งเสียงของคุณ <br class="hidden sm:block" />
            <span class="text-transparent bg-clip-text bg-gradient-to-r from-rose-500 to-orange-400">
              เพื่อเปลี่ยนพิริยาลัยให้ดีกว่า
            </span>
          </h1>
          
          <p class="mt-6 mx-auto max-w-2xl text-lg text-slate-500 font-light leading-relaxed">
            แพลตฟอร์มรับฟังข้อคิดเห็นของนักเรียนอย่างเป็นทางการ แจ้งปัญหาง่าย ติดตามสถานะโปร่งใส 
            ปกปิดตัวตนได้ บริหารจัดการโดยสภานักเรียนโรงเรียนพิริยาลัย
          </p>

          <div class="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
            <button @click="goLogin" class="w-full sm:w-auto rounded-full bg-rose-600 px-8 py-3.5 text-base font-semibold text-white shadow-lg shadow-rose-500/30 hover:bg-rose-500 transition-all active:scale-95">
              แจ้งเรื่องเลยตอนนี้
            </button>
            <button @click="scrollToId('stats')" class="w-full sm:w-auto flex items-center justify-center gap-2 rounded-full bg-white px-8 py-3.5 text-base font-semibold text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50 transition-all active:scale-95">
              <i class="bi bi-bar-chart"></i> ดูสถิติการแก้ไข
            </button>
          </div>

          <!-- Trust Indicators -->
          <div class="mt-16 flex flex-wrap justify-center gap-8 text-sm font-medium text-slate-400">
            <div class="flex items-center gap-2"><i class="bi bi-shield-check text-lg text-emerald-500"></i> โปร่งใสตรวจสอบได้</div>
            <div class="flex items-center gap-2"><i class="bi bi-incognito text-lg text-indigo-500"></i> รองรับการปกปิดตัวตน</div>
            <div class="flex items-center gap-2"><i class="bi bi-lightning-charge text-lg text-amber-500"></i> ส่งตรงถึงผู้รับผิดชอบ</div>
          </div>
        </div>
      </section>

      <!-- 📊 STATS (Clean Bento Layout) -->
      <section id="stats" class="py-24 bg-white border-y border-slate-100">
        <div class="mx-auto max-w-7xl px-6 lg:px-8">
          
          <div class="mb-12">
            <h2 class="text-3xl font-bold tracking-tight text-slate-900">สถานะการดำเนินงาน</h2>
            <p class="mt-2 text-slate-500">ตัวเลขจริงจากระบบ เพื่อให้ทุกคนเห็นความคืบหน้าของทุกเสียงสะท้อน</p>
          </div>

          <div v-if="isLoading.stats" class="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
            <div v-for="i in 4" :key="i" class="h-32 bg-slate-50 rounded-2xl border border-slate-100 animate-pulse"></div>
          </div>

          <div v-else-if="stats" ref="statsGridRef" class="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
            <!-- Stat 1 -->
            <div class="bg-[#FAFAFA] rounded-3xl p-6 border border-slate-100 flex flex-col justify-between">
              <div class="flex items-center gap-3 text-slate-500 mb-6">
                <i class="bi bi-inbox p-2 bg-white rounded-xl shadow-sm"></i>
                <span class="text-sm font-medium">เรื่องทั้งหมดที่ได้รับ</span>
              </div>
              <div class="text-5xl font-bold text-slate-900" :data-target="stats.total_issues">{{ stats.total_issues }}</div>
            </div>
            
            <!-- Stat 2 -->
            <div class="bg-[#FAFAFA] rounded-3xl p-6 border border-slate-100 flex flex-col justify-between">
              <div class="flex items-center gap-3 text-slate-500 mb-6">
                <i class="bi bi-check2-circle p-2 bg-emerald-50 text-emerald-600 rounded-xl shadow-sm"></i>
                <span class="text-sm font-medium">แก้ไขสำเร็จแล้ว</span>
              </div>
              <div class="flex items-baseline gap-2">
                <div class="text-5xl font-bold text-slate-900" :data-target="stats.resolved_issues">{{ stats.resolved_issues }}</div>
                <div class="text-sm font-medium text-emerald-500 bg-emerald-50 px-2 py-1 rounded-full">{{ stats.resolved_rate_percent }}%</div>
              </div>
            </div>

            <!-- Stat 3 -->
            <div class="bg-[#FAFAFA] rounded-3xl p-6 border border-slate-100 flex flex-col justify-between">
              <div class="flex items-center gap-3 text-slate-500 mb-6">
                <i class="bi bi-hourglass-split p-2 bg-amber-50 text-amber-600 rounded-xl shadow-sm"></i>
                <span class="text-sm font-medium">กำลังดำเนินการ</span>
              </div>
              <div class="text-5xl font-bold text-slate-900" :data-target="stats.routed_issues">{{ stats.routed_issues }}</div>
            </div>

            <!-- Stat 4 -->
            <div class="bg-[#FAFAFA] rounded-3xl p-6 border border-slate-100 flex flex-col justify-between">
              <div class="flex items-center gap-3 text-slate-500 mb-6">
                <i class="bi bi-chat-text p-2 bg-blue-50 text-blue-600 rounded-xl shadow-sm"></i>
                <span class="text-sm font-medium">กระทู้ PIRI Talk Active</span>
              </div>
              <div class="text-5xl font-bold text-slate-900" :data-target="stats.active_talk_threads">{{ stats.active_talk_threads }}</div>
            </div>
          </div>
        </div>
      </section>

      <!-- 🪜 WORKFLOW (Elegant Linear Stepper) -->
      <section id="flow" class="py-24">
        <div class="mx-auto max-w-7xl px-6 lg:px-8">
          
          <div class="text-center max-w-2xl mx-auto mb-16">
            <h2 class="text-3xl font-bold tracking-tight text-slate-900">เส้นทางของทุกเสียงสะท้อน</h2>
            <p class="mt-4 text-slate-500 text-lg">
              ระบบออกแบบให้มีการไต่ระดับ (Escalation) เป็นทอดๆ เพื่อให้มั่นใจว่าปัญหาจะถึงมือผู้ที่มีอำนาจจัดการโดยตรง
            </p>
          </div>

          <div class="grid md:grid-cols-4 gap-8 relative">
            <!-- Line connecting steps (Desktop) -->
            <div class="hidden md:block absolute top-8 left-[10%] right-[10%] h-0.5 bg-slate-200 z-0"></div>
            
            <div v-for="step in workflowSteps" :key="step.id" class="relative z-10 flex flex-col items-center text-center">
              <div class="w-16 h-16 bg-white rounded-2xl border border-slate-200 shadow-sm flex items-center justify-center text-2xl text-slate-700 mb-6">
                <i :class="['bi', step.icon]"></i>
              </div>
              <div class="text-xs font-bold text-rose-500 tracking-widest mb-2">STEP {{ step.id }}</div>
              <h3 class="text-lg font-bold text-slate-900 mb-2">{{ step.title }}</h3>
              <p class="text-sm text-slate-500">{{ step.desc }}</p>
            </div>
          </div>
        </div>
      </section>

      <!-- 💥 IMPACT / RESOLVED CASES (Masonry / Clean Cards) -->
      <section id="impact" class="py-24 bg-white border-t border-slate-100">
        <div class="mx-auto max-w-7xl px-6 lg:px-8">
          
          <div class="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-12">
            <div>
              <h2 class="text-3xl font-bold tracking-tight text-slate-900">ผลลัพธ์ที่เกิดขึ้นจริง</h2>
              <p class="mt-2 text-slate-500">ตัวอย่างเรื่องราวที่ได้รับการแก้ไขผ่านระบบของเรา</p>
            </div>
            <button @click="goLogin" class="text-sm font-semibold text-rose-600 hover:text-rose-700">ดูเรื่องทั้งหมด <i class="bi bi-arrow-right"></i></button>
          </div>

          <div v-if="isLoading.cases" class="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            <div v-for="i in 3" :key="i" class="h-48 bg-slate-50 rounded-3xl border border-slate-100 animate-pulse"></div>
          </div>

          <div v-else-if="resolvedCases.length === 0" class="text-center py-20 bg-slate-50 rounded-3xl border border-slate-200 border-dashed">
            <i class="bi bi-inbox text-4xl text-slate-300 mb-4 block"></i>
            <p class="text-slate-500">ยังไม่มีประวัติการแก้ไขสำเร็จ</p>
          </div>

          <div v-else class="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            <div v-for="c in resolvedCases" :key="c.id" class="group bg-[#FAFAFA] rounded-3xl p-6 border border-slate-100 hover:border-slate-300 transition-colors flex flex-col">
              <div class="flex items-center justify-between mb-4">
                <span class="px-3 py-1 bg-white border border-slate-200 rounded-full text-xs font-medium text-slate-600 shadow-sm">{{ c.category }}</span>
                <span class="text-xs text-slate-400"><i class="bi bi-calendar-check"></i> {{ formatThaiDate(c.resolved_at) }}</span>
              </div>
              <h3 class="text-base font-bold text-slate-900 mb-3 line-clamp-2">"{{ c.title }}"</h3>
              <div class="bg-emerald-50 text-emerald-800 rounded-2xl p-4 text-sm mt-auto">
                <div class="font-bold text-emerald-600 text-xs mb-1 uppercase tracking-wider">ผลการแก้ไข</div>
                <p class="line-clamp-3">{{ c.solution_summary }}</p>
              </div>
              <div class="flex items-center justify-between mt-4 pt-4 border-t border-slate-200/60 text-xs text-slate-500">
                <span class="flex items-center gap-1.5"><i class="bi bi-person-circle text-slate-400"></i> {{ c.reporter_mask }}</span>
                <span class="flex items-center gap-1.5"><i class="bi bi-building text-slate-400"></i> {{ c.department_in_charge }}</span>
              </div>
            </div>
          </div>

        </div>
      </section>

      <!-- 🚀 ECOSYSTEM (Unified Light/Gray Tone, Soft & Clean) -->
      <section id="ecosystem" class="py-24 bg-slate-900 text-white rounded-t-[3rem] mt-12 mx-2 sm:mx-6 lg:mx-8 mb-6 relative overflow-hidden">
        <!-- Abstract gradient mesh inside the dark card -->
        <div class="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-slate-800 via-slate-900 to-slate-950"></div>
        
        <div class="relative z-10 mx-auto max-w-5xl px-6 text-center">
          <h2 class="text-3xl sm:text-5xl font-bold tracking-tight mb-6">ไม่ใช่แค่พื้นที่รับเรื่องร้องเรียน</h2>
          <p class="text-lg text-slate-400 max-w-2xl mx-auto mb-16">
            PIRIvoice มาพร้อมเครื่องมือที่ช่วยสร้างวัฒนธรรมการมีส่วนร่วมในโรงเรียน 
            เปลี่ยนทุกเสียงให้เป็นพลังในการตัดสินใจร่วมกัน
          </p>

          <div class="grid md:grid-cols-2 gap-6 text-left">
            <!-- PIRI Talk -->
            <div class="bg-white/5 border border-white/10 rounded-3xl p-8 backdrop-blur-md">
              <div class="w-12 h-12 bg-blue-500/20 text-blue-400 rounded-2xl flex items-center justify-center text-2xl mb-6">
                <i class="bi bi-chat-quote-fill"></i>
              </div>
              <h3 class="text-xl font-bold mb-3">PIRI Talk</h3>
              <p class="text-slate-400 leading-relaxed">
                เวทีสนทนาสาธารณะ (Forum) เปิดโอกาสให้นักเรียนตั้งกระทู้ เสนอไอเดีย 
                และถกเถียงประเด็นต่างๆ อย่างสร้างสรรค์ ภายใต้การดูแลเนื้อหาโดยสภานักเรียน
              </p>
            </div>
            
            <!-- PIRI Vote -->
            <div class="bg-white/5 border border-white/10 rounded-3xl p-8 backdrop-blur-md">
              <div class="w-12 h-12 bg-rose-500/20 text-rose-400 rounded-2xl flex items-center justify-center text-2xl mb-6">
                <i class="bi bi-bar-chart-steps"></i>
              </div>
              <h3 class="text-xl font-bold mb-3">PIRI Vote</h3>
              <p class="text-slate-400 leading-relaxed">
                ระบบลงคะแนนเสียงออนไลน์ เพื่อหาฉันทามติในประเด็นสำคัญของโรงเรียน 
                นำเสียงส่วนใหญ่มาประกอบการผลักดันนโยบายอย่างเป็นรูปธรรม
              </p>
            </div>
          </div>

          <div class="mt-16">
            <button @click="goLogin" class="rounded-full bg-white text-slate-900 px-8 py-4 text-base font-bold shadow-lg hover:bg-slate-100 hover:scale-105 transition-all active:scale-95">
              เริ่มต้นใช้งานแพลตฟอร์ม <i class="bi bi-arrow-right ml-2"></i>
            </button>
          </div>
        </div>
      </section>

    </main>

    <!-- 🦶 FOOTER (Minimalist) -->
    <footer class="bg-[#FAFAFA] pt-12 pb-8 border-t border-slate-200">
      <div class="mx-auto max-w-7xl px-6 lg:px-8 flex flex-col md:flex-row justify-between items-center gap-6 text-sm text-slate-500">
        <div class="flex items-center gap-3">
          <img src="/logos/council-logo.png" class="h-6 w-6 grayscale opacity-60" />
          <span class="font-medium">สภานักเรียน โรงเรียนพิริยาลัยจังหวัดแพร่</span>
        </div>
        
        <div class="flex items-center gap-4">
          <span>&copy; 2026 PIRIvoice Platform.</span>
          <span class="w-1 h-1 bg-slate-300 rounded-full"></span>
          <a href="https://www.singto1597.xyz/" target="_blank" rel="noopener" class="hover:text-slate-900 transition-colors flex items-center gap-1.5 font-medium">
            <i class="bi bi-code-slash"></i> พัฒนพล สุธรรม (Developer)
          </a>
        </div>
      </div>
    </footer>
  </div>
</template>

<style scoped>
/* ลดความซับซ้อนของ CSS เดิมทิ้งไป เน้น Standard Tailwind Class แทน */
/* เพิ่มแค่ Smooth Scroll และซ่อน Scrollbar */

html {
  scroll-behavior: smooth;
}

::-webkit-scrollbar {
  width: 8px;
}
::-webkit-scrollbar-track {
  background: #FAFAFA;
}
::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 4px;
}
::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}
</style>