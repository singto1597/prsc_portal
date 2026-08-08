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
  @apply bg-gray-50 text-gray-900;
  margin: 0;
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
}
</style>
