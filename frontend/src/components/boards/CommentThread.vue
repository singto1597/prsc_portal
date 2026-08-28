<script setup lang="ts">
import { ref } from 'vue'
import Swal from 'sweetalert2'
import { addComment } from '@/services/board'
import type { BoardComment } from '@/types/board'

/**
 * 💬 คอมเมนต์ 1 อัน + รีพลายซ้อน (recursive — อ้างอิงตัวเองด้วยชื่อไฟล์)
 * - แสดง avatar/ชื่อ/เวลา/ข้อความ + ปุ่ม "ตอบกลับ"
 * - reply → เปิดช่องพิมพ์ใต้คอมเมนต์ → addComment(parent_id) → emit refresh ให้ parent โหลดใหม่
 * ความลึกถูกจำกัดฝั่ง backend แล้ว (MAX_DISPLAY_DEPTH) — recursive ปลอดภัย
 */
const props = defineProps<{ boardId: number; comment: BoardComment }>()

const emit = defineEmits<{ refresh: [] }>()

const replying = ref(false)
const replyBody = ref('')
const posting = ref(false)

function fmtTime(iso: string): string {
  return new Date(iso).toLocaleString('th-TH', {
    timeZone: 'Asia/Bangkok',
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

async function submitReply() {
  const body = replyBody.value.trim()
  if (!body) return
  posting.value = true
  try {
    await addComment(props.boardId, body, props.comment.id)
    replyBody.value = ''
    replying.value = false
    Swal.fire({ icon: 'success', title: 'ตอบกลับแล้ว', timer: 1000, showConfirmButton: false })
    emit('refresh')
  } catch (e) {
    Swal.fire({ icon: 'error', title: 'ตอบกลับไม่สำเร็จ', text: e instanceof Error ? e.message : String(e) })
  } finally {
    posting.value = false
  }
}
</script>

<template>
  <div class="pl-4 border-l-2 border-gray-100">
    <!-- ตัวคอมเมนต์ -->
    <div class="flex gap-2.5">
      <div
        class="w-8 h-8 rounded-full bg-red-100 text-red-600 flex items-center justify-center font-bold text-sm shrink-0"
      >
        {{ (comment.commenter_name || '?').charAt(0) }}
      </div>
      <div class="min-w-0 flex-1">
        <div class="flex items-center gap-2 flex-wrap">
          <span class="text-sm font-semibold text-gray-800">{{ comment.commenter_name || 'ไม่ระบุชื่อ' }}</span>
          <span class="text-xs text-gray-400">{{ fmtTime(comment.created_at) }}</span>
          <span v-if="comment.is_edited" class="text-[11px] text-gray-400">· แก้ไขแล้ว</span>
        </div>
        <p class="text-sm text-gray-700 mt-0.5 whitespace-pre-wrap break-words">{{ comment.body }}</p>
        <button
          type="button"
          @click="replying = !replying"
          class="mt-1 text-xs text-gray-400 hover:text-red-600 font-medium flex items-center gap-1"
        >
          <i class="bi bi-reply"></i> ตอบกลับ
        </button>

        <!-- ช่องตอบกลับ -->
        <div v-if="replying" class="mt-2 flex gap-2">
          <input
            v-model="replyBody"
            type="text"
            placeholder="พิมพ์คำตอบ..."
            maxlength="1000"
            class="flex-1 px-3 py-2 border border-gray-300 rounded-xl text-sm"
            @keyup.enter="submitReply"
          />
          <button
            type="button"
            :disabled="posting || !replyBody.trim()"
            @click="submitReply"
            class="px-3.5 py-2 bg-red-600 text-white rounded-xl text-sm hover:bg-red-700 disabled:opacity-50"
          >
            {{ posting ? '...' : 'ตอบ' }}
          </button>
        </div>
      </div>
    </div>

    <!-- รีพลายซ้อน (recursive — self-reference ด้วยชื่อไฟล์) -->
    <div v-if="comment.replies.length" class="mt-3 space-y-3">
      <CommentThread v-for="r in comment.replies" :key="r.id" :board-id="boardId" :comment="r" @refresh="emit('refresh')" />
    </div>
  </div>
</template>
