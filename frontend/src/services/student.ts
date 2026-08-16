import api from './api';
import type { Student, Room, ImportJob } from '@/types/student';

// Student API

export async function listRooms(): Promise<Room[]> {
  return (await api.get('/api/rooms')) as Room[];
}

export async function listStudents(params?: { room_id?: number; search?: string }): Promise<Student[]> {
  return (await api.get('/api/students', { params })) as Student[];
}

// ===================== Import นักเรียนจาก Excel (Queue) =====================
// Flow: upload (PENDING) → start (QUEUED → worker ประมวลผล) → poll progress

export async function uploadStudentExcel(file: File, defaultPassword = '1234'): Promise<ImportJob> {
  // 1. สร้างกล่อง Form สำหรับใส่ไฟล์เท่านั้น
  const form = new FormData();
  form.append('file', file);

  // 2. ยิง API โดยแยกของ 2 อย่างให้ถูกต้องตามที่ Backend ต้องการ
  return (await api.post('/api/upload-student-excel', form, {
    // แนบไฟล์ไปใน Body พร้อมบังคับ Header
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    // แนบ default_password ไปใน URL Query
    params: {
      default_password: defaultPassword,
    },
  })) as ImportJob;
}

export async function startImportJob(jobId: number): Promise<ImportJob> {
  return (await api.post(`/api/start-import-job/${jobId}`)) as ImportJob;
}

export async function listImportJobs(): Promise<ImportJob[]> {
  return (await api.get('/api/import-jobs')) as ImportJob[];
}

export async function downloadImportTemplate(): Promise<Blob> {
  // responseType:'blob' สำคัญ — ไฟล์ .xlsx เป็น binary ถ้าไม่ตั้งจะกลายเป็น text ที่เสียหาย
  return (await api.get('/api/import-student-template', { responseType: 'blob' })) as Blob;
}

export async function updateStudent(
  studentId: number,
  data: { class_role?: string; status?: string; is_admin?: boolean; staff_level?: string | null },
): Promise<void> {
  await api.patch(`/api/students/${studentId}`, data);
}
