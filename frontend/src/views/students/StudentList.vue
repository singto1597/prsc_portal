<script setup lang="ts">
import { ref, onMounted } from 'vue';
import Swal from 'sweetalert2';
import { listStudents, listRooms, updateStudent } from '@/services/student';
import type { Student, Room } from '@/types/student';

const students = ref<Student[]>([]);
const rooms = ref<Room[]>([]);
const isLoading = ref(true);
const roomFilter = ref<number | ''>('');
const search = ref('');

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

async function load() {
  isLoading.value = true;
  try {
    [students.value, rooms.value] = await Promise.all([
      listStudents({ room_id: roomFilter.value || undefined, search: search.value || undefined }),
      listRooms(),
    ]);
  } catch (e: any) {
    Swal.fire({ icon: 'error', title: 'โหลดข้อมูลไม่สำเร็จ', text: e.message });
  } finally {
    isLoading.value = false;
  }
}
onMounted(load);

async function changeRole(student: Student) {
  const { value } = await Swal.fire({
    icon: 'question',
    title: 'เปลี่ยนตำแหน่ง: ' + (student.first_name || '') + ' ' + (student.last_name || ''),
    input: 'select',
    inputOptions: ROLE_LABELS,
    inputValue: student.class_role,
    showCancelButton: true,
    confirmButtonText: 'บันทึก',
    cancelButtonText: 'ยกเลิก',
  });
  if (!value) return;
  try {
    await updateStudent(student.id, { class_role: value });
    Swal.fire({ icon: 'success', title: 'บันทึกแล้ว', timer: 1000, showConfirmButton: false });
    load();
  } catch (e: any) {
    Swal.fire({ icon: 'error', title: 'ไม่สำเร็จ', text: e.message });
  }
}
</script>

<template>
  <div>
    <div class="flex items-center justify-between mb-5">
      <h1 class="text-2xl font-bold text-gray-900"><i class="bi bi-mortarboard mr-1"></i> รายชื่อนักเรียน</h1>
    </div>

    <!-- Filters -->
    <div class="flex gap-3 mb-4">
      <select v-model="roomFilter" @change="load" class="px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white">
        <option value="">ทุกห้อง</option>
        <option v-for="r in rooms" :key="r.id" :value="r.id">{{ r.room_code }}</option>
      </select>
      <input v-model="search" @keyup.enter="load" type="text" placeholder="ค้นหา รหัสนักเรียน/ชื่อ..."
        class="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm" />
      <button @click="load" class="px-4 py-2 bg-gray-100 rounded-lg text-sm hover:bg-gray-200">
        <i class="bi bi-search"></i> ค้นหา
      </button>
    </div>

    <div v-if="isLoading" class="flex justify-center py-16">
      <div class="animate-spin w-10 h-10 border-4 border-red-600 border-t-transparent rounded-full"></div>
    </div>

    <div v-else class="bg-white rounded-xl shadow-sm overflow-hidden">
      <table class="w-full text-sm">
        <thead class="bg-gray-50 text-gray-500">
          <tr>
            <th class="px-4 py-3 text-left">เลขที่</th>
            <th class="px-4 py-3 text-left">รหัสนักเรียน</th>
            <th class="px-4 py-3 text-left">ชื่อ-นามสกุล</th>
            <th class="px-4 py-3 text-left">ห้อง</th>
            <th class="px-4 py-3 text-left">ตำแหน่ง</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-100">
          <tr v-for="s in students" :key="s.id" class="hover:bg-gray-50">
            <td class="px-4 py-2.5 text-gray-500">{{ s.student_no }}</td>
            <td class="px-4 py-2.5 font-mono text-gray-600">{{ s.student_id }}</td>
            <td class="px-4 py-2.5 font-medium text-gray-800">
              {{ s.prefix || '' }} {{ s.first_name || '' }} {{ s.last_name || '' }}
            </td>
            <td class="px-4 py-2.5">{{ s.room_code }}</td>
            <td class="px-4 py-2.5">
              <button @click="changeRole(s)" class="px-2.5 py-1 rounded-full text-xs font-medium"
                :class="s.class_role === 'student' ? 'bg-gray-100 text-gray-600' : 'bg-red-100 text-red-700'">
                {{ ROLE_LABELS[s.class_role] || s.class_role }} <i class="bi bi-pencil-square text-[10px]"></i>
              </button>
            </td>
          </tr>
          <tr v-if="!students.length">
            <td colspan="5" class="px-4 py-8 text-center text-gray-400">ไม่พบนักเรียน</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
