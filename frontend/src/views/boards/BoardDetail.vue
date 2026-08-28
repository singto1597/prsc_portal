<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Swal from 'sweetalert2'
import { getBoard, submitVote, addComment } from '@/services/board'
import { BOARD_TYPE_LABELS, boardTypeIcon, type BoardDetail } from '@/types/board'
import CommentThread from '@/components/boards/CommentThread.vue'

/**
 * 📄 PIRI Board — รองรับ 2 เลย์เอาต์:
 * - Vote: ตัวเลือกแบบ progress bar + เลือกโหวต (1 เสียง/คน — เปลี่ยนไม่ได้)
 * - Talk: คอมเมนต์แบบ threaded (CommentThread recursive)
 */
const route = useRoute()
const router = useRouter()

const board = ref<BoardDetail | null>(null)
const isLoading = ref(true)
const loadError = ref('')

// ===== Vote =====
const selectedChoice = ref<number | null>(null)
const voting = ref(false)
const myVoted = computed(() => (board.value?.my_vote_choice_id ?? null) !== null)

function choicePercent(c: { vote_count: number }): number {
  const total = board.value?.total_votes ?? 0
  if (total <= 0) return 0
  return Math.round((c.vote_count / total) * 100)
}

async function handleVote() {
  if (!board.value || selectedChoice.value === null || myVoted.value) return
  voting.value = true
  try {
    await submitVote(board.value.id, selectedChoice.value)
    Swal.fire({ icon: 'success', title: 'ส่งเสียงโหวตแล้ว!', timer: 1200, showConfirmButton: false })
    await load()
  } catch (e) {
    Swal.fire({ icon: 'error', title: 'โหวตไม่สำเร็จ', text: e instanceof Error ? e.message : String(e) })
  } finally {
    voting.value = false
  }
}

// ===== Talk =====
const commentBody = ref('')
const postingComment = ref(false)

async function submitComment() {
  if (!board.value || !commentBody.value.trim()) return
  postingComment.value = true
  try {
    await addComment(board.value.id, commentBody.value.trim())
    commentBody.value = ''
    Swal.fire({ icon: 'success', title: 'คอมเมนต์แล้ว', timer: 1000, showConfirmButton: false })
    await load()
  } catch (e) {
    Swal.fire({ icon: 'error', title: 'คอมเมนต์ไม่สำเร็จ', text: e instanceof Error ? e.message : String(e) })
  } finally {
    postingComment.value = false
  }
}

async function load() {
  isLoading.value = true
  loadError.value = ''
  try {
    board.value = await getBoard(Number(route.params.id))
    // รีเซ็ตตัวเลือกที่เลือก (หลังโหวตแล้ว reload — ป้องกัน select ตัวเดิมหลงเหลือ)
    if (board.value?.my_vote_choice_id) selectedChoice.value = null
  } catch (e) {
    loadError.value = e instanceof Error ? e.message : 'โหลดบอร์ดไม่สำเร็จ'
  } finally {
    isLoading.value = false
  }
}

onMounted(load)

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString('th-TH', {
    timeZone: 'Asia/Bangkok',
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })
}

// คอมเมนต์ root (parent_comment_id = null) — backend ส่ง tree ที่ roots อยู่ระดับบน
const rootComments = computed(() => board.value?.comments ?? [])
</script>

