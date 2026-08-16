// Student data models (ตรงกับ backend snake_case)

export interface Student {
  id: number;
  room_id: number | null;    // admin/ครูสภา (school-wide) ไม่ผูกห้อง → null
  room_code?: string | null;
  room_name?: string | null;
  student_id: string;
  student_no: number | null; // ครู/แอดมิน ไม่มีเลขที่ → null
  prefix?: string | null;
  first_name?: string | null;
  last_name?: string | null;
  nickname?: string | null;
  class_role: string;        // ตำแหน่ง เช่น class_president, vice_academic, teacher, teacher_council, admin
  staff_level: string | null; // (ครูทั่วไป) ระดับชั้นที่รับผิดชอบ เช่น ม.4
  is_admin: boolean;
  permissions: string[];
  status: string;
}

export interface Room {
  id: number;
  room_code: string;
  room_name: string;
  level?: string | null;
  room_number?: number | null;
}
