import api from './api';
import type { AuditLogListResponse, AuditLogFilters } from '@/types/audit';

// Audit Log API — ดูประวัติการใช้งาน (ต้องมีสิทธิ์ VIEW_AUDIT_LOG)

export interface ListAuditLogParams extends AuditLogFilters {
  limit?: number;
  offset?: number;
}

export async function listAuditLogs(params: ListAuditLogParams = {}): Promise<AuditLogListResponse> {
  const { action, entity_type, status, q, date_from, date_to, limit, offset } = params;
  const res = (await api.get('/api/audit-logs', {
    params: {
      action: action || undefined,
      entity_type: entity_type || undefined,
      status: status || undefined,
      q: q || undefined,
      date_from: date_from || undefined,
      date_to: date_to || undefined,
      limit: limit ?? 20,
      offset: offset ?? 0,
    },
  })) as AuditLogListResponse;
  return res;
}
