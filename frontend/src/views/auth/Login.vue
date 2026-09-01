<!-- eslint-disable vue/multi-word-component-names -- ชื่อ Login ตาม spec (หน้าล็อกอิน) -->
<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import Swal from 'sweetalert2';
import { useAuthStore } from '@/stores/auth';

const authStore = useAuthStore();
const router = useRouter();

const username = ref('');
const password = ref('');
const isLoading = ref(false);
const showPassword = ref(false);

// ฟังก์ชันหา Route ปลายทางหลัง login
function homeRouteName(): string {
  if (authStore.hasPermission('VIEW_DASHBOARD')) return 'dashboard';
  if (authStore.hasPermission('RECEIVE_ISSUES')) return 'received-issues';
  return 'new-issue';
}

async function handleLogin() {
  if (!username.value || !password.value) {
    Swal.fire({ icon: 'warning', title: 'ข้อมูลไม่ครบถ้วน', text: 'กรุณากรอกรหัสนักเรียนและรหัสผ่าน' });
    return;
  }

  isLoading.value = true;
  try {
    await authStore.login(username.value.trim(), password.value);

    if (authStore.mustChangePassword) {
      Swal.fire({
        icon: 'info',
        title: 'ตั้งรหัสผ่านใหม่',
        text: 'เพื่อความปลอดภัย บัญชีนี้ต้องเปลี่ยนรหัสผ่านก่อนใช้งาน',
        timer: 2000,
        showConfirmButton: false,
      });
      router.push({ name: 'profile-password' });
      return;
    }

    Swal.fire({ icon: 'success', title: 'เข้าสู่ระบบสำเร็จ!', text: 'ยินดีต้อนรับสู่ PIRIvoice', timer: 1200, showConfirmButton: false });
    router.push({ name: homeRouteName() });
  } catch (e) {
    const msg =
      typeof e === 'string'
        ? e
        : e instanceof Error
          ? e.message
          : 'รหัสนักเรียนหรือรหัสผ่านไม่ถูกต้อง';
    Swal.fire({ icon: 'error', title: 'เข้าสู่ระบบไม่สำเร็จ', text: msg });
  } finally {
    isLoading.value = false;
  }
}
</script>

