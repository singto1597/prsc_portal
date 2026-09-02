<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import Swal from 'sweetalert2'
import { approveToPublic } from '@/services/issue'
import { DESTINATION_LABELS, type Issue } from '@/types/issue'
import { BOARD_TYPE_LABELS, type BoardType } from '@/types/board'

/**
 * 🏛️ Modal อนุมัติเผยแพร่สาธารณะ (สภานักเรียน/แอดมิน)
 * - board_type ถูก lock ตาม requested_destination ของเรื่อง (vote→vote, talk→talk — backend บังคับ)
 * - vote board → ใส่ตัวเลือกโหวต (อย่างน้อย 2, ไม่ซ้ำ)
 * - talk board → สลับเปิด/ปิดคอมเมนต์ (allow_comments)
 *
 * v-model:open ควบคุมเปิด/ปิด; @approved → คืน board_id ที่สร้าง (parent นำไป navigate)
 */
const props = defineProps<{ issue: Issue | null }>()

const open = defineModel<boolean>('open', { default: false })
const emit = defineEmits<{ approved: [boardId: number] }>()

// ปลายทางที่ขอ (vote/talk เท่านั้นที่เข้ามาถึง modal นี้) — ใช้เป็น board_type ตรง ๆ
const boardType = computed<BoardType>(() => {
  return props.issue?.requested_destination === 'talk' ? 'talk' : 'vote'
})

const voteChoices = ref<string[]>(['', ''])
const allowComments = ref(true)
const submitting = ref(false)

// เปิด modal → รีเซ็ตฟอร์มทุกครั้ง
watch(
  () => open.value,
  (isOpen) => {
    if (isOpen && props.issue) {
      voteChoices.value = ['', '']
      allowComments.value = true
      submitting.value = false
    }
  },
)

function addChoice() {
  voteChoices.value.push('')
}
function removeChoice(idx: number) {
  if (voteChoices.value.length > 2) voteChoices.value.splice(idx, 1)
}

