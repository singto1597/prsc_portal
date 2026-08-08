import api from './api';

// 👤 My Profile API

export interface MyProfile {
  id: number;
  student_id: string;
  student_no: number;
  prefix: string | null;
  first_name: string | null;
  last_name: string | null;
  nickname: string | null;
  class_role: string;
  status: string;
  room_id: number;
  room_code: string | null;
  room_name: string | null;
  level: string | null;
  username: string;
  full_name: string | null;
  phone_number: string | null;
  email: string | null;
}

export async function getMyProfile(): Promise<MyProfile> {
  const res: any = await api.get('/api/students/me/profile');
  return res;
}

export async function updateMyProfile(data: Partial<MyProfile>): Promise<MyProfile> {
  const res: any = await api.patch('/api/students/me/profile', data);
  return res;
}

export async function changePassword(old_password: string, new_password: string): Promise<void> {
  await api.post('/api/auth/change-password', { old_password, new_password });
}
