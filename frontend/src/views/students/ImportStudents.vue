<script setup lang="ts">
import { ref } from 'vue';
import Swal from 'sweetalert2';
import { importStudents } from '@/services/student';

const file = ref<File | null>(null);
const isLoading = ref(false);
const result = ref<{ total_rows: number; imported: number; skipped: number; errors: string[] } | null>(null);

function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement;
  file.value = input.files?.[0] || null;
}

async function handleImport() {
  if (!file.value) {
    Swal.fire({ icon: 'warning', title: 'เลือกไฟล์ก่อน', text: 'กรุณาเลือกไฟล์ Excel (.xlsx)' });
    return;
  }
  if (!/\.(xlsx|xls)$/i.test(file.value.name)) {
    Swal.fire({ icon: 'warning', title: 'ไฟล์ไม่ถูกต้อง', text: 'กรุณาใช้ไฟล์ .xlsx' });
    return;
  }

  isLoading.value = true;
  result.value = null;
  try {
    const res = await importStudents(file.value);
    result.value = res;
    Swal.fire({
      icon: 'success',
      title: 'นำเข้าสำเร็จ!',
      html: `นำเข้า <b>${res.imported}</b> คน<br>ข้าม <b>${res.skipped}</b> คน`,
    });
  } catch (e: any) {
    Swal.fire({ icon: 'error', title: 'นำเข้าไม่สำเร็จ', text: e.message });
  } finally {
    isLoading.value = false;
  }
}
</script>

<template>
  <div class="max-w-2xl mx-auto">
    <h1 class="text-2xl font-bold text-gray-900 mb-2"><i class="bi bi-inbox mr-1"></i> นำเข้านักเรียนจาก Excel</h1>

    <div class="bg-red-50 border border-red-200 rounded-xl p-4 mb-5 text-sm text-red-800">
      <p class="font-semibold mb-1">รูปแบบไฟล์ Excel (.xlsx) — หัวคอลัมน์:</p>
      <code class="text-xs bg-white px-2 py-1 rounded">รหัสนักเรียน | ห้องเรียน | เลขที่ | คำนำหน้า | ชื่อ | นามสกุล | ชื่อเล่น | ตำแหน่งในห้องเรียน</code>
      <p class="text-xs mt-2 text-red-600">
        • ตำแหน่ง เช่น: หัวหน้าห้อง, รองวิชาการ, รองวินัย, รองกิจกรรม, รองปฏิคม, ประธานระดับ, ประธานสภา<br>
        • ห้องเรียนรูปแบบ: ม.4/1 (สร้างห้องใหม่ให้อัตโนมัติถ้ายังไม่มี)<br>
        • 🔑 รหัสผ่านเริ่มต้น = เลขรหัสนักเรียน (เช่น รหัส 47075 → ใช้ 47075/47075 เข้าระบบครั้งแรก)
      </p>
    </div>

    <div class="bg-white rounded-xl shadow-sm p-5 space-y-4">
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">เลือกไฟล์ Excel</label>
        <input type="file" accept=".xlsx,.xls" @change="onFileChange"
          class="w-full text-sm file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-red-600 file:text-white hover:file:bg-red-700" />
      </div>
      <button @click="handleImport" :disabled="isLoading"
        class="w-full py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 font-medium">
        {{ isLoading ? 'กำลังนำเข้า...' : 'นำเข้านักเรียน' }}
      </button>

      <div v-if="result" class="bg-green-50 border border-green-200 rounded-lg p-4 text-sm">
        <p><b>ทั้งหมด:</b> {{ result.total_rows }} แถว</p>
        <p><b>นำเข้า:</b> {{ result.imported }} คน</p>
        <p><b>ข้าม:</b> {{ result.skipped }} คน</p>
        <div v-if="result.errors.length" class="mt-2">
          <p class="text-red-600 font-medium">ข้อผิดพลาด:</p>
          <ul class="text-xs text-red-500 list-disc pl-4 mt-1 max-h-40 overflow-auto">
            <li v-for="(e, idx) in result.errors" :key="idx">{{ e }}</li>
          </ul>
        </div>
      </div>
    </div>
  </div>
</template>
