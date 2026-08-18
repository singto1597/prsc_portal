<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { useRouter } from 'vue-router';
import Swal from 'sweetalert2';
import { getMyProfile, type MyProfile } from '@/services/profile';
import { useAuthStore } from '@/stores/auth';

const router = useRouter();
const authStore = useAuthStore();

const profile = ref<MyProfile | null>(null);
const isLoading = ref(true);
const menuOpen = ref(false);

const ROLE_LABELS: Record<string, string> = {
  student: 'นักเรียน',
  class_president: 'หัวหน้าห้อง',
  vice_academic: 'รองวิชาการ',
  vice_discipline: 'รองวินัย',
  vice_activity: 'รองกิจกรรม',
  vice_reception: 'รองปฏิคม',
  level_president: 'ประธานระดับ',
  council_member: 'สภานักเรียน',
  council_president: 'ประธานสภา',
  teacher: 'ครู',
  teacher_council: 'ครูสภา',
  admin: 'แอดมิน',
};

const avatarChar = computed(() => {
  const name = profile.value?.nickname || profile.value?.first_name || '';
  return name ? name.charAt(0).toUpperCase() : 'ส';
});

const fullName = computed(() => {
  const p = profile.value;
  if (!p) return '';
  return [p.prefix, p.first_name, p.last_name].filter(Boolean).join(' ').trim();
});

const roleLabel = computed(() => {
  const r = profile.value?.class_role || '';
  return ROLE_LABELS[r] || r || 'สมาชิก';
});

async function load() {
  isLoading.value = true;
  try {
    profile.value = await getMyProfile();
  } catch (e: unknown) {
    Swal.fire({ icon: 'error', title: 'โหลดโปรไฟล์ไม่สำเร็จ', text: e instanceof Error ? e.message : 'เกิดข้อผิดพลาด' });
  } finally {
    isLoading.value = false;
  }
}
onMounted(load);

const goEdit = () => { menuOpen.value = false; router.push({ name: 'profile-edit' }); };
const goPassword = () => { menuOpen.value = false; router.push({ name: 'profile-password' }); };

