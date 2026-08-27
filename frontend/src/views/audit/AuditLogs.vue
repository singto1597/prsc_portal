<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import Swal from 'sweetalert2';
import { listAuditLogs } from '@/services/audit';
import type { AuditLogEntry } from '@/types/audit';
import PaginationBar from '@/components/PaginationBar.vue';

// ===== ป้าย action → ภาษาไทย (ให้ตรงกับ backend dashboard_service.ACTION_LABELS) =====
const ACTION_LABELS: Record<string, string> = {
  login: 'เข้าสู่ระบบ',
  CREATE_ISSUE: 'แจ้งเรื่องใหม่',
  UPDATE_ISSUE: 'แก้ไขเรื่อง',
  ACCEPT_ISSUE: 'รับเรื่อง',
  UPDATE_COUNTDOWN: 'ตั้งเวลาแก้',
  CREATE_STEP: 'เพิ่มขั้นตอน',
  UPDATE_STEP: 'ทำขั้นตอนเสร็จ',
  ESCALATE_ISSUE: 'ส่งต่อระดับบน',
  RESOLVE_ISSUE: 'ปิดเรื่อง',
  CANCEL_ISSUE: 'ยกเลิกเรื่อง',
  REJECT_ISSUE: 'ปัดตกเรื่อง',
  CREATE_COMMENT: 'คอมเมนต์',
  UPDATE_COMMENT: 'แก้คอมเมนต์',
  DELETE_COMMENT: 'ลบคอมเมนต์',
  CREATE_USER: 'สร้างผู้ใช้',
  CHANGE_PASSWORD: 'เปลี่ยนรหัสผ่าน',
  UPDATE_STUDENT: 'แก้ไขนักเรียน',
  CREATE_ROOM: 'สร้างห้อง',
  UPDATE_PROFILE: 'แก้โปรไฟล์',
  UPLOAD_IMPORT_EXCEL: 'อัปโหลด Excel',
  START_IMPORT_JOB: 'เริ่มนำเข้า',
  PROCESS_IMPORT_JOB: 'กำลังนำเข้า',
  COMPLETE_IMPORT_JOB: 'นำเข้าสำเร็จ',
  FAIL_IMPORT_JOB: 'นำเข้าล้มเหลว',
  RECOVER_IMPORT_JOB: 'กู้คืนงานนำเข้า',
  READ_ME: 'ดูข้อมูลตัวเอง',
  READ_PROFILE: 'ดูโปรไฟล์',
  READ_ISSUES: 'ดูรายการเรื่อง',
  READ_ISSUE: 'ดูรายละเอียดเรื่อง',
  READ_ROOMS: 'ดูห้องเรียน',
  READ_STUDENTS: 'ดูรายชื่อนักเรียน',
  READ_IMPORT_JOBS: 'ดูงานนำเข้า',
  READ_DASHBOARD: 'ดูแดชบอร์ด',
  READ_DASHBOARD_TRAFFIC: 'ดูสถิติการใช้งาน',
  READ_AUDIT_LOGS: 'ดูบันทึกการใช้งาน',
};

function actionLabel(action: string): string {
  return ACTION_LABELS[action] ?? action;
}

const STATUS_BADGE: Record<string, string> = {
  success: 'bg-green-100 text-green-700',
  error: 'bg-red-100 text-red-700',
  partial: 'bg-amber-100 text-amber-700',
};

// ===== ข้อมูล + การโหลด =====
const items = ref<AuditLogEntry[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = 20;
const isLoading = ref(true);
const error = ref('');

// ===== ตัวกรอง =====
const fAction = ref('');
const fStatus = ref('');
const fEntityType = ref('');
const fQ = ref('');
const fDateFrom = ref('');
const fDateTo = ref('');
let qTimer: ReturnType<typeof setTimeout> | null = null;

const pages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)));

async function load() {
  isLoading.value = true;
  error.value = '';
  try {
    const res = await listAuditLogs({
      action: fAction.value || undefined,
      status: fStatus.value || undefined,
      entity_type: fEntityType.value || undefined,
      q: fQ.value || undefined,
      date_from: fDateFrom.value || undefined,
      date_to: fDateTo.value || undefined,
      limit: pageSize,
      offset: (page.value - 1) * pageSize,
    });
    items.value = res.items;
    total.value = res.total;
  } catch (e) {
    const msg = e instanceof Error ? e.message : 'เกิดข้อผิดพลาด';
    error.value = msg;
    Swal.fire({ icon: 'error', title: 'โหลดบันทึกการใช้งานไม่สำเร็จ', text: msg });
  } finally {
    isLoading.value = false;
  }
}

function resetAndLoad() {
  page.value = 1;
  load();
}

// เปลี่ยนฟิลเตอร์ → โหลดหน้า 1 (q เดบานซ์ 300ms กันพิมพ์เร็ว)
watch([fAction, fStatus, fEntityType, fDateFrom, fDateTo], resetAndLoad);
watch(fQ, () => {
  if (qTimer) clearTimeout(qTimer);
  qTimer = setTimeout(resetAndLoad, 300);
});

onMounted(load);

