<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import Swal from 'sweetalert2';
import { getMyProfile, updateMyProfile, changePassword, type MyProfile } from '@/services/profile';
import { useAuthStore } from '@/stores/auth';

const authStore = useAuthStore();

const profile = ref<MyProfile | null>(null);
const isLoading = ref(true);
const isEditing = ref(false);

// form
const editPrefix = ref('');
const editFirstName = ref('');
const editLastName = ref('');
const editNickname = ref('');
const editPhone = ref('');
const editEmail = ref('');

// password form
const oldPass = ref('');
const newPass = ref('');
const confirmPass = ref('');

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
};

const avatarChar = computed(() => {
  const name = profile.value?.nickname || profile.value?.first_name || '';
  return name ? name.charAt(0).toUpperCase() : 'ส';
});

async function load() {
  isLoading.value = true;
  try {
    profile.value = await getMyProfile();
  } catch (e: any) {
    Swal.fire({ icon: 'error', title: 'โหลดโปรไฟล์ไม่สำเร็จ', text: e.message });
  } finally {
    isLoading.value = false;
  }
}
onMounted(load);

function startEdit() {
  if (!profile.value) return;
  isEditing.value = true;
  editPrefix.value = profile.value.prefix || '';
  editFirstName.value = profile.value.first_name || '';
  editLastName.value = profile.value.last_name || '';
  editNickname.value = profile.value.nickname || '';
  editPhone.value = profile.value.phone_number || '';
  editEmail.value = profile.value.email || '';
}

async function saveProfile() {
  if (!editFirstName.value.trim() || !editLastName.value.trim()) {
    Swal.fire({ icon: 'warning', title: 'กรอกชื่อให้ครบ', text: 'ชื่อ และ นามสกุล จำเป็น' });
    return;
  }
  try {
    profile.value = await updateMyProfile({
      prefix: editPrefix.value.trim() || null,
      first_name: editFirstName.value.trim(),
      last_name: editLastName.value.trim(),
      nickname: editNickname.value.trim() || null,
      phone_number: editPhone.value.trim() || null,
      email: editEmail.value.trim() || null,
    });
    isEditing.value = false;
    // อัปเดต display name ใน auth store
    await authStore.loadMe();
    Swal.fire({ icon: 'success', title: 'บันทึกโปรไฟล์แล้ว', timer: 1200, showConfirmButton: false });
  } catch (e: any) {
    Swal.fire({ icon: 'error', title: 'บันทึกไม่สำเร็จ', text: e.message });
  }
}

async function submitChangePassword() {
  if (!oldPass.value || !newPass.value || !confirmPass.value) {
    Swal.fire({ icon: 'warning', title: 'กรอกให้ครบ', text: 'กรอกรหัสผ่านเดิม, ใหม่, ยืนยัน' });
    return;
  }
  if (newPass.value !== confirmPass.value) {
    Swal.fire({ icon: 'warning', title: 'รหัสผ่านใหม่ไม่ตรงกัน', text: 'ยืนยันรหัสผ่านให้ตรงกับรหัสใหม่' });
    return;
  }
  if (newPass.value.length < 4) {
    Swal.fire({ icon: 'warning', title: 'รหัสสั้นไป', text: 'รหัสผ่านใหม่อย่างน้อย 4 ตัว' });
    return;
  }
  try {
    await changePassword(oldPass.value, newPass.value);
    oldPass.value = newPass.value = confirmPass.value = '';
    Swal.fire({ icon: 'success', title: 'เปลี่ยนรหัสผ่านสำเร็จ!', text: 'ครั้งหน้าใช้รหัสใหม่ในการเข้าสู่ระบบ' });
  } catch (e: any) {
    Swal.fire({ icon: 'error', title: 'เปลี่ยนรหัสไม่สำเร็จ', text: e.message });
  }
}
</script>