<template>
  <div class="relative flex min-h-screen flex-col overflow-x-clip bg-[#FAFAFC] font-sans text-slate-900 selection:bg-rose-500/30 selection:text-rose-900">
    <!-- 🎨 พื้นหลังตกแต่ง: Premium Animated Glow -->
    <div class="pointer-events-none absolute inset-0 overflow-hidden">
      <div class="animate-blob absolute -right-[5%] -top-[10%] h-[800px] w-[800px] rounded-full bg-gradient-to-b from-red-100/70 to-rose-50/20 opacity-70 blur-[100px]"></div>
      <div class="animate-blob animation-delay-2000 absolute -left-[10%] top-[35%] h-[600px] w-[600px] rounded-full bg-gradient-to-tr from-rose-200/40 to-transparent opacity-60 blur-[80px]"></div>
      <div
        class="absolute inset-0 opacity-50 [mask-image:linear-gradient(to_bottom,white,transparent)] [background-image:url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAiIGhlaWdodD0iMjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8vMjAwMC9zdmciPjxjaXJjbGUgY3g9IjEiIGN5PSIxIiByPSIxIiBmaWxsPSJyZ2JhKDAsIDAsIDAsIDAuMDQpIi8+PC9zdmc+')]"
      ></div>
    </div>

    <!-- ⚡ Navbar: Minimalist -->
    <header class="relative z-20 mx-auto flex w-full max-w-7xl items-center justify-between px-6 py-6 lg:px-8 animate-fade-in">
      <div class="flex items-center gap-3">
        <div class="flex items-center gap-2">
          <div class="flex h-10 w-10 items-center justify-center rounded-xl border border-slate-200/60 bg-white p-1 shadow-sm transition-transform duration-300 hover:scale-105">
            <img src="/logos/school-logo.png" alt="โลโก้โรงเรียน" class="h-full w-full object-contain" />
          </div>
          <div class="flex h-10 w-10 items-center justify-center rounded-xl border border-slate-200/60 bg-white p-1 shadow-sm transition-transform duration-300 hover:scale-105">
            <img src="/logos/council-logo.png" alt="โลโก้สภานักเรียน" class="h-full w-full object-contain" />
          </div>
        </div>
        <div class="mx-2 hidden h-6 border-l border-slate-300 sm:block"></div>
        <router-link to="/" class="group flex items-center gap-1">
          <span class="text-xl font-black tracking-tight text-slate-800">
            PIRI<span class="bg-gradient-to-r from-red-600 to-rose-600 bg-clip-text text-transparent">voice</span>
          </span>
        </router-link>
      </div>
      <div class="hidden md:flex relative group">
        <div class="absolute inset-0 rounded-full bg-red-400/20 opacity-0 blur-md transition-opacity duration-500 group-hover:opacity-100"></div>
        <span class="relative rounded-full border border-slate-200/80 bg-white/70 px-4 py-1.5 text-xs font-semibold text-slate-600 shadow-sm backdrop-blur-md">
          🏫 เสียงจากชาวพิริยาลัย
        </span>
      </div>
    </header>

    <!-- 🔐 ส่วนกลาง: เฉพาะการเข้าสู่ระบบ -->
    <main class="relative z-10 flex flex-1 items-center justify-center px-6 py-10">
      <div class="w-full max-w-[420px] animate-slide-up-fade">
        <!-- การ์ดซ้อนด้านหลัง -->
        <div class="absolute inset-0 -z-10 -translate-y-4 scale-[0.94] rounded-[2.5rem] border border-red-100/50 bg-gradient-to-br from-rose-100/80 to-white shadow-2xl shadow-rose-200/50"></div>

        <div class="relative rounded-[2rem] border border-white bg-white/90 p-8 shadow-[0_20px_40px_-15px_rgba(0,0,0,0.05)] backdrop-blur-xl sm:p-10">
          <div class="mb-8 text-center">
            <!-- โลโก้ทั้ง 2 -->
            <div class="mb-5 flex items-center justify-center gap-4">
              <div class="relative flex h-16 w-16 items-center justify-center rounded-full bg-white p-1.5 shadow-lg ring-2 ring-red-100 ring-offset-2">
                <img src="/logos/school-logo.png" alt="โลโก้โรงเรียน" class="relative h-full w-full object-contain" />
              </div>
              <div class="relative flex h-16 w-16 items-center justify-center rounded-full bg-white p-1.5 shadow-lg ring-2 ring-rose-100 ring-offset-2">
                <img src="/logos/council-logo.png" alt="โลโก้สภานักเรียน" class="relative h-full w-full object-contain" />
              </div>
            </div>

            <h2 class="text-2xl font-black tracking-tight text-slate-900">เข้าสู่ระบบ</h2>
            <p class="mt-2 text-sm font-medium text-slate-500">กรุณากรอกข้อมูลเพื่อเข้าใช้งานระบบ</p>
          </div>

          <form @submit.prevent="handleLogin" class="space-y-5">
            <!-- กลุ่มรหัสนักเรียน -->
            <div class="group">
              <label class="mb-1.5 block text-sm font-semibold text-slate-700 transition-colors group-focus-within:text-red-600">รหัสนักเรียน</label>
              <div class="relative">
                <i class="bi bi-person absolute left-4 top-1/2 -translate-y-1/2 text-lg text-slate-400 transition-colors group-focus-within:text-red-500"></i>
                <input
                  v-model="username"
                  type="text"
                  autocomplete="username"
                  class="w-full rounded-xl border border-slate-200 bg-slate-50 py-3.5 pl-11 pr-4 text-sm shadow-sm outline-none transition-all focus:border-red-500 focus:bg-white focus:ring-[3px] focus:ring-red-500/20 sm:text-base"
                  placeholder="เช่น 41001"
                  :disabled="isLoading"
                />
              </div>
            </div>

            <!-- กลุ่มรหัสผ่าน -->
            <div class="group">
              <label class="mb-1.5 block text-sm font-semibold text-slate-700 transition-colors group-focus-within:text-red-600">รหัสผ่าน</label>
              <div class="relative">
                <i class="bi bi-lock absolute left-4 top-1/2 -translate-y-1/2 text-lg text-slate-400 transition-colors group-focus-within:text-red-500"></i>
                <input
                  v-model="password"
                  :type="showPassword ? 'text' : 'password'"
                  autocomplete="current-password"
                  class="w-full rounded-xl border border-slate-200 bg-slate-50 py-3.5 pl-11 pr-12 text-sm shadow-sm outline-none transition-all focus:border-red-500 focus:bg-white focus:ring-[3px] focus:ring-red-500/20 sm:text-base"
                  placeholder="••••••••"
                  :disabled="isLoading"
                />
                <button
                  type="button"
                  @click="showPassword = !showPassword"
                  class="absolute right-3 top-1/2 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"
                  :aria-label="showPassword ? 'ซ่อนรหัสผ่าน' : 'แสดงรหัสผ่าน'"
                >
                  <i :class="showPassword ? 'bi bi-eye-slash' : 'bi bi-eye'"></i>
                </button>
              </div>
            </div>

            <!-- ปุ่ม Submit แบบ Animated Gradient -->
            <button
              type="submit"
              :disabled="isLoading"
              class="relative mt-4 flex w-full items-center justify-center rounded-xl bg-gradient-to-r from-red-600 via-rose-500 to-red-600 bg-[length:200%_auto] py-3.5 text-base font-bold text-white shadow-lg shadow-red-500/30 transition-all hover:bg-right hover:shadow-red-500/50 focus:outline-none focus:ring-2 focus:ring-red-500/50 focus:ring-offset-2 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-70"
            >
              <i v-if="!isLoading" class="bi bi-arrow-right-circle mr-2 text-lg"></i>
              <i v-else class="bi bi-arrow-repeat mr-2 animate-spin text-lg"></i>
              {{ isLoading ? 'กำลังตรวจสอบ...' : 'เข้าสู่ระบบเลย' }}
            </button>
          </form>

          <!-- Note box: รหัสผ่านเริ่มต้น -->
          <div class="mt-6 rounded-xl border-y border-r border-slate-100/80 border-l-4 border-l-red-500 bg-gradient-to-r from-rose-50 to-slate-50 p-4 shadow-sm">
            <div class="flex items-start gap-3">
              <i class="bi bi-info-circle-fill mt-0.5 text-red-500"></i>
              <p class="text-[12px] leading-relaxed text-slate-600">
                <strong class="mb-0.5 block font-bold text-slate-800">รหัสผ่านเริ่มต้น</strong>
                สำหรับนักเรียนและบุคลากร รหัสผ่านตั้งต้นคือ
                <code class="rounded border border-red-200 bg-white px-1.5 py-0.5 font-mono text-red-600 shadow-sm">รหัสนักเรียน/บุคลากร</code>
                ของท่าน
              </p>
            </div>
          </div>
        </div>
      </div>
    </main>

    <!-- Footer -->
    <footer class="relative z-10 border-t border-slate-200/60 bg-white py-8 text-center">
      <div class="flex flex-col items-center justify-center gap-2">
        <p class="text-sm font-medium text-slate-500">
          คณะกรรมการสภานักเรียน · <span class="font-bold text-slate-700">โรงเรียนพิริยาลัยจังหวัดแพร่</span>
        </p>
        <div class="flex flex-col items-center gap-2 text-xs font-medium text-slate-400 sm:flex-row">
          <span>© 2026 PIRIvoice. สงวนลิขสิทธิ์</span>
          <span class="hidden text-slate-300 sm:inline-block">•</span>
          <div class="flex items-center gap-1.5">
            <span>พัฒนาโดย</span>
            <a
              href="https://www.singto1597.xyz/"
              target="_blank"
              rel="noopener noreferrer"
              class="rounded-md border border-slate-200/60 bg-slate-100 px-2.5 py-1 font-semibold text-slate-600 transition-all duration-200 hover:border-red-200 hover:bg-red-50 hover:text-red-600 hover:shadow-sm"
            >
              นายพัฒนพล สุธรรม
            </a>
          </div>
        </div>
      </div>
    </footer>
  </div>
