<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { useRoute } from 'vue-router';
import Swal from 'sweetalert2';
import { getIssue, acceptIssue, addStep, completeStep, escalateIssue, resolveIssue, updateCountdown, cancelIssue } from '@/services/issue';
import { MAIN_CATEGORY_LABELS, subcategoryLabel, STATUS_LABELS, LEVEL_LABELS, type Issue } from '@/types/issue';
import { useAuthStore } from '@/stores/auth';

const route = useRoute();
const authStore = useAuthStore();

const issue = ref<Issue | null>(null);
const isLoading = ref(true);

const daysInput = ref(3);
const newStepTitle = ref('');
const newStepDetail = ref('');
const escalateReason = ref('');
const resolveNote = ref('');

async function load() {
  isLoading.value = true;
  try {
    issue.value = await getIssue(Number(route.params.id));
  } catch (e: any) {
    Swal.fire({ icon: 'error', title: 'ไม่สามารถโหลดเรื่องได้', text: e.message });
  } finally {
    isLoading.value = false;
  }
}
onMounted(load);

const canReceive = computed(() => {
  if (!issue.value || !authStore.user) return false;
  if (issue.value.current_assignee_id) return false;
  if (issue.value.status !== 'pending' && issue.value.status !== 'escalated') return false;
  // ระดับของผู้ใช้ (สูงสุด) == ระดับปัจจุบันของเรื่อง
  const myLevel = getMyLevel();
  return myLevel === issue.value.current_level;
});

const canManage = computed(() => {
  if (!issue.value || !authStore.user) return false;
  return (
    issue.value.current_assignee_id === authStore.user.id ||
    authStore.isAdmin
  );
});

const canEscalate = computed(() => {
  if (!canManage.value) return false;
  if (issue.value?.current_level === 'council') return false;
  return issue.value?.status === 'in_progress';
});

const canCancel = computed(() => {
  if (!issue.value || !authStore.user) return false;
  // เฉพาะผู้แจ้ง หรือ admin
  const isReporter = issue.value.reporter_id === authStore.user.id;
  if (!isReporter && !authStore.isAdmin) return false;
  // เรื่องที่ปิดแล้ว ยกเลิกไม่ได้
  if (issue.value.status === 'resolved') return false;
  return true;
});

function getMyLevel(): string {
  // ระดับสูงสุดจาก roles
  const roleLevels: Record<string, string> = {
    class_president: 'room', vice_academic: 'room', vice_discipline: 'room',
    vice_activity: 'room', vice_reception: 'room',
    level_president: 'level',
    council_member: 'council', council_president: 'council',
  };
  let best = 'student';
  for (const r of authStore.roles) {
    const lv = roleLevels[r.role || ''] || 'student';
    const rank = { student: 0, room: 1, level: 2, council: 3 };
    if (rank[lv as keyof typeof rank] > rank[best as keyof typeof rank]) best = lv;
  }
  return best;
}

async function handleAccept() {
  if (!issue.value) return;
  const { value } = await Swal.fire({
    icon: 'question',
    title: 'รับเรื่องนี้?',
    html: 'ตั้งเวลา (วัน) ที่คิดว่าจะใช้แก้ปัญหา',
    input: 'number',
    inputValue: daysInput.value,
    inputAttributes: { min: '1', max: '365' },
    showCancelButton: true,
    confirmButtonText: 'รับเรื่อง',
    cancelButtonText: 'ยกเลิก',
  });
  if (!value) return;

  try {
    await acceptIssue(issue.value.id, Number(value));
    Swal.fire({ icon: 'success', title: 'รับเรื่องแล้ว!', text: `ตั้งเวลา ${value} วัน`, timer: 1500, showConfirmButton: false });
    load();
  } catch (e: any) {
    Swal.fire({ icon: 'error', title: 'ไม่สำเร็จ', text: e.message });
  }
}

async function handleAddStep() {
  if (!issue.value || !newStepTitle.value.trim()) return;
  try {
    await addStep(issue.value.id, newStepTitle.value.trim(), newStepDetail.value.trim() || undefined);
    newStepTitle.value = '';
    newStepDetail.value = '';
    Swal.fire({ icon: 'success', title: 'เพิ่มขั้นตอนแล้ว', timer: 1000, showConfirmButton: false });
    load();
  } catch (e: any) {
    Swal.fire({ icon: 'error', title: 'ไม่สำเร็จ', text: e.message });
  }
}

