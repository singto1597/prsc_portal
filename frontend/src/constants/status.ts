// สีสถานะ (semantic) — ใช้ร่วมกันทั้งหน้า อย่าให้สีหมวดหลักมาทับ
// pending=เหลือง, in_progress=น้ำเงิน, escalated=ส้ม, resolved=เขียว, cancelled=เทา, rejected=กุหลาบ

export const STATUS_DOT: Record<string, string> = {
  pending: 'bg-yellow-500',
  in_progress: 'bg-blue-500',
  escalated: 'bg-orange-500',
  resolved: 'bg-green-500',
  cancelled: 'bg-gray-400',
  rejected: 'bg-rose-500',
};

export const STATUS_BAR: Record<string, string> = {
  pending: 'bg-yellow-400',
  in_progress: 'bg-blue-500',
  escalated: 'bg-orange-500',
  resolved: 'bg-green-500',
  cancelled: 'bg-gray-300',
  rejected: 'bg-rose-400',
};

export const STATUS_BADGE: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-700',
  in_progress: 'bg-blue-100 text-blue-700',
  escalated: 'bg-orange-100 text-orange-700',
  resolved: 'bg-green-100 text-green-700',
  cancelled: 'bg-gray-200 text-gray-500',
  rejected: 'bg-rose-100 text-rose-700',
};

// ป้ายสั้น (สำหรับแถวรายการ/ชิป) — แยกจาก STATUS_LABELS ยาวที่ใช้ใน dropdown/filter
export const STATUS_SHORT: Record<string, string> = {
  pending: 'รอรับ',
  in_progress: 'กำลังทำ',
  escalated: 'ส่งต่อ',
  resolved: 'เสร็จแล้ว',
  cancelled: 'ยกเลิก',
  rejected: 'ปัดตก',
};

export function statusShort(status: string): string {
  return STATUS_SHORT[status] ?? status;
}
