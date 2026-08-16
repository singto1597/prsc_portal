<script setup lang="ts">
// แถบสถานะรวมแบบ stacked (5 สี semantic) — ใช้ที่ KPI band + header หมวดหลัก
import { STATUS_BAR } from '@/constants/status';
import type { StatusStat } from '@/services/dashboard';

const props = defineProps<{
  stats: StatusStat[];
  total: number;
  heightClass?: string; // เช่น 'h-2.5' / 'h-1.5'
}>();

// ความกว้างของแต่ละ segment (สถานะที่ count=0 → กว้าง 0)
function width(s: StatusStat): number {
  if (!props.total || !s.count) return 0;
  return Math.round((s.count / props.total) * 100);
}
</script>

<template>
  <div
    class="w-full flex rounded-full overflow-hidden bg-gray-100"
    :class="heightClass || 'h-2.5'"
    role="img"
    :aria-label="stats.map((s) => `${s.label} ${s.count}`).join(', ')"
  >
    <div
      v-for="s in stats"
      :key="s.status"
      v-show="s.count > 0"
      class="h-full"
      :class="STATUS_BAR[s.status] ?? 'bg-gray-300'"
      :style="{ width: width(s) + '%' }"
      :title="`${s.label}: ${s.count} เรื่อง`"
    ></div>
  </div>
</template>
