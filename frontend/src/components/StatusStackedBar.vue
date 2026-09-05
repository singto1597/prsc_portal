<script setup lang="ts">
// แถบสถานะรวมแบบ stacked (5 สี semantic) — ใช้ที่ KPI band + header หมวดหลัก
import { STATUS_BAR } from '@/constants/status';
import type { StatusStat } from '@/services/dashboard';

const props = defineProps<{
  stats: StatusStat[];
  total: number;
  heightClass?: string; // เช่น 'h-2.5' / 'h-1.5'
}>();

// สัดส่วนของแต่ละ segment ใช้ flex-grow (ไม่ใช้ Math.round ต่อ segment)
// — Math.round แบบแยก segment ทำให้ผลรวม < 100% เหลือริ้วเทา (เช่น 33+33+33=99)
//   flex-grow เติมเต็ม 100% เสมอ ไม่มี rounding error
function grow(s: StatusStat): number {
  if (!props.total || !s.count) return 0;
  return s.count / props.total;
}
</script>

<template>
  <div
    class="w-full flex rounded-full overflow-hidden bg-stone-100"
    :class="heightClass || 'h-2.5'"
    role="img"
    :aria-label="stats.map((s) => `${s.label} ${s.count}`).join(', ')"
  >
    <div
      v-for="s in stats"
      :key="s.status"
      v-show="s.count > 0"
      class="h-full"
      :class="STATUS_BAR[s.status] ?? 'bg-stone-300'"
      :style="{ flexGrow: grow(s), flexBasis: '0%' }"
      :title="`${s.label}: ${s.count} เรื่อง`"
    ></div>
  </div>
</template>
