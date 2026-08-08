import api from './api';
import type { AuthUser } from '@/types/auth';

// Auth API — login, me
export async function login(username: string, password: string): Promise<{ access_token: string; user: AuthUser }> {
  const res: any = await api.post('/api/auth/login', { username, password });
  return res;
}

export async function fetchMe(): Promise<AuthUser> {
  const res: any = await api.get('/api/auth/me');
  return res;
}
