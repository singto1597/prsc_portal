<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue';
import { RouterView, RouterLink, useRouter, useRoute } from 'vue-router';
import Swal from 'sweetalert2';
import { useAuthStore } from '@/stores/auth';
import { useNotificationsStore } from '@/stores/notifications';
import PlaybookSidebarMenu from '@/components/playbooks/PlaybookSidebarMenu.vue';
import { PLAYBOOKS } from '@/types/playbook';

const authStore = useAuthStore();
const notificationsStore = useNotificationsStore();
const router = useRouter();
const route = useRoute();

const isMoreOpen = ref(false);
const scrollEl = ref<HTMLElement | null>(null);

// ปรับ scroll ขึ้นบนสุดทุกครั้งที่เปลี่ยนหน้า (iOS-like push)
watch(
  () => route.path,
  () => nextTick(() => scrollEl.value?.scrollTo({ top: 0 })),
);

onMounted(async () => {
  if (authStore.isAuthenticated) {
    try {
      await authStore.loadMe();
      notificationsStore.startPolling(); // 🔔 เริ่ม poll badge
    } catch {
      authStore.logout();
      router.push({ name: 'login' });
    }
  }
});

onBeforeUnmount(() => {
  notificationsStore.stopPolling();
});

const displayName = computed(() => authStore.displayName);

// ตัวอักษรตัวแรกของชื่อ → avatar
const avatarChar = computed(() => {
  const name = authStore.user?.full_name || authStore.displayName || '';
  return name ? name.charAt(0).toUpperCase() : 'ส';
});

const roleLabel = computed(() => {
  const first = authStore.roles[0];
  const map: Record<string, string> = {
    student: 'นักเรียน',
    class_president: 'หัวหน้าห้อง',
    vice_academic: 'รองวิชาการ',
    vice_discipline: 'รองวินัย',
    vice_activity: 'รองกิจกรรม',
    vice_reception: 'รองปฏิคม',
    level_president: 'ประธานระดับ',
    council_member: 'สภานักเรียน',
    council_president: 'ประธานสภา',
    teacher_council: 'ครูสภานักเรียน',
    teacher: 'ครู',
  };
  return first ? map[first.role || ''] || first.role || 'นักเรียน' : 'นักเรียน';
});

// 📍 ตำแหน่ง/ห้องสำหรับทักทาย (เช่น "หัวหน้าห้อง ม.4/1")
const roleLine = computed(() => {
  const first = authStore.roles[0];
  if (!first) return roleLabel.value;
  if (first.room_name) return `${roleLabel.value} · ${first.room_name}`;
  if (first.level) return `${roleLabel.value} · ${first.level}`;
  return roleLabel.value;
});

// หน้า title บน top bar (iOS navigation bar)
const routeTitles: Record<string, string> = {
  home: 'หน้าแรก',
  dashboard: 'แดชบอร์ด',
  profile: 'โปรไฟล์',
  'profile-edit': 'แก้ไขโปรไฟล์',
  'profile-password': 'เปลี่ยนรหัสผ่าน',
  'new-issue': 'แจ้งเรื่อง',
  'my-issues': 'เรื่องของฉัน',
  'received-issues': 'เรื่องที่รับ / ระดับฉัน',
  'issue-detail': 'รายละเอียดเรื่อง',
  'issue-edit': 'แก้ไขเรื่อง',
  boards: 'PIRI Boards',
  'board-detail': 'PIRI Boards',
  'board-reports': 'จัดการรายงาน',
  playbooks: 'P.R. Playbooks',
  'playbook-reader': 'อ่านหนังสือ',
  notifications: 'การแจ้งเตือน',
  students: 'รายชื่อนักเรียน',
  'import-students': 'นำเข้านักเรียน',
  'audit-logs': 'บันทึกการใช้งาน',
};
const routeTitle = computed(() => routeTitles[(route.name as string) || ''] || 'PIRIvoice');

function logout() {
  isMoreOpen.value = false;
  Swal.fire({
    icon: 'question',
    title: 'ออกจากระบบ?',
    showCancelButton: true,
    confirmButtonText: 'ออกจากระบบ',
    cancelButtonText: 'ยกเลิก',
  }).then((result) => {
    if (result.isConfirmed) {
      authStore.logout();
      router.push({ name: 'login' });
    }
  });
}

