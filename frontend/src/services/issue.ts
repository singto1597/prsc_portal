import api from './api'
import type { Issue, IssueComment, UpdateIssuePayload } from '@/types/issue'

// Issue API

export interface CreateIssuePayload {
  main_category: string
  category: string
  title: string
  description: string
  is_anonymous: boolean
  room_id?: number | null
  start_level?: string
}

export async function listIssues(params: {
  mine?: boolean
  received?: boolean
  status?: string
  category?: string
  main_category?: string
  level?: string
  limit?: number
  offset?: number
}): Promise<Issue[]> {
  const res = (await api.get('/api/issues', { params })) as Issue[]
  return res
}

export async function getIssue(id: number): Promise<Issue> {
  const res: any = await api.get(`/api/issues/${id}`)
  return res
}

export async function createIssue(payload: CreateIssuePayload): Promise<Issue> {
  const res: any = await api.post('/api/issues', payload)
  return res
}

export async function updateIssue(id: number, payload: UpdateIssuePayload): Promise<Issue> {
  return (await api.patch(`/api/issues/${id}`, payload)) as Issue
}

export async function acceptIssue(id: number, estimated_days: number): Promise<void> {
  await api.post(`/api/issues/${id}/accept`, { estimated_days })
}

export async function updateCountdown(id: number, estimated_days: number): Promise<void> {
  await api.patch(`/api/issues/${id}/countdown`, { estimated_days })
}

export async function addStep(id: number, step_title: string, step_detail?: string): Promise<any> {
  const res: any = await api.post(`/api/issues/${id}/steps`, { step_title, step_detail })
  return res
}

export async function completeStep(id: number, stepId: number): Promise<void> {
  await api.patch(`/api/issues/${id}/steps/${stepId}/complete`)
}

export async function escalateIssue(id: number, reason?: string): Promise<void> {
  await api.post(`/api/issues/${id}/escalate`, { reason })
}

export async function resolveIssue(id: number, note?: string): Promise<void> {
  await api.post(`/api/issues/${id}/resolve`, { reason: note })
}

export async function cancelIssue(id: number, reason?: string): Promise<void> {
  await api.post(`/api/issues/${id}/cancel`, { reason })
}

// ===== คอมเมนต์ (แบบ YouTube) =====
export async function createComment(issueId: number, body: string): Promise<IssueComment> {
  return (await api.post(`/api/issues/${issueId}/comments`, { body })) as IssueComment
}

export async function updateComment(
  issueId: number,
  commentId: number,
  body: string,
): Promise<IssueComment> {
  return (await api.patch(`/api/issues/${issueId}/comments/${commentId}`, { body })) as IssueComment
}

export async function deleteComment(issueId: number, commentId: number): Promise<void> {
  await api.delete(`/api/issues/${issueId}/comments/${commentId}`)
}
