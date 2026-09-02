<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import Swal from 'sweetalert2'
import { listNotifications } from '@/services/notification'
import { GROUP_TABS, NOTIFICATION_TYPE_ICONS, type NotificationItem, type NotificationGroup } from '@/types/notification'
import { useNotificationsStore } from '@/stores/notifications'
import PaginationBar from '@/components/PaginationBar.vue'

/**
 * 🔔 หน้าแจ้งเตือนกลาง (เข้าได้ทุกคน) — badge messenger style
 * - แท็บ: ทั้งหมด / เรื่องของฉัน / เรื่องที่รับ / PIRI Boards / จัดการรายงาน
 * - แถวยังไม่อ่านไฮไลต์แดงอ่อน + ปุ่ม mark-read รายการ
 * - "อ่านทั้งหมด" เคลียร์ทุกกลุ่ม
 * - คลิกแถว → ไปที่เรื่อง/บอร์ด/รายงานที่เกี่ยวข้อง (แล้ว mark อ่าน)
 */
const router = useRouter()
const notificationsStore = useNotificationsStore()

const items = ref<NotificationItem[]>([])
const total = ref(0)
const isLoading = ref(true)
const error = ref('')
const activeTab = ref<'' | NotificationGroup>('')
const unreadOnly = ref(false)
const page = ref(1)
const pageSize = 15

onMounted(load)

watch([activeTab, unreadOnly], () => {
  page.value = 1
  load()
})

function onPageChange(n: number) {
  page.value = n
  load()
}

