// สถานะงาน Import นักเรียนจาก Excel (Queue) — ป้าย/สี/การตัดสินใจ
// ใช้ร่วมกันทั้งหน้า import (ตาราง Queue List + progress bar)
// Status flow: PENDING → QUEUED → PROCESSING → COMPLETED / FAILED
import type { ImportJobStatus } from '@/types/student';

export const IMPORT_STATUS_LABELS: Record<ImportJobStatus, string> = {
  PENDING: 'รอเริ่มงาน',
  QUEUED: 'รอ worker',
  PROCESSING: 'กำลังนำเข้า...',
  COMPLETED: 'เสร็จสิ้น',
  FAILED: 'ล้มเหลว',
};

export const IMPORT_STATUS_BADGES: Record<ImportJobStatus, string> = {
  PENDING: 'badge-warning',
  QUEUED: 'badge-info',
  PROCESSING: 'badge-info',
  COMPLETED: 'badge-success',
  FAILED: 'badge-error',
};

// สีหลอด progress bar (ส่วนเติม + ตัวเลขเปอร์เซ็นต์) ตามสถานะ
export const IMPORT_BAR_FILL: Record<ImportJobStatus, string> = {
  PENDING: 'bg-gray-300',
  QUEUED: 'bg-blue-400',
  PROCESSING: 'bg-red-600',
  COMPLETED: 'bg-green-500',
  FAILED: 'bg-red-400',
};

export const IMPORT_BAR_TEXT: Record<ImportJobStatus, string> = {
  PENDING: 'text-gray-500',
  QUEUED: 'text-blue-600',
  PROCESSING: 'text-red-600',
  COMPLETED: 'text-green-600',
  FAILED: 'text-red-500',
};

// งานที่กำลังทำงาน (worker ยังไม่จบ) — ใช้ตัดสินใจว่า poll ต่อไปไหม
export function isImportJobRunning(status: ImportJobStatus): boolean {
  return status === 'QUEUED' || status === 'PROCESSING';
}
