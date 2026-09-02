<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue';
import Swal from 'sweetalert2';
import {
  uploadStudentExcel,
  startImportJob,
  listImportJobs,
  downloadImportTemplate,
} from '@/services/student';
import type { ImportJob } from '@/types/student';
import {
  IMPORT_STATUS_LABELS,
  IMPORT_STATUS_BADGES,
  IMPORT_BAR_FILL,
  IMPORT_BAR_TEXT,
  isImportJobRunning,
} from '@/constants/importStatus';

// Short polling — ดึงสถานะงานจาก API ทุกๆ 2.5 วิ (ผู้ใช้ไม่ต้องรอลุ้นหน้าเว็บค้าง)
const POLL_INTERVAL_MS = 2500;

const file = ref<File | null>(null);
const isUploading = ref(false);
const isDownloadingTemplate = ref(false);
const isStartingJobId = ref<number | null>(null);
const isRefreshing = ref(false);

// รายการงานใน Queue List (ใหม่สุดก่อนจาก backend)
const jobs = ref<ImportJob[]>([]);
const isJobsLoading = ref(true);
// โหลดครั้งแรก/รีเฟรชพลาด (network ติดขัด) — ห้ามโชว์ "ยังไม่มีไฟล์" หลอกครู (อาจมีไฟล์ในคิวจริง)
const loadError = ref(false);
// poll ติดกันเกินลิมิต — โชว์แบนเนอร์บอก user ว่าเชื่อมต่อไม่แน่นอน (ไม่ปิด poll — พอ network กลับมา update เอง)
const isPollError = ref(false);

// Polling — กัน poll ซ้อน: ใน-flight guard กัน request ค้างซ้อนกันคิว
const POLL_FAIL_LIMIT = 3;
let pollTimer: number | null = null;
let pollInFlight = false;
let pollFailStreak = 0;

// จำนวนงานที่กำลังทำงาน (QUEUED/PROCESSING) — โชว์ indicator + ใช้ตัดสินใจ poll ต่อไป
const runningJobs = computed(() => jobs.value.filter((j) => isImportJobRunning(j.status)));

function errorMessage(e: unknown): string {
  return e instanceof Error ? e.message : 'เกิดข้อผิดพลาดจาก API';
}