async function handleConfirm() {
  if (!props.issue) return

  const cleaned = voteChoices.value.map((c) => c.trim()).filter(Boolean)
  if (boardType.value === 'vote') {
    if (cleaned.length < 2) {
      Swal.fire({ icon: 'warning', title: 'ใส่ตัวเลือกไม่ครบ', text: 'บอร์ดโหวตต้องมีตัวเลือกอย่างน้อย 2 ตัวเลือก' })
      return
    }
    if (new Set(cleaned).size !== cleaned.length) {
      Swal.fire({ icon: 'warning', title: 'ตัวเลือกซ้ำกัน', text: 'กรุณาใส่ตัวเลือกแต่ละอันไม่ซ้ำกัน' })
      return
    }
  }

  submitting.value = true
  try {
    const res = await approveToPublic(props.issue.id, {
      board_type: boardType.value,
      vote_choices: boardType.value === 'vote' ? cleaned : undefined,
      allow_comments: allowComments.value,
    })
    Swal.fire({ icon: 'success', title: 'อนุมัติเผยแพร่แล้ว!', text: 'เรื่องถูกเผยแพร่เป็น PIRI Board แล้ว', timer: 1500, showConfirmButton: false })
    open.value = false
    emit('approved', res.board_id)
  } catch (e) {
    Swal.fire({ icon: 'error', title: 'อนุมัติไม่สำเร็จ', text: e instanceof Error ? e.message : String(e) })
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <Transition name="modal">
    <div v-if="open && issue" class="fixed inset-0 z-50 flex items-center justify-center p-4" @click.self="open = false">
      <!-- overlay -->
      <div class="absolute inset-0 bg-gray-900/50 backdrop-blur-sm"></div>

      <!-- card -->
      <div class="relative w-full max-w-lg bg-white rounded-2xl shadow-2xl p-5 sm:p-6 max-h-[90vh] overflow-y-auto">
        <div class="flex items-start justify-between gap-3 mb-4">
          <div>
            <h2 class="text-lg font-bold text-gray-900">
              <i class="bi bi-people-fill text-red-500 mr-1"></i> อนุมัติเผยแพร่สาธารณะ
            </h2>
            <p class="text-sm text-gray-500 mt-0.5">สภานักเรียน/แอดมิน พิจารณาเรื่องนี้เป็น PIRI Board</p>
          </div>
          <button type="button" class="w-8 h-8 flex items-center justify-center rounded-lg text-gray-400 hover:bg-gray-100 hover:text-gray-600" @click="open = false">
            <i class="bi bi-x-lg"></i>
          </button>
        </div>

        <!-- สรุปเรื่อง -->
        <div class="bg-gray-50 rounded-xl p-3 mb-4">
          <p class="text-sm font-semibold text-gray-800 break-words">{{ issue.title }}</p>
          <p class="text-xs text-gray-500 mt-0.5">ประเภทที่ขอ: {{ DESTINATION_LABELS[issue.requested_destination || 'normal'] }}</p>
        </div>

        <!-- ประเภท board (lock ตามที่ผู้แจ้งขอ — backend บังคับให้ตรง) -->
        <div class="mb-4">
          <label class="block text-sm font-medium text-gray-700 mb-1.5">ประเภทบอร์ด</label>
          <div class="inline-flex items-center gap-2 px-3 py-2 rounded-xl text-sm font-semibold"
            :class="boardType === 'vote' ? 'bg-red-100 text-red-700' : 'bg-rose-100 text-rose-700'">
            <i :class="boardType === 'vote' ? 'bi bi-bar-chart-fill' : 'bi bi-chat-dots-fill'"></i>
            {{ BOARD_TYPE_LABELS[boardType] }}
          </div>
        </div>

        <!-- vote board → ตั้งค่าตัวเลือกโหวต -->
        <div v-if="boardType === 'vote'" class="mb-4">
          <label class="block text-sm font-medium text-gray-700 mb-1.5">
            ตัวเลือกโหวต <span class="text-gray-400 font-normal">(อย่างน้อย 2 ตัวเลือก)</span>
          </label>
          <div class="space-y-2">
            <div v-for="(c, idx) in voteChoices" :key="idx" class="flex gap-2">
              <input
                v-model="voteChoices[idx]"
                type="text"
                :data-testid="'choice-input-' + idx"
                :placeholder="`ตัวเลือกที่ ${idx + 1}`"
                maxlength="200"
                class="flex-1 px-3 py-2.5 border border-gray-300 rounded-xl text-sm focus:ring-2 focus:ring-red-500"
              />
              <button
                type="button"
                :disabled="voteChoices.length <= 2"
                @click="removeChoice(idx)"
                title="ลบตัวเลือก"
                class="w-10 h-10 flex items-center justify-center rounded-xl border border-gray-200 text-gray-400 hover:text-red-500 hover:border-red-200 disabled:opacity-30 disabled:cursor-not-allowed"
              >
                <i class="bi bi-trash"></i>
              </button>
            </div>
          </div>
          <button type="button" @click="addChoice" class="mt-2 text-sm text-red-600 hover:text-red-700 font-medium flex items-center gap-1">
            <i class="bi bi-plus-circle"></i> เพิ่มตัวเลือก
          </button>
        </div>

        <!-- talk board → เปิด/ปิดคอมเมนต์ -->
        <div v-else class="mb-4">
          <label class="flex items-center gap-2 text-sm text-gray-700 cursor-pointer select-none">
            <input v-model="allowComments" type="checkbox" class="w-4 h-4 rounded bg-white border-gray-300 text-red-600 focus:ring-red-500 accent-red-600" />
            เปิดให้คอมเมนต์บนบอร์ดได้
          </label>
          <p class="text-xs text-gray-400 mt-1 ml-6">ปิดถ้าอยากให้เป็นบอร์ดอ่านอย่างเดียว (ไม่ให้คอมเมนต์)</p>
        </div>

        <!-- actions -->
        <div class="flex gap-2 pt-2">
          <button type="button" @click="open = false" class="flex-1 py-2.5 rounded-xl bg-gray-100 text-gray-700 hover:bg-gray-200 text-sm font-medium">
            ยกเลิก
          </button>
          <button
            type="button"
            :disabled="submitting"
            data-testid="approve-confirm"
            @click="handleConfirm"
            class="flex-1 py-2.5 rounded-xl bg-red-600 text-white hover:bg-red-700 disabled:opacity-50 text-sm font-medium"
          >
            {{ submitting ? 'กำลังอนุมัติ...' : 'อนุมัติเผยแพร่' }}
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.modal-enter-active, .modal-leave-active { transition: opacity 0.2s ease; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
</style>
