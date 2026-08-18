<script setup lang="ts">
import { ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import Swal from 'sweetalert2';
import { createIssue } from '@/services/issue';
import { MAIN_CATEGORIES, LEVEL_LABELS, type MainCategory, type Category } from '@/types/issue';
import { useAuthStore } from '@/stores/auth';

const router = useRouter();
const authStore = useAuthStore();

const mainCategory = ref<MainCategory | ''>('');
const category = ref<Category | ''>('');
const title = ref('');
const description = ref('');
const isAnonymous = ref(false);
const startLevel = ref('room');
const isLoading = ref(false);

// ระดับของผู้ใช้ (สูงสุด) — ใช้กำหนดว่าให้เลือกระดับเริ่มต้นได้แค่ไหน
const myLevel = computed(() => {
  const roleLevels: Record<string, string> = {
    class_president: 'room', vice_academic: 'room', vice_discipline: 'room',
    vice_activity: 'room', vice_reception: 'room',
    level_president: 'level',
    council_member: 'council', council_president: 'council',
    teacher: 'council', teacher_council: 'council', admin: 'council',
  };
  let best = 'student';
  for (const r of authStore.roles) {
    const lv = roleLevels[r.role || ''] || 'student';
    const rank = { student: 0, room: 1, level: 2, council: 3 };
    if (rank[lv as keyof typeof rank] > rank[best as keyof typeof rank]) best = lv;
  }
  return best;
});

// ระดับที่ user เลือกได้ (ตั้งแต่ room ถึงระดับตัวเอง)
const selectableLevels = computed(() => {
  const all = ['room', 'level', 'council'];
  const rank = { student: 0, room: 1, level: 2, council: 3 };
  const myRank = rank[myLevel.value as keyof typeof rank] || 0;
  return all.filter((l) => rank[l as keyof typeof rank] <= myRank);
});

// หมวดหมู่ย่อยตามหมวดหลักที่เลือก (จาก MAIN_CATEGORIES — ตรงกับ backend config/categories.json)
const availableCategories = computed<Category[]>(() => {
  if (!mainCategory.value) return [];
  return Object.keys(MAIN_CATEGORIES[mainCategory.value].subcategories) as Category[];
});

async function handleSubmit() {
  if (!mainCategory.value) {
    Swal.fire({ icon: 'warning', title: 'เลือกหมวดหลักก่อน', text: 'กรุณาเลือกหมวดหลัก (เสนอความคิดเห็น / สุขภาวะทางกายและใจ / แจ้งเหตุ)' });
    return;
  }
  if (!category.value) {
    Swal.fire({ icon: 'warning', title: 'เลือกหมวดหมู่ก่อน', text: 'กรุณาเลือกหมวดหมู่ย่อย' });
    return;
  }
  if (title.value.trim().length < 3) {
    Swal.fire({ icon: 'warning', title: 'หัวข้อสั้นไป', text: 'กรุณากรอกหัวข้ออย่างน้อย 3 ตัวอักษร' });
    return;
  }
  if (description.value.trim().length < 3) {
    Swal.fire({ icon: 'warning', title: 'รายละเอียดสั้นไป', text: 'กรุณากรอกรายละเอียดอย่างน้อย 3 ตัวอักษร' });
    return;
  }

  isLoading.value = true;
  try {
    const issue = await createIssue({
      main_category: mainCategory.value,
      category: category.value,
      start_level: startLevel.value,
      title: title.value.trim(),
      description: description.value.trim(),
      is_anonymous: isAnonymous.value,
    });
    Swal.fire({
      icon: 'success',
      title: 'แจ้งเรื่องสำเร็จ!',
      html: 'เรื่องของคุณถูกส่งไปยัง<b>หัวหน้าห้อง + รองฝ่าย</b>แล้ว<br>ติดตามสถานะได้ที่ "เรื่องของฉัน"',
      confirmButtonText: 'ตกลง',
    }).then(() => {
      router.push({ name: 'issue-detail', params: { id: issue.id } });
    });
  } catch (e: any) {
    Swal.fire({ icon: 'error', title: 'แจ้งเรื่องไม่สำเร็จ', text: e.message || 'เกิดข้อผิดพลาด' });
  } finally {
    isLoading.value = false;
  }
}
</script>

<template>
  <div class="max-w-2xl mx-auto">
    <h1 class="text-xl sm:text-2xl font-bold text-gray-900 mb-1 leading-tight"><i class="bi bi-pencil-square mr-1 text-red-500"></i> แจ้งปัญหา / ความคิดเห็น</h1>
    <p class="text-gray-500 text-sm mb-6">เรื่องจะถูกส่งต่อไปยังหัวหน้าห้อง + รองฝ่าย เพื่อดำเนินการ</p>

    <!-- Step 1: หมวดหลัก -->
    <div class="mb-6">
      <label class="block text-sm font-medium text-gray-700 mb-2">1. เลือกหมวดหลัก</label>
      <div class="grid grid-cols-3 gap-2 sm:gap-3">
        <button
          v-for="(info, key) in MAIN_CATEGORIES"
          :key="key"
          type="button"
          @click="mainCategory = key as MainCategory; category = ''"
          class="p-3 sm:p-4 min-h-[88px] sm:min-h-0 rounded-xl border-2 text-center transition flex flex-col items-center justify-center"
          :class="mainCategory === key
            ? 'border-red-600 bg-red-50 text-red-700'
            : 'border-gray-200 hover:border-red-300'"
        >
          <div class="text-xl sm:text-2xl mb-1">
            <i v-if="key === 'suggestion'" class="bi bi-lightbulb"></i>
            <i v-else-if="key === 'wellbeing'" class="bi bi-heart-pulse"></i>
            <i v-else class="bi bi-exclamation-triangle"></i>
          </div>
          <div class="text-xs sm:text-sm font-medium leading-snug break-words">{{ info.label }}</div>
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
          :class="category === c
            ? 'bg-red-600 text-white border-red-600'
            : 'border-gray-300 hover:border-red-400'"
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
      <!-- ระดับเริ่มต้น (เฉพาะผู้มีระดับสูง — หัวหน้าห้อง/ประธานระดับ/สภา) -->
      <div v-if="selectableLevels.length > 1" class="bg-gray-50 rounded-lg p-3">
        <label class="block text-sm font-medium text-gray-700 mb-2">ระดับเริ่มต้นของเรื่อง</label>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="lv in selectableLevels"
            :key="lv"
            type="button"
            @click="startLevel = lv"
            class="px-3 py-1.5 rounded-full border text-sm transition"
            :class="startLevel === lv
              ? 'bg-red-600 text-white border-red-600'
              : 'border-gray-300 hover:border-red-400'"
          >
            {{ LEVEL_LABELS[lv as keyof typeof LEVEL_LABELS] }}
          </button>
        </div>
        <p class="text-xs text-gray-400 mt-1.5">เลือกเริ่มที่ระดับสูงขึ้นได้เลย ไม่ต้องแจ้งแล้วส่งต่อทีหลัง</p>
      </div>

      <label class="flex items-center gap-2 text-sm text-gray-700 cursor-pointer select-none">
        <input v-model="isAnonymous" type="checkbox"
          class="w-4 h-4 rounded bg-white border-gray-300 text-red-600 focus:ring-red-500 accent-red-600" />
        <span>ซ่อนชื่อฉัน (แจ้งแบบไม่ระบุชื่อ)</span>
      </label>
      <button
        type="submit"
        :disabled="isLoading"
        class="w-full py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 font-medium"
      >
        {{ isLoading ? 'กำลังส่ง...' : 'ส่งเรื่อง' }}
      </button>
    </form>
  </div>
</template>
