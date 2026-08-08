// Issue / Feedback data models

export type IssueLevel = 'room' | 'level' | 'council';
export type IssueStatus = 'pending' | 'in_progress' | 'resolved' | 'escalated' | 'cancelled';
export type TopicType = 'living' | 'problem' | 'suggestion';
export type Category = 'academic' | 'discipline' | 'activity' | 'reception' | 'sanitation' | 'other';

export interface IssueStep {
  id: number;
  step_title: string;
  step_detail: string | null;
  step_order: number;
  is_completed: boolean;
  completed_at: string | null;
}

export interface IssueCountdown {
  id: number;
  estimated_days: number;
  started_at: string;
  deadline: string;
  is_overdue: boolean;
}

export interface Escalation {
  id: number;
  from_level: string;
  to_level: string;
  reason: string | null;
  created_at: string;
}

export interface StatusHistory {
  id: number;
  status: string;
  note: string | null;
  created_at: string;
}

export interface Issue {
  id: number;
  room_id: number | null;
  room_name: string | null;
  topic_type: TopicType;
  category: Category;
  title: string;
  description: string;
  image_url: string | null;
  reporter_id: number | null;
  reporter_name: string | null;
  reporter_room: string | null;
  current_level: IssueLevel;
  current_assignee_id: number | null;
  current_assignee_role: string | null;
  current_assignee_name: string | null;
  status: IssueStatus;
  priority: string;
  is_anonymous: boolean;
  resolved_at: string | null;
  created_at: string;
  updated_at: string;
  steps?: IssueStep[];
  countdown?: IssueCountdown | null;
  escalations?: Escalation[];
  status_history?: StatusHistory[];
}

// ===== Labels (ภาษาไทย) =====
export const TOPIC_LABELS: Record<TopicType, string> = {
  living: 'แจ้งสภาพความเป็นอยู่',
  problem: 'แจ้งปัญหา',
  suggestion: 'ข้อเสนอแนะ',
};

export const CATEGORY_LABELS: Record<Category, string> = {
  academic: 'วิชาการ',
  discipline: 'วินัย',
  activity: 'กิจกรรม',
  reception: 'ปฏิคม',
  sanitation: 'สุขาภิบาล',
  other: 'อื่นๆ',
};

export const STATUS_LABELS: Record<string, string> = {
  pending: 'รอรับเรื่อง',
  in_progress: 'กำลังดำเนินการ',
  resolved: 'แก้ไขเสร็จ',
  escalated: 'ส่งต่อระดับบน',
  cancelled: 'ถูกยกเลิก',
};

export const LEVEL_LABELS: Record<IssueLevel, string> = {
  room: 'หัวหน้าห้อง / รองฝ่าย',
  level: 'ประธานระดับ',
  council: 'สภานักเรียน',
};
