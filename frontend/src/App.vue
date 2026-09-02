<script setup lang="ts">
import { RouterView, useRoute } from 'vue-router';

const route = useRoute();
</script>

<template>
  <RouterView v-slot="{ Component }">
    <!-- Login: standalone — render ตรง ไม่ซ้อน transition (MainLayout มีของตัวเอง)
         หน้าอื่น: อยู่ใน MainLayout แล้ว จะ animate ข้างในเอง -->
    <component :is="Component" :key="route.path" />
  </RouterView>
</template>

<style>
/* Global Styles can go here */
body {
  /* #FAFAFC = โทนพรีเมียมเดียวกับ Landing/Login (แทน gray-50 เก่า) */
  @apply bg-[#FAFAFC] text-slate-900;
  margin: 0;
  /* ฟอนต์หลัก Noto Sans Thai (ไทย) — fallback sans-serif เสมอ (ตรงกับ tailwind.config + main.css) */
  font-family: 'Noto Sans Thai', Tahoma, Arial, system-ui, -apple-system, sans-serif;
}
</style>
