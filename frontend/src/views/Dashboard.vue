<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  ArcElement,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
} from 'chart.js';
import { Bar, Doughnut, Line } from 'vue-chartjs';
import Swal from 'sweetalert2';
import { getDashboardSummary, type DashboardSummary } from '@/services/dashboard';

ChartJS.register(CategoryScale, LinearScale, BarElement, ArcElement, PointElement, LineElement, Tooltip, Legend);

const data = ref<DashboardSummary | null>(null);
const isLoading = ref(true);

onMounted(async () => {
  try {
    data.value = await getDashboardSummary();
  } catch (e: any) {
    Swal.fire({ icon: 'error', title: 'ไม่สามารถโหลด Dashboard', text: e.message });
  } finally {
    isLoading.value = false;
  }
});

// Charts data
const categoryChart = computed(() => ({
  labels: data.value?.top_categories.map((c) => c.label) || [],
  datasets: [{
    label: 'จำนวนเรื่อง',
    data: data.value?.top_categories.map((c) => c.count) || [],
    backgroundColor: ['#3b82f6', '#8b5cf6', '#f59e0b', '#10b981', '#ef4444', '#6b7280'],
  }],
}));

const statusChart = computed(() => ({
  labels: data.value?.by_status.map((s) => s.label) || [],
  datasets: [{
    data: data.value?.by_status.map((s) => s.count) || [],
    backgroundColor: ['#f59e0b', '#3b82f6', '#10b981', '#ef4444'],
  }],
}));

const trendChart = computed(() => ({
  labels: (data.value?.trend || []).map((t) => t.date.slice(5)),
  datasets: [{
    label: 'จำนวนเรื่อง/วัน',
    data: (data.value?.trend || []).map((t) => t.count),
    borderColor: '#3b82f6',
    backgroundColor: 'rgba(59,130,246,0.1)',
    fill: true,
    tension: 0.3,
  }],
}));

const chartOptions = { responsive: true, maintainAspectRatio: false };

const stats = computed(() => [
  { label: 'เรื่องทั้งหมด', value: data.value?.total_issues ?? 0, icon: 'bi-files', color: 'text-red-600 bg-red-50' },
  { label: 'รอรับเรื่อง', value: data.value?.pending ?? 0, icon: 'bi-hourglass-top', color: 'text-yellow-600 bg-yellow-50' },
  { label: 'กำลังดำเนินการ', value: data.value?.in_progress ?? 0, icon: 'bi-gear', color: 'text-rose-600 bg-rose-50' },
  { label: 'แก้ไขเสร็จ', value: data.value?.resolved ?? 0, icon: 'bi-check-circle', color: 'text-green-600 bg-green-50' },
  { label: 'ส่งต่อระดับบน', value: data.value?.escalated ?? 0, icon: 'bi-arrow-up-circle', color: 'text-red-600 bg-red-50' },
  { label: 'นักเรียนในระบบ', value: data.value?.total_students ?? 0, icon: 'bi-people', color: 'text-purple-600 bg-purple-50' },
  { label: 'ห้องเรียน', value: data.value?.total_rooms ?? 0, icon: 'bi-door-closed', color: 'text-cyan-600 bg-cyan-50' },
]);
</script>

<template>
  <div>
    <h1 class="text-2xl font-bold text-gray-900 mb-5"><i class="bi bi-bar-chart mr-1"></i> แดชบอร์ด</h1>

    <div v-if="isLoading" class="flex justify-center py-20">
      <div class="animate-spin w-10 h-10 border-4 border-red-600 border-t-transparent rounded-full"></div>
    </div>

    <div v-else-if="data" class="space-y-6">
      <!-- Stat cards -->
      <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-7 gap-3">
        <div v-for="s in stats" :key="s.label" class="bg-white rounded-xl shadow-sm p-4">
          <div class="w-9 h-9 rounded-lg flex items-center justify-center mb-2" :class="s.color">
            <i class="bi" :class="s.icon"></i>
          </div>
          <p class="text-2xl font-bold text-gray-900">{{ s.value }}</p>
          <p class="text-xs text-gray-500">{{ s.label }}</p>
        </div>
      </div>

      <!-- Charts -->
      <div class="grid md:grid-cols-2 gap-4">
        <div class="bg-white rounded-xl shadow-sm p-4">
          <h3 class="font-semibold text-gray-800 mb-3">หมวดหมู่ที่ถูกแจ้งเยอะสุด</h3>
          <div class="h-64"><Bar :data="categoryChart" :options="chartOptions" /></div>
        </div>
        <div class="bg-white rounded-xl shadow-sm p-4">
          <h3 class="font-semibold text-gray-800 mb-3">สัดส่วนตามสถานะ</h3>
          <div class="h-64"><Doughnut :data="statusChart" :options="chartOptions" /></div>
        </div>
      </div>

      <div class="bg-white rounded-xl shadow-sm p-4">
        <h3 class="font-semibold text-gray-800 mb-3">แนวโน้มเรื่องที่แจ้ง (7 วัน)</h3>
        <div class="h-64"><Line :data="trendChart" :options="chartOptions" /></div>
      </div>
    </div>
  </div>
</template>
