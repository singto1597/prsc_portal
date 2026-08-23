<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { RouterLink } from 'vue-router';
import { listIssues } from '@/services/issue';
import { MAIN_CATEGORY_LABELS, subcategoryLabel, STATUS_LABELS, LEVEL_LABELS, type Issue } from '@/types/issue';

const issues = ref<Issue[]>([]);
const isLoading = ref(true);
const error = ref('');

onMounted(async () => {
  try {
    issues.value = await listIssues({ mine: true });
  } catch (e: any) {
    error.value = e.message || 'โหลดข้อมูลไม่สำเร็จ';
  } finally {
    isLoading.value = false;
  }
});

function statusColor(s: string) {
  return {
    pending: 'bg-yellow-100 text-yellow-700',
    in_progress: 'bg-blue-100 text-blue-700',
    resolved: 'bg-green-100 text-green-700',
    escalated: 'bg-orange-100 text-orange-700',
    cancelled: 'bg-gray-200 text-gray-500',
    rejected: 'bg-rose-100 text-rose-700',
  }[s] || 'bg-gray-100 text-gray-600';
}
</script>

<template>
  <div>
    <div class="flex flex-wrap items-center justify-between gap-3 mb-5">
      <div>
        <h1 class="text-xl sm:text-2xl font-bold text-gray-900 leading-tight"><i class="bi bi-file-earmark-text mr-1 text-red-500"></i> เรื่องของฉัน</h1>
        <p class="text-sm text-gray-500">ติดตามสถานะเรื่องที่คุณแจ้ง</p>
      </div>
      <RouterLink to="/issues/new" class="btn-gradient text-sm shrink-0">
        <i class="bi bi-plus-lg"></i> แจ้งเรื่องใหม่
      </RouterLink>
    </div>

    <div v-if="isLoading" class="flex justify-center py-16">
      <div class="animate-spin w-10 h-10 border-4 border-red-600 border-t-transparent rounded-full"></div>
    </div>
    <div v-else-if="error" class="text-red-500 text-center py-10">{{ error }}</div>

    <div v-else-if="!issues.length" class="bg-white rounded-xl p-10 text-center text-gray-400">
      <div class="text-4xl mb-2"><i class="bi bi-inbox"></i></div>
      <p>ยังไม่มีเรื่องที่คุณแจ้ง</p>
      <RouterLink to="/issues/new" class="inline-block mt-3 text-red-600 hover:underline">แจ้งเรื่องแรกของคุณ <i class="bi bi-arrow-right"></i></RouterLink>
    </div>

    <TransitionGroup v-else name="list" tag="div" class="grid gap-3">
      <RouterLink
        v-for="i in issues"
        :key="i.id"
        :to="{ name: 'issue-detail', params: { id: i.id } }"
        class="bg-white rounded-xl shadow-sm p-4 hover:shadow-md transition block"
      >
        <div class="flex items-start justify-between gap-3">
          <div class="flex-1 min-w-0">
            <div class="flex gap-2 mb-1.5">
              <span class="px-2 py-0.5 bg-red-100 text-red-700 text-xs rounded-full">{{ MAIN_CATEGORY_LABELS[i.main_category] }}</span>
              <span class="px-2 py-0.5 bg-purple-100 text-purple-700 text-xs rounded-full">{{ subcategoryLabel(i.main_category, i.category) }}</span>
            </div>
            <h3 class="font-semibold text-gray-900 truncate">{{ i.title }}</h3>
            <p class="text-xs text-gray-500 mt-1">ตอนนี้อยู่ที่: {{ LEVEL_LABELS[i.current_level] }}</p>
          </div>
          <div class="text-right shrink-0">
            <span class="px-2.5 py-1 text-xs font-medium rounded-full whitespace-nowrap" :class="statusColor(i.status)">
              {{ STATUS_LABELS[i.status] }}
            </span>
          </div>
        </div>
      </RouterLink>
    </TransitionGroup>
  </div>
</template>

<style scoped>
/* list animation */
.list-enter-active, .list-leave-active { transition: all 0.25s ease; }
.list-enter-from { opacity: 0; transform: translateY(10px); }
.list-leave-to { opacity: 0; transform: translateY(-6px); }
</style>
