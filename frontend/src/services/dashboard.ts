import api from './api';
import type {
  DashboardSummary,
  DashboardTraffic,
  MainCategoryDashboard,
  RecentIssue,
  StatusStat,
  SubcategoryDashboard,
  TrafficAction,
  TrafficDaily,
  TrendPoint,
} from '@/types/dashboard';

// Re-export ประเภทข้อมูล (ให้โค้ดเก่าที่ import จาก service ยังทำงานได้)
export type {
  DashboardSummary,
  DashboardTraffic,
  MainCategoryDashboard,
  RecentIssue,
  StatusStat,
  SubcategoryDashboard,
  TrafficAction,
  TrafficDaily,
  TrendPoint,
};

// Dashboard API — สถิติกลุ่มตาม 3 หมวดหลัก (suggestion / wellbeing / report)

export async function getDashboardSummary(): Promise<DashboardSummary> {
  const res = (await api.get('/api/dashboard/summary')) as DashboardSummary;
  return res;
}

// 📊 สถิติการเข้าใช้งาน (30 วัน) — เฉพาะบทบาทระดับโรงเรียน
export async function getDashboardTraffic(): Promise<DashboardTraffic> {
  const res = (await api.get('/api/dashboard/traffic')) as DashboardTraffic;
  return res;
}