// 🔔 จำนวน仍未อ่านตามกลุ่ม (guard — counts[x] อาจ undefined)
function unread(key: string): number {
  return notificationsStore.counts[key] || 0;
}

// 🔔 unread badge ตามเมนู (map path → group_type จาก store)
const menuBadge = (path: string): number => {
  const g = {
    '/app/issues/mine': 'issue_mine',
    '/app/issues/received': 'issue_received',
    '/app/boards': 'board',
    '/app/boards/reports': 'report',
  } as Record<string, string>;
  const group = g[path];
  return group ? notificationsStore.counts[group] || 0 : 0;
};

interface NavItem {
  name: string;
  path: string;
  icon: string;
  badge: number;
  label?: string; // ป้ายสั้น (bottom bar)
}

// เมนูตาม permission (ใช้ร่วม: sidebar desktop + sheet มือถือ)
const menuItems = computed<NavItem[]>(() => {
  const items: NavItem[] = [];
  items.push({ name: 'หน้าแรก', path: '/app/home', icon: 'bi-house-door-fill', badge: 0 });
  if (authStore.hasPermission('VIEW_DASHBOARD')) {
    items.push({ name: 'แดชบอร์ด', path: '/app/dashboard', icon: 'bi-grid-1x2', badge: 0 });
  }
  items.push({ name: 'แจ้งเรื่อง', path: '/app/issues/new', icon: 'bi-pencil-square', badge: 0 });
  items.push({ name: 'เรื่องของฉัน', path: '/app/issues/mine', icon: 'bi-file-earmark-text', badge: menuBadge('/app/issues/mine') });
  items.push({ name: 'PIRI Boards', path: '/app/boards', icon: 'bi-columns-gap', badge: menuBadge('/app/boards') });
  if (authStore.hasPermission('RECEIVE_ISSUES')) {
    items.push({ name: 'เรื่องที่รับ / ระดับฉัน', path: '/app/issues/received', icon: 'bi-inbox', badge: menuBadge('/app/issues/received') });
  }
  if (authStore.isCouncilAuthority) {
    items.push({ name: 'จัดการรายงาน', path: '/app/boards/reports', icon: 'bi-flag-fill', badge: menuBadge('/app/boards/reports') });
  }
  if (authStore.hasPermission('MANAGE_STUDENTS')) {
    items.push({ name: 'นักเรียน', path: '/app/students', icon: 'bi-people', badge: 0 });
    items.push({ name: 'นำเข้า Excel', path: '/app/students/import', icon: 'bi-file-earmark-arrow-up', badge: 0 });
  }
  if (authStore.hasPermission('VIEW_AUDIT_LOG')) {
    items.push({ name: 'บันทึกการใช้งาน', path: '/app/audit-logs', icon: 'bi-clock-history', badge: 0 });
  }
  return items;
});

const isActive = (path: string): boolean => {
  if (path === '/app/dashboard') return route.path === '/app/dashboard';
  if (path === '/app/home') return route.path === '/app/home';
  if (path === '/app/boards') return route.path === '/app/boards';
  return route.path.startsWith(path);
};

const goHome = () => {
  isMoreOpen.value = false;
  router.push({ name: 'home' });
};
</script>

