<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue';
import Swal from 'sweetalert2';
import { uploadStudentExcel, startImportJob, listImportJobs } from '@/services/student';
import type { ImportJob, ImportJobStatus } from '@/types/student';

const file = ref<File | null>(null);
const isUploading = ref(false);
const isStartingJobId = ref<number | null>(null);

// รายการงาน import ทั้งหมด (ใช้ดูประวัติ + progress)
const jobs = ref<ImportJob[]>([]);
const isJobsLoading = ref(true);

// Polling — กัน poll ซ้อน ถ้ามี timer ค้างอยู่ + ใน-flight guard (กัน request ซ้อนค้างคิว)
let pollTimer: number | null = null;
let pollInFlight = false;

const STATUS_LABELS: Record<ImportJobStatus, string> = {
  PENDING: 'รอเริ่มงาน',
  QUEUED: 'รอ worker',
  PROCESSING: 'กำลังนำเข้า...',
  COMPLETED: 'เสร็จสิ้น',
  FAILED: 'ล้มเหลว',
};

const STATUS_BADGES: Record<ImportJobStatus, string> = {
  PENDING: 'badge-warning',
  QUEUED: 'badge-info',
  PROCESSING: 'badge-info',
  COMPLETED: 'badge-success',
  FAILED: 'badge-error',
};

function errorMessage(e: unknown): string {
  return e instanceof Error ? e.message : 'เกิดข้อผิดพลาดจาก API';
}

function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement;
  file.value = input.files?.[0] || null;
}

function isRunning(status: ImportJobStatus): boolean {
  return status === 'PROCESSING' || status === 'QUEUED';
}

async function handleUpload() {
  if (!file.value) {
    Swal.fire({ icon: 'warning', title: 'เลือกไฟล์ก่อน', text: 'กรุณาเลือกไฟล์ Excel (.xlsx)' });
    return;
  }
  if (!/\.(xlsx|xls)$/i.test(file.value.name)) {
    Swal.fire({ icon: 'warning', title: 'ไฟล์ไม่ถูกต้อง', text: 'กรุณาใช้ไฟล์ .xlsx' });
    return;
  }

  isUploading.value = true;
  try {
    const job = await uploadStudentExcel(file.value);
    await refreshJobs();
    Swal.fire({
      icon: 'success',
      title: 'อัปโหลดไฟล์สำเร็จ!',
      html: `พบข้อมูล <b>${job.total_rows}</b> แถว<br>กด "เริ่มนำเข้า" เพื่อสั่งให้ระบบทำงาน`,
    });
  } catch (e) {
    Swal.fire({ icon: 'error', title: 'อัปโหลดไม่สำเร็จ', text: errorMessage(e) });
  } finally {
    isUploading.value = false;
  }
}

async function handleStart(jobId: number) {
  isStartingJobId.value = jobId;
  try {
    const job = await startImportJob(jobId);
    await refreshJobs();
    if (job.status === 'QUEUED') {
      Swal.fire({
        icon: 'success',
        title: 'เริ่มงานแล้ว!',
        text: 'ระบบกำลังนำเข้านักเรียน... ดูความคืบหน้าในตารางด้านล่าง',
      });
    }
  } catch (e) {
    Swal.fire({ icon: 'error', title: 'เริ่มงานไม่สำเร็จ', text: errorMessage(e) });
  } finally {
    isStartingJobId.value = null;
  }
}

async function refreshJobs() {
  try {
    jobs.value = await listImportJobs();
    // ถ้ามีงานที่กำลังทำงาน/รอ worker → เริ่ม poll progress
    if (jobs.value.some((j) => isRunning(j.status))) {
      startPolling();
    }
  } catch {
    // ไม่พัง UI — โชว์แค่ตารางว่าง
  } finally {
    isJobsLoading.value = false;
  }
}

function startPolling() {
  if (pollTimer !== null) return;
  pollTimer = window.setInterval(async () => {
    // ใน-flight guard — ถ้ารอบก่อนยังไม่เสร็จ (network ช้า) ข้ามรอบนี้ กัน poll ซ้อน
    if (pollInFlight) return;
    pollInFlight = true;
    try {
      jobs.value = await listImportJobs();
      const stillRunning = jobs.value.some((j) => isRunning(j.status));
      if (!stillRunning) stopPolling();
    } catch {
      // error ชั่วคราว (เช่น network หลุด) — ไม่หยุด poll ถาวร ปล่อย poll รอบถัดไปลองใหม่
      // (หยุด poll เฉพาะเมื่องานทั้งหมดจบลงเท่านั้น ดูเงื่อนไข !stillRunning)
    } finally {
      pollInFlight = false;
    }
  }, 3000);
}

function stopPolling() {
  if (pollTimer !== null) {
    window.clearInterval(pollTimer);
    pollTimer = null;
  }
}

onMounted(refreshJobs);
onBeforeUnmount(stopPolling);
</script>

