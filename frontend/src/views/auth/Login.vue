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

// 🌟 ข้อมูลแนะนำเว็บไซต์
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

// 🔎 คำค้นหายอดนิยม
const searchKeywords = [
  'ระบบรับฟังความคิดเห็น', 'แจ้งปัญหาโรงเรียน', 'สภานักเรียน', 
  'พิริยาลัย', 'PIRIvoice', 'เสียงจากชาวพิริยาลัย'
];

// ฟังก์ชันหา Route ปลายทาง
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
  } catch (e: any) {
    Swal.fire({ icon: 'error', title: 'เข้าสู่ระบบไม่สำเร็จ', text: e.message || 'รหัสนักเรียนหรือรหัสผ่านไม่ถูกต้อง' });
  } finally {
    isLoading.value = false;
  }
}
</script>

<template>
  <div class="relative min-h-screen selection:bg-rose-500/30 selection:text-rose-900 bg-[#FAFAFC] text-slate-900 font-sans overflow-x-hidden">
    
    <!-- 🎨 พื้นหลังตกแต่ง: Premium Animated Glow -->
    <div class="absolute inset-0 pointer-events-none overflow-hidden">
      <!-- วงกลมบนขวา ลอยไปมาเบาๆ -->
      <div class="absolute -top-[10%] -right-[5%] w-[800px] h-[800px] rounded-full bg-gradient-to-b from-red-100/70 to-rose-50/20 blur-[100px] opacity-70 animate-blob"></div>
      <!-- วงกลมล่างซ้าย ลอยสลับกัน -->
      <div class="absolute top-[35%] -left-[10%] w-[600px] h-[600px] rounded-full bg-gradient-to-tr from-rose-200/40 to-transparent blur-[80px] opacity-60 animate-blob animation-delay-2000"></div>
      <!-- Pattern จุดไข่ปลาบางๆ -->
      <div class="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAiIGhlaWdodD0iMjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGNpcmNsZSBjeD0iMSIgY3k9IjEiIHI9IjEiIGZpbGw9InJnYmEoMCwgMCwgMCwgMC4wNCkiLz48L3N2Zz4=')] [mask-image:linear-gradient(to_bottom,white,transparent)] opacity-50"></div>
    </div>

    <!-- ⚡ Navbar: Minimalist -->
    <header class="relative z-20 flex items-center justify-between px-6 py-6 mx-auto max-w-7xl lg:px-8 animate-fade-in">
      <div class="flex items-center gap-3">
        <div class="flex items-center gap-2">
          <img src="/logos/school-logo.png" alt="School Logo" class="w-10 h-10 object-cover rounded-xl shadow-sm border border-slate-200/60 transition-transform duration-300 hover:scale-105" />
          <img src="/logos/council-logo.png" alt="Council Logo" class="w-10 h-10 object-cover rounded-xl shadow-sm border border-slate-200/60 transition-transform duration-300 hover:scale-105" />
        </div>
        <div class="hidden sm:block border-l border-slate-300 h-6 mx-2"></div>
        <a href="/" class="flex items-center gap-1 group">
          <span class="text-xl font-bold tracking-tight text-slate-800">PIRI<span class="font-light text-rose-600 transition-colors duration-300 group-hover:text-red-600">voice</span></span>
        </a>
      </div>
      <div class="hidden md:flex relative group">
        <!-- Glow effect ด้านหลัง Badge -->
        <div class="absolute inset-0 bg-red-400/20 blur-md rounded-full opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
        <span class="relative px-4 py-1.5 text-xs font-semibold border rounded-full text-slate-600 bg-white/70 border-slate-200/80 backdrop-blur-md shadow-sm">
          🏫 เสียงจากชาวพิริยาลัย
        </span>
      </div>
    </header>

    <main class="relative z-10">
      <!-- 🌟 Section 1: Hero & Login -->
      <section class="px-6 pt-6 pb-20 mx-auto max-w-7xl lg:px-8 lg:pt-12 lg:pb-32">
        <!-- ปรับ lg:gap-16 ให้ระยะห่างพอดี และจัด Layout กึ่งกลาง -->
        <div class="grid items-center grid-cols-1 gap-12 lg:grid-cols-2 lg:gap-16 xl:gap-24">
          
          <!-- ฝั่งซ้าย: Typography & Intro -->
          <div class="order-2 text-center lg:order-1 lg:text-left animate-slide-up-fade">
            <div class="inline-flex items-center gap-2 px-3.5 py-1.5 mb-6 text-sm font-semibold text-red-700 bg-red-50/80 border border-red-100 rounded-full shadow-sm">
              <span class="relative flex w-2 h-2">
                <span class="absolute inline-flex w-full h-full bg-red-400 rounded-full opacity-75 animate-ping"></span>
                <span class="relative inline-flex w-2 h-2 bg-red-500 rounded-full"></span>
              </span>
              ระบบรับฟังความคิดเห็น สภานักเรียน
            </div>
            
            <h1 class="text-4xl font-black tracking-tight text-slate-900 sm:text-5xl lg:text-[3.5rem] leading-[1.15]">
              ให้เสียงของทุกคน <br class="hidden lg:block" />
              <!-- ใส่ Gradient ที่มีมิติมากขึ้น -->
              <span class="text-transparent bg-clip-text bg-gradient-to-br from-red-600 via-rose-500 to-red-600 drop-shadow-sm">ไม่ถูกมองข้าม</span>
            </h1>
            
            <p class="mt-6 text-base leading-relaxed text-slate-500 sm:text-lg lg:max-w-xl font-medium">
              ส่งข้อคิดเห็น ปัญหา หรือข้อเสนอแนะ ผ่านระบบไต่ระดับตามสายงาน จากหัวหน้าห้องถึงสภานักเรียน พร้อมติดตามสถานะการแก้ไขอย่างโปร่งใส
            </p>

            <!-- Keywords Pills -->
            <div class="flex flex-wrap items-center justify-center lg:justify-start gap-2 mt-8">
              <span v-for="k in searchKeywords.slice(0, 4)" :key="k" class="px-3 py-1.5 text-[11px] font-semibold text-slate-500 hover:text-red-600 hover:border-red-200 hover:bg-red-50 transition-colors cursor-default bg-white/60 backdrop-blur-sm border border-slate-200 rounded-lg shadow-sm">
                #{{ k }}
              </span>
            </div>
          </div>

          <!-- ฝั่งขวา: Login Card (ปรับตำแหน่ง mx-auto ให้อยู่กึ่งกลาง ไม่ติดขวา) -->
          <div class="order-1 lg:order-2 animate-slide-up-fade" style="animation-delay: 100ms;">
            <div class="relative w-full max-w-[420px] mx-auto">
              <!-- การ์ดซ้อนด้านหลัง สร้างมิติที่สวยขึ้นและเรืองแสงนิดๆ -->
              <div class="absolute inset-0 transform translate-y-4 rounded-[2.5rem] bg-gradient-to-br from-rose-100/80 to-white border border-red-100/50 scale-[0.94] -z-10 shadow-2xl shadow-rose-200/50"></div>
              
              <div class="relative bg-white/90 backdrop-blur-xl border border-white shadow-[0_20px_40px_-15px_rgba(0,0,0,0.05)] rounded-[2rem] p-8 sm:p-10">
                <div class="text-center mb-8">
                  <div class="inline-flex justify-center items-center w-12 h-12 rounded-xl bg-red-50 text-red-600 mb-4 shadow-sm border border-red-100">
                    <i class="bi bi-box-arrow-in-right text-2xl"></i>
                  </div>
                  <h2 class="text-2xl font-bold tracking-tight text-slate-900">เข้าสู่ระบบ</h2>
                  <p class="mt-2 text-sm text-slate-500">กรุณากรอกข้อมูลเพื่อเข้าใช้งานระบบ</p>
                </div>

                <form @submit.prevent="handleLogin" class="space-y-5">
                  <!-- กลุ่มรหัสนักเรียน -->
                  <div class="group">
                    <label class="block text-sm font-semibold text-slate-700 mb-1.5 group-focus-within:text-red-600 transition-colors">รหัสนักเรียน</label>
                    <div class="relative">
                      <i class="bi bi-person absolute left-4 top-1/2 -translate-y-1/2 text-slate-400 text-lg group-focus-within:text-red-500 transition-colors"></i>
                      <input
                        v-model="username"
                        type="text"
                        autocomplete="username"
                        class="w-full pl-11 pr-4 py-3.5 bg-slate-50 border border-slate-200 rounded-xl focus:bg-white focus:ring-[3px] focus:ring-red-500/20 focus:border-red-500 transition-all text-sm sm:text-base outline-none shadow-sm"
                        placeholder="เช่น 41001"
                        :disabled="isLoading"
                      />
                    </div>
                  </div>

                  <!-- กลุ่มรหัสผ่าน -->
                  <div class="group">
                    <label class="block text-sm font-semibold text-slate-700 mb-1.5 group-focus-within:text-red-600 transition-colors">รหัสผ่าน</label>
                    <div class="relative">
                      <i class="bi bi-lock absolute left-4 top-1/2 -translate-y-1/2 text-slate-400 text-lg group-focus-within:text-red-500 transition-colors"></i>
                      <input
                        v-model="password"
                        :type="showPassword ? 'text' : 'password'"
                        autocomplete="current-password"
                        class="w-full pl-11 pr-12 py-3.5 bg-slate-50 border border-slate-200 rounded-xl focus:bg-white focus:ring-[3px] focus:ring-red-500/20 focus:border-red-500 transition-all text-sm sm:text-base outline-none shadow-sm"
                        placeholder="••••••••"
                        :disabled="isLoading"
                      />
                      <button
                        type="button"
                        @click="showPassword = !showPassword"
                        class="absolute right-3 top-1/2 -translate-y-1/2 w-8 h-8 flex items-center justify-center text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
                      >
                        <i :class="showPassword ? 'bi bi-eye-slash' : 'bi bi-eye'"></i>
                      </button>
                    </div>
                  </div>

                  <!-- ปุ่ม Submit แบบ Animated Gradient -->
                  <button
                    type="submit"
                    :disabled="isLoading"
                    class="relative flex items-center justify-center w-full py-3.5 mt-4 text-base font-semibold text-white transition-all bg-gradient-to-r from-red-600 via-rose-500 to-red-600 bg-[length:200%_auto] hover:bg-right rounded-xl shadow-lg shadow-red-500/30 hover:shadow-red-500/50 focus:outline-none focus:ring-2 focus:ring-red-500/50 focus:ring-offset-2 active:scale-[0.98] disabled:opacity-70 disabled:cursor-not-allowed"
                  >
                    <i v-if="!isLoading" class="bi bi-arrow-right-circle mr-2 text-lg"></i>
                    <i v-else class="bi bi-arrow-repeat animate-spin mr-2 text-lg"></i>
                    {{ isLoading ? 'กำลังตรวจสอบ...' : 'เข้าสู่ระบบเลย' }}
                  </button>
                </form>

                <!-- Note box แบบ Premium -->
                <div class="mt-6 p-4 rounded-xl border-l-4 border-l-red-500 bg-gradient-to-r from-rose-50 to-slate-50 border-y border-r border-slate-100/80 shadow-sm">
                  <div class="flex items-start gap-3">
                    <i class="bi bi-info-circle-fill text-red-500 mt-0.5"></i>
                    <p class="text-[12px] text-slate-600 leading-relaxed">
                      <strong class="text-slate-800 font-bold block mb-0.5">รหัสผ่านเริ่มต้น</strong>
                      สำหรับนักเรียนและบุคลากร รหัสผ่านตั้งต้นคือ <code class="bg-white px-1.5 py-0.5 rounded border border-red-200 text-red-600 font-mono shadow-sm">รหัสนักเรียน/บุคลากร</code> ของท่าน
                    </p>
                  </div>
                </div>

              </div>
            </div>
          </div>

        </div>
      </section>

      <!-- 🌟 Section 2: Features -->
      <section class="border-t bg-white/60 border-slate-200/50 backdrop-blur-xl relative overflow-hidden">
        <!-- วงกลมประดับพื้นหลังใน Section ฟีเจอร์ -->
        <div class="absolute bottom-0 right-0 w-[400px] h-[400px] bg-red-50/50 rounded-full blur-[80px] -z-10 translate-y-1/2"></div>
        
        <div class="px-6 py-16 mx-auto max-w-7xl lg:px-8 lg:py-24">
          
          <div class="max-w-2xl mx-auto text-center animate-slide-up-fade" style="animation-delay: 200ms;">
            <h2 class="text-2xl font-black tracking-tight text-slate-900 sm:text-3xl">ฟีเจอร์เด่นของระบบ</h2>
            <p class="mt-4 text-slate-500 font-medium">ช่วยให้การจัดการปัญหาในโรงเรียนเป็นไปอย่างเป็นระบบและตรวจสอบได้</p>
          </div>

          <div class="grid grid-cols-1 gap-6 mt-12 sm:grid-cols-2 lg:grid-cols-4 animate-slide-up-fade" style="animation-delay: 300ms;">
            <!-- Feature Cards (เพิ่ม Hover effect ให้นุ่มนวลขึ้น) -->
            <div v-for="(f, index) in introFeatures" :key="index" class="group p-6 transition-all duration-300 bg-white/80 backdrop-blur-sm border rounded-2xl border-slate-200 hover:border-red-300 hover:shadow-xl hover:shadow-red-100/50 hover:-translate-y-1.5">
              <div class="flex items-center justify-center w-12 h-12 mb-5 rounded-xl bg-slate-50 text-slate-500 group-hover:bg-red-50 group-hover:text-red-600 transition-colors duration-300 border border-slate-100 group-hover:border-red-100">
                <i :class="['bi', f.icon, 'text-xl']"></i>
              </div>
              <h3 class="text-base font-bold text-slate-900 group-hover:text-red-700 transition-colors">{{ f.title }}</h3>
              <p class="mt-2 text-sm leading-relaxed text-slate-500">{{ f.desc }}</p>
            </div>
          </div>

          <!-- Flow Steps (อัปเกรดความสวยงามของ Timeline) -->
          <div class="mt-20 pt-16 border-t border-slate-200/60 animate-slide-up-fade" style="animation-delay: 400ms;">
            <div class="text-center mb-10">
              <h3 class="text-lg font-bold text-slate-800">ขั้นตอนการทำงาน</h3>
            </div>
            <div class="flex flex-col md:flex-row justify-center items-start md:items-center gap-8 md:gap-4 max-w-4xl mx-auto">
              <template v-for="(step, idx) in flowSteps" :key="step.title">
                <div class="flex flex-col items-center text-center flex-1 w-full group">
                  <div class="relative w-16 h-16 rounded-2xl bg-white border border-slate-200 shadow-sm flex items-center justify-center text-slate-400 mb-5 z-10 transition-all duration-300 group-hover:border-rose-300 group-hover:shadow-rose-100 group-hover:text-rose-600 group-hover:-translate-y-1">
                    <i :class="['bi', step.icon, 'text-2xl']"></i>
                    <!-- ตัวเลขลำดับ (ปรับให้ดู Modern) -->
                    <span class="absolute -top-2 -right-2 w-6 h-6 bg-slate-900 text-white text-[11px] font-bold rounded-lg flex items-center justify-center shadow-md border-2 border-white group-hover:bg-rose-600 transition-colors">
                      {{ idx + 1 }}
                    </span>
                  </div>
                  <h4 class="text-sm font-bold text-slate-900">{{ step.title }}</h4>
                  <p class="text-xs text-slate-500 mt-1 max-w-[200px]">{{ step.desc }}</p>
                </div>
                <!-- เส้นเชื่อม -->
                <div v-if="idx < flowSteps.length - 1" class="hidden md:block w-20 h-[2px] bg-gradient-to-r from-slate-200 to-slate-200 mb-12"></div>
              </template>
            </div>
          </div>

        </div>
      </section>
    </main>

    <!-- Footer -->
    <footer class="py-10 text-center bg-white border-t border-slate-200/60">
      <div class="flex flex-col items-center justify-center gap-3">
        <p class="text-sm font-medium text-slate-500">
          คณะกรรมการสภานักเรียน · <span class="font-bold text-slate-700">โรงเรียนพิริยาลัยจังหวัดแพร่</span>
        </p>
        <div class="flex flex-col sm:flex-row items-center gap-2 text-xs font-medium text-slate-400">
          <span>&copy; 2026 PIRIvoice. สงวนลิขสิทธิ์</span>
          <span class="hidden sm:inline-block text-slate-300">•</span>
          <div class="flex items-center gap-1.5 mt-2 sm:mt-0">
            <span>พัฒนาโดย</span>
            <a 
              href="https://www.singto1597.xyz/" 
              target="_blank" 
              rel="noopener noreferrer"
              class="px-2.5 py-1 text-slate-600 font-semibold bg-slate-100 rounded-md border border-slate-200/60 transition-all duration-200 hover:text-red-600 hover:bg-red-50 hover:border-red-200 hover:shadow-sm"
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
</style>