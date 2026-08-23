<script setup lang="ts">
import { ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import Swal from 'sweetalert2';
import { useAuthStore } from '@/stores/auth';

const authStore = useAuthStore();
const router = useRouter();

const username = ref('');
const password = ref('');
const isLoading = ref(false);
const showPassword = ref(false);

// 🌟 ข้อมูลแนะนำเว็บไซต์ (แผงซ้าย) — โชว์ก่อนเข้าสู่ระบบ
const introFeatures = [
  { icon: 'bi-chat-square-text', title: 'แจ้งข้อคิดเห็น / ปัญหา', desc: 'นักเรียนทุกคนส่งเรื่องได้ทุกเวลา' },
  { icon: 'bi-diagram-3', title: 'ไต่ระดับตามสายงาน', desc: 'หัวหน้าห้อง → ประธานระดับ → สภานักเรียน' },
  { icon: 'bi-stopwatch', title: 'ตั้งเวลานับถอยหลัง', desc: 'ผู้รับงานตั้งเวลาแก้ปัญหาให้โปร่งใส' },
  { icon: 'bi-bar-chart-line', title: 'Dashboard สถิติ', desc: 'เห็นภาพรวมปัญหาและความคืบหน้า' },
];

// 🪜 ขั้นตอนการทำงานของระบบ
const flowSteps = [
  { icon: 'bi-pencil-square', title: 'แจ้งเรื่อง', desc: 'นักเรียนส่งข้อคิดเห็น/ปัญหาเข้าสู่ระบบ' },
  { icon: 'bi-arrow-up-right-circle', title: 'ไต่ระดับ', desc: 'ส่งต่อหัวหน้าห้อง → ระดับ → สภานักเรียน' },
  { icon: 'bi-check2-circle', title: 'ติดตามผล', desc: 'ผู้แจ้งดูสถานะปัจจุบันได้ตลอดเวลา' },
];

// 🔎 คำค้นหายอดนิยม (SEO + แนะนำผู้มาเยือน)
const searchKeywords = [
  'ระบบรับฟังความคิดเห็น',
  'แจ้งปัญหาโรงเรียน',
  'สภานักเรียน',
  'พิริยาลัย',
  'PIRIvoice',
  'Pirivoice',
  'เสียงจากชาวพิริยาลัย',
];

// นักเรียน → ไปหน้าแจ้งปัญหา, ระดับอื่น → ไปหน้าที่เหมาะสม
function homeRouteName(): string {
  if (authStore.hasPermission('VIEW_DASHBOARD')) return 'dashboard';
  if (authStore.hasPermission('RECEIVE_ISSUES')) return 'received-issues';
  return 'new-issue';
}

async function handleLogin() {
  if (!username.value || !password.value) {
    Swal.fire({ icon: 'warning', title: 'กรอกข้อมูลไม่ครบ', text: 'กรุณากรอก รหัสนักเรียน และ รหัสผ่าน' });
    return;
  }

  isLoading.value = true;
  try {
    await authStore.login(username.value.trim(), password.value);
    // บัญชีที่ระบบสร้างให้ (seed) → บังคับเปลี่ยนรหัสก่อนใช้งาน (router guard คุมอีกชั้น)
    if (authStore.mustChangePassword) {
      Swal.fire({
        icon: 'warning',
        title: 'เข้าสู่ระบบสำเร็จ',
        text: 'บัญชีนี้ต้องเปลี่ยนรหัสผ่านก่อนใช้งาน',
        timer: 1800,
        showConfirmButton: false,
      });
      router.push({ name: 'profile-password' });
      return;
    }
    Swal.fire({ icon: 'success', title: 'เข้าสู่ระบบสำเร็จ!', text: 'ยินดีต้อนรับ', timer: 1000, showConfirmButton: false });
    router.push({ name: homeRouteName() });
  } catch (e: any) {
    Swal.fire({ icon: 'error', title: 'เข้าสู่ระบบไม่สำเร็จ', text: e.message || 'ตรวจสอบรหัสนักเรียนและรหัสผ่าน' });
  } finally {
    isLoading.value = false;
  }
}
</script>

<template>
  <!-- 🌅 พื้นหลัง gradient + วงกลมตกแต่ง -->
  <div class="min-h-screen relative overflow-hidden bg-gradient-to-br from-red-50 via-white to-rose-100">
    <!-- วงกลมเบลอตกแต่งพื้นหลัง -->
    <div class="pointer-events-none absolute -top-40 -right-40 w-[500px] h-[500px] rounded-full bg-red-200/40 blur-3xl"></div>
    <div class="pointer-events-none absolute -bottom-40 -left-40 w-[500px] h-[500px] rounded-full bg-rose-200/40 blur-3xl"></div>

    <div class="relative min-h-screen w-full flex items-center justify-center p-4 sm:p-6 lg:p-10">
      <div class="w-full max-w-6xl grid lg:grid-cols-2 rounded-3xl overflow-hidden shadow-2xl bg-white/90 backdrop-blur border border-red-100/60">

        <!-- ====== ⭐ แผงแนะนำเว็บไซต์ (ซ้าย) ====== -->
        <div class="relative bg-gradient-to-br from-red-700 via-red-600 to-rose-600 text-white p-8 sm:p-10 lg:p-12">
          <!-- วงกลมตกแต่งในแผง -->
          <div class="pointer-events-none absolute -top-24 -right-24 w-72 h-72 rounded-full bg-white/10"></div>
          <div class="pointer-events-none absolute -bottom-32 -left-16 w-80 h-80 rounded-full bg-black/10"></div>

          <div class="relative">
            <!-- 🏫 โลโก้โรงเรียน + 🏛️ โลโก้สภานักเรียน -->
            <div class="flex items-center gap-4 mb-8">
              <div class="flex -space-x-3">
                <img src="/logos/school-logo.png" alt="โลโก้โรงเรียนพิริยาลัยจังหวัดแพร่"
                  class="w-16 h-16 rounded-2xl object-cover shadow-xl ring-2 ring-white/40" />
                <img src="/logos/council-logo.png" alt="โลโก้สภานักเรียนพิริยาลัย"
                  class="w-16 h-16 rounded-2xl object-cover shadow-xl ring-2 ring-white/40" />
              </div>
              <div>
                <h1 class="text-3xl font-black tracking-tight leading-none">PIRIvoice</h1>
                <p class="text-red-100 text-sm mt-1 font-medium">เสียงจากชาวพิริยาลัย</p>
              </div>
            </div>

            <!-- 📣 ข้อความแนะนำเว็บไซต์ -->
            <div class="mb-8">
              <span class="inline-block px-3 py-1 rounded-full bg-white/20 backdrop-blur text-xs font-bold tracking-wide mb-4">
                🏫 ระบบรับฟังความคิดเห็นและปัญหาสภานักเรียน
              </span>
              <h2 class="text-2xl sm:text-3xl font-bold leading-snug mb-4">
                ให้เสียงของทุกคน<br />ไม่ถูกมองข้าม
              </h2>
              <p class="text-red-50/90 leading-relaxed">
                PIRIvoice เป็นเว็บไซต์ของ<strong class="text-white">สภานักเรียน</strong> ให้ทุกคนใน
                <strong class="text-white">โรงเรียนพิริยาลัยจังหวัดแพร่</strong> ส่งข้อคิดเห็น ปัญหา หรือข้อเสนอแนะ
                แล้วระบบจะนำเรื่องไปไต่ระดับตามสายงาน เริ่มจากหัวหน้าห้องและรอง 4 ฝ่าย ขึ้นไปจนถึง
                สภานักเรียน / ประธานสภา พร้อมตั้งเวลานับถอยหลังให้ปัญหาได้รับการแก้ไขอย่างโปร่งใส
              </p>
            </div>

            <!-- ✨ จุดเด่นของระบบ -->
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-8">
              <div v-for="f in introFeatures" :key="f.title"
                class="flex items-start gap-3 bg-white/10 backdrop-blur rounded-2xl p-4 border border-white/15">
                <i :class="['bi', f.icon, 'text-xl mt-0.5']"></i>
                <div>
                  <p class="font-bold text-sm">{{ f.title }}</p>
                  <p class="text-red-100/80 text-xs mt-0.5">{{ f.desc }}</p>
                </div>
              </div>
            </div>

            <!-- 🪜 ขั้นตอนการทำงาน -->
            <div class="mb-8">
              <p class="text-xs font-bold tracking-widest text-red-100 uppercase mb-3">การทำงานของระบบ</p>
              <div class="space-y-3">
                <div v-for="(s, i) in flowSteps" :key="s.title" class="flex items-start gap-3">
                  <div class="flex flex-col items-center">
                    <span class="w-7 h-7 rounded-full bg-white text-red-600 font-black text-sm flex items-center justify-center shrink-0">{{ i + 1 }}</span>
                    <span v-if="i < flowSteps.length - 1" class="w-px flex-1 bg-white/30 my-1"></span>
                  </div>
                  <div class="pb-2">
                    <p class="font-bold text-sm flex items-center gap-1.5"><i :class="['bi', s.icon, 'text-red-100']"></i>{{ s.title }}</p>
                    <p class="text-red-100/80 text-xs mt-0.5">{{ s.desc }}</p>
                  </div>
                </div>
              </div>
            </div>

            <!-- 🔎 คีย์เวิร์ดแนะนำ -->
            <div class="mb-8">
              <p class="text-xs font-bold tracking-widest text-red-100 uppercase mb-3">ค้นหาเราได้จาก</p>
              <div class="flex flex-wrap gap-2">
                <span v-for="k in searchKeywords" :key="k"
                  class="px-3 py-1 rounded-full bg-white/10 border border-white/20 text-xs text-red-50/90 backdrop-blur">
                  #{{ k }}
                </span>
              </div>
            </div>

            <!-- 🏛️ ข้อมูลโรงเรียน -->
            <div class="pt-6 border-t border-white/20">
              <p class="text-xs text-red-100/80 leading-relaxed">
                คณะกรรมการสภานักเรียน · <span class="font-semibold text-white">โรงเรียนพิริยาลัยจังหวัดแพร่</span><br />
                <span class="text-red-100/60">151 ถ.ยันตรกิจโกศล ต.ในเวียง อ.เมือง จ.แพร่ 54000</span>
              </p>
            </div>
          </div>
        </div>

        <!-- ====== 🔐 แผงล็อกอิน (ขวา) ====== -->
        <div class="relative flex items-center justify-center p-8 sm:p-10 lg:p-12">
          <div class="w-full max-w-md">
            <!-- โลโก้บนมือถือ (ซ่อนบน desktop เพราะแผงซ้ายมีแล้ว) -->
            <div class="lg:hidden text-center mb-8">
              <div class="flex items-center justify-center gap-3 mb-3">
                <img src="/logos/school-logo.png" alt="โลโก้โรงเรียน"
                  class="w-12 h-12 rounded-full object-cover shadow-lg ring-2 ring-red-200 ring-offset-2" />
                <img src="/logos/council-logo.png" alt="โลโก้สภานักเรียน"
                  class="w-12 h-12 rounded-full object-cover shadow-lg ring-2 ring-rose-200 ring-offset-2" />
              </div>
              <h1 class="text-2xl font-bold text-gray-900 tracking-tight">PIRIvoice</h1>
              <p class="text-gray-500 mt-1 text-sm">เสียงจากชาวพิริยาลัย — เข้าสู่ระบบ</p>
            </div>

            <div class="lg:text-center">
              <h2 class="text-2xl font-bold text-gray-900 tracking-tight">ยินดีต้อนรับ 👋</h2>
              <p class="text-gray-500 mt-1 text-sm">กรอกรหัสนักเรียนและรหัสผ่านเพื่อเข้าสู่ระบบ</p>
            </div>

            <form @submit.prevent="handleLogin" class="mt-8 space-y-5">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1.5">รหัสนักเรียน</label>
                <div class="relative">
                  <i class="bi bi-person absolute left-4 top-1/2 -translate-y-1/2 text-gray-400"></i>
                  <input
                    v-model="username"
                    type="text"
                    autocomplete="username"
                    class="w-full pl-11 pr-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-red-500 focus:border-red-500 transition text-[16px]"
                    placeholder="เช่น 41001"
                    :disabled="isLoading"
                  />
                </div>
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1.5">รหัสผ่าน</label>
                <div class="relative">
                  <i class="bi bi-lock absolute left-4 top-1/2 -translate-y-1/2 text-gray-400"></i>
                  <input
                    v-model="password"
                    :type="showPassword ? 'text' : 'password'"
                    autocomplete="current-password"
                    class="w-full pl-11 pr-12 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-red-500 focus:border-red-500 transition text-[16px]"
                    placeholder="••••••••"
                    :disabled="isLoading"
                  />
                  <button
                    type="button"
                    @click="showPassword = !showPassword"
                    class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition"
                    :aria-label="showPassword ? 'ซ่อนรหัสผ่าน' : 'แสดงรหัสผ่าน'"
                  >
                    <i :class="showPassword ? 'bi bi-eye-slash' : 'bi bi-eye'"></i>
                  </button>
                </div>
              </div>

              <button
                type="submit"
                :disabled="isLoading"
                class="w-full py-3.5 bg-gradient-to-r from-red-600 to-rose-600 text-white rounded-xl hover:from-red-700 hover:to-rose-700 disabled:opacity-50 font-semibold shadow-md hover:shadow-lg transition-all"
              >
                <i class="bi bi-box-arrow-in-right mr-2"></i>
                {{ isLoading ? 'กำลังเข้าสู่ระบบ...' : 'เข้าสู่ระบบ' }}
              </button>
            </form>

            <!-- 💡 หมายเหตุสำหรับผู้ใช้ -->
            <div class="mt-8 rounded-xl bg-red-50/70 border border-red-100 p-4 text-xs text-gray-500 leading-relaxed">
              <p class="font-semibold text-red-700 mb-1">💡 สำหรับนักเรียน / บุคลากร</p>
              รหัสผ่านเริ่มต้นคือ <span class="font-mono font-semibold text-gray-700">เลขรหัสนักเรียน</span> (เช่น 41001)
              — แนะนำให้เปลี่ยนรหัสผ่านครั้งแรกที่เข้าสู่ระบบ
            </div>

            <p class="text-[11px] text-gray-400 text-center mt-8 leading-relaxed">
              พัฒนาโดย <span class="font-medium text-gray-500">นายพัฒนพล สุธรรม</span><br />
              <span class="text-gray-300">© 2026 PIRIvoice. สงวนลิขสิทธิ์</span>
            </p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
