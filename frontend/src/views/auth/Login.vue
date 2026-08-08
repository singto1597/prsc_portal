<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import Swal from 'sweetalert2';
import { useAuthStore } from '@/stores/auth';

const authStore = useAuthStore();
const router = useRouter();

const username = ref('');
const password = ref('');
const isLoading = ref(false);

// นักเรียน → ไปหน้าแจ้งปัญหา, ระดับอื่น → ไปหน้าที่เหมาะสม
function homeRouteName(): string {
  if (authStore.hasPermission('VIEW_DASHBOARD')) return 'dashboard';
  if (authStore.hasPermission('RECEIVE_ISSUES')) return 'received-issues';
  return 'new-issue';
}

async function handleLogin() {
  if (!username.value || !password.value) {
    Swal.fire({ icon: 'warning', title: 'กรอกข้อมูลไม่ครบ', text: 'กรุณากรอก รหัสนักเรียน และ รหัสผ่าน' });
    return;
  }

  isLoading.value = true;
  try {
    await authStore.login(username.value.trim(), password.value);
    Swal.fire({ icon: 'success', title: 'เข้าสู่ระบบสำเร็จ!', text: `ยินดีต้อนรับ`, timer: 1000, showConfirmButton: false });
    router.push({ name: homeRouteName() });
  } catch (e: any) {
    Swal.fire({ icon: 'error', title: 'เข้าสู่ระบบไม่สำเร็จ', text: e.message || 'ตรวจสอบรหัสนักเรียนและรหัสผ่าน' });
  } finally {
    isLoading.value = false;
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-gradient-to-br from-red-50 via-white to-rose-100 p-4">
    <div class="w-full max-w-md">
      <div class="bg-white/90 backdrop-blur p-8 rounded-3xl shadow-2xl border border-red-50">
        <div class="text-center mb-8">
          <!-- 🏫 โลโก้โรงเรียน + 🏛️ โลโก้สภานักเรียน วางข้างกันตรงกลาง -->
          <div class="flex items-center justify-center gap-4 mb-4">
            <img src="/logos/school-logo.png" alt="โลโก้โรงเรียน"
              class="w-16 h-16 rounded-full object-cover shadow-lg ring-2 ring-red-200 ring-offset-2" />
            <img src="/logos/council-logo.png" alt="โลโก้สภานักเรียน"
              class="w-16 h-16 rounded-full object-cover shadow-lg ring-2 ring-rose-200 ring-offset-2" />
          </div>
          <h1 class="text-2xl font-bold text-gray-900 tracking-tight">PRSC Portal</h1>
          <p class="text-gray-500 mt-1">ระบบรับความคิดเห็นและปัญหาสภานักเรียน</p>
        </div>

        <form @submit.prevent="handleLogin" class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">รหัสนักเรียน</label>
            <input
              v-model="username"
              type="text"
              class="w-full px-4 py-2.5 border border-gray-300 rounded-xl focus:ring-2 focus:ring-red-500 focus:border-red-500 transition"
              placeholder="เช่น 41001"
              :disabled="isLoading"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">รหัสผ่าน</label>
            <input
              v-model="password"
              type="password"
              class="w-full px-4 py-2.5 border border-gray-300 rounded-xl focus:ring-2 focus:ring-red-500 focus:border-red-500 transition"
              placeholder="••••"
              :disabled="isLoading"
            />
          </div>
          <button
            type="submit"
            :disabled="isLoading"
            class="w-full py-3 bg-gradient-to-r from-red-600 to-rose-600 text-white rounded-xl hover:from-red-700 hover:to-rose-700 disabled:opacity-50 font-semibold shadow-md hover:shadow-lg transition-all"
          >
            {{ isLoading ? 'กำลังเข้าสู่ระบบ...' : 'เข้าสู่ระบบ' }}
          </button>
        </form>

        <p class="text-[11px] text-gray-400 text-center mt-6 leading-relaxed">
          พัฒนาโดย <span class="font-medium text-gray-500">นายพัฒนพล สุธรรม</span><br />
          <span class="text-gray-300">© 2026 PRSC Portal. สงวนลิขสิทธิ์</span>
        </p>
      </div>
    </div>
  </div>
</template>
