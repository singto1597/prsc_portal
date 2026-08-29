<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { listBoards } from '@/services/board'
import { BOARD_TYPE_LABELS, boardTypeIcon, type BoardSummary, type BoardType } from '@/types/board'
import PaginationBar from '@/components/PaginationBar.vue'

/**
 * 📋 PIRI Boards — feed สาธารณะ (PIRI Vote + PIRI Talk)
 * กรองตามประเภท (ทั้งหมด/โหวต/พูดคุย) + ค้นหา + แบ่งหน้า
 */
const boards = ref<BoardSummary[]>([])
const total = ref(0)
const isLoading = ref(true)
const error = ref('')
const typeFilter = ref<'' | BoardType>('') // '' = ทั้งหมด
const q = ref('')
const page = ref(1)
const pageSize = 12

// แท็บกรองประเภท
const TABS: Array<{ value: '' | BoardType; label: string; icon: string }> = [
  { value: '', label: 'ทั้งหมด', icon: 'bi bi-grid' },
  { value: 'vote', label: 'โหวต', icon: 'bi bi-bar-chart-fill' },
  { value: 'talk', label: 'พูดคุย', icon: 'bi bi-chat-dots-fill' },
]

onMounted(load)

// ค้นหา (debounce 300ms) → กลับหน้า 1
let timer: ReturnType<typeof setTimeout> | undefined
watch(q, () => {
  clearTimeout(timer)
  timer = setTimeout(() => {
    page.value = 1
    load()
  }, 300)
})

function switchType(t: '' | BoardType) {
  typeFilter.value = t
  page.value = 1
  load()
}

function onPageChange(n: number) {
  page.value = n
  load()
}

async function load() {
  isLoading.value = true
  error.value = ''
  try {
    const res = await listBoards({
      board_type: typeFilter.value || undefined,
      q: q.value.trim() || undefined,
      limit: pageSize,
      offset: (page.value - 1) * pageSize,
    })
    boards.value = res.items
    total.value = res.total
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'โหลดข้อมูลไม่สำเร็จ'
  } finally {
    isLoading.value = false
  }
}

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString('th-TH', {
    timeZone: 'Asia/Bangkok',
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })
}
</script>

<template>
  <div>
    <div class="flex flex-wrap items-center justify-between gap-3 mb-5">
      <div>
        <h1 class="text-xl sm:text-2xl font-bold text-gray-900 leading-tight">
          <i class="bi bi-columns-gap mr-1 text-red-500"></i> PIRI Boards
        </h1>
        <p class="text-sm text-gray-500">โหวต + พูดคุยสาธารณะ ที่สภานักเรียนอนุมัติแล้ว</p>
      </div>
    </div>

    <!-- แถบกรอง + ค้นหา -->
    <div class="flex flex-wrap items-center gap-2 mb-5">
      <div class="flex gap-1 p-1 bg-gray-100 rounded-xl">
        <button
          v-for="t in TABS"
          :key="t.value"
          type="button"
          @click="switchType(t.value)"
          class="px-3.5 py-2 rounded-lg text-sm font-medium transition flex items-center gap-1.5"
          :class="typeFilter === t.value ? 'bg-white shadow text-red-600' : 'text-gray-500 hover:text-gray-700'"
        >
          <i :class="t.icon"></i> {{ t.label }}
        </button>
      </div>

      <div class="relative flex-1 min-w-[180px] sm:flex-none sm:w-72">
        <i class="bi bi-search absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm"></i>
        <input
          v-model="q"
          type="search"
          placeholder="ค้นหาบอร์ด..."
          class="w-full pl-9 pr-3 py-2.5 border border-gray-300 rounded-xl text-sm bg-white focus:ring-2 focus:ring-red-500"
        />
      </div>

      <span class="text-sm text-gray-400 ml-auto tabular-nums">{{ total.toLocaleString('en-US') }} บอร์ด</span>
    </div>

    <div v-if="isLoading" class="flex justify-center py-16">
      <div class="animate-spin w-10 h-10 border-4 border-red-600 border-t-transparent rounded-full"></div>
    </div>
    <div v-else-if="error" class="text-red-500 text-center py-10">{{ error }}</div>

    <div v-else-if="!boards.length" class="bg-white rounded-xl p-12 text-center text-gray-400">
      <div class="text-4xl mb-2"><i class="bi bi-columns-gap"></i></div>
      <p>ยังไม่มีบอร์ดในเงื่อนไขนี้</p>
    </div>

    <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      <RouterLink
        v-for="b in boards"
        :key="b.id"
        :to="{ name: 'board-detail', params: { id: b.id } }"
        class="bg-white rounded-xl shadow-sm p-5 hover:shadow-md transition flex flex-col"
      >
        <div class="flex items-center justify-between mb-2">
          <span class="flex items-center gap-1.5 text-xs font-semibold"
            :class="b.board_type === 'vote' ? 'text-violet-600' : 'text-sky-600'">
            <i :class="boardTypeIcon(b.board_type)"></i> {{ BOARD_TYPE_LABELS[b.board_type] }}
          </span>
          <span class="text-xs text-gray-400">{{ fmtDate(b.created_at) }}</span>
        </div>

        <h3 class="font-semibold text-gray-900 leading-snug mb-1 line-clamp-2">{{ b.title }}</h3>
        <p class="text-sm text-gray-500 mb-3 line-clamp-2">{{ b.description }}</p>

        <div class="mt-auto">
          <div v-if="b.tags.length" class="flex flex-wrap gap-1.5 mb-3">
            <span v-for="tag in b.tags.slice(0, 4)" :key="tag" class="px-2 py-0.5 bg-gray-100 text-gray-600 text-[11px] rounded-full">
              #{{ tag }}
            </span>
          </div>
          <div class="flex items-center justify-between text-xs text-gray-500 pt-2 border-t border-gray-100">
            <span class="truncate">
              <i class="bi bi-person mr-1"></i>
              {{ b.is_anonymous ? 'ไม่ระบุชื่อ' : b.author_name || 'สภานักเรียน' }}
            </span>
            <span class="flex items-center gap-3 shrink-0 ml-2">
              <span v-if="b.board_type === 'vote'"><i class="bi bi-bar-chart mr-1"></i>{{ b.total_votes.toLocaleString('en-US') }}</span>
              <span v-else><i class="bi bi-chat-left-text mr-1"></i>{{ b.comment_count.toLocaleString('en-US') }}</span>
            </span>
          </div>
        </div>
      </RouterLink>
    </div>

    <PaginationBar :total="total" :page="page" :page-size="pageSize" :loading="isLoading" @page-change="onPageChange" />
  </div>
</template>