<template>
  <div v-if="isLoading" class="flex justify-center py-20">
    <div class="animate-spin w-10 h-10 border-4 border-red-600 border-t-transparent rounded-full"></div>
  </div>

  <div v-else-if="loadError" class="max-w-3xl mx-auto bg-white rounded-xl shadow-sm p-10 text-center">
    <div class="text-4xl text-gray-300 mb-3"><i class="bi bi-file-earmark-x"></i></div>
    <p class="text-gray-600 font-medium">{{ loadError }}</p>
    <button @click="router.push({ name: 'boards' })" class="mt-4 px-4 py-2 bg-red-600 text-white rounded-xl text-sm hover:bg-red-700">
      กลับไป PIRI Boards
    </button>
  </div>

  <div v-else-if="board" class="max-w-3xl mx-auto space-y-5">
    <!-- ปุ่มกลับ -->
    <button @click="router.push({ name: 'boards' })" class="flex items-center gap-1 text-sm text-gray-500 hover:text-red-600 font-medium">
      <i class="bi bi-arrow-left"></i> PIRI Boards
    </button>

    <!-- Header -->
    <div class="bg-white rounded-xl shadow-sm p-5">
      <div class="flex items-center justify-between gap-3 mb-2">
        <span class="flex items-center gap-1.5 text-xs font-semibold"
          :class="board.board_type === 'vote' ? 'text-violet-600' : 'text-sky-600'">
          <i :class="boardTypeIcon(board.board_type)"></i> บอร์ด{{ BOARD_TYPE_LABELS[board.board_type] }}
        </span>
        <span class="text-xs text-gray-400">{{ fmtDate(board.created_at) }}</span>
      </div>
      <h1 class="text-lg sm:text-xl font-bold text-gray-900 leading-snug break-words">{{ board.title }}</h1>
      <p class="text-gray-500 text-sm mt-1">โดย {{ board.is_anonymous ? 'ไม่ระบุชื่อ' : board.author_name || 'สภานักเรียน' }}</p>
      <p class="text-gray-700 mt-3 whitespace-pre-wrap break-words">{{ board.description }}</p>
      <div v-if="board.tags.length" class="flex flex-wrap gap-1.5 mt-3">
        <span v-for="tag in board.tags" :key="tag" class="px-2 py-0.5 bg-gray-100 text-gray-600 text-[11px] rounded-full">#{{ tag }}</span>
      </div>
    </div>

    <!-- ===================== Vote layout ===================== -->
    <div v-if="board.board_type === 'vote'" class="bg-white rounded-xl shadow-sm p-5">
      <div class="flex items-center justify-between mb-1">
        <h2 class="text-lg font-bold text-gray-800"><i class="bi bi-bar-chart-fill mr-1 text-violet-600"></i> โหวต</h2>
        <span class="text-sm text-gray-500 tabular-nums">{{ board.total_votes.toLocaleString('en-US') }} เสียง</span>
      </div>

      <!-- แบนเนอร์: โหวตแล้ว → เปลี่ยนตัวเลือกไม่ได้ -->
      <div v-if="myVoted" class="mb-4 px-3 py-2 bg-emerald-50 border border-emerald-200 text-emerald-700 text-sm rounded-xl">
        <i class="bi bi-check-circle-fill mr-1"></i> คุณส่งเสียงโหวตแล้ว — แต่ละคนโหวตได้ 1 ครั้ง
      </div>

      <div class="space-y-3">
        <button
          v-for="c in board.choices"
          :key="c.id"
          type="button"
          :disabled="myVoted"
          @click="selectedChoice = c.id"
          class="w-full text-left p-4 rounded-xl border-2 transition"
          :class="[
            !myVoted && selectedChoice === c.id
              ? 'border-red-600 bg-red-50'
              : 'border-gray-200 hover:border-red-300',
            board.my_vote_choice_id === c.id ? 'ring-2 ring-emerald-400 border-emerald-400' : '',
            myVoted ? 'cursor-default' : 'cursor-pointer',
          ]"
        >
          <div class="flex items-center justify-between gap-3 mb-2">
            <span class="font-semibold text-gray-900 text-sm sm:text-base flex items-center gap-2">
              <span v-if="board.my_vote_choice_id === c.id" class="text-emerald-600"><i class="bi bi-check-circle-fill"></i></span>
              {{ c.choice_text }}
            </span>
            <span class="text-sm text-gray-500 tabular-nums whitespace-nowrap">
              {{ c.vote_count.toLocaleString('en-US') }} เสียง · {{ choicePercent(c) }}%
            </span>
          </div>
          <!-- progress bar -->
          <div class="h-2.5 bg-gray-100 rounded-full overflow-hidden">
            <div
              class="h-full rounded-full transition-all duration-500"
              :class="board.my_vote_choice_id === c.id ? 'bg-emerald-500' : 'bg-violet-500'"
              :style="{ width: choicePercent(c) + '%' }"
            ></div>
          </div>
        </button>
      </div>

      <p v-if="!board.choices.length" class="text-sm text-gray-400 py-2">ยังไม่มีตัวเลือกโหวต</p>

      <button
        v-if="!myVoted"
        type="button"
        :disabled="selectedChoice === null || voting"
        @click="handleVote"
        class="mt-4 w-full py-3 bg-red-600 text-white rounded-xl hover:bg-red-700 disabled:opacity-50 font-medium"
      >
        {{ voting ? 'กำลังส่งเสียง...' : selectedChoice === null ? 'เลือกตัวเลือกก่อนโหวต' : 'ส่งเสียงโหวต' }}
      </button>
    </div>

    <!-- ===================== Talk layout ===================== -->
    <div v-else class="bg-white rounded-xl shadow-sm p-5">
      <h2 class="text-lg font-bold text-gray-800 mb-4">
        <i class="bi bi-chat-left-text mr-1 text-sky-600"></i> พูดคุย
        <span v-if="rootComments.length" class="text-sm font-normal text-gray-400">({{ board.comment_count }})</span>
      </h2>

      <!-- ปิดคอมเมนต์ -->
      <div v-if="!board.allow_comments" class="mb-4 px-3 py-2 bg-gray-50 text-gray-500 text-sm rounded-xl">
        <i class="bi bi-lock mr-1"></i> บอร์ดนี้ปิดคอมเมนต์ (อ่านอย่างเดียว)
      </div>

      <!-- ช่องคอมเมนต์ root -->
      <div v-if="board.allow_comments" class="flex gap-2 mb-5">
        <input
          v-model="commentBody"
          type="text"
          placeholder="ร่วมแสดงความเห็น..."
          maxlength="1000"
          class="flex-1 px-3 py-2.5 border border-gray-300 rounded-xl text-sm focus:ring-2 focus:ring-red-500"
          @keyup.enter="submitComment"
        />
        <button
          type="button"
          :disabled="postingComment || !commentBody.trim()"
          @click="submitComment"
          class="px-4 py-2.5 bg-red-600 text-white rounded-xl text-sm hover:bg-red-700 disabled:opacity-50"
        >
          {{ postingComment ? '...' : 'ส่ง' }}
        </button>
      </div>

      <!-- กระทู้คอมเมนต์ (threaded) -->
      <div v-if="rootComments.length" class="space-y-4">
        <CommentThread v-for="c in rootComments" :key="c.id" :board-id="board.id" :comment="c" @refresh="load" />
      </div>
      <p v-else-if="board.allow_comments" class="text-sm text-gray-400 py-2">ยังไม่มีความเห็น — เป็นคนแรกที่ร่วมพูดคุย</p>
    </div>
  </div>
</template>