<template>
  <div class="relative flex h-screen overflow-hidden bg-[#FAFAF9] font-sans text-stone-900 selection:bg-[#B91C1C]/15 selection:text-[#B91C1C]">

    <!-- ============ Sidebar (desktop ≥ lg) ============ -->
    <aside class="relative z-30 hidden flex-shrink-0 p-4 lg:block">
      <div class="flex h-full w-[290px] flex-col overflow-hidden rounded-[1.75rem] border border-stone-200 bg-white">
        <!-- Brand -->
        <div class="flex items-center gap-3 px-5 pb-4 pt-6">
          <RouterLink to="/app/home" class="flex items-center gap-2.5 group">
            <div class="flex -space-x-2">
              <img src="/logos/school-logo.png" alt="โลโก้โรงเรียน" class="h-9 w-9 rounded-xl border border-stone-200 object-cover" />
              <img src="/logos/council-logo.png" alt="โลโก้สภานักเรียน" class="h-9 w-9 rounded-xl border border-stone-200 object-cover" />
            </div>
            <div class="leading-none">
              <span class="text-[15px] font-bold tracking-tight text-stone-900">
                PIRI<span class="text-[#B91C1C]">voice</span>
              </span>
              <p class="mt-1 text-[10px] font-medium tracking-wide text-stone-400">เสียงจากชาวพิริยาลัย</p>
            </div>
          </RouterLink>
        </div>

        <!-- Nav -->
        <nav class="flex-1 overflow-y-auto px-3 pb-2">
          <p class="px-3 pb-2 pt-1 text-[10px] font-bold uppercase tracking-[0.18em] text-stone-400">เมนู</p>
          <div class="space-y-1">
            <RouterLink
              v-for="item in menuItems"
              :key="item.path"
              :to="item.path"
              class="flex items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm font-semibold transition-colors duration-200"
              :class="isActive(item.path)
                ? 'bg-[#B91C1C] text-white'
                : 'text-stone-600 hover:bg-stone-100 hover:text-[#B91C1C]'"
            >
              <i :class="['bi', item.icon, 'text-[17px]']"></i>
              <span class="min-w-0 flex-1 truncate">{{ item.name }}</span>
              <span
                v-if="item.badge > 0"
                class="min-w-[20px] rounded-full px-1.5 py-0.5 text-center text-[10px] font-bold"
                :class="isActive(item.path) ? 'bg-white/20 text-white' : 'bg-[#B91C1C] text-white'"
              >
                {{ item.badge > 99 ? '99+' : item.badge }}
              </span>
            </RouterLink>
          </div>

          <!-- 📖 P.R. Playbooks — 6 เล่ม -->
          <div class="mt-3">
            <PlaybookSidebarMenu />
          </div>
        </nav>

        <!-- User footer -->
        <div class="border-t border-stone-200 p-3">
          <div class="flex items-center gap-3 rounded-xl border border-stone-200 bg-stone-50 p-3">
            <button @click="goHome" class="h-11 w-11 shrink-0 rounded-xl bg-[#B91C1C] text-sm font-black text-white ring-2 ring-white">
              {{ avatarChar }}
            </button>
            <div class="min-w-0 flex-1 text-left" @click="router.push({ name: 'profile' })">
              <p class="truncate text-sm font-bold leading-tight text-stone-800">{{ displayName }}</p>
              <p class="mt-0.5 truncate text-[11px] font-semibold text-stone-500">{{ roleLine }}</p>
            </div>
            <button
              @click="logout"
              title="ออกจากระบบ"
              class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-stone-400 transition-colors hover:bg-stone-100 hover:text-[#B91C1C]"
            >
              <i class="bi bi-box-arrow-right text-lg"></i>
            </button>
          </div>
        </div>
      </div>
    </aside>

    <!-- ============ Main column ============ -->
    <div class="relative z-10 flex min-w-0 flex-1 flex-col">
      <!-- ⚡ Top app bar (glass เหมือน navbar Landing) -->
      <header
        class="relative z-30 shrink-0 border-b transition-colors"
        :class="route.path === '/app/home' ? 'border-transparent bg-transparent' : 'border-stone-200 bg-white'"
        style="padding-top: env(safe-area-inset-top, 0px)"
      >
        <div class="mx-auto flex h-16 w-full max-w-7xl items-center gap-3 px-4 lg:px-6">
          <!-- Brand (มือถือ) -->
          <RouterLink
            to="/app/home"
            class="flex shrink-0 items-center gap-2 lg:hidden"
            aria-label="หน้าแรก"
          >
            <span class="relative flex h-9 w-9 items-center justify-center overflow-hidden rounded-xl border border-stone-200 bg-white p-0.5">
              <img src="/logos/school-logo.png" alt="โลโก้โรงเรียน" class="h-full w-full object-contain" />
            </span>
          </RouterLink>

          <!-- Title -->
          <div class="min-w-0 flex-1">
            <h1 class="truncate text-[15px] font-bold text-stone-900 sm:text-base lg:text-lg">
              {{ routeTitle }}
            </h1>
            <p class="hidden truncate text-[10px] font-semibold tracking-wide text-stone-500 sm:block lg:hidden">
              {{ roleLine }}
            </p>
          </div>

          <!-- Actions -->
          <div class="flex shrink-0 items-center gap-2">
            <RouterLink
              to="/app/issues/new"
              class="hidden items-center gap-1.5 rounded-xl bg-[#B91C1C] px-4 py-2 text-sm font-bold text-white transition-colors hover:bg-[#991B1B] active:scale-[0.97] xl:flex"
            >
              <i class="bi bi-pencil-square"></i>
               แจ้งเรื่อง
            </RouterLink>

            <!-- 🔔 กระดิ่ง -->
            <RouterLink
              to="/app/notifications"
              title="การแจ้งเตือน"
              class="relative flex h-10 w-10 items-center justify-center rounded-xl text-stone-500 transition-colors hover:bg-stone-100 hover:text-stone-900"
            >
              <i class="bi bi-bell text-xl"></i>
              <span
                v-if="notificationsStore.total > 0"
                class="absolute -right-0.5 -top-0.5 flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-[#B91C1C] px-1 text-[10px] font-bold text-white ring-2 ring-white"
              >
                {{ notificationsStore.total > 99 ? '99+' : notificationsStore.total }}
              </span>
            </RouterLink>

            <!-- Avatar → โปรไฟล์ -->
            <RouterLink
              to="/app/profile"
              title="โปรไฟล์ของฉัน"
              class="flex h-10 w-10 items-center justify-center rounded-xl bg-[#B91C1C] text-sm font-black text-white ring-2 ring-stone-200 transition-transform hover:scale-105 active:scale-95"
            >
              {{ avatarChar }}
            </RouterLink>
          </div>
        </div>
      </header>

      <!-- Content -->
      <main ref="scrollEl" class="flex-1 overflow-y-auto overscroll-contain pb-[calc(env(safe-area-inset-bottom,0px)+9rem)] lg:pb-8">
        <div class="mx-auto w-full max-w-7xl px-4 pt-4 sm:px-6 lg:px-8 lg:pt-6">
          <RouterView v-slot="{ Component }">
            <Transition name="page" mode="out-in" appear>
              <component :is="Component" :key="route.fullPath" />
            </Transition>
          </RouterView>
        </div>
      </main>
    </div>

    <!-- ============ Mobile bottom tab bar (iOS-style, < lg) ============ -->
    <nav
      class="pointer-events-none fixed inset-x-0 bottom-0 z-40 lg:hidden"
      style="bottom: calc(env(safe-area-inset-bottom, 0px) + 0.6rem)"
      aria-label="เมนูหลัก"
    >
      <div class="pointer-events-auto mx-auto w-[calc(100%-1.5rem)] max-w-[440px] rounded-[2rem] border border-stone-200 bg-white px-1.5 pb-1.5 pt-2.5">
        <div class="flex items-end justify-between">
          <!-- หน้าแรก -->
          <RouterLink
            to="/app/home"
            class="flex min-w-0 flex-1 flex-col items-center gap-0.5 rounded-2xl px-1 py-1.5 text-[10px] font-bold transition-colors"
            :class="route.path === '/app/home' ? 'text-[#B91C1C]' : 'text-stone-400'"
          >
            <i :class="['bi text-xl', route.path === '/app/home' ? 'bi-house-door-fill' : 'bi-house-door']"></i>
            <span class="truncate">หน้าแรก</span>
          </RouterLink>

          <!-- เรื่องของฉัน -->
          <RouterLink
            to="/app/issues/mine"
            class="relative flex min-w-0 flex-1 flex-col items-center gap-0.5 rounded-2xl px-1 py-1.5 text-[10px] font-bold transition-colors"
            :class="isActive('/app/issues/mine') ? 'text-[#B91C1C]' : 'text-stone-400'"
          >
            <span class="relative">
              <i :class="['bi text-xl', isActive('/app/issues/mine') ? 'bi-file-earmark-text-fill' : 'bi-file-earmark-text']"></i>
              <span
                v-if="unread('issue_mine') > 0"
                class="absolute -right-2.5 -top-1 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-[#B91C1C] px-1 text-[9px] font-bold text-white ring-2 ring-white"
              >
                {{ unread('issue_mine') > 99 ? '99+' : unread('issue_mine') }}
              </span>
            </span>
            <span class="truncate">ของฉัน</span>
          </RouterLink>

          <!-- ➕ FAB แจ้งเรื่อง (กลาง) — กะทัดรัด ไม่ทับเนื้อหา -->
          <RouterLink
            to="/app/issues/new"
            class="relative flex min-w-0 flex-1 flex-col items-center gap-1 pb-0.5 text-[9px] font-bold text-[#B91C1C]"
          >
            <span class="-mt-5 flex h-10 w-10 items-center justify-center rounded-[0.85rem] bg-[#B91C1C] text-base text-white ring-[3px] ring-white transition-transform active:scale-95">
              <i class="bi bi-plus-lg"></i>
            </span>
            <span class="leading-none">แจ้งเรื่อง</span>
          </RouterLink>

          <!-- PIRI Boards -->
          <RouterLink
            to="/app/boards"
            class="relative flex min-w-0 flex-1 flex-col items-center gap-0.5 rounded-2xl px-1 py-1.5 text-[10px] font-bold transition-colors"
            :class="isActive('/app/boards') ? 'text-[#B91C1C]' : 'text-stone-400'"
          >
            <span class="relative">
              <i class="bi text-xl bi-columns-gap"></i>
              <span
                v-if="unread('board') > 0"
                class="absolute -right-2.5 -top-1 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-[#B91C1C] px-1 text-[9px] font-bold text-white ring-2 ring-white"
              >
                {{ unread('board') > 99 ? '99+' : unread('board') }}
              </span>
            </span>
            <span class="truncate">Boards</span>
          </RouterLink>

          <!-- เพิ่มเติม (เปิด sheet เมนูทั้งหมด) -->
          <button
            type="button"
            @click="isMoreOpen = true"
            class="flex min-w-0 flex-1 flex-col items-center gap-0.5 rounded-2xl px-1 py-1.5 text-[10px] font-bold transition-colors"
            :class="isMoreOpen ? 'text-[#B91C1C]' : 'text-stone-400'"
          >
            <i :class="['bi text-xl', isMoreOpen ? 'bi-x-lg' : 'bi-grid-3x3-gap-fill']"></i>
            <span class="truncate">เพิ่มเติม</span>
          </button>
        </div>
      </div>
    </nav>

    <!-- ============ Bottom sheet: เมนูทั้งหมด (มือถือ) ============ -->
    <Transition name="sheet">
      <div v-if="isMoreOpen" class="fixed inset-0 z-50 lg:hidden">
        <div class="absolute inset-0 bg-stone-900/40" @click="isMoreOpen = false"></div>
        <div class="absolute inset-x-0 bottom-0 max-h-[86vh] overflow-y-auto rounded-t-[2rem] border-t border-stone-200 bg-white pb-safe">
          <!-- Handle -->
          <div class="mx-auto mt-3 h-1.5 w-10 rounded-full bg-stone-200"></div>

          <!-- User header -->
          <div class="flex items-center gap-3 px-6 pb-4 pt-4">
            <button
              @click="isMoreOpen = false; router.push({ name: 'profile' })"
              class="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-[#B91C1C] text-base font-black text-white"
            >
              {{ avatarChar }}
            </button>
            <div class="min-w-0 flex-1" @click="isMoreOpen = false; router.push({ name: 'profile' })">
              <p class="truncate text-base font-bold text-stone-900">สวัสดี, {{ displayName }}</p>
              <p class="truncate text-xs font-semibold text-stone-500">{{ roleLine }}</p>
            </div>
            <button
              @click="isMoreOpen = false"
              class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-stone-400 hover:bg-stone-100"
              aria-label="ปิดเมนู"
            >
              <i class="bi bi-x-lg text-lg"></i>
            </button>
          </div>

          <div class="mx-6 h-px bg-stone-200"></div>

          <!-- Menu items -->
          <div class="space-y-1 px-3 py-3">
            <p class="px-3 pb-1 pt-1 text-[10px] font-bold uppercase tracking-[0.16em] text-stone-400">เมนูทั้งหมด</p>
            <button
              v-for="item in menuItems"
              :key="item.path"
              type="button"
              @click="isMoreOpen = false; router.push(item.path)"
              class="flex w-full items-center gap-3 rounded-xl px-3.5 py-3 text-left text-sm font-semibold transition-colors"
              :class="isActive(item.path) ? 'bg-stone-100 text-[#B91C1C]' : 'text-stone-600 hover:bg-stone-50'"
            >
              <i :class="['bi', item.icon, 'text-lg', isActive(item.path) ? 'text-[#B91C1C]' : 'text-stone-400']"></i>
              <span class="min-w-0 flex-1 truncate">{{ item.name }}</span>
              <span
                v-if="item.badge > 0"
                class="min-w-[20px] rounded-full bg-[#B91C1C] px-1.5 py-0.5 text-center text-[10px] font-bold text-white"
              >
                {{ item.badge > 99 ? '99+' : item.badge }}
              </span>
              <i class="bi bi-chevron-right text-xs text-stone-300"></i>
            </button>
          </div>

          <!-- 📖 P.R. Playbooks -->
          <div class="mx-6 h-px bg-stone-200"></div>
          <div class="px-3 py-3">
            <div class="flex items-center justify-between px-3 pb-1">
              <p class="text-[10px] font-bold uppercase tracking-[0.16em] text-stone-400">P.R. Playbooks</p>
              <button
                type="button"
                class="text-[11px] font-bold text-[#B91C1C] hover:underline"
                @click="isMoreOpen = false; router.push({ name: 'playbooks' })"
              >
                ดูทั้งหมด
              </button>
            </div>
            <div class="space-y-0.5">
              <button
                v-for="pb in PLAYBOOKS"
                :key="pb.id"
                type="button"
                @click="isMoreOpen = false; router.push({ name: 'playbook-reader', params: { id: pb.id } })"
                class="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-left text-sm font-semibold text-stone-600 transition-colors hover:bg-stone-100 hover:text-[#B91C1C]"
              >
                <span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-stone-100 text-stone-600">
                  <i class="bi bi-journal-bookmark text-sm"></i>
                </span>
                <span class="truncate">{{ pb.title }}</span>
              </button>
            </div>
          </div>

          <!-- Account -->
          <div class="mx-6 h-px bg-stone-200"></div>
          <div class="grid grid-cols-2 gap-2 px-6 py-4">
            <button
              type="button"
              @click="isMoreOpen = false; router.push({ name: 'profile-edit' })"
              class="btn-ghost-ui !justify-start !px-3 !py-3 text-sm"
            >
              <i class="bi bi-person-badge text-base"></i> แก้ไขโปรไฟล์
            </button>
            <button
              type="button"
              @click="isMoreOpen = false; router.push({ name: 'profile-password' })"
              class="btn-ghost-ui !justify-start !px-3 !py-3 text-sm"
            >
              <i class="bi bi-key text-base"></i> เปลี่ยนรหัสผ่าน
            </button>
            <button
              type="button"
              @click="logout"
              class="col-span-2 flex w-full items-center justify-center gap-2 rounded-xl border border-stone-200 bg-stone-100 py-3 text-sm font-bold text-stone-700 transition-colors hover:bg-stone-200"
            >
              <i class="bi bi-box-arrow-right text-base"></i> ออกจากระบบ
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
/* fade สำหรับ backdrop + slide สำหรับ sheet (มือถือ) */
.sheet-enter-active,
.sheet-leave-active {
  transition: opacity 0.25s ease;
}
.sheet-enter-active .absolute.inset-x-0,
.sheet-leave-active .absolute.inset-x-0 {
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
.sheet-enter-from,
.sheet-leave-to {
  opacity: 0;
}
.sheet-enter-from .absolute.inset-x-0,
.sheet-leave-to .absolute.inset-x-0 {
  transform: translateY(100%);
}

/* ♿ เคารพผู้ที่ปิดแอนิเมชัน */
@media (prefers-reduced-motion: reduce) {
  .sheet-enter-active,
  .sheet-leave-active {
    transition: none !important;
  }
}
</style>

<style>
/* ✨ หน้าเปลี่ยนแบบ smooth (เฉพาะ content) — global เพราะ Transition อยู่ใน MainLayout
   mode="out-in" + appear → fade + เลื่อนขึ้นนุ่ม ๆ */
.page-enter-active {
  transition: opacity 0.35s cubic-bezier(0.4, 0, 0.2, 1), transform 0.35s cubic-bezier(0.4, 0, 0.2, 1);
}
.page-leave-active {
  transition: opacity 0.15s ease;
}
.page-enter-from {
  opacity: 0;
  transform: translateY(16px);
}
.page-leave-to {
  opacity: 0;
}
</style>
