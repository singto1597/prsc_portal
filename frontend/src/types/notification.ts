// 🔔 ระบบแจ้งเตือน (Notifications) — badge ตามเมนู + หน้าแจ้งเตือนกลาง
// group_type ตรงกับ backend: badge "เรื่องของฉัน" / "เรื่องที่รับ" / PIRI Boards / จัดการรายงาน

export type NotificationGroup = 'issue_mine' | 'issue_received' | 'board' | 'report'

export interface NotificationItem {
  id: number
  group_type: NotificationGroup
  type: string // issue_new | issue_update | issue_comment | board_new | board_reply | board_hidden | report_new | report_actioned
  title: string
  body: string
  entity_type: string | null // issue | piri_board | piri_board_comment | piri_board_report
  entity_id: number | null
  board_id: number | null
  actor_id: number | null
  actor_name: string | null
  read_at: string | null // null = ยังไม่อ่าน
  created_at: string
}

export interface NotificationListResponse {
  items: NotificationItem[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface UnreadCounts {
  counts: Record<NotificationGroup, number>
  total: number
}

export interface MarkReadPayload {
  ids?: number[]
  group_type?: NotificationGroup
  entity_type?: string
  entity_id?: number
  board_id?: number
  read_all?: boolean
}

// Tab ของหน้าแจ้งเตือน — '' = ทั้งหมด
export const GROUP_TABS: Array<{ value: '' | NotificationGroup; label: string; icon: string }> = [
  { value: '', label: 'ทั้งหมด', icon: 'bi bi-list-ul' },
  { value: 'issue_mine', label: 'เรื่องของฉัน', icon: 'bi bi-file-earmark-text' },
  { value: 'issue_received', label: 'เรื่องที่รับ', icon: 'bi bi-inbox' },
  { value: 'board', label: 'PIRI Boards', icon: 'bi bi-columns-gap' },
  { value: 'report', label: 'จัดการรายงาน', icon: 'bi bi-flag-fill' },
]

// ไอคอน per type (ใช้หน้าแจ้งเตือน)
export const NOTIFICATION_TYPE_ICONS: Record<string, string> = {
  issue_new: 'bi bi-inbox',
  issue_update: 'bi bi-arrow-repeat',
  issue_comment: 'bi bi-chat-dots',
  board_new: 'bi bi-columns-gap',
  board_reply: 'bi bi-reply',
  board_hidden: 'bi bi-eye-slash',
  report_new: 'bi bi-flag-fill',
  report_actioned: 'bi bi-check2-circle',
}
