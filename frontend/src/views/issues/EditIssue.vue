<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import Swal from 'sweetalert2'
import { getIssue, updateIssue } from '@/services/issue'
import { MAIN_CATEGORIES, type MainCategory, type Category } from '@/types/issue'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const issueId = Number(route.params.id)
const mainCategory = ref<MainCategory | ''>('')
const category = ref<Category | ''>('')
const title = ref('')
const description = ref('')
const isAnonymous = ref(false)
const isLoading = ref(true) // โหลดข้อมูลเรื่อง
const isSaving = ref(false) // กำลังบันทึก

function errMsg(e: unknown): string {
  return e instanceof Error ? e.message : String(e)
}

// เลือกหมวดหลัก + รีเซ็ตหมวดย่อย (แยกเป็นฟังก์ชัน กัน prettier หั่น inline handler ให้พัง)
function selectMainCategory(key: MainCategory) {
  mainCategory.value = key
  category.value = ''
}

// หมวดหมู่ย่อยตามหมวดหลักที่เลือก (ตรงกับ backend config/categories.json)
const availableCategories = computed<Category[]>(() => {
  if (!mainCategory.value) return []
  return Object.keys(MAIN_CATEGORIES[mainCategory.value].subcategories) as Category[]
})

onMounted(async () => {
  try {
    const issue = await getIssue(issueId)

    // ตรวจสิทธิ์: ผู้แจ้ง หรือ admin
    const isReporter = !!authStore.user && issue.reporter_id === authStore.user.id
    if (!isReporter && !authStore.isAdmin) {
      Swal.fire({
        icon: 'error',
        title: 'ไม่มีสิทธิ์แก้ไข',
        text: 'เฉพาะผู้แจ้งเรื่องเท่านั้นที่แก้ไขเรื่องนี้ได้',
      })
      router.replace({ name: 'issue-detail', params: { id: issueId } })
      return
    }
    // เรื่องปิดแล้ว → แก้ไม่ได้ (backend ก็บล็อกอยู่แล้ว — UI กันไว้ก่อน)
    if (['resolved', 'cancelled', 'rejected'].includes(issue.status)) {
      Swal.fire({
        icon: 'warning',
        title: 'เรื่องนี้ปิดแล้ว',
        text: 'ไม่สามารถแก้ไขเรื่องที่ปิดแล้วได้',
      })
      router.replace({ name: 'issue-detail', params: { id: issueId } })
      return
    }

    // prefill ข้อมูลเดิม
    mainCategory.value = issue.main_category
    category.value = issue.category
    title.value = issue.title
    description.value = issue.description
    isAnonymous.value = issue.is_anonymous
  } catch (e) {
    Swal.fire({
      icon: 'error',
      title: 'ไม่สามารถโหลดเรื่องได้',
      text: errMsg(e) || 'เกิดข้อผิดพลาด',
    })
    router.replace({ name: 'issue-detail', params: { id: issueId } })
  } finally {
    isLoading.value = false
  }
})

async function handleSubmit() {
  if (!mainCategory.value) {
    Swal.fire({
      icon: 'warning',
      title: 'เลือกหมวดหลักก่อน',
      text: 'กรุณาเลือกหมวดหลัก (เสนอความคิดเห็น / สุขภาวะทางกายและใจ / แจ้งเหตุ)',
    })
    return
  }
  if (!category.value) {
    Swal.fire({ icon: 'warning', title: 'เลือกหมวดหมู่ก่อน', text: 'กรุณาเลือกหมวดหมู่ย่อย' })
    return
  }
  if (title.value.trim().length < 3) {
    Swal.fire({
      icon: 'warning',
      title: 'หัวข้อสั้นไป',
      text: 'กรุณากรอกหัวข้ออย่างน้อย 3 ตัวอักษร',
    })
    return
  }
  if (description.value.trim().length < 3) {
    Swal.fire({
      icon: 'warning',
      title: 'รายละเอียดสั้นไป',
      text: 'กรุณากรอกรายละเอียดอย่างน้อย 3 ตัวอักษร',
    })
    return
  }

  isSaving.value = true
  try {
    const updated = await updateIssue(issueId, {
      main_category: mainCategory.value,
      category: category.value,
      title: title.value.trim(),
      description: description.value.trim(),
      is_anonymous: isAnonymous.value,
    })
    Swal.fire({
      icon: 'success',
      title: 'บันทึกการแก้ไขแล้ว',
      text: 'ข้อมูลเรื่องถูกอัปเดตแล้ว',
      confirmButtonText: 'ตกลง',
    }).then(() => {
      router.push({ name: 'issue-detail', params: { id: updated.id } })
    })
  } catch (e) {
    Swal.fire({ icon: 'error', title: 'บันทึกไม่สำเร็จ', text: errMsg(e) || 'เกิดข้อผิดพลาด' })
  } finally {
    isSaving.value = false
  }
}
</script>

