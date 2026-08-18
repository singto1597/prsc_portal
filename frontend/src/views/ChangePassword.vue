<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import Swal from 'sweetalert2';
import { changePassword } from '@/services/profile';
import { useAuthStore } from '@/stores/auth';

const router = useRouter();
const authStore = useAuthStore();

const oldPass = ref('');
const newPass = ref('');
const confirmPass = ref('');
const isSaving = ref(false);

// โดนบังคับเปลี่ยนรหัส (บัญชีที่ระบบสร้างให้ ตอนเปิดระบบครั้งแรก)
const isForced = authStore.mustChangePassword;

// หน้าแรกตามบทบาท (เหมือน Login)
function homeRouteName(): string {
  if (authStore.hasPermission('VIEW_DASHBOARD')) return 'dashboard';
  if (authStore.hasPermission('RECEIVE_ISSUES')) return 'received-issues';
  return 'new-issue';
}

async function submit() {
  if (!oldPass.value || !newPass.value || !confirmPass.value) {
    Swal.fire({ icon: 'warning', title: 'กรอกให้ครบ', text: 'กรอกรหัสผ่านเดิม, ใหม่, ยืนยัน' });
    return;
  }
  if (newPass.value.length < 4) {
    Swal.fire({ icon: 'warning', title: 'รหัสสั้นไป', text: 'รหัสผ่านใหม่อย่างน้อย 4 ตัว' });
    return;
  }
  if (newPass.value !== confirmPass.value) {
    Swal.fire({ icon: 'warning', title: 'รหัสผ่านใหม่ไม่ตรงกัน', text: 'ยืนยันรหัสผ่านให้ตรงกับรหัสใหม่' });
    return;
  }

  isSaving.value = true;
  try {
    await changePassword(oldPass.value, newPass.value);
    oldPass.value = newPass.value = confirmPass.value = '';
    // อัปเดต flag (must_change_password → false) แล้วค่อยพากลับหน้าแรก
    try { await authStore.loadMe(); } catch { /* ignore */ }
    Swal.fire({
      icon: 'success',
      title: 'เปลี่ยนรหัสผ่านสำเร็จ!',
      text: 'ครั้งหน้าใช้รหัสใหม่ในการเข้าสู่ระบบ',
      timer: 1500,
      showConfirmButton: false,
    }).then(() => {
      router.push({ name: homeRouteName() });
    });
  } catch (e: unknown) {
    Swal.fire({ icon: 'error', title: 'เปลี่ยนรหัสไม่สำเร็จ', text: e instanceof Error ? e.message : 'เกิดข้อผิดพลาด' });
  } finally {
    isSaving.value = false;
  }
}

const goBack = () => router.push({ name: 'profile' });

const inputCls = 'w-full px-3.5 py-2.5 border border-gray-300 rounded-xl text-sm mt-1 focus:ring-2 focus:ring-red-500 focus:border-red-500 transition';
</script>

<template>
  <div class="max-w-2xl mx-auto">
    <form @submit.prevent="submit" class="space-y-4">
      <!-- Header -->
      <div class="flex items-center gap-3">
        <button type="button" @click="goBack" class="w-9 h-9 rounded-xl bg-white border border-gray-200 text-gray-500 hover:text-red-600 hover:border-red-300 flex items-center justify-center transition shrink-0">
          <i class="bi bi-arrow-left text-lg"></i>
        </button>
        <div>
          <h1 class="text-xl sm:text-2xl font-bold text-gray-900 leading-tight"><i class="bi bi-shield-lock mr-1 text-red-500"></i> เปลี่ยนรหัสผ่าน</h1>
          <p class="text-sm text-gray-500">ตั้งรหัสผ่านใหม่เพื่อความปลอดภัย</p>
        </div>
      </div>

      <!-- บังคับเปลี่ยนครั้งแรก -->
      <div v-if="isForced" class="bg-amber-50 border border-amber-200 rounded-2xl p-4 text-sm text-amber-800 flex gap-3">
        <i class="bi bi-shield-exclamation text-xl shrink-0"></i>
        <div>
          <p class="font-bold">บัญชีนี้เป็นบัญชีเริ่มต้นของระบบ</p>
          <p class="text-amber-700 mt-0.5">กรุณาเปลี่ยนรหัสผ่านก่อนใช้งาน เพื่อป้องกันผู้อื่นเข้าถึง</p>
        </div>
      </div>

      <div class="bg-white rounded-2xl shadow-sm p-5 space-y-4">
        <div>
          <label class="text-xs font-medium text-gray-500">รหัสผ่านเดิม</label>
          <input v-model="oldPass" type="password" :class="inputCls" placeholder="••••••" autocomplete="current-password" />
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label class="text-xs font-medium text-gray-500">รหัสผ่านใหม่</label>
            <input v-model="newPass" type="password" :class="inputCls" placeholder="อย่างน้อย 4 ตัว" autocomplete="new-password" />
          </div>
          <div>
            <label class="text-xs font-medium text-gray-500">ยืนยันรหัสผ่านใหม่</label>
            <input v-model="confirmPass" type="password" :class="inputCls" placeholder="พิมพ์ซ้ำอีกครั้ง" autocomplete="new-password" />
          </div>
        </div>
      </div>

      <button
        type="submit"
        :disabled="isSaving"
        class="w-full py-3 bg-gradient-to-r from-red-600 to-rose-600 text-white rounded-xl hover:from-red-700 hover:to-rose-700 disabled:opacity-50 font-semibold shadow-md shadow-red-200 transition-all"
      >
        <i class="bi bi-key mr-1"></i> {{ isSaving ? 'กำลังเปลี่ยน...' : 'เปลี่ยนรหัสผ่าน' }}
      </button>
    </form>
  </div>
</template>
