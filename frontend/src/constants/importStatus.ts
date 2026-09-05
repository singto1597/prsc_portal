// สถานะงาน Import นักเรียนจาก Excel (Queue) — คำอธิบาย + การตัดสินใจ poll
// (สี/ป้ายสถานะย้ายไปอยู่ที่หน้านั้นแล้ว ตาม Civic palette — อย่าใส่สีย้อนกลับมาที่นี่)
// Status flow: PENDING → QUEUED → PROCESSING → COMPLETED / FAILED
import type { ImportJobStatus } from '@/types/student';

export const IMPORT_STATUS_LABELS: Record<ImportJobStatus, string> = {
  PENDING: 'รอเริ่มงาน',
  QUEUED: 'รอ worker',
  PROCESSING: 'กำลังนำเข้า...',
  COMPLETED: 'เสร็จสิ้น',
  FAILED: 'ล้มเหลว',
};

// งานที่กำลังทำงาน (worker ยังไม่จบ) — ใช้ตัดสินใจว่า poll ต่อไปไหม
export function isImportJobRunning(status: ImportJobStatus): boolean {
  return status === 'QUEUED' || status === 'PROCESSING';
}