function logout() {
  menuOpen.value = false;
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

// แถวข้อมูลส่วนตัว (icon + label + value) — กันเบียด/ตัดคำบนจอเล็ก
const infoRows = computed(() => {
  const p = profile.value;
  if (!p) return [];
  const rows: { icon: string; label: string; value: string }[] = [
    { icon: 'bi-person-badge', label: 'รหัสนักเรียน', value: p.student_id },
    { icon: 'bi-hash', label: 'เลขที่', value: p.student_no ? String(p.student_no) : '-' },
    { icon: 'bi-emoji-smile', label: 'ชื่อเล่น', value: p.nickname || '-' },
    { icon: 'bi-telephone', label: 'เบอร์โทร', value: p.phone_number || '-' },
    { icon: 'bi-envelope', label: 'อีเมล', value: p.email || '-' },
    { icon: 'bi-door-closed', label: 'ห้องเรียน', value: p.room_code ? `${p.room_code}${p.level ? ` (${p.level})` : ''}` : '-' },
  ];
  // ชื่อผู้ใช้ (login) — แสดงเฉพาะเมื่อต่างจากรหัสนักเรียน (เช่น admin/ครู ที่ใช้ username ยาว)
  if (p.username && p.username !== p.student_id) {
    rows.push({ icon: 'bi-person-vcard', label: 'ชื่อผู้ใช้', value: p.username });
  }
  return rows;
});
</script>

<template>
  <div class="max-w-3xl mx-auto">
    <div v-if="isLoading" class="flex justify-center py-20">
      <div class="animate-spin w-10 h-10 border-4 border-red-600 border-t-transparent rounded-full"></div>
    </div>

    <div v-else-if="profile" class="space-y-4">
      <!-- ===== Cover banner (แบบ FB) — เมนู ⋮ อยู่นอก overflow-hidden กัน dropdown ถูกตัด ===== -->
      <div class="relative">
        <div class="bg-gradient-to-r from-red-600 via-rose-600 to-red-700 rounded-2xl shadow-lg overflow-hidden h-24 sm:h-28">
          <!-- ลวดลายพื้นหลังบางๆ (ดูมีมิติ ไม่ทึบ) -->
          <div class="absolute -right-8 -top-10 w-36 h-36 rounded-full bg-white/10"></div>
          <div class="absolute right-24 -bottom-12 w-24 h-24 rounded-full bg-white/10"></div>
          <div class="absolute right-1/3 -top-6 w-16 h-16 rounded-full bg-white/5"></div>
        </div>

        <!-- เมนูจุด 3 จุด (ตั้งค่าโปรไฟล์) -->
        <div class="absolute top-3 right-3 z-30">
          <button
            @click="menuOpen = !menuOpen"
            aria-label="เมนูโปรไฟล์"
            class="w-9 h-9 rounded-full bg-black/20 text-white hover:bg-black/30 flex items-center justify-center backdrop-blur-sm transition"
            :class="{ 'bg-black/30': menuOpen }"
          >
            <i class="bi bi-three-dots-vertical text-lg"></i>
          </button>

          <transition name="fade-up">
            <div v-if="menuOpen" class="absolute right-0 top-11 w-56 bg-white rounded-2xl shadow-xl border border-gray-100 py-2 z-50">
              <div class="px-4 py-1.5 mb-1 border-b border-gray-50">
                <p class="text-[10px] font-bold text-gray-400 uppercase tracking-widest">การจัดการบัญชี</p>
              </div>
              <button @click="goEdit" class="w-full text-left px-4 py-2.5 text-sm font-semibold text-gray-700 hover:bg-red-50 hover:text-red-600 transition-colors flex items-center gap-3">
                <i class="bi bi-pencil-square text-lg"></i> แก้ไขโปรไฟล์
              </button>
              <button @click="goPassword" class="w-full text-left px-4 py-2.5 text-sm font-semibold text-gray-700 hover:bg-red-50 hover:text-red-600 transition-colors flex items-center gap-3">
                <i class="bi bi-shield-lock text-lg"></i> เปลี่ยนรหัสผ่าน
              </button>
              <div class="h-px bg-gray-100 my-1"></div>
              <button @click="logout" class="w-full text-left px-4 py-2.5 text-sm font-bold text-red-500 hover:bg-red-50 hover:text-red-600 transition-colors flex items-center gap-3">
                <i class="bi bi-box-arrow-right text-lg"></i> ออกจากระบบ
              </button>
            </div>
          </transition>
        </div>

        <!-- Overlay ปิดเมนู (อยู่ใต้เมนู z-30 แต่ทับเนื้อหาด้านล่าง) -->
        <div v-if="menuOpen" class="fixed inset-0 z-20" @click="menuOpen = false"></div>

        <!-- ===== ตัวตน: avatar เล็กมุมซ้าย + ชื่อเต็ม (ไม่ตัดคำ) ===== -->
        <div class="-mt-10 sm:-mt-12 px-4 sm:px-6 relative z-10">
        <div class="flex items-end gap-3">
          <div class="w-16 h-16 sm:w-20 sm:h-20 rounded-2xl bg-white p-0.5 shadow-lg ring-4 ring-white shrink-0">
            <div class="w-full h-full rounded-[14px] bg-gradient-to-br from-red-100 to-rose-50 text-red-600 flex items-center justify-center text-2xl sm:text-3xl font-bold">
              {{ avatarChar }}
            </div>
          </div>
          <div class="pb-0.5 min-w-0 flex-1">
            <h1 class="text-lg sm:text-2xl font-bold text-gray-900 leading-snug break-words">{{ fullName }}</h1>
            <div class="flex flex-wrap gap-1.5 mt-1.5">
              <span class="px-2.5 py-1 bg-red-100 text-red-700 text-xs font-semibold rounded-full">
                <i class="bi bi-mortarboard mr-1"></i>{{ roleLabel }}
              </span>
              <span v-if="profile.staff_level" class="px-2.5 py-1 bg-amber-100 text-amber-700 text-xs font-semibold rounded-full">
                <i class="bi bi-clipboard-check mr-1"></i>ระดับ {{ profile.staff_level }}
              </span>
              <span v-if="profile.room_code" class="px-2.5 py-1 bg-gray-100 text-gray-600 text-xs font-medium rounded-full">
                <i class="bi bi-door-closed mr-1"></i>{{ profile.room_code }}
              </span>
            </div>
          </div>
        </div>
      </div>
      </div>

      <!-- ===== ข้อมูลส่วนตัว (row icon — กันเบียดจอเล็ก) ===== -->
      <div class="bg-white rounded-2xl shadow-sm p-5">
        <h2 class="text-base font-bold text-gray-800 mb-4 flex items-center gap-2">
          <i class="bi bi-person-lines-fill text-red-500"></i> ข้อมูลส่วนตัว
        </h2>
        <div class="grid sm:grid-cols-2 gap-x-6 gap-y-3">
          <div
            v-for="row in infoRows"
            :key="row.label"
            class="flex items-center gap-3 py-1.5 min-w-0"
          >
            <span class="w-8 h-8 rounded-lg bg-gray-50 text-gray-400 flex items-center justify-center shrink-0">
              <i :class="['bi', row.icon]"></i>
            </span>
            <div class="min-w-0">
              <p class="text-[11px] text-gray-400 font-medium leading-tight">{{ row.label }}</p>
              <p class="text-sm text-gray-800 font-medium break-words leading-snug">{{ row.value }}</p>
            </div>
          </div>
        </div>
      </div>

      <p class="text-center text-[11px] text-gray-300 pb-4">
        แก้ไขโปรไฟล์หรือเปลี่ยนรหัสผ่านได้จากเมนู <i class="bi bi-three-dots-vertical"></i> มุมขวาบน
      </p>
    </div>
  </div>
</template>

<style scoped>
.fade-up-enter-active, .fade-up-leave-active { transition: all 0.18s ease; }
.fade-up-enter-from, .fade-up-leave-to { opacity: 0; transform: translateY(6px) scale(0.98); }
</style>