async function handleCompleteStep(stepId: number) {
  if (!issue.value) return;
  try {
    await completeStep(issue.value.id, stepId);
    load();
  } catch (e: any) {
    Swal.fire({ icon: 'error', title: 'ไม่สำเร็จ', text: e.message });
  }
}

async function handleEscalate() {
  if (!issue.value) return;
  const { value } = await Swal.fire({
    icon: 'warning',
    title: 'ส่งต่อเรื่องนี้ไประดับบน?',
    text: 'ถ้าเกินความสามารถหรือไม่ทันเวลา',
    input: 'text',
    inputPlaceholder: 'เหตุผล (ไม่บังคับ)',
    showCancelButton: true,
    confirmButtonText: 'ส่งต่อ',
    cancelButtonText: 'ยกเลิก',
  });
  if (value === undefined) return;

  try {
    await escalateIssue(issue.value.id, value || undefined);
    Swal.fire({ icon: 'success', title: 'ส่งต่อแล้ว!', text: `ส่งต่อไปยังระดับบน`, timer: 1500, showConfirmButton: false });
    load();
  } catch (e: any) {
    Swal.fire({ icon: 'error', title: 'ไม่สำเร็จ', text: e.message });
  }
}

async function handleResolve() {
  if (!issue.value) return;
  const { value } = await Swal.fire({
    icon: 'success',
    title: 'ปิดเรื่องนี้?',
    text: 'ยืนยันว่าแก้ไขเสร็จสิ้น',
    input: 'text',
    inputPlaceholder: 'สรุปผลการแก้ไข (ไม่บังคับ)',
    showCancelButton: true,
    confirmButtonText: 'ปิดเรื่อง',
    cancelButtonText: 'ยกเลิก',
  });
  if (value === undefined) return;

  try {
    await resolveIssue(issue.value.id, value || undefined);
    Swal.fire({ icon: 'success', title: 'ปิดเรื่องแล้ว!', timer: 1500, showConfirmButton: false });
    load();
  } catch (e: any) {
    Swal.fire({ icon: 'error', title: 'ไม่สำเร็จ', text: e.message });
  }
}

async function handleCancel() {
  if (!issue.value) return;
  const { value } = await Swal.fire({
    icon: 'warning',
    title: 'ยกเลิกเรื่องนี้?',
    text: 'กันส่งผิดหรือไม่ต้องการแล้ว — เมื่อยกเลิกแล้วจะกู้คืนไม่ได้',
    input: 'text',
    inputPlaceholder: 'เหตุผล (ไม่บังคับ)',
    showCancelButton: true,
    confirmButtonText: 'ยกเลิกเรื่อง',
    confirmButtonColor: '#ef4444',
    cancelButtonText: 'กลับไป',
  });
  if (value === undefined) return;

  try {
    await cancelIssue(issue.value.id, value || undefined);
    Swal.fire({ icon: 'success', title: 'ยกเลิกเรื่องแล้ว', timer: 1500, showConfirmButton: false });
    load();
  } catch (e: any) {
    Swal.fire({ icon: 'error', title: 'ยกเลิกไม่สำเร็จ', text: e.message });
  }
}

async function handleExtendCountdown() {
  if (!issue.value) return;
  const { value } = await Swal.fire({
    icon: 'question',
    title: 'ยืดเวลาการแก้ปัญหา',
    input: 'number',
    inputValue: issue.value.countdown?.estimated_days || 3,
    inputAttributes: { min: '1', max: '365' },
    showCancelButton: true,
    confirmButtonText: 'ยืดเวลา',
    cancelButtonText: 'ยกเลิก',
  });
  if (!value) return;
  try {
    await updateCountdown(issue.value.id, Number(value));
    Swal.fire({ icon: 'success', title: 'ยืดเวลาแล้ว', timer: 1500, showConfirmButton: false });
    load();
  } catch (e: any) {
    Swal.fire({ icon: 'error', title: 'ไม่สำเร็จ', text: e.message });
  }
}