<template>
  <div class="max-w-2xl mx-auto">
    <div v-if="isLoading" class="flex justify-center py-16">
      <div
        class="animate-spin w-10 h-10 border-4 border-red-600 border-t-transparent rounded-full"
      ></div>
    </div>

    <template v-else>
      <h1 class="text-xl sm:text-2xl font-bold text-gray-900 mb-1 leading-tight">
        <i class="bi bi-pencil-square mr-1 text-red-500"></i> แก้ไขเรื่อง
      </h1>
      <p class="text-gray-500 text-sm mb-6">แก้ไขข้อมูลเรื่องที่แจ้งไปแล้ว (เฉพาะผู้แจ้ง)</p>

      <!-- Step 1: หมวดหลัก -->
      <div class="mb-6">
        <label class="block text-sm font-medium text-gray-700 mb-2">1. เลือกหมวดหลัก</label>
        <div class="grid grid-cols-3 gap-2 sm:gap-3">
          <button
            v-for="(info, key) in MAIN_CATEGORIES"
            :key="key"
            type="button"
            @click="selectMainCategory(key as MainCategory)"
            class="p-3 sm:p-4 min-h-[88px] sm:min-h-0 rounded-xl border-2 text-center transition flex flex-col items-center justify-center"
            :class="
              mainCategory === key
                ? 'border-red-600 bg-red-50 text-red-700'
                : 'border-gray-200 hover:border-red-300'
            "
          >
            <div class="text-xl sm:text-2xl mb-1">
              <i v-if="key === 'suggestion'" class="bi bi-lightbulb"></i>
              <i v-else-if="key === 'wellbeing'" class="bi bi-heart-pulse"></i>
              <i v-else class="bi bi-exclamation-triangle"></i>
            </div>
            <div class="text-xs sm:text-sm font-medium leading-snug break-words">
              {{ info.label }}
            </div>
          </button>
        </div>
      </div>

      <!-- Step 2: หมวดหมู่ย่อย -->
      <div v-if="mainCategory" class="mb-6">
        <label class="block text-sm font-medium text-gray-700 mb-2">2. เลือกหมวดหมู่</label>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="c in availableCategories"
            :key="c"
            type="button"
            @click="category = c"
            class="px-4 py-2 rounded-full border text-sm transition"
            :class="
              category === c
                ? 'bg-red-600 text-white border-red-600'
                : 'border-gray-300 hover:border-red-400'
            "
          >
            {{ MAIN_CATEGORIES[mainCategory as MainCategory].subcategories[c] }}
          </button>
        </div>
      </div>

      <!-- Step 3: รายละเอียด -->
      <form @submit.prevent="handleSubmit" class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">3. หัวข้อ</label>
          <input
            v-model="title"
            type="text"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500"
            placeholder="สรุปสั้นๆ ว่าเรื่องอะไร"
            maxlength="200"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">4. รายละเอียด</label>
          <textarea
            v-model="description"
            rows="5"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500"
            placeholder="อธิบายปัญหาหรือความคิดเห็นให้ละเอียด..."
          ></textarea>
        </div>

        <label class="flex items-center gap-2 text-sm text-gray-700 cursor-pointer select-none">
          <input
            v-model="isAnonymous"
            type="checkbox"
            class="w-4 h-4 rounded bg-white border-gray-300 text-red-600 focus:ring-red-500 accent-red-600"
          />
          <span>ซ่อนชื่อฉัน (แจ้งแบบไม่ระบุชื่อ)</span>
        </label>

        <div class="flex gap-3">
          <button
            type="button"
            @click="router.push({ name: 'issue-detail', params: { id: issueId } })"
            class="px-4 py-3 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 font-medium"
          >
            ยกเลิก
          </button>
          <button
            type="submit"
            :disabled="isSaving"
            class="flex-1 py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 font-medium"
          >
            {{ isSaving ? 'กำลังบันทึก...' : 'บันทึกการแก้ไข' }}
          </button>
        </div>
      </form>
    </template>
  </div>
</template>