async function load() {
  isLoading.value = true
  error.value = ''
  try {
    const res = await listNotifications({
      group_type: activeTab.value || undefined,
      unread_only: unreadOnly.value || undefined,
      limit: pageSize,
      offset: (page.value - 1) * pageSize,
    })
    items.value = res.items
    total.value = res.total
    await notificationsStore.fetchCounts() // badge อัปเดตตามจริง
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'โหลดการแจ้งเตือนไม่สำเร็จ'
  } finally {
    isLoading.value = false
  }
}

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleString('th-TH', {
    timeZone: 'Asia/Bangkok',
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function iconFor(n: NotificationItem): string {
  return NOTIFICATION_TYPE_ICONS[n.type] || 'bi bi-bell'
}

// ✅ mark อ่านรายการเดียว (ไม่ navigate)
async function markOne(n: NotificationItem) {
  if (n.read_at) return
  try {
    await notificationsStore.read({ ids: [n.id] })
    n.read_at = new Date().toISOString()
  } catch (e) {
    Swal.fire({ icon: 'error', title: 'ไม่สำเร็จ', text: e instanceof Error ? e.message : String(e) })
  }
}

// ✅ อ่านทั้งหมด
async function markAll() {
  const { isConfirmed } = await Swal.fire({
    icon: 'question',
    title: 'อ่านทั้งหมด?',
    text: 'จะทำเครื่องหมายว่าได้อ่านทุกการแจ้งเตือน',
    showCancelButton: true,
    confirmButtonText: 'อ่านทั้งหมด',
    cancelButtonText: 'ยกเลิก',
  })
  if (!isConfirmed) return
  try {
    await notificationsStore.read({ read_all: true })
    page.value = 1
    await load()
  } catch (e) {
    Swal.fire({ icon: 'error', title: 'ไม่สำเร็จ', text: e instanceof Error ? e.message : String(e) })
  }
}

// 🧭 คลิกแถว → navigate ไปที่ entity + mark อ่าน
function go(n: NotificationItem) {
  if (n.group_type === 'report') {
    void notificationsStore.read({ group_type: 'report' })
    // report_new → สภาเท่านั้น → ไปคิวรายงาน;
    // report_actioned → ผู้แจ้ง (อาจเป็นนักเรียน) → ไปบอร์ดนั้น (board-reports กันสิทธิ์)
    if (n.type === 'report_new') {
      void router.push({ name: 'board-reports' })
    } else if (n.board_id != null) {
      void router.push({ name: 'board-detail', params: { id: n.board_id } })
    }
    return
  }
  if (n.entity_type === 'issue' && n.entity_id != null) {
    void notificationsStore.read({ entity_type: 'issue', entity_id: n.entity_id })
    void router.push({ name: 'issue-detail', params: { id: n.entity_id } })
    return
  }
  if (n.board_id != null) {
    void notificationsStore.read({ board_id: n.board_id })
    void router.push({ name: 'board-detail', params: { id: n.board_id } })
    return
  }
  void markOne(n)
}
</script>

<template>
  <div>
    <div class="flex flex-wrap items-center justify-between gap-3 mb-5">
      <div>
        <h1 class="text-xl font-black tracking-tight text-slate-900 leading-tight sm:text-2xl">
          <i class="bi bi-bell-fill mr-1 text-red-500"></i> การแจ้งเตือน
        </h1>
        <p class="text-sm text-slate-500">
          เรื่องที่ยังไม่ได้อ่าน {{ notificationsStore.total > 0 ? `(${notificationsStore.total})` : '' }}
        </p>
      </div>
      <div class="flex items-center gap-2">
        <button
          @click="unreadOnly = !unreadOnly"
          class="px-3 py-2 rounded-xl text-sm font-semibold border transition-colors"
          :class="unreadOnly ? 'bg-red-600 text-white border-red-600' : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'"
        >
          <i class="bi bi-envelope mr-1"></i> ยังไม่อ่าน
        </button>
        <button
          v-if="notificationsStore.total > 0"
          @click="markAll"
          class="px-3 py-2 rounded-xl text-sm font-bold bg-white border border-red-200 text-red-600 hover:bg-red-50 transition-colors"
        >
          <i class="bi bi-check2-all mr-1"></i> อ่านทั้งหมด
        </button>
      </div>
    </div>

    <!-- แท็บกลุ่ม -->
    <div class="flex gap-2 flex-wrap mb-4">
      <button
        v-for="tab in GROUP_TABS"
        :key="tab.value"
        @click="activeTab = tab.value"
        class="px-4 py-2 rounded-xl text-sm font-bold transition-all border"
        :class="activeTab === tab.value
          ? 'bg-red-600 text-white border-red-600 shadow-sm'
          : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'"
      >
        <i :class="[tab.icon, 'mr-1.5']"></i> {{ tab.label }}
        <span v-if="tab.value && (notificationsStore.counts[tab.value] ?? 0) > 0"
          class="ml-1.5 text-[11px] font-bold px-1.5 py-0.5 rounded-full"
          :class="activeTab === tab.value ? 'bg-white/25' : 'bg-red-100 text-red-600'">
          {{ notificationsStore.counts[tab.value] ?? 0 }}
        </span>
      </button>
    </div>

    <!-- loading -->
    <div v-if="isLoading" class="flex justify-center py-16">
      <div class="w-10 h-10 border-4 border-red-200 border-t-red-600 rounded-full animate-spin"></div>
    </div>

    <!-- error -->
    <div v-else-if="error" class="bg-red-50 text-red-600 rounded-xl p-6 text-center text-sm">{{ error }}</div>

    <!-- ว่าง -->
    <div v-else-if="items.length === 0" class="bg-white rounded-2xl p-12 text-center text-slate-400">
      <div class="text-4xl mb-3"><i class="bi bi-bell-slash"></i></div>
      <p class="font-semibold">ไม่มีการแจ้งเตือน</p>
      <p class="text-sm">เมื่อมีเรื่องใหม่/บอร์ดใหม่/คอมเมนต์ตอบกลับ จะขึ้นตรงนี้</p>
    </div>

    <!-- รายการ -->
    <div v-else class="space-y-2">
      <div
        v-for="n in items"
        :key="n.id"
        class="bg-white rounded-2xl border cursor-pointer transition-colors"
        :class="n.read_at
          ? 'border-slate-100 hover:border-slate-200'
          : 'border-red-100 bg-red-50/40 hover:border-red-200'"
        @click="go(n)"
      >
        <div class="flex items-start gap-3 p-4">
          <div class="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
            :class="n.read_at ? 'bg-slate-100 text-slate-400' : 'bg-red-100 text-red-600'">
            <i :class="[iconFor(n), 'text-lg']"></i>
          </div>
          <div class="flex-1 min-w-0">
            <div class="flex items-start justify-between gap-2">
              <p class="font-bold text-sm text-slate-900 leading-snug">{{ n.title }}</p>
              <span class="text-[11px] text-slate-400 whitespace-nowrap shrink-0">{{ fmtDate(n.created_at) }}</span>
            </div>
            <p class="text-sm text-slate-500 mt-0.5 leading-snug line-clamp-2">{{ n.body }}</p>
            <div class="mt-1.5 flex items-center gap-2">
              <span class="text-[11px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-500 font-semibold">{{ n.actor_name || 'ระบบ' }}</span>
              <span v-if="!n.read_at" class="w-2 h-2 rounded-full bg-red-500 inline-block"></span>
            </div>
          </div>
          <button
            v-if="!n.read_at"
            @click.stop="markOne(n)"
            class="shrink-0 px-2.5 py-1.5 rounded-lg text-[11px] font-bold text-red-600 hover:bg-red-100 transition-colors"
            title="ทำเครื่องหมายว่าอ่านแล้ว"
          >
            อ่านแล้ว
          </button>
        </div>
      </div>

      <PaginationBar :total="total" :page="page" :page-size="pageSize" :loading="isLoading" @page-change="onPageChange" />
    </div>
  </div>
</template>