</template>

<style scoped>
/* Animations ที่ดูเป็นธรรมชาติแบบงาน Premium */
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slideUpFade {
  from {
    opacity: 0;
    transform: translateY(20px) scale(0.98);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

/* อนิเมชันทำให้พื้นหลังขยับสไลด์ไปมาเบาๆ */
@keyframes blob {
  0% { transform: translate(0px, 0px) scale(1); }
  33% { transform: translate(30px, -50px) scale(1.05); }
  66% { transform: translate(-20px, 20px) scale(0.95); }
  100% { transform: translate(0px, 0px) scale(1); }
}

.animate-fade-in {
  animation: fadeIn 0.8s ease-out forwards;
}

.animate-slide-up-fade {
  opacity: 0;
  animation: slideUpFade 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}

.animate-blob {
  animation: blob 15s infinite alternate ease-in-out;
}

.animation-delay-2000 {
  animation-delay: 2s;
}

/* ลบลูกศรใน input type number */
input[type="number"]::-webkit-inner-spin-button,
input[type="number"]::-webkit-outer-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

/* 🔤 Keyboard focus ตามธีม */
input:focus-visible,
button:focus-visible,
a:focus-visible {
  outline: 2px solid rgba(225, 29, 72, 0.65);
  outline-offset: 2px;
}

/* ♿ เคารพผู้ที่ปิดแอนิเมชัน */
@media (prefers-reduced-motion: reduce) {
  .animate-blob,
  .animate-slide-up-fade,
  .animate-fade-in {
    animation: none !important;
  }
  .animate-slide-up-fade,
  .animate-fade-in {
    opacity: 1 !important;
  }
}
</style>
