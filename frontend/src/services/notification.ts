import api from './api'
import type {
  NotificationGroup,
  NotificationListResponse,
  UnreadCounts,
  MarkReadPayload,
} from '@/types/notification'

// 🔔 Notification API — api interceptor unwrap response.data แล้ว (ดู services/api.ts)

export async function listNotifications(params: {
  group_type?: NotificationGroup
  unread_only?: boolean
  limit?: number
  offset?: number
} = {}): Promise<NotificationListResponse> {
  return (await api.get('/api/notifications', {
    params: {
      group_type: params.group_type || undefined,
      unread_only: params.unread_only || undefined,
      limit: params.limit ?? 50,
      offset: params.offset ?? 0,
    },
  })) as NotificationListResponse
}

export async function getUnreadCounts(): Promise<UnreadCounts> {
  return (await api.get('/api/notifications/unread-count')) as UnreadCounts
}

export async function markRead(payload: MarkReadPayload): Promise<{ updated: number }> {
  return (await api.post('/api/notifications/read', payload)) as { updated: number }
}
