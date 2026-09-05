/** @type {import('tailwindcss').Config} */
import daisyui from 'daisyui';

export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        // ฟอนต์หลัก 'Noto Sans Thai' (รองรับภาษาไทย) — fallback เป็น sans-serif เสมอ
        // กัน Google Fonts โหลดไม่ทัน/โดน block แล้วหลุดไปเป็น serif
        sans: ['"Noto Sans Thai"', 'sans-serif'],
        // พาดหัว/Display 'Anuphan' (จับคู่กับ Landing) — ใช้กับ headline/ตัวเลขใหญ่
        display: ['"Anuphan"', '"Noto Sans Thai"', 'sans-serif'],
      },
    },
  },
  plugins: [
    daisyui,
  ],
  daisyui: {
    themes: false, // false = ใช้ default theme ไปก่อน (ปรับทีหลังได้)
  },
}
