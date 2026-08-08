import api from './api';
import type { Issue } from '@/types/issue';

// Issue API

export interface CreateIssuePayload {
  topic_type: string;
  category: string;
  title: string;
  description: string;
  is_anonymous: boolean;
  room_id?: number | null;
  start_level?: string;
}

export async function listIssues(params: {
  mine?: boolean;
  received?: boolean;
  status?: string;
  category?: string;
  level?: string;
  limit?: number;
  offset?: number;
}): Promise<Issue[]> {
  const res: any = await api.get('/api/issues', { params });
  return res;
}

export async function getIssue(id: number): Promise<Issue> {
  const res: any = await api.get(`/api/issues/${id}`);
  return res;
}

export async function createIssue(payload: CreateIssuePayload): Promise<Issue> {
  const res: any = await api.post('/api/issues', payload);
  return res;
}


export async function acceptIssue(id: number, estimated_days: number): Promise<void> {
  await api.post(`/api/issues/${id}/accept`, { estimated_days });
}

export async function updateCountdown(id: number, estimated_days: number): Promise<void> {
  await api.patch(`/api/issues/${id}/countdown`, { estimated_days });
}

export async function addStep(id: number, step_title: string, step_detail?: string): Promise<any> {
  const res: any = await api.post(`/api/issues/${id}/steps`, { step_title, step_detail });
  return res;
}

export async function completeStep(id: number, stepId: number): Promise<void> {
  await api.patch(`/api/issues/${id}/steps/${stepId}/complete`);
}

export async function escalateIssue(id: number, reason?: string): Promise<void> {
  await api.post(`/api/issues/${id}/escalate`, { reason });
}

export async function resolveIssue(id: number, note?: string): Promise<void> {
  await api.post(`/api/issues/${id}/resolve`, { reason: note });
}

export async function cancelIssue(id: number, reason?: string): Promise<void> {
  await api.post(`/api/issues/${id}/cancel`, { reason });
}