<template>
  <div class="max-w-2xl mx-auto">
    <div v-if="isLoading" class="flex justify-center py-20">
      <div class="animate-spin w-10 h-10 border-4 border-red-600 border-t-transparent rounded-full"></div>
    </div>

    <div v-else-if="profile" class="space-y-5">
      <!-- Header card -->
      <div class="bg-white rounded-xl shadow-sm p-6">
        <div class="flex items-center gap-4">
          <div class="w-20 h-20 rounded-full bg-gradient-to-br from-red-100 to-red-50 text-red-600 flex items-center justify-center text-3xl font-bold shadow-inner border border-red-100">
            {{ avatarChar }}
          </div>
          <div class="flex-1">
            <h1 class="text-2xl font-bold text-gray-900">
              {{ profile.prefix || '' }} {{ profile.first_name }} {{ profile.last_name }}
            </h1>
            <div class="flex flex-wrap gap-2 mt-2">
              <span class="px-2.5 py-0.5 bg-red-100 text-red-700 text-xs rounded-full">
                <i class="bi bi-mortarboard mr-1"></i>{{ ROLE_LABELS[profile.class_role] || profile.class_role }}
              </span>
              <span class="px-2.5 py-0.5 bg-gray-100 text-gray-600 text-xs rounded-full">
                <i class="bi bi-door-closed mr-1"></i>{{ profile.room_code }}
              </span>
              <span class="px-2.5 py-0.5 bg-gray-100 text-gray-600 text-xs rounded-full">
                <i class="bi bi-hash mr-1"></i>{{ profile.student_no }}
              </span>
            </div>
          </div>
          <button v-if="!isEditing" @click="startEdit" class="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 text-sm">
            <i class="bi bi-pencil-square mr-1"></i> แก้ไข
          </button>
        </div>
      </div>

      <!-- Profile details -->
      <div class="bg-white rounded-xl shadow-sm p-6">
        <h2 class="text-lg font-bold text-gray-800 mb-4">ข้อมูลส่วนตัว</h2>

        <div v-if="!isEditing" class="grid grid-cols-2 gap-4">
          <div>
            <p class="text-xs text-gray-400 font-medium">รหัสนักเรียน</p>
            <p class="font-mono text-gray-800">{{ profile.student_id }}</p>
          </div>
          <div>
            <p class="text-xs text-gray-400 font-medium">เลขที่</p>
            <p class="text-gray-800">{{ profile.student_no }}</p>
          </div>
          <div>
            <p class="text-xs text-gray-400 font-medium">ชื่อ</p>
            <p class="text-gray-800">{{ profile.first_name }}</p>
          </div>
          <div>
            <p class="text-xs text-gray-400 font-medium">นามสกุล</p>
            <p class="text-gray-800">{{ profile.last_name }}</p>
          </div>
          <div>
            <p class="text-xs text-gray-400 font-medium">ชื่อเล่น</p>
            <p class="text-gray-800">{{ profile.nickname || '-' }}</p>
          </div>
          <div>
            <p class="text-xs text-gray-400 font-medium">เบอร์โทร</p>
            <p class="text-gray-800">{{ profile.phone_number || '-' }}</p>
          </div>
          <div>
            <p class="text-xs text-gray-400 font-medium">อีเมล</p>
            <p class="text-gray-800">{{ profile.email || '-' }}</p>
          </div>
          <div>
            <p class="text-xs text-gray-400 font-medium">ห้องเรียน</p>
            <p class="text-gray-800">{{ profile.room_code }} ({{ profile.level }})</p>
          </div>
        </div>

        <!-- Edit form -->
        <div v-else class="space-y-3">
          <div class="grid grid-cols-3 gap-3">
            <div>
              <label class="text-xs text-gray-500">คำนำหน้า</label>
              <input v-model="editPrefix" class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm mt-1" placeholder="นาย/นางสาว" />
            </div>
            <div>
              <label class="text-xs text-gray-500">ชื่อ *</label>
              <input v-model="editFirstName" class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm mt-1" />
            </div>
            <div>
              <label class="text-xs text-gray-500">นามสกุล *</label>
              <input v-model="editLastName" class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm mt-1" />
            </div>
          </div>
          <div>
            <label class="text-xs text-gray-500">ชื่อเล่น</label>
            <input v-model="editNickname" class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm mt-1" />
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="text-xs text-gray-500">เบอร์โทร</label>
              <input v-model="editPhone" class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm mt-1" />
            </div>
            <div>
              <label class="text-xs text-gray-500">อีเมล</label>
              <input v-model="editEmail" type="email" class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm mt-1" />
            </div>
          </div>
          <div class="flex gap-2 pt-2">
            <button @click="saveProfile" class="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 text-sm">
              <i class="bi bi-check-lg mr-1"></i> บันทึก
            </button>
            <button @click="isEditing = false" class="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 text-sm">
              ยกเลิก
            </button>
          </div>
        </div>
      </div>

      <!-- Change password -->
      <div class="bg-white rounded-xl shadow-sm p-6">
        <h2 class="text-lg font-bold text-gray-800 mb-4">เปลี่ยนรหัสผ่าน</h2>
        <div class="space-y-3">
          <div>
            <label class="text-xs text-gray-500">รหัสผ่านเดิม</label>
            <input v-model="oldPass" type="password" class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm mt-1" placeholder="••••••" />
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="text-xs text-gray-500">รหัสผ่านใหม่</label>
              <input v-model="newPass" type="password" class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm mt-1" placeholder="อย่างน้อย 4 ตัว" />
            </div>
            <div>
              <label class="text-xs text-gray-500">ยืนยันรหัสผ่านใหม่</label>
              <input v-model="confirmPass" type="password" class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm mt-1" placeholder="พิมพ์ซ้ำ" />
            </div>
          </div>
          <button @click="submitChangePassword" class="px-4 py-2 bg-gray-800 text-white rounded-lg hover:bg-gray-900 text-sm">
            <i class="bi bi-shield-lock mr-1"></i> เปลี่ยนรหัสผ่าน
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
