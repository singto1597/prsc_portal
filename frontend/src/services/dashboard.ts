import api from './api';

// Dashboard API — สถิติกลุ่มตาม 3 หมวดหลัก (suggestion / wellbeing / report)

export interface StatusStat {
  status: string;
  label: string;
  count: number;
}

export interface CategoryStat {
  category: string;
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

export interface MainCategoryDashboard {
  code: string;
  label: string;
  total: number;
  by_status: StatusStat[];
  top_subcategories: CategoryStat[];
  recent_issues: RecentIssue[];
}

export interface DashboardSummary {
  scope: string;              // 'all' = ทั้งโรงเรียน / 'level' = เฉพาะระดับชั้น (ครูทั่วไป) / 'none' = ครูที่ยังไม่มีระดับชั้น
  scope_label: string | null; // เช่น 'ม.4' เมื่อ scope = level
  total_issues: number;
  pending: number;
  in_progress: number;
  resolved: number;
  escalated: number;
  cancelled: number;
  overdue: number;
  total_students: number;
  total_rooms: number;
  by_status: StatusStat[];
  main_categories: MainCategoryDashboard[];
  trend: TrendPoint[];
  usage_count: number;
  recent_logins: { actor: string; at: string }[];
}

export async function getDashboardSummary(): Promise<DashboardSummary> {
  const res = (await api.get('/api/dashboard/summary')) as DashboardSummary;
  return res;
}
