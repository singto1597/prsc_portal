// Auth types

export interface UserRoleInfo {
  role: string | null;
  room_id: number | null;
  room_name: string | null;
  student_no: number | null;
  level: string | null;
}

export interface AuthUser {
  id: number;
  username: string;
  full_name: string | null;
  is_admin: boolean;
  permissions: string[];
  roles: UserRoleInfo[];
}