// 🛡️ ชื่อไฟล์มาจาก user (backend สะท้อนกลับ verbatim) — ต้อง escape ก่อนใส่ใน html ของ Swal
// (SweetAlert2 แทรก html ผ่าน innerHTML → ไฟล์ชื่อ <img onerror=...> ที่ถูกกฎหมายใน Linux/Mac กลายเป็น XSS ได้)
function escapeHtml(value: string): string {
  const chars: Record<string, string> = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  return value.replace(/[&<>"']/g, (c) => chars[c] ?? c);
}

function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement;
  file.value = input.files?.[0] || null;
  // รีเซ็ตค่า input หลังอ่าน — ให้เลือกไฟล์เดิมซ้ำได้อีก (change event จะไม่ยิงถ้าค่าไม่เปลี่ยน)
  input.value = '';
}

// ===================== ดาวน์โหลด Template =====================
async function handleDownloadTemplate() {
  isDownloadingTemplate.value = true;
  try {
    const blob = await downloadImportTemplate();
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'student_import_template.xlsx';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    // revoke ช้าๆ — browser ดาวน์โหลดแบบ async ถ้า revoke ทันทีบางตัว (เช่น Firefox) จะได้ไฟล์ 0 bytes
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (e) {
    Swal.fire({ icon: 'error', title: 'ดาวน์โหลดไม่สำเร็จ', text: errorMessage(e) });
  } finally {
    isDownloadingTemplate.value = false;
  }
}

// ===================== อัปโหลด → เข้า Queue ทันที =====================
async function handleUpload() {
  if (!file.value) {
    Swal.fire({ icon: 'warning', title: 'เลือกไฟล์ก่อน', text: 'กรุณาเลือกไฟล์ Excel (.xlsx)' });
    return;
  }
  // เฉพาะ .xlsx — legacy .xls (BIFF) อ่านด้วย openpyxl ไม่ได้ (รับแล้วก็ 400) กันเลยตั้งแต่หน้าเว็บ
  if (!/\.xlsx$/i.test(file.value.name)) {
    Swal.fire({ icon: 'warning', title: 'ไฟล์ไม่ถูกต้อง', text: 'กรุณาใช้ไฟล์ .xlsx' });
    return;
  }

  isUploading.value = true;
  try {
    const job = await uploadStudentExcel(file.value);
    file.value = null;
    await refreshJobs();
    Swal.fire({
      icon: 'success',
      title: 'อัปโหลดเข้า Queue แล้ว!',
      // escapeHtml ชื่อไฟล์ (มาจาก user) กัน XSS — Swal ใช้ innerHTML
      html: `ไฟล์ <b>${escapeHtml(job.file_name)}</b> พบข้อมูล <b>${job.total_rows}</b> แถว<br>กดปุ่ม <b>"เริ่มเดี๋ยวนี้"</b> ใน Queue List ด้านล่างเพื่อสั่งให้ระบบทำงาน`,
    });
  } catch (e) {
    Swal.fire({ icon: 'error', title: 'อัปโหลดไม่สำเร็จ', text: errorMessage(e) });
  } finally {
    isUploading.value = false;
  }
}

// ===================== กดเริ่มงาน (เริ่มเดี๋ยวนี้ / ลองใหม่) =====================
async function handleStart(jobId: number) {
  isStartingJobId.value = jobId;
  try {
    const job = await startImportJob(jobId);
    await refreshJobs();
    if (job.status === 'QUEUED') {
      Swal.fire({
        icon: 'success',
        title: 'เริ่มงานแล้ว!',
        text: 'ระบบกำลังนำเข้านักเรียนเบื้องหลัง — ดูความคืบหน้า (หลอดเปอร์เซ็นต์) ใน Queue List',
        timer: 2500,
        showConfirmButton: false,
      });
    }
  } catch (e) {
    Swal.fire({ icon: 'error', title: 'เริ่มงานไม่สำเร็จ', text: errorMessage(e) });
  } finally {
    isStartingJobId.value = null;
  }
}

// ===================== ดึง Queue List + Short Polling =====================
async function refreshJobs(showSpinner = false) {
  if (showSpinner) isRefreshing.value = true;
  try {
    jobs.value = await listImportJobs();
    loadError.value = false;
    pollFailStreak = 0;
    isPollError.value = false;
    // มีงานกำลังทำงาน/รอ worker → เริ่ม poll; ไม่มี → หยุด (ประหยัด request)
    if (runningJobs.value.length) startPolling();
    else stopPolling();
  } catch {
    // ยังเก็บรายการเดิมไว้ — แค่ปักธงพลาด (กันโชว์ "ไม่มีไฟล์" หลอก + เปิดให้ user กดลองใหม่ได้)
    loadError.value = true;
  } finally {
    isJobsLoading.value = false;
    if (showSpinner) isRefreshing.value = false;
  }
}

async function pollOnce() {
  try {
    jobs.value = await listImportJobs();
    pollFailStreak = 0;
    isPollError.value = false;
    // ไม่มีงานที่กำลังทำงานแล้ว → หยุด poll (ประหยัด request)
    if (!runningJobs.value.length) stopPolling();
  } catch {
    // error ชั่วคราว (network หลุด) — นับต่อเนื่อง ถ้าติดกันเกินลิมิต โชว์แบนเนอร์เตือน
    // (ไม่หยุด poll ถาวร — พอ network กลับมา รอบถัดไปจะ update + ปิดแบนเนอร์เอง)
    pollFailStreak += 1;
    if (pollFailStreak >= POLL_FAIL_LIMIT) isPollError.value = true;
  }
}

function startPolling() {
  if (pollTimer !== null) return;
  pollTimer = window.setInterval(async () => {
    // ใน-flight guard — ถ้ารอบก่อนยังไม่เสร็จ (network ช้า) ข้ามรอบ กัน poll ซ้อน
    if (pollInFlight) return;
    pollInFlight = true;
    try {
      await pollOnce();
    } finally {
      pollInFlight = false;
    }
  }, POLL_INTERVAL_MS);
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
  <div class="max-w-5xl mx-auto">
    <!-- หัวข้อ + ปุ่มดาวน์โหลด Template -->
    <div class="flex flex-wrap items-center justify-between gap-3 mb-5">
      <div>
        <h1 class="text-xl sm:text-2xl font-bold text-gray-900 leading-tight">
          <i class="bi bi-file-earmark-excel mr-1 text-red-500"></i> นำเข้านักเรียนจาก Excel
        </h1>
        <p class="text-sm text-gray-500">อัปโหลดรายชื่อ + ตำแหน่งในห้องเรียนเป็นชุด</p>
      </div>
      <button
        @click="handleDownloadTemplate"
        :disabled="isDownloadingTemplate"
        class="btn btn-outline btn-error btn-sm gap-1 disabled:opacity-50"
      >
        <i v-if="isDownloadingTemplate" class="loading loading-spinner loading-xs"></i>
        <i v-else class="bi bi-file-earmark-excel"></i>
        ดาวน์โหลดตัวอย่างไฟล์ (Template)
      </button>
    </div>

    <!-- รูปแบบไฟล์ — อธิบายชัดเจนว่าคอลัมน์ต้องเป๊ะ -->
    <div class="bg-red-50 border border-red-200 rounded-xl p-4 mb-5 text-sm">
      <p class="font-semibold text-red-800 mb-2">
        <i class="bi bi-info-circle mr-1"></i>
        ไฟล์ต้องมีคอลัมน์และข้อมูลในลักษณะนี้ ระบบถึงจะอ่านได้แน่นอน — <span class="underline">คอลัมน์ต้องเป๊ะ</span>
        (ห้ามเพิ่ม / ลบ / เปลี่ยนชื่อ / ซ้ำ):
      </p>
      <div class="overflow-x-auto rounded-lg border border-red-100 bg-white">
        <table class="table table-xs w-full">
          <thead>
            <tr class="bg-red-50 text-red-600">
              <th>คอลัมน์</th>
              <th>จำเป็น</th>
              <th>ตัวอย่าง</th>
              <th class="min-w-[200px]">คำอธิบาย</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td class="font-mono">รหัสนักเรียน</td><td>✅ ต้องมี</td><td class="font-mono">47001</td>
              <td>เลขประจำตัว (ใช้เป็น username + รหัสผ่านเริ่มต้น)</td>
            </tr>
            <tr>
              <td class="font-mono">ห้องเรียน</td><td>✅ ต้องมี</td><td class="font-mono">ม.4/1</td>
              <td>ระบบสร้างห้องอัตโนมัติถ้ายังไม่มี</td>
            </tr>
            <tr>
              <td class="font-mono">เลขที่</td><td>✅ ต้องมี</td><td class="font-mono">1</td>
              <td>ตัวเลข (1, 2, 3 ...)</td>
            </tr>
            <tr>
              <td class="font-mono">คำนำหน้า</td><td>เว้นได้</td><td class="font-mono">นาย / นางสาว</td><td>—</td>
            </tr>
            <tr>
              <td class="font-mono">ชื่อ</td><td>แนะนำ</td><td class="font-mono">สมชาย</td>
              <td>ห้ามเว้นทั้ง ชื่อ + นามสกุล</td>
            </tr>
            <tr>
              <td class="font-mono">นามสกุล</td><td>แนะนำ</td><td class="font-mono">ใจดี</td><td>—</td>
            </tr>
            <tr>
              <td class="font-mono">ชื่อเล่น</td><td>เว้นได้</td><td class="font-mono">ชาย</td><td>—</td>
            </tr>
            <tr>
              <td class="font-mono">ตำแหน่งในห้องเรียน</td><td>เว้นได้</td><td class="font-mono">หัวหน้าห้อง</td>
              <td>เว้นว่าง = นักเรียนธรรมดา</td>
            </tr>
          </tbody>
        </table>
      </div>
      <ul class="mt-3 text-xs text-red-700 space-y-1">
        <li>
          • <b>ตำแหน่ง</b> ที่รองรับ: หัวหน้าห้อง, รองวิชาการ, รองวินัย, รองกิจกรรม, รองปฏิคม,
          ประธานระดับ, สภานักเรียน, ประธานสภา, ครู, ครูสภา, แอดมิน
        </li>
        <li>• <b>ห้องเรียน</b> รูปแบบ: ม.4/1 (ระดับ/ห้อง)</li>
        <li>• 🔑 รหัสผ่านเริ่มต้น = เลขรหัสนักเรียน (เช่น 47001 → เข้าระบบด้วย 47001/47001)</li>
        <li>• ⚠️ ไฟล์ตัวอย่างมีแถวตัวอย่าง (00001, 00002) — ระบบจะ<b>ข้ามแถวที่รหัสขึ้นต้น 000</b> อัตโนมัติ
          (ลบออกก่อนอัปโหลดก็ได้เพื่อความเรียบร้อย)</li>
      </ul>
    </div>

    <!-- ขั้นตอนที่ 1: อัปโหลดเข้า Queue -->
    <div class="bg-white rounded-2xl shadow-sm p-5 space-y-4">
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">
          1. เลือกไฟล์ Excel <span class="text-gray-400 font-normal">(.xlsx)</span>
        </label>
        <div class="flex flex-wrap items-center gap-2">
          <input
            type="file"
            accept=".xlsx"
            @change="onFileChange"
            class="flex-1 min-w-[200px] text-sm file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-red-600 file:text-white hover:file:bg-red-700"
          />
          <!-- แสดงชื่อไฟล์ที่เลือก — custom file input ซ่อนข้อความ "No file chosen" ของ browser -->
          <span
            v-if="file"
            class="inline-flex items-center gap-1.5 text-sm text-gray-700 bg-gray-50 border border-gray-200 rounded-lg px-2.5 py-1.5 max-w-full"
            :title="file.name"
          >
            <i class="bi bi-file-earmark-excel text-red-600"></i>
            <span class="truncate max-w-[260px]">{{ file.name }}</span>
            <button type="button" class="text-gray-400 hover:text-red-600" title="ล้างไฟล์ที่เลือก" @click="file = null">
              <i class="bi bi-x-lg"></i>
            </button>
          </span>
          <span v-else class="text-xs text-gray-400">ยังไม่ได้เลือกไฟล์ (.xlsx)</span>
        </div>
      </div>
      <button
        @click="handleUpload"
        :disabled="isUploading"
        class="w-full py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 font-medium"
      >
        <i v-if="isUploading" class="loading loading-spinner loading-sm mr-1"></i>
        {{ isUploading ? 'กำลังตรวจสอบและอัปโหลดเข้า Queue...' : 'อัปโหลดเข้า Queue' }}
      </button>
      <p class="text-xs text-gray-400">
        <i class="bi bi-arrow-clockwise mr-1"></i>
        อัปโหลดเสร็จ ไฟล์จะถูกส่งเข้า <b>Queue</b> ทันที — ไม่ต้องค้างหน้านี้รอ
        จากนั้นกด <b>"เริ่มเดี๋ยวนี้"</b> ใน Queue List เพื่อสั่งให้ระบบทำงานเบื้องหลัง
      </p>
    </div>

    <!-- ขั้นตอนที่ 2: Queue List + Progress Bar -->
    <div class="bg-white rounded-2xl shadow-sm p-5 mt-5">
      <div class="flex flex-wrap items-center justify-between gap-2 mb-3">
        <h2 class="text-lg font-semibold text-gray-900">
          <i class="bi bi-list-ul mr-1"></i> Queue List — คิวนำเข้านักเรียน
          <span v-if="jobs.length" class="ml-1 text-sm font-normal text-gray-400">({{ jobs.length }})</span>
        </h2>
        <div class="flex items-center gap-2">
          <span v-if="runningJobs.length" class="badge badge-info badge-sm gap-1">
            <span class="loading loading-spinner loading-xs"></span>
            กำลังทำงาน {{ runningJobs.length }} งาน
          </span>
          <button
            @click="refreshJobs(true)"
            :disabled="isRefreshing"
            class="btn btn-xs btn-ghost gap-1 disabled:opacity-50"
          >
            <i :class="isRefreshing ? 'loading loading-spinner loading-xs' : 'bi bi-arrow-clockwise'"></i>
            รีเฟรช
          </button>
        </div>
      </div>

      <!-- poll ติดขัดต่อเนื่อง → บอก user ว่าระบบยังพยายามเชื่อมต่อ (bar ไม่ได้ค้างเงียบๆ) -->
      <div
        v-if="isPollError"
        class="alert alert-warning py-2 px-3 text-sm mb-3"
        role="alert"
      >
        <i class="bi bi-wifi-off mr-1"></i>
        เชื่อมต่อกับระบบไม่เสถียร — สถานะอาจไม่ทันสมัย ระบบกำลังลองเชื่อมต่อใหม่ทุก
        {{ POLL_INTERVAL_MS / 1000 }} วินาที
        <button
          @click="refreshJobs(true)"
          :disabled="isRefreshing"
          class="btn btn-xs btn-ghost ml-auto gap-1 disabled:opacity-50"
        >
          <i :class="isRefreshing ? 'loading loading-spinner loading-xs' : 'bi bi-arrow-clockwise'"></i>
          ลองใหม่
        </button>
      </div>

      <div v-if="isJobsLoading" class="flex justify-center py-10">
        <span class="loading loading-spinner loading-lg text-red-600"></span>
      </div>

      <!-- โหลดพลาด (ไม่ใช่ "ไม่มีไฟล์") — โชว์ error + ปุ่มลองใหม่ กันครูเห็น "ไม่มีไฟล์" แล้วอัปโหลดซ้ำซ้อน -->
      <div v-else-if="loadError" class="text-sm text-red-600 text-center py-8" role="alert">
        <i class="bi bi-wifi-off mr-1"></i>
        ไม่สามารถโหลด Queue List ได้ — ตรวจสอบการเชื่อมต่อกับระบบ
        <div class="mt-2">
          <button
            @click="refreshJobs(true)"
            :disabled="isRefreshing"
            class="btn btn-xs btn-outline btn-error gap-1 disabled:opacity-50"
          >
            <i :class="isRefreshing ? 'loading loading-spinner loading-xs' : 'bi bi-arrow-clockwise'"></i>
            ลองใหม่
          </button>
        </div>
      </div>

      <div v-else-if="jobs.length === 0" class="text-sm text-gray-400 text-center py-8">
        ยังไม่มีไฟล์ในคิว — อัปโหลดไฟล์ด้านบนก่อน
      </div>

      <div v-else class="overflow-x-auto">
        <table class="table table-sm w-full">
          <thead>
            <tr class="text-gray-500 text-xs">
              <th>ไฟล์</th>
              <th>สถานะ</th>
              <th class="min-w-[220px]">ความคืบหน้า</th>
              <th>นำเข้า / ข้าม</th>
              <th class="text-right">จัดการ</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="job in jobs" :key="job.id">
              <tr class="align-middle">
                <td class="font-medium text-sm">
                  {{ job.file_name }}
                  <div class="text-xs text-gray-400">
                    {{ new Date(job.created_at).toLocaleString('th-TH', { timeZone: 'Asia/Bangkok' }) }}
                  </div>
                </td>
                <td>
                  <span class="badge badge-sm" :class="IMPORT_STATUS_BADGES[job.status]">
                    {{ IMPORT_STATUS_LABELS[job.status] }}
                  </span>
                  <!-- error_message โชว์เฉพาะ FAILED — กัน error เก่าค้างเมื่อลองใหม่แล้วสำเร็จ -->
                  <div v-if="job.status === 'FAILED' && job.error_message" class="text-xs text-red-500 mt-1 max-w-[180px]">
                    {{ job.error_message }}
                  </div>
                </td>
                <td>
                  <!-- หลอดเปอร์เซ็นต์: เติมตาม progress_percent, เขียวเต็มหลอดเมื่อเสร็จ -->
                  <div class="flex items-center gap-2">
                    <div class="relative h-5 flex-1 min-w-[130px] rounded-full bg-gray-100 border border-gray-200 overflow-hidden">
                      <div
                        class="absolute inset-y-0 left-0 rounded-full transition-all duration-500 ease-out"
                        :class="[IMPORT_BAR_FILL[job.status], isImportJobRunning(job.status) ? 'animate-pulse' : '']"
                        :style="{ width: job.progress_percent + '%' }"
                      ></div>
                      <span
                        v-if="job.status === 'COMPLETED'"
                        class="absolute inset-0 flex items-center justify-center text-white text-[11px] font-bold"
                      >
                        <i class="bi bi-check-lg mr-0.5"></i> เสร็จสิ้น
                      </span>
                    </div>
                    <span class="text-sm font-bold tabular-nums shrink-0" :class="IMPORT_BAR_TEXT[job.status]">
                      {{ job.progress_percent }}%
                    </span>
                  </div>
                  <div class="text-xs text-gray-500 mt-1">
                    {{ job.processed_rows }}/{{ job.total_rows }} แถว
                  </div>
                </td>
                <td class="text-sm text-gray-600 whitespace-nowrap">
                  <span class="text-green-600 font-semibold">{{ job.imported_count }}</span>
                  /
                  <span class="text-amber-600 font-semibold">{{ job.skipped_count }}</span>
                </td>
                <td class="text-right">
                  <!-- รอเริ่มงาน → ปุ่มเริ่มเดี๋ยวนี้ -->
                  <button
                    v-if="job.status === 'PENDING'"
                    @click="handleStart(job.id)"
                    :disabled="isStartingJobId !== null"
                    class="btn btn-sm btn-primary gap-1 disabled:opacity-50"
                  >
                    <i v-if="isStartingJobId === job.id" class="loading loading-spinner loading-xs"></i>
                    <i v-else class="bi bi-play-fill"></i>
                    เริ่มเดี๋ยวนี้
                  </button>
                  <!-- ล้มเหลว → ลองใหม่ -->
                  <button
                    v-else-if="job.status === 'FAILED'"
                    @click="handleStart(job.id)"
                    :disabled="isStartingJobId !== null"
                    class="btn btn-sm btn-outline btn-error gap-1 disabled:opacity-50"
                  >
                    <i v-if="isStartingJobId === job.id" class="loading loading-spinner loading-xs"></i>
                    <i v-else class="bi bi-arrow-counterclockwise"></i>
                    ลองใหม่
                  </button>
                  <!-- กำลังทำงาน/รอ worker → spinner -->
                  <span v-else-if="isImportJobRunning(job.status)" class="inline-flex items-center gap-1 text-xs text-blue-500">
                    <span class="loading loading-spinner loading-xs"></span> ทำงานอยู่
                  </span>
                  <span v-else class="text-xs text-gray-400">—</span>
                </td>
              </tr>
              <!-- error_logs รายแถว (แถวที่ข้อมูลผิด/ถูกข้าม) -->
              <tr v-if="job.error_logs.length" :key="'err-' + job.id" class="border-t-0">
                <td colspan="5" class="py-1">
                  <details class="bg-red-50 border border-red-100 rounded-lg p-3 text-xs">
                    <summary class="text-red-600 font-medium cursor-pointer">
                      {{ job.file_name }} — ข้อผิดพลาด {{ job.error_logs.length }} รายการ
                    </summary>
                    <ul class="list-disc pl-4 mt-2 text-red-500 max-h-40 overflow-auto">
                      <li v-for="(e, idx) in job.error_logs" :key="idx">{{ e }}</li>
                    </ul>
                  </details>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
