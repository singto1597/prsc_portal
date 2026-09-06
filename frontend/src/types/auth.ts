// Auth types

export interface UserRoleInfo {
  role: string | null // ตำแหน่ง เช่น class_president, teacher, teacher_council, admin
  room_id: number | null
  room_name: string | null
  student_no: number | null
  first_name: string | null // ชื่อจริง (avatar ใช้ตัวแรกของชื่อ)
  level: string | null // ระดับชั้น เช่น ม.4
  staff_level: string | null // (ครูทั่วไป) ระดับชั้นที่รับผิดชอบ เช่น ม.4
  is_admin: boolean // role นี้เป็น admin หรือไม่
  permissions: string[] // permissions ของ role นี้
  responsibilities: string[] // หมวดหน้าที่ (เฉพาะ council_member / level_vice_president)
}

export interface AuthUser {
  id: number
  username: string
  full_name: string | null
  first_name: string | null // ชื่อจริง (avatar ใช้ตัวแรกของชื่อ) — fallback full_name/username
  is_admin: boolean
  permissions: string[]
  must_change_password: boolean // บัญชี seed: บังคับเปลี่ยนรหัสครั้งแรก
  roles: UserRoleInfo[]
}
