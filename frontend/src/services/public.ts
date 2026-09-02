import api from './api'

// Public API (prefix /api/v1) — ประกาศโรงเรียน หน้า Home/Welcome
// (Landing เรียกตรงผ่าน api instance — เก็บไว้ที่ service ให้ authed views ใช้ตามกฎ)

export type AnnouncementPriority = 'normal' | 'high' | 'urgent'

export interface Announcement {
  id: number
  message: string
  priority: AnnouncementPriority
  link?: string | null
}

export async function listPublicAnnouncements(): Promise<Announcement[]> {
  return (await api.get('/api/v1/public/announcements')) as Announcement[]
}