function fmtDate(iso: string | null): string {
  if (!iso) return '-';
  const d = new Date(iso);
  return d.toLocaleString('th-TH', { timeZone: 'Asia/Bangkok', day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function countdownLabel(days: number): string {
  if (days <= 0) return 'หมดเวลา';
  if (days === 1) return 'เหลือ 1 วัน';
  return `เหลือ ${days} วัน`;
}
</script>

<template>
  <div v-if="isLoading" class="flex justify-center py-20">
    <div class="animate-spin w-10 h-10 border-4 border-red-600 border-t-transparent rounded-full"></div>
  </div>

  <div v-else-if="issue" class="max-w-3xl mx-auto space-y-5">
    <!-- Header -->
    <div class="bg-white rounded-xl shadow-sm p-5">
      <div class="flex items-start justify-between gap-3">
        <div class="min-w-0">
          <div class="flex flex-wrap gap-2 mb-2">
            <span class="px-2.5 py-0.5 bg-red-100 text-red-700 text-xs rounded-full">
              {{ MAIN_CATEGORY_LABELS[issue.main_category] }}
            </span>
            <span class="px-2.5 py-0.5 bg-purple-100 text-purple-700 text-xs rounded-full">
              {{ subcategoryLabel(issue.main_category, issue.category) }}
            </span>
            <span class="px-2.5 py-0.5 bg-gray-100 text-gray-600 text-xs rounded-full">
              {{ LEVEL_LABELS[issue.current_level] }}
            </span>
          </div>
          <h1 class="text-lg sm:text-xl font-bold text-gray-900 leading-snug break-words">{{ issue.title }}</h1>
          <p class="text-gray-500 text-sm mt-1 break-words">โดย {{ issue.reporter_name || 'ไม่ระบุชื่อ' }} {{ issue.reporter_room ? `(${issue.reporter_room})` : '' }}</p>
        </div>
        <span class="px-3 py-1 text-sm font-medium rounded-full whitespace-nowrap shrink-0"
          :class="{
            'bg-yellow-100 text-yellow-700': issue.status === 'pending',
            'bg-blue-100 text-blue-700': issue.status === 'in_progress',
            'bg-green-100 text-green-700': issue.status === 'resolved',
            'bg-orange-100 text-orange-700': issue.status === 'escalated',
            'bg-gray-200 text-gray-500': issue.status === 'cancelled',
          }"
        >
          {{ STATUS_LABELS[issue.status] }}
        </span>
      </div>
      <p class="text-gray-700 mt-4 whitespace-pre-wrap">{{ issue.description }}</p>
      <p class="text-xs text-gray-400 mt-3">แจ้งเมื่อ {{ fmtDate(issue.created_at) }} · ห้อง {{ issue.room_name }}</p>
    </div>

    <!-- Actions (mobile = ปุ่มเต็มแถว, กดง่าย) -->
    <div v-if="canReceive || canManage" class="grid grid-cols-1 sm:flex sm:flex-wrap gap-2">
      <button v-if="canReceive" @click="handleAccept"
        class="px-4 py-2.5 bg-red-600 text-white rounded-xl hover:bg-red-700 text-sm font-medium">
        <i class="bi bi-hand-thumbs-up mr-1"></i> รับเรื่อง + ตั้งเวลา
      </button>
      <button v-if="canManage && canEscalate" @click="handleEscalate"
        class="px-4 py-2.5 bg-orange-500 text-white rounded-xl hover:bg-orange-600 text-sm font-medium">
        <i class="bi bi-arrow-up-circle mr-1"></i> ส่งต่อไประดับบน
      </button>
      <button v-if="canManage && issue.status === 'in_progress'" @click="handleResolve"
        class="px-4 py-2.5 bg-green-600 text-white rounded-xl hover:bg-green-700 text-sm font-medium">
        <i class="bi bi-check2-circle mr-1"></i> ปิดเรื่อง (เสร็จแล้ว)
      </button>
      <button v-if="canManage && issue.countdown && issue.status === 'in_progress'" @click="handleExtendCountdown"
        class="px-4 py-2.5 bg-gray-100 text-gray-700 rounded-xl hover:bg-gray-200 text-sm font-medium">
        <i class="bi bi-clock-history mr-1"></i> ยืดเวลา
      </button>
      <!-- ยกเลิก (ผู้แจ้ง — กันส่งผิด) -->
      <button v-if="canCancel" @click="handleCancel"
        class="px-4 py-2.5 bg-red-50 text-red-600 border border-red-200 rounded-xl hover:bg-red-100 text-sm font-medium">
        <i class="bi bi-x-circle mr-1"></i> ยกเลิกเรื่อง
      </button>
    </div>

    <!-- Countdown -->
    <div v-if="issue.countdown" class="bg-white rounded-xl shadow-sm p-5 border-l-4"
      :class="issue.countdown.is_overdue ? 'border-red-500' : 'border-red-500'">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <i class="bi bi-hourglass-split text-xl" :class="issue.countdown.is_overdue ? 'text-red-500' : 'text-red-500'"></i>
          <div>
            <p class="text-sm font-medium text-gray-700">การนับถอยหลัง</p>
            <p class="text-xs text-gray-400">ตั้งไว้ {{ issue.countdown.estimated_days }} วัน · ถึง {{ fmtDate(issue.countdown.deadline) }}</p>
          </div>
        </div>
        <div class="text-lg font-bold" :class="issue.countdown.is_overdue ? 'text-red-500' : 'text-red-600'">
          {{ issue.countdown.is_overdue ? 'เกินเวลา!' : countdownLabel(issue.countdown.estimated_days) }}
        </div>
      </div>
    </div>

    <!-- Steps -->
    <div class="bg-white rounded-xl shadow-sm p-5">
      <h2 class="text-lg font-bold text-gray-800 mb-3"><i class="bi bi-diagram-3 mr-1"></i> ขั้นตอนการดำเนินงาน</h2>
      <div v-if="issue.steps && issue.steps.length" class="space-y-2">
        <div v-for="s in issue.steps" :key="s.id" class="flex items-center gap-3 p-2.5 rounded-lg"
          :class="s.is_completed ? 'bg-green-50' : 'bg-gray-50'">
          <button v-if="canManage && !s.is_completed" @click="handleCompleteStep(s.id)"
            class="w-6 h-6 rounded-full border-2 border-gray-300 hover:border-green-500 flex items-center justify-center text-xs"
            title="ทำขั้นตอนนี้สำเร็จ">
            <i class="bi bi-check text-green-500 hidden"></i>
          </button>
          <div v-else class="w-6 h-6 rounded-full flex items-center justify-center"
            :class="s.is_completed ? 'bg-green-500 text-white' : 'bg-gray-200'">
            <i v-if="s.is_completed" class="bi bi-check text-xs"></i>
          </div>
          <div class="flex-1">
            <p class="text-sm font-medium" :class="s.is_completed ? 'text-gray-500 line-through' : 'text-gray-800'">
              {{ s.step_title }}
            </p>
            <p v-if="s.step_detail" class="text-xs text-gray-500">{{ s.step_detail }}</p>
          </div>
        </div>
      </div>
      <p v-else class="text-sm text-gray-400">ยังไม่มีขั้นตอนการดำเนินงาน</p>

      <div v-if="canManage" class="mt-3 grid grid-cols-1 sm:flex gap-2">
        <input v-model="newStepTitle" type="text" placeholder="เพิ่มขั้นตอน..."
          class="w-full sm:flex-1 px-3 py-2.5 border border-gray-300 rounded-xl text-sm"
          @keyup.enter="handleAddStep" />
        <input v-model="newStepDetail" type="text" placeholder="รายละเอียด (ไม่บังคับ)"
          class="w-full sm:w-48 px-3 py-2.5 border border-gray-300 rounded-xl text-sm"
          @keyup.enter="handleAddStep" />
        <button @click="handleAddStep" class="px-4 py-2.5 bg-gray-100 rounded-xl text-sm hover:bg-gray-200">
          <i class="bi bi-plus-lg"></i>
        </button>
      </div>
    </div>

    <!-- Timeline -->
    <div class="bg-white rounded-xl shadow-sm p-5">
      <h2 class="text-lg font-bold text-gray-800 mb-3"><i class="bi bi-clock-history mr-1"></i> ประวัติการดำเนินงาน</h2>
      <div v-if="issue.status_history && issue.status_history.length" class="relative pl-5 border-l-2 border-gray-200 space-y-4">
        <div v-for="h in issue.status_history" :key="h.id" class="relative">
          <div class="absolute -left-[25px] top-1 w-3 h-3 rounded-full bg-red-500"></div>
          <p class="text-sm text-gray-700">{{ h.note }}</p>
          <p class="text-xs text-gray-400">{{ fmtDate(h.created_at) }}</p>
        </div>
      </div>
      <p v-else class="text-sm text-gray-400">ไม่มีประวัติ</p>
    </div>
  </div>
</template>
