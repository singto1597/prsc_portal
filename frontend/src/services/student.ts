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
  // 1. สร้างกล่อง Form สำหรับใส่ไฟล์เท่านั้น
  const form = new FormData();
  form.append('file', file);

  // 2. ยิง API โดยแยกของ 2 อย่างให้ถูกต้องตามที่ Backend ต้องการ
  const res: any = await api.post('/api/students/import', form, {
    // แนบไฟล์ไปใน Body พร้อมบังคับ Header
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    // แนบ default_password ไปใน URL Query
    params: {
      default_password: default_password,
    },
  });
  
  return res;
}

export async function updateStudent(
  studentId: number,
  data: { class_role?: string; status?: string; is_admin?: boolean },
): Promise<void> {
  await api.patch(`/api/students/${studentId}`, data);
}
