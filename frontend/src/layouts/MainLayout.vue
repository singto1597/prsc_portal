<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue';
import { RouterView, RouterLink, useRouter, useRoute } from 'vue-router';
import Swal from 'sweetalert2';
import { useAuthStore } from '@/stores/auth';
import { useNotificationsStore } from '@/stores/notifications';
import PlaybookSidebarMenu from '@/components/playbooks/PlaybookSidebarMenu.vue';

const authStore = useAuthStore();
const notificationsStore = useNotificationsStore();
const router = useRouter();
const route = useRoute();

const isSidebarOpen = ref(false);
const activeDropdown = ref<string | null>(null);

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
  };
  return first ? map[first.role || ''] || first.role || 'นักเรียน' : 'นักเรียน';
});

const toggleDropdown = (name: string) => {
  activeDropdown.value = activeDropdown.value === name ? null : name;
};
const closeDropdowns = () => { activeDropdown.value = null; };

const goToProfile = () => {
  closeDropdowns();
  router.push({ name: 'profile' });
};

const goToPassword = () => {
  closeDropdowns();
  router.push({ name: 'profile-password' });
};

function logout() {
  closeDropdowns();
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

// 🔔 unread badge ตามเมนู (map path → group_type จาก store)
const menuBadge = (path: string): number => {
  const g = {
    '/issues/mine': 'issue_mine',
    '/issues/received': 'issue_received',
    '/boards': 'board',
    '/boards/reports': 'report',
  } as Record<string, string>;
  const group = g[path];
  return group ? notificationsStore.counts[group] || 0 : 0;
};

// เมนูตาม permission
const menuItems = computed(() => {
  const items: Array<{ name: string; path: string; icon: string; badge: number }> = [];
  if (authStore.hasPermission('VIEW_DASHBOARD')) {
    items.push({ name: 'แดชบอร์ด', path: '/dashboard', icon: 'bi-grid-1x2', badge: 0 });
  }
  items.push({ name: 'แจ้งปัญหา / ความคิดเห็น', path: '/issues/new', icon: 'bi-pencil-square', badge: 0 });
  items.push({ name: 'เรื่องของฉัน', path: '/issues/mine', icon: 'bi-file-earmark-text', badge: menuBadge('/issues/mine') });
  items.push({ name: 'PIRI Boards', path: '/boards', icon: 'bi-columns-gap', badge: menuBadge('/boards') });
  if (authStore.isCouncilAuthority) {
    items.push({ name: 'จัดการรายงาน', path: '/boards/reports', icon: 'bi-flag-fill', badge: menuBadge('/boards/reports') });
  }
  if (authStore.hasPermission('RECEIVE_ISSUES')) {
    items.push({ name: 'เรื่องที่รับ / ระดับฉัน', path: '/issues/received', icon: 'bi-inbox', badge: menuBadge('/issues/received') });
  }
  if (authStore.hasPermission('MANAGE_STUDENTS')) {
    items.push({ name: 'นักเรียน', path: '/students', icon: 'bi-people', badge: 0 });
    items.push({ name: 'นำเข้า Excel', path: '/students/import', icon: 'bi-file-earmark-arrow-up', badge: 0 });
  }
  if (authStore.hasPermission('VIEW_AUDIT_LOG')) {
    items.push({ name: 'บันทึกการใช้งาน', path: '/audit-logs', icon: 'bi-clock-history', badge: 0 });
  }
  return items;
});

const isActive = (path: string) => {
  if (path === '/dashboard') return route.path === '/dashboard';
  return route.path.startsWith(path);
};
</script>

<template>
  <div class="flex h-screen bg-gray-50 overflow-hidden relative">
    <!-- overlay ปิด dropdown -->
    <div v-if="activeDropdown" class="fixed inset-0 z-20" @click="closeDropdowns"></div>

    <!-- Sidebar (desktop) -->
    <aside class="hidden md:flex md:flex-shrink-0 relative z-50">
      <div class="flex flex-col w-64 bg-white border-r border-gray-100 shadow-sm h-full">
        <!-- Brand -->
        <RouterLink to="/" class="flex items-center h-16 px-5 bg-gradient-to-r from-red-600 to-red-700 shrink-0">
          <img src="/logos/school-logo.png" alt="โลโก้โรงเรียน" class="w-9 h-9 rounded-full object-cover mr-3 border border-white/30" />
          <div>
            <span class="text-white text-base font-black tracking-wider leading-none">PIRIvoice</span>
            <p class="text-[10px] text-red-100 leading-none mt-1">เสียงจากชาวพิริยาลัย</p>
          </div>
        </RouterLink>

        <div class="flex-1 flex flex-col overflow-y-auto">
          <nav class="flex-1 px-3 py-4 space-y-1">
            <RouterLink
              v-for="item in menuItems"
              :key="item.path"
              :to="item.path"
              class="flex items-center px-3.5 py-3 text-sm font-semibold rounded-xl transition-all group"
              :class="isActive(item.path)
                ? 'bg-red-50 text-red-600 shadow-sm border border-red-100/50'
                : 'text-gray-500 hover:bg-gray-50 hover:text-gray-900'"
            >
              <i :class="['bi', item.icon, 'text-lg mr-3', isActive(item.path) ? '' : 'transition-transform group-hover:scale-110']"></i>
              {{ item.name }}
              <span
                v-if="item.badge > 0"
                class="ml-auto min-w-[20px] h-5 px-1.5 rounded-full bg-red-600 text-white text-[11px] font-bold flex items-center justify-center"
              >
                {{ item.badge > 99 ? '99+' : item.badge }}
              </span>
            </RouterLink>

            <!-- 📖 คู่มือสภานักเรียน (P.R. Playbook) — 6 เล่ม -->
            <PlaybookSidebarMenu class="pt-1" />
          </nav>

          <!-- User footer -->
          <div class="p-3 border-t border-gray-100 bg-gray-50/50 relative">
            <div class="flex items-center justify-between p-2 rounded-xl hover:bg-white border border-transparent hover:border-gray-200 transition-all group">
              <div class="flex items-center overflow-hidden flex-1 cursor-pointer" @click="goToProfile">
                <div class="w-9 h-9 rounded-full bg-gradient-to-br from-red-100 to-red-50 text-red-600 flex items-center justify-center font-bold shadow-inner border border-red-100 shrink-0">
                  {{ avatarChar }}
                </div>
                <div class="ml-3 overflow-hidden">
                  <p class="text-sm font-bold text-gray-800 truncate leading-none mb-1">{{ displayName }}</p>
                  <p class="text-[10px] tracking-wider text-red-500 font-bold uppercase truncate leading-none">{{ roleLabel }}</p>
                </div>
              </div>
              <!-- 🔔 กระดิ่งแจ้งเตือน (badge = unread ทั้งหมด) -->
              <RouterLink
                to="/notifications"
                title="การแจ้งเตือน"
                class="relative w-8 h-8 flex items-center justify-center rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-colors shrink-0 ml-1"
              >
                <i class="bi bi-bell-fill text-lg"></i>
                <span
                  v-if="notificationsStore.total > 0"
                  class="absolute -top-1 -right-1 min-w-[16px] h-4 px-1 rounded-full bg-red-600 text-white text-[10px] font-bold flex items-center justify-center"
                >
                  {{ notificationsStore.total > 99 ? '99+' : notificationsStore.total }}
                </span>
              </RouterLink>
              <button
                @click.stop="toggleDropdown('sidebarSettings')"
                class="w-8 h-8 flex items-center justify-center rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-colors shrink-0 ml-1"
                :class="{'bg-gray-200 text-gray-800': activeDropdown === 'sidebarSettings'}"
              >
                <i class="bi bi-gear-fill text-lg"></i>
              </button>
            </div>

            <!-- Dropdown -->
            <transition name="fade-up">
              <div v-if="activeDropdown === 'sidebarSettings'"
                class="absolute bottom-full left-4 mb-2 w-56 bg-white rounded-2xl shadow-xl border border-gray-100 py-2 z-50">
                <div class="px-4 py-2 mb-1 border-b border-gray-50">
                  <p class="text-[10px] font-bold text-gray-400 uppercase tracking-widest">การจัดการ</p>
                </div>
                <button @click="goToProfile" class="w-full text-left px-4 py-2.5 text-sm font-semibold text-gray-700 hover:bg-red-50 hover:text-red-600 transition-colors flex items-center gap-3">
                  <i class="bi bi-person-badge text-lg"></i> โปรไฟล์ของฉัน
                </button>
                <button @click="goToPassword" class="w-full text-left px-4 py-2.5 text-sm font-semibold text-gray-700 hover:bg-red-50 hover:text-red-600 transition-colors flex items-center gap-3">
                  <i class="bi bi-key text-lg"></i> เปลี่ยนรหัสผ่าน
                </button>
                <div class="h-px bg-gray-100 my-1"></div>
                <button @click="logout" class="w-full text-left px-4 py-2.5 text-sm font-bold text-red-500 hover:bg-red-50 hover:text-red-600 transition-colors flex items-center gap-3">
                  <i class="bi bi-box-arrow-right text-lg"></i> ออกจากระบบ
                </button>
              </div>
            </transition>
          </div>
        </div>
      </div>
    </aside>

    <!-- Mobile overlay -->
    <Transition name="fade">
      <div v-if="isSidebarOpen" class="fixed inset-0 z-40 md:hidden bg-gray-900/40 backdrop-blur-sm" @click="isSidebarOpen = false"></div>
    </Transition>

    <!-- Mobile sidebar drawer -->
    <Transition name="slide">
      <div v-if="isSidebarOpen" class="fixed inset-y-0 left-0 z-50 md:hidden w-64 bg-white shadow-2xl flex flex-col">
        <div class="flex items-center h-14 px-4 bg-gradient-to-r from-red-600 to-red-700">
          <img src="/logos/school-logo.png" alt="โลโก้โรงเรียน" class="w-8 h-8 rounded-full object-cover mr-3" />
          <span class="text-white font-black">PIRIvoice</span>
        </div>
        <nav class="flex-1 p-3 space-y-1 overflow-y-auto">
          <RouterLink
            v-for="item in menuItems"
            :key="item.path"
            :to="item.path"
            @click="isSidebarOpen = false"
            class="flex items-center px-3.5 py-3 text-sm font-semibold rounded-xl"
            :class="isActive(item.path) ? 'bg-red-50 text-red-600' : 'text-gray-500 hover:bg-gray-50'"
          >
            <i :class="['bi', item.icon, 'text-lg mr-3']"></i>
            {{ item.name }}
            <span
              v-if="item.badge > 0"
              class="ml-auto min-w-[20px] h-5 px-1.5 rounded-full bg-red-600 text-white text-[11px] font-bold flex items-center justify-center"
            >
              {{ item.badge > 99 ? '99+' : item.badge }}
            </span>
          </RouterLink>

          <!-- 📖 คู่มือสภานักเรียน (P.R. Playbook) — 6 เล่ม (มือถือ: ปิด drawer หลังคลิก) -->
          <PlaybookSidebarMenu close-on-navigate @navigate="isSidebarOpen = false" class="pt-1" />
        </nav>
        <div class="p-3 border-t border-gray-100">
          <button @click="isSidebarOpen = false; goToProfile()" class="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-semibold text-gray-700 hover:bg-red-50">
            <i class="bi bi-person-badge text-lg"></i> โปรไฟล์ของฉัน
          </button>
          <button @click="isSidebarOpen = false; goToPassword()" class="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-semibold text-gray-700 hover:bg-red-50">
            <i class="bi bi-key text-lg"></i> เปลี่ยนรหัสผ่าน
          </button>
          <button @click="isSidebarOpen = false; logout()" class="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-bold text-red-500 hover:bg-red-50 mt-1">
            <i class="bi bi-box-arrow-right text-lg"></i> ออกจากระบบ
          </button>
        </div>
      </div>
    </Transition>

    <!-- Main -->
    <div class="flex-1 flex flex-col overflow-hidden">
      <!-- Mobile header -->
      <header class="md:hidden fixed top-0 left-0 right-0 z-30 bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between">
        <button @click="isSidebarOpen = true" class="text-2xl text-gray-600">
          <i class="bi bi-list"></i>
        </button>
        <div class="flex items-center gap-2">
          <img src="/logos/school-logo.png" alt="โลโก้โรงเรียน" class="w-7 h-7 rounded-full object-cover" />
          <span class="font-bold text-red-700">PIRIvoice</span>
        </div>
        <div class="flex items-center gap-2">
          <!-- 🔔 กระดิ่งแจ้งเตือน (mobile) -->
          <RouterLink to="/notifications" class="relative w-8 h-8 flex items-center justify-center text-gray-600">
            <i class="bi bi-bell-fill text-lg"></i>
            <span
              v-if="notificationsStore.total > 0"
              class="absolute -top-1 -right-1 min-w-[16px] h-4 px-1 rounded-full bg-red-600 text-white text-[10px] font-bold flex items-center justify-center"
            >
              {{ notificationsStore.total > 99 ? '99+' : notificationsStore.total }}
            </span>
          </RouterLink>
          <button @click="goToProfile" class="w-8 h-8 rounded-full bg-gradient-to-br from-red-100 to-red-50 text-red-600 flex items-center justify-center text-sm font-bold">
            {{ avatarChar }}
          </button>
        </div>
      </header>

      <main class="flex-1 overflow-y-auto p-4 md:p-6 mt-14 md:mt-0 max-w-7xl w-full mx-auto">
        <RouterView v-slot="{ Component }">
          <Transition name="page" mode="out-in" appear>
            <component :is="Component" :key="route.fullPath" />
          </Transition>
        </RouterView>
      </main>

      <!-- 🏫 Footer ทุกหน้าในระบบ — ตัวหนังสือเล็กๆ เงียบๆ คล้ายเครดิตหน้า login -->
      <footer class="shrink-0 px-4 py-2.5 md:py-3 text-center border-t border-gray-100/80 bg-white/40">
        <p class="text-[11px] text-gray-400 leading-relaxed">
          คณะกรรมการสภานักเรียน · โรงเรียนพิริยาลัยจังหวัดแพร่
          <span class="text-gray-300">© 2026</span>
        </p>
        <p class="text-[10px] text-gray-300 leading-relaxed mt-0.5">
          151 ถ.ยันตรกิจโกศล ต.ในเวียง อ.เมือง จ.แพร่ 54000
        </p>
      </footer>
    </div>
  </div>
</template>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
.fade-up-enter-active, .fade-up-leave-active { transition: all 0.2s; }
.fade-up-enter-from, .fade-up-leave-to { opacity: 0; transform: translateY(8px); }
.slide-enter-active, .slide-leave-active { transition: transform 0.25s; }
.slide-enter-from, .slide-leave-to { transform: translateX(-100%); }
</style>

<style>
/* ✨ หน้าเปลี่ยนแบบ smooth (เฉพาะ content — ไม่แตะ sidebar)
   mode="out-in" + appear → หน้าใหม่ fade+เลื่อนขึ้นชัดเจน */
.page-enter-active {
  transition: opacity 0.35s cubic-bezier(0.4, 0, 0.2, 1), transform 0.35s cubic-bezier(0.4, 0, 0.2, 1);
}
.page-leave-active {
  transition: opacity 0.15s ease;
}
.page-enter-from {
  opacity: 0;
  transform: translateY(20px);
}
.page-leave-to {
  opacity: 0;
}
</style>