<template>
  <div class="max-w-4xl mx-auto">
    <h1 class="text-2xl font-bold text-gray-900 mb-2"><i class="bi bi-inbox mr-1"></i> นำเข้านักเรียนจาก Excel</h1>

    <!-- รูปแบบไฟล์ -->
    <div class="bg-red-50 border border-red-200 rounded-xl p-4 mb-5 text-sm text-red-800">
      <p class="font-semibold mb-1">รูปแบบไฟล์ Excel (.xlsx) — หัวคอลัมน์ (ต้องเป๊ะ ห้ามมีคอลัมน์เกิน):</p>
      <code class="text-xs bg-white px-2 py-1 rounded">รหัสนักเรียน | ห้องเรียน | เลขที่ | คำนำหน้า | ชื่อ | นามสกุล | ชื่อเล่น | ตำแหน่งในห้องเรียน</code>
      <p class="text-xs mt-2 text-red-600">
        • ตำแหน่ง เช่น: หัวหน้าห้อง, รองวิชาการ, รองวินัย, รองกิจกรรม, รองปฏิคม, ประธานระดับ, ประธานสภา<br>
        • ห้องเรียนรูปแบบ: ม.4/1 (สร้างห้องใหม่ให้อัตโนมัติถ้ายังไม่มี)<br>
        • 🔑 รหัสผ่านเริ่มต้น = เลขรหัสนักเรียน (เช่น รหัส 47075 → ใช้ 47075/47075 เข้าระบบครั้งแรก)<br>
        • ⚙️ ระบบนำเข้าแบบคิว (Queue) — อัปโหลดเสร็จต้องกด "เริ่มนำเข้า" อีกครั้ง ระบบจะทำงานเบื้องหลัง
      </p>
    </div>

    <!-- ขั้นตอน 1: อัปโหลด -->
    <div class="bg-white rounded-xl shadow-sm p-5 space-y-4">
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">1. เลือกไฟล์ Excel</label>
        <input type="file" accept=".xlsx,.xls" @change="onFileChange"
          class="w-full text-sm file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-red-600 file:text-white hover:file:bg-red-700" />
      </div>
      <button @click="handleUpload" :disabled="isUploading"
        class="w-full py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 font-medium">
        {{ isUploading ? 'กำลังตรวจสอบและอัปโหลด...' : 'อัปโหลดไฟล์' }}
      </button>
    </div>

    <!-- ตารางประวัติงาน import -->
    <div class="bg-white rounded-xl shadow-sm p-5 mt-5">
      <div class="flex items-center justify-between mb-3">
        <h2 class="text-lg font-semibold text-gray-900">รายการงานนำเข้า</h2>
        <span v-if="isJobsLoading" class="loading loading-spinner loading-sm text-red-600"></span>
      </div>

      <div v-if="jobs.length === 0 && !isJobsLoading" class="text-sm text-gray-400 text-center py-6">
        ยังไม่มีงานนำเข้า — อัปโหลดไฟล์ด้านบนก่อน
      </div>

      <div v-else class="overflow-x-auto">
        <table class="table table-sm w-full">
          <thead>
            <tr class="text-gray-500 text-xs">
              <th>ไฟล์</th>
              <th>สถานะ</th>
              <th>ความคืบหน้า</th>
              <th>นำเข้า/ข้าม</th>
              <th class="text-right">จัดการ</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="job in jobs" :key="job.id">
              <td class="font-medium text-sm">
                {{ job.file_name }}
                <div class="text-xs text-gray-400">
                  {{ new Date(job.created_at).toLocaleString('th-TH', { timeZone: 'Asia/Bangkok' }) }}
                </div>
              </td>
              <td>
                <span class="badge badge-sm" :class="STATUS_BADGES[job.status]">{{ STATUS_LABELS[job.status] }}</span>
                <!-- error_message โชว์เฉพาะสถานะ FAILED — กัน error เก่าค้างเมื่อลองใหม่แล้วสำเร็จ -->
                <div v-if="job.status === 'FAILED' && job.error_message" class="text-xs text-red-500 mt-1">
                  {{ job.error_message }}
                </div>
              </td>
              <td class="min-w-[160px]">
                <div v-if="job.status === 'PENDING' || job.status === 'QUEUED' || job.status === 'PROCESSING'">
                  <progress class="progress progress-primary w-full" :value="job.progress_percent" max="100"></progress>
                  <div class="text-xs text-gray-500 mt-1">{{ job.processed_rows }}/{{ job.total_rows }} แถว ({{ job.progress_percent }}%)</div>
                </div>
                <div v-else class="text-sm text-gray-600">
                  {{ job.imported_count + job.skipped_count }}/{{ job.total_rows }} แถว
                </div>
              </td>
              <td class="text-sm text-gray-600">
                <span class="text-green-600">{{ job.imported_count }}</span> /
                <span class="text-amber-600">{{ job.skipped_count }}</span>
              </td>
              <td class="text-right">
                <button
                  v-if="job.status === 'PENDING'"
                  @click="handleStart(job.id)"
                  :disabled="isStartingJobId !== null"
                  class="btn btn-sm btn-primary disabled:opacity-50">
                  <span v-if="isStartingJobId === job.id" class="loading loading-spinner loading-xs"></span>
                  เริ่มนำเข้า
                </button>
                <button
                  v-else-if="job.status === 'FAILED'"
                  @click="handleStart(job.id)"
                  :disabled="isStartingJobId !== null"
                  class="btn btn-sm btn-outline btn-error disabled:opacity-50">
                  ลองใหม่
                </button>
                <span v-else class="text-xs text-gray-400">—</span>
              </td>
            </tr>
          </tbody>
        </table>

        <!-- error_logs ของงานที่เพิ่งเสร็จ -->
        <div v-for="job in jobs" :key="'err' + job.id">
          <div v-if="job.error_logs.length" class="mt-2">
            <details class="bg-red-50 border border-red-100 rounded-lg p-3 text-xs">
              <summary class="text-red-600 font-medium cursor-pointer">
                {{ job.file_name }} — ข้อผิดพลาด {{ job.error_logs.length }} รายการ
              </summary>
              <ul class="list-disc pl-4 mt-2 text-red-500 max-h-40 overflow-auto">
                <li v-for="(e, idx) in job.error_logs" :key="idx">{{ e }}</li>
              </ul>
            </details>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
