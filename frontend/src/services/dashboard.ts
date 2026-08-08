import api from './api';

// Dashboard API

export interface CategoryStat {
  category: string;
  label: string;
  count: number;
}

export interface StatusStat {
  status: string;
  label: string;
  count: number;
}

export interface TrendPoint {
  date: string;
  count: number;
}

export interface DashboardSummary {
  total_issues: number;
  pending: number;
  in_progress: number;
  resolved: number;
  escalated: number;
  total_students: number;
  total_rooms: number;
  top_categories: CategoryStat[];
  by_status: StatusStat[];
  trend: TrendPoint[];
  usage_count: number;
  recent_logins: { actor: string; at: string }[];
}

export async function getDashboardSummary(): Promise<DashboardSummary> {
  const res: any = await api.get('/api/dashboard/summary');
  return res;
}