// ===== การแสดงผล =====
function fmtDateTime(iso: string): string {
  return new Date(iso).toLocaleString('th-TH', {
    timeZone: 'Asia/Bangkok',
    day: 'numeric', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
}

const expanded = ref<Set<string>>(new Set());

function toggleExpand(id: string) {
  const next = new Set(expanded.value);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  expanded.value = next;
}

function hasPayload(e: AuditLogEntry): boolean {
  return !!e.new_values || !!e.old_values || !!e.error_detail;
}

function fmtPayload(v: Record<string, unknown> | null): string {
  if (!v) return '-';
  try {
    return JSON.stringify(v, null, 2);
  } catch {
    return String(v);
  }
}

function statusBadge(s: string): string {
  return STATUS_BADGE[s] ?? 'bg-gray-100 text-gray-600';
}

const hasData = computed(() => items.value.length > 0);
</script>

<template>
  <div>
    <!-- Header -->
    <div class="flex flex-wrap items-center justify-between gap-3 mb-5">
      <div>
        <h1 class="text-xl sm:text-2xl font-bold text-gray-900 leading-tight">
          <i class="bi bi-clock-history mr-1 text-red-500"></i> บันทึกการใช้งาน
        </h1>
        <p class="text-xs text-gray-400 mt-0.5">ประวัติทุกการกระทำในระบบ (เข้าสู่ระบบ / เพิ่ม / ดึงข้อมูล / แก้ไข / ลบ)</p>
      </div>
      <button
        type="button"
        @click="load"
        :disabled="isLoading"
        title="รีเฟรช"
        class="w-9 h-9 rounded-xl bg-white border border-gray-200 text-gray-500 hover:text-red-600 hover:border-red-300 flex items-center justify-center transition disabled:opacity-50"
      >
        <i class="bi bi-arrow-clockwise" :class="{ 'animate-spin': isLoading }"></i>
      </button>
    </div>

    <!-- ตัวกรอง -->
    <div class="bg-white rounded-2xl shadow-sm p-4 mb-4">
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-3">
        <div>
          <label class="block text-xs text-gray-500 mb-1">Action</label>
          <input
            v-model="fAction"
            type="text"
            placeholder="เช่น login, CREATE_ISSUE"
            class="w-full input input-bordered input-sm"
          />
        </div>
        <div>
          <label class="block text-xs text-gray-500 mb-1">สถานะ</label>
          <select v-model="fStatus" class="w-full select select-bordered select-sm">
            <option value="">ทั้งหมด</option>
            <option value="success">สำเร็จ</option>
            <option value="error">ผิดพลาด</option>
            <option value="partial">บางส่วน</option>
          </select>
        </div>
        <div>
          <label class="block text-xs text-gray-500 mb-1">ชนิดข้อมูล</label>
          <input
            v-model="fEntityType"
            type="text"
            placeholder="เช่น issue, user"
            class="w-full input input-bordered input-sm"
          />
        </div>
        <div>
          <label class="block text-xs text-gray-500 mb-1">ค้นหา (ผู้ใช้/error)</label>
          <input v-model="fQ" type="text" placeholder="ชื่อผู้ใช้ / ข้อความ" class="w-full input input-bordered input-sm" />
        </div>
        <div>
          <label class="block text-xs text-gray-500 mb-1">จากวันที่</label>
          <input v-model="fDateFrom" type="date" class="w-full input input-bordered input-sm" />
        </div>
        <div>
          <label class="block text-xs text-gray-500 mb-1">ถึงวันที่</label>
          <input v-model="fDateTo" type="date" class="w-full input input-bordered input-sm" />
        </div>
      </div>
    </div>

    <!-- Loading skeleton -->
    <div v-if="isLoading && !hasData" class="bg-white rounded-2xl shadow-sm overflow-hidden">
      <div class="p-4 space-y-3">
        <div v-for="i in 6" :key="i" class="flex gap-3 items-center">
          <div class="h-8 w-8 bg-gray-200 animate-pulse rounded-lg"></div>
          <div class="flex-1 space-y-1.5">
            <div class="h-3 w-1/3 bg-gray-200 animate-pulse rounded"></div>
            <div class="h-3 w-1/2 bg-gray-100 animate-pulse rounded"></div>
          </div>
        </div>
      </div>
    </div>

    <!-- Error -->
    <div v-else-if="error && !hasData" class="bg-white rounded-2xl shadow-sm p-12 text-center">
      <div class="text-5xl mb-3 text-red-300"><i class="bi bi-exclamation-triangle"></i></div>
      <h2 class="text-lg font-bold text-gray-800 mb-1">โหลดข้อมูลไม่สำเร็จ</h2>
      <p class="text-sm text-gray-500 mb-5 max-w-md mx-auto">{{ error }}</p>
      <button
        type="button"
        @click="load"
        class="px-5 py-2.5 bg-red-600 text-white rounded-xl hover:bg-red-700 text-sm font-medium transition"
      >
        <i class="bi bi-arrow-clockwise mr-1"></i> ลองใหม่
      </button>
    </div>

    <!-- Empty -->
    <div v-else-if="!isLoading && !hasData" class="bg-white rounded-2xl shadow-sm p-12 text-center">
      <div class="text-5xl mb-3 text-gray-300"><i class="bi bi-inbox"></i></div>
      <p class="text-sm text-gray-500">ยังไม่มีบันทึกการใช้งานตามเงื่อนไขนี้</p>
    </div>

    <!-- ตาราง -->
    <div v-else class="bg-white rounded-2xl shadow-sm overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left text-xs text-gray-400 border-b border-gray-100">
              <th class="px-4 py-3 font-medium">เวลา</th>
              <th class="px-4 py-3 font-medium">ผู้ใช้</th>
              <th class="px-4 py-3 font-medium">การกระทำ</th>
              <th class="px-4 py-3 font-medium">ข้อมูล</th>
              <th class="px-4 py-3 font-medium">สถานะ</th>
              <th class="px-4 py-3 font-medium">IP</th>
              <th class="px-4 py-3 font-medium"></th>
            </tr>
          </thead>
          <tbody>
            <template v-for="e in items" :key="e.id">
              <tr class="border-b border-gray-50 hover:bg-gray-50/50">
                <td class="px-4 py-2.5 text-gray-500 whitespace-nowrap tabular-nums">{{ fmtDateTime(e.created_at) }}</td>
                <td class="px-4 py-2.5">
                  <span class="font-medium text-gray-700">{{ e.actor_identifier }}</span>
                  <span v-if="e.ip_address" class="block text-[11px] text-gray-400 tabular-nums">{{ e.ip_address }}</span>
                </td>
                <td class="px-4 py-2.5">
                  <span class="inline-flex items-center gap-1.5">
                    <span class="font-medium text-gray-800">{{ actionLabel(e.action) }}</span>
                    <span class="text-[11px] text-gray-400 font-mono">{{ e.action }}</span>
                  </span>
                  <span v-if="e.endpoint_or_command" class="block text-[11px] text-gray-400 font-mono">{{ e.endpoint_or_command }}</span>
                </td>
                <td class="px-4 py-2.5 text-gray-500">
                  <template v-if="e.entity_type">
                    <span class="text-gray-400">{{ e.entity_type }}</span>
                    <span v-if="e.entity_id" class="text-gray-600 font-mono">#{{ e.entity_id }}</span>
                  </template>
                  <span v-else class="text-gray-300">-</span>
                </td>
                <td class="px-4 py-2.5">
                  <span class="px-2 py-0.5 text-[11px] font-medium rounded-full" :class="statusBadge(e.status)">
                    {{ e.status }}
                  </span>
                </td>
                <td class="px-4 py-2.5 text-gray-500 font-mono text-xs">{{ e.ip_address || '-' }}</td>
                <td class="px-4 py-2.5 text-right">
                  <button
                    v-if="hasPayload(e)"
                    type="button"
                    @click="toggleExpand(e.id)"
                    class="w-8 h-8 inline-flex items-center justify-center rounded-lg text-gray-400 hover:text-red-600 hover:bg-red-50 transition"
                    :title="expanded.has(e.id) ? 'ย่อรายละเอียด' : 'ดูรายละเอียด'"
                  >
                    <i class="bi" :class="expanded.has(e.id) ? 'bi-chevron-up' : 'bi-chevron-down'"></i>
                  </button>
                </td>
              </tr>
              <!-- รายละเอียดเก่า/ใหม่ (expand) -->
              <tr v-if="expanded.has(e.id)" class="bg-gray-50/60 border-b border-gray-100">
                <td colspan="7" class="px-4 py-3">
                  <div class="grid lg:grid-cols-2 gap-3">
                    <div>
                      <p class="text-xs font-semibold text-gray-500 mb-1">ค่าเดิม (old_values)</p>
                      <pre class="text-[11px] text-gray-600 bg-white rounded-lg p-2.5 border border-gray-100 overflow-x-auto">{{ fmtPayload(e.old_values) }}</pre>
                    </div>
                    <div>
                      <p class="text-xs font-semibold text-gray-500 mb-1">ค่าใหม่ (new_values)</p>
                      <pre class="text-[11px] text-gray-600 bg-white rounded-lg p-2.5 border border-gray-100 overflow-x-auto">{{ fmtPayload(e.new_values) }}</pre>
                    </div>
                    <div v-if="e.error_detail" class="lg:col-span-2">
                      <p class="text-xs font-semibold text-red-500 mb-1">ข้อผิดพลาด</p>
                      <pre class="text-[11px] text-red-600 bg-red-50 rounded-lg p-2.5 border border-red-100 overflow-x-auto">{{ e.error_detail }}</pre>
                    </div>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>

      <div class="px-4 py-3 text-xs text-gray-400 flex items-center justify-between">
        <span>แสดง {{ items.length }} จาก {{ total }} รายการ</span>
        <span v-if="pages > 1">หน้า {{ page }} / {{ pages }}</span>
      </div>
    </div>

    <PaginationBar :total="total" :page="page" :page-size="pageSize" :loading="isLoading" @page-change="page = $event; load()" />
  </div>
</template>
