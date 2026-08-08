import api from './api';
import type { Student, Room } from '@/types/student';

// Student API

export async function listRooms(): Promise<Room[]> {
  const res: any = await api.get('/api/rooms');
  return res;
}

export async function listStudents(params?: { room_id?: number; search?: string }): Promise<Student[]> {
  const res: any = await api.get('/api/students', { params });
  return res;
}

export async function importStudents(file: File, default_password = '1234'): Promise<{
  total_rows: number;
  imported: number;
  skipped: number;
  errors: string[];
}> {
  const form = new FormData();
  form.append('file', file);
  form.append('default_password', default_password);
  const res: any = await api.post('/api/students/import', form);
  return res;
}

export async function updateStudent(
  studentId: number,
  data: { class_role?: string; status?: string; is_admin?: boolean },
): Promise<void> {
  await api.patch(`/api/students/${studentId}`, data);
}
