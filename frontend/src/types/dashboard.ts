// ประเภทข้อมูล Dashboard (สถิติ + การเข้าใช้งาน)

export interface StatusStat {
  status: string;
  label: string;
  count: number;
}

export interface TrendPoint {
  date: string;
  count: number;
}

export interface RecentIssue {
  id: number;
  title: string;
  main_category: string;
  category: string;
  category_label: string;
  status: string;
  current_level: string;
  room_name: string | null;
  created_at: string;
}

export interface SubcategoryDashboard {
  category: string;
  label: string;
  description: string;
  count: number;
  by_status: StatusStat[];
}

export interface MainCategoryDashboard {
  code: string;
  label: string;
  description: string;
  total: number;
  overdue: number;
  by_status: StatusStat[];
  subcategories: SubcategoryDashboard[];
  recent_issues: RecentIssue[];
}

export interface DashboardSummary {
  scope: string; // 'all' = ทั้งโรงเรียน / 'level' = เฉพาะระดับชั้น (ครูทั่วไป) / 'none' = ครูที่ยังไม่มีระดับชั้น
  scope_label: string | null; // เช่น 'ม.4' เมื่อ scope = level
  total_issues: number;
  pending: number;
  in_progress: number;
  resolved: number;
  escalated: number;
  cancelled: number;
  rejected: number;
  overdue: number;
  total_students: number;
  total_rooms: number;
  by_status: StatusStat[];
  main_categories: MainCategoryDashboard[];
  trend: TrendPoint[];
  usage_count: number;
  recent_logins: { actor: string; at: string }[];
}

// ===== Traffic (สถิติการเข้าใช้งาน 30 วัน) =====
export interface TrafficDaily {
  date: string; // YYYY-MM-DD (Asia/Bangkok)
  count: number;
}

export interface TrafficAction {
  action: string;
  label: string;
  count: number;
}

export interface DashboardTraffic {
  daily_logins: TrafficDaily[];
  daily_actions: TrafficDaily[];
  daily_active_users: TrafficDaily[];
  action_breakdown: TrafficAction[];
  total_logins: number;
  unique_users: number;
  failed_logins: number;
}
