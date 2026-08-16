// Issue / Feedback data models

export type IssueLevel = 'room' | 'level' | 'council';
export type IssueStatus = 'pending' | 'in_progress' | 'resolved' | 'escalated' | 'cancelled';

// หมวดหลัก 3 หมวด (ตรงกับ backend config/categories.json)
export type MainCategory = 'suggestion' | 'wellbeing' | 'report';
// หมวดย่อยทั้งหมด (แต่ละหมวดย่อยอยู่ใต้หมวดหลักเดียว)
export type Category =
  | 'academic'
  | 'reception'
  | 'activity'
  | 'discipline'
  | 'democracy'
  | 'physical_health'
  | 'mental_health'
  | 'complaint'
  | 'grievance';

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
  main_category: MainCategory;
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

// ===== Labels (ภาษาไทย) — ตรงกับ backend config/categories.json =====
export interface MainCategoryInfo {
  label: string;
  subcategories: Record<string, string>;
}

export const MAIN_CATEGORIES: Record<MainCategory, MainCategoryInfo> = {
  suggestion: {
    label: 'เสนอความคิดเห็น',
    subcategories: {
      academic: 'วิชาการ',
      reception: 'ปฏิคม',
      activity: 'กิจกรรม',
      discipline: 'วินัย',
      democracy: 'ประชาธิปไตย',
    },
  },
  wellbeing: {
    label: 'สุขภาวะทางกายและใจ',
    subcategories: {
      physical_health: 'สุขภาวะทางกาย',
      mental_health: 'สุขภาวะทางใจ',
    },
  },
  report: {
    label: 'แจ้งเหตุ',
    subcategories: {
      complaint: 'ร้องทุกข์',
      grievance: 'ร้องเรียน',
    },
  },
};

export const MAIN_CATEGORY_LABELS: Record<MainCategory, string> = {
  suggestion: 'เสนอความคิดเห็น',
  wellbeing: 'สุขภาวะทางกายและใจ',
  report: 'แจ้งเหตุ',
};

export function subcategoryLabel(main_category: MainCategory, category: string): string {
  return MAIN_CATEGORIES[main_category]?.subcategories[category] ?? category;
}

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
