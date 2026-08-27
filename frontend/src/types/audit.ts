// ประเภทข้อมูล Audit Log (บันทึกการใช้งาน)

export interface AuditLogEntry {
  id: string;
  trace_id: string | null;
  user_id: number | null;
  actor_identifier: string;
  client_source: string;
  service_name: string;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  status: string; // success / error / partial
  error_detail: string | null;
  old_values: Record<string, unknown> | null;
  new_values: Record<string, unknown> | null;
  endpoint_or_command: string | null;
  ip_address: string | null;
  user_agent: string | null;
  execution_time_ms: number | null;
  created_at: string;
}

export interface AuditLogListResponse {
  items: AuditLogEntry[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface AuditLogFilters {
  action?: string;
  entity_type?: string;
  status?: string;
  q?: string;
  date_from?: string; // YYYY-MM-DD
  date_to?: string; // YYYY-MM-DD
}
