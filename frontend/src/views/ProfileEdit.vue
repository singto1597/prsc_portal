<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { useRouter } from 'vue-router';
import Swal from 'sweetalert2';
import { getMyProfile, updateMyProfile } from '@/services/profile';
import { useAuthStore } from '@/stores/auth';

const router = useRouter();
const authStore = useAuthStore();

const isLoading = ref(true);
const isSaving = ref(false);

const editPrefix = ref('');
const editFirstName = ref('');
const editLastName = ref('');
const editNickname = ref('');
const editPhone = ref('');
const editEmail = ref('');

onMounted(async () => {
  try {
    const p = await getMyProfile();
    editPrefix.value = p.prefix || '';
    editFirstName.value = p.first_name || '';
    editLastName.value = p.last_name || '';
    editNickname.value = p.nickname || '';
    editPhone.value = p.phone_number || '';
    editEmail.value = p.email || '';
  } catch (e: unknown) {
    Swal.fire({ icon: 'error', title: 'โหลดโปรไฟล์ไม่สำเร็จ', text: e instanceof Error ? e.message : 'เกิดข้อผิดพลาด' });
  } finally {
    isLoading.value = false;
  }
});

const canSave = computed(() => editFirstName.value.trim() && editLastName.value.trim());

async function saveProfile() {
  if (!editFirstName.value.trim() || !editLastName.value.trim()) {
    Swal.fire({ icon: 'warning', title: 'กรอกชื่อให้ครบ', text: 'ชื่อ และ นามสกุล จำเป็น' });
    return;
  }
  isSaving.value = true;
  try {
    await updateMyProfile({
      prefix: editPrefix.value.trim() || null,
      first_name: editFirstName.value.trim(),
      last_name: editLastName.value.trim(),
      nickname: editNickname.value.trim() || null,
      phone_number: editPhone.value.trim() || null,
      email: editEmail.value.trim() || null,
    });
    // อัปเดต display name ใน auth store (ชื่อที่ขึ้น sidebar/header)
    await authStore.loadMe();
    Swal.fire({ icon: 'success', title: 'บันทึกโปรไฟล์แล้ว', timer: 1200, showConfirmButton: false });
    router.push({ name: 'profile' });
  } catch (e: unknown) {
    Swal.fire({ icon: 'error', title: 'บันทึกไม่สำเร็จ', text: e instanceof Error ? e.message : 'เกิดข้อผิดพลาด' });
  } finally {
    isSaving.value = false;
  }
}

const goBack = () => router.push({ name: 'profile' });

const inputCls = 'w-full px-3.5 py-2.5 border border-gray-300 rounded-xl text-sm mt-1 focus:ring-2 focus:ring-red-500 focus:border-red-500 transition';
</script>

<template>
  <div class="max-w-2xl mx-auto">
    <div v-if="isLoading" class="flex justify-center py-20">
      <div class="animate-spin w-10 h-10 border-4 border-red-600 border-t-transparent rounded-full"></div>
    </div>

    <form v-else @submit.prevent="saveProfile" class="space-y-4">
      <!-- Header -->
      <div class="flex items-center gap-3">
        <button type="button" @click="goBack" class="w-9 h-9 rounded-xl bg-white border border-gray-200 text-gray-500 hover:text-red-600 hover:border-red-300 flex items-center justify-center transition shrink-0">
          <i class="bi bi-arrow-left text-lg"></i>
        </button>
        <div>
          <h1 class="text-xl sm:text-2xl font-bold text-gray-900 leading-tight"><i class="bi bi-pencil-square mr-1 text-red-500"></i> แก้ไขโปรไฟล์</h1>
          <p class="text-sm text-gray-500">แก้ข้อมูลส่วนตัวของคุณ</p>
        </div>
      </div>

      <div class="bg-white rounded-2xl shadow-sm p-5 space-y-4">
        <!-- ชื่อ: คำนำหน้า / ชื่อ / นามสกุล (mobile = 1 คอลัมน์) -->
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div>
            <label class="text-xs font-medium text-gray-500">คำนำหน้า</label>
            <input v-model="editPrefix" :class="inputCls" placeholder="นาย / นางสาว" />
          </div>
          <div>
            <label class="text-xs font-medium text-gray-500">ชื่อ <span class="text-red-500">*</span></label>
            <input v-model="editFirstName" :class="inputCls" required />
          </div>
          <div>
            <label class="text-xs font-medium text-gray-500">นามสกุล <span class="text-red-500">*</span></label>
            <input v-model="editLastName" :class="inputCls" required />
          </div>
        </div>

        <div>
          <label class="text-xs font-medium text-gray-500">ชื่อเล่น</label>
          <input v-model="editNickname" :class="inputCls" placeholder="ชื่อที่เพื่อนเรียก" />
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label class="text-xs font-medium text-gray-500">เบอร์โทร</label>
            <input v-model="editPhone" :class="inputCls" type="tel" placeholder="08x-xxx-xxxx" />
          </div>
          <div>
            <label class="text-xs font-medium text-gray-500">อีเมล</label>
            <input v-model="editEmail" :class="inputCls" type="email" placeholder="example@mail.com" />
          </div>
        </div>
      </div>

      <!-- ปุ่ม -->
      <div class="flex gap-2 pt-1">
        <button
          type="submit"
          :disabled="isSaving || !canSave"
          class="flex-1 py-3 bg-gradient-to-r from-red-600 to-rose-600 text-white rounded-xl hover:from-red-700 hover:to-rose-700 disabled:opacity-50 font-semibold shadow-md shadow-red-200 transition-all"
        >
          <i class="bi bi-check-lg mr-1"></i> {{ isSaving ? 'กำลังบันทึก...' : 'บันทึก' }}
        </button>
        <button
          type="button"
          @click="goBack"
          class="px-5 py-3 bg-white border border-gray-200 text-gray-600 rounded-xl hover:bg-gray-50 text-sm font-medium transition"
        >
          ยกเลิก
        </button>
      </div>
    </form>
  </div>
</template>
