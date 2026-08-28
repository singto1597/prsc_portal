// PIRI Boards (PIRI Vote + PIRI Talk) — data models
// ตรงกับ backend models/board_schemas.py

export type BoardType = 'vote' | 'talk'

// ตัวเลือกโหวต 1 อัน (มี vote_count เพื่อคำนวณ % บน frontend)
export interface VoteChoice {
  id: number
  choice_text: string
  description: string | null
  image_url: string | null
  sort_order: number
  vote_count: number
}

// คอมเมนต์ใน board — แบบ threaded (replies ซ้อนกัน; ความลึกถูกจำกัดฝั่ง service)
export interface BoardComment {
  id: number
  parent_comment_id: number | null
  user_id: number | null
  commenter_name: string | null
  body: string
  is_edited: boolean
  created_at: string
  updated_at: string | null
  replies: BoardComment[]
}

// การ์ด board ใน feed — ไม่มี pyramid visibility (ข้อมูลสาธารณะ)
export interface BoardSummary {
  id: number
  board_type: BoardType
  title: string
  description: string
  cover_image_url: string | null
  source_issue_id: number | null
  author_id: number | null
  author_name: string | null // null ถ้า board anonymous
  is_anonymous: boolean
  comment_count: number
  view_count: number
  status: string
  tags: string[]
  total_votes: number // เฉพาะ vote board (รวมทุก choice)
  created_at: string
}

// รายละเอียด board — vote: choices + my_vote; talk: comments (threaded)
export interface BoardDetail extends BoardSummary {
  allow_comments: boolean
  my_vote_choice_id: number | null // board ที่ user โหวตแล้ว (ชี้ choice_id) — ใช้ highlight ปุ่ม
  choices: VoteChoice[]
  comments: BoardComment[]
}

// feed แบบแบ่งหน้า (pattern เดียวกับ /issues)
export interface BoardListResponse {
  items: BoardSummary[]
  total: number
  page: number
  page_size: number
  pages: number
}

// ผลการโหวต (POST vote response)
export interface VoteResult {
  status: string
  vote_id: number
  board_id: number
  choice_id: number
  choice_text: string
}

export const BOARD_TYPE_LABELS: Record<BoardType, string> = {
  vote: 'โหวต',
  talk: 'พูดคุย',
}

export function boardTypeIcon(t: BoardType): string {
  return t === 'vote' ? 'bi bi-bar-chart-fill' : 'bi bi-chat-dots-fill'
}

// ===== Report (แจ้งความไม่เหมาะสม) — ตรงกับ backend piri_board_reports =====
export type ReportReason = 'bullying' | 'profanity' | 'spam' | 'privacy' | 'other'
export type ReportStatus = 'open' | 'resolved' | 'dismissed'

// รายงาน 1 รายการในคิวโมเดอเรชัน (สภา/แอดมิน)
export interface ReportItem {
  id: number
  board_id: number
  board_title: string
  comment_id: number
  comment_body: string
  reporter_id: number | null
  reporter_name: string | null
  reason: ReportReason
  detail: string | null
  status: ReportStatus
  resolved_by: number | null
  resolved_at: string | null
  resolution_note: string | null
  created_at: string
}

export interface ReportListResponse {
  items: ReportItem[]
  total: number
  page: number
  page_size: number
  pages: number
}

export const REPORT_REASONS: ReportReason[] = ['bullying', 'profanity', 'spam', 'privacy', 'other']

export const REPORT_REASON_LABELS: Record<ReportReason, string> = {
  bullying: 'กลั่นแกล้ง/คุกคาม',
  profanity: 'คำหยาบคาย',
  spam: 'สแปม/โฆษณา',
  privacy: 'เปิดเผยข้อมูลส่วนตัว',
  other: 'อื่นๆ',
}

export const REPORT_STATUS_LABELS: Record<ReportStatus, string> = {
  open: 'รอจัดการ',
  resolved: 'ซ่อนแล้ว',
  dismissed: 'ปัดตก',
}

export function reportStatusBadge(s: ReportStatus): string {
  return {
    open: 'bg-amber-100 text-amber-700',
    resolved: 'bg-emerald-100 text-emerald-700',
    dismissed: 'bg-gray-100 text-gray-600',
  }[s]
}
