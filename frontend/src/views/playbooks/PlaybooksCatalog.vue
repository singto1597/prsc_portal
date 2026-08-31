<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink } from 'vue-router'
import { PLAYBOOKS, playbookVolume } from '@/types/playbook'

// ปกที่ไฟล์ยังไม่วางจริง (404) → ใช้ placeholder gradient แทนรูปกากบาท
const failedCovers = ref<Set<string>>(new Set())
function onCoverError(id: string) {
  failedCovers.value = new Set([...failedCovers.value, id])
}
const isCoverBroken = (id: string) => failedCovers.value.has(id)
</script>

<template>
  <div>
    <div class="mb-6">
      <h1 class="text-xl sm:text-2xl font-bold text-gray-900 leading-tight">
        <i class="bi bi-journal-bookmark-fill mr-1 text-red-500"></i> P.R. Playbooks
      </h1>
      <p class="text-sm text-gray-500 mt-1">P.R. Playbooks — คู่มือสภานักเรียนฉบับ E-book อ่านเลื่อนลงได้ ครอบคลุม 6 หมวดหมู่</p>
    </div>

    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      <RouterLink
        v-for="pb in PLAYBOOKS"
        :key="pb.id"
        :to="{ name: 'playbook-reader', params: { id: pb.id } }"
        class="page-card overflow-hidden flex flex-col hover:shadow-md transition card-hover"
      >
        <!-- 🔖 ปก -->
        <div class="relative aspect-[3/4] bg-gradient-to-br from-red-100 to-rose-50 flex items-center justify-center">
          <img
            v-if="!isCoverBroken(pb.id)"
            :src="pb.coverImage"
            :alt="`ปก ${pb.title}`"
            loading="lazy"
            @error="onCoverError(pb.id)"
            class="absolute inset-0 w-full h-full object-cover"
          />
          <div v-else class="text-center text-red-300">
            <i class="bi bi-journal-text text-5xl"></i>
            <p class="text-xs font-semibold mt-2">ยังไม่พร้อมใช้งาน</p>
          </div>
          <!-- ป้ายเล่มที่ -->
          <span class="absolute top-3 left-3 px-2 py-1 rounded-full bg-red-600 text-white text-[11px] font-bold shadow">
            เล่มที่ {{ playbookVolume(pb.id) }}
          </span>
        </div>

        <!-- ข้อมูลเล่ม -->
        <div class="p-4 flex flex-col flex-1">
          <h3 class="font-bold text-gray-900 leading-snug mb-1.5">{{ pb.title }}</h3>
          <p class="text-sm text-gray-500 mb-3 line-clamp-2">{{ pb.description }}</p>

          <div class="mt-auto flex items-center justify-between pt-3 border-t border-gray-100">
            <span class="text-xs text-gray-400 flex items-center gap-1.5">
              <i class="bi bi-file-earmark-text"></i> {{ pb.totalPages }} หน้า
            </span>
            <span class="inline-flex items-center gap-1.5 text-xs font-bold text-red-600">
              อ่านเล่มนี้ <i class="bi bi-arrow-right"></i>
            </span>
          </div>
        </div>
      </RouterLink>
    </div>

    <!-- หมายเหตุการจัดเก็บไฟล์ -->
    <p class="mt-6 text-xs text-gray-400 leading-relaxed">
      <i class="bi bi-info-circle mr-1"></i>
      ไฟล์หนังสือถูกจัดเก็บที่ public/playbooks/vol1 – vol6 (รูปปก cover.webp, หน้าหนังสือ page-01.webp … และ PDF ต้นฉบับ playbook.pdf)
    </p>
  </div>
</template>
