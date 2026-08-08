import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import api from '@/services/api';
import * as authService from '@/services/auth';
import type { AuthUser } from '@/types/auth';

// จัดการ Session/Auth state

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref<string | null>(localStorage.getItem('access_token'));
  const user = ref<AuthUser | null>(null);

  const isAuthenticated = computed(() => !!accessToken.value);

  // ชื่อย่อ/สิทธิ์
  const displayName = computed(() => user.value?.full_name || user.value?.username || '');
  const roles = computed(() => user.value?.roles || []);
  const isAdmin = computed(() => user.value?.is_admin ?? false);
  const permissions = computed(() => user.value?.permissions || []);

  function setToken(token: string) {
    accessToken.value = token;
    localStorage.setItem('access_token', token);
  }

  function setUser(u: AuthUser) {
    user.value = u;
    localStorage.setItem('user_id_str', String(u.id));
  }

  async function login(username: string, password: string): Promise<AuthUser> {
    const res = await authService.login(username, password);
    setToken(res.access_token);
    setUser(res.user);
    return res.user;
  }

  async function loadMe() {
    if (!accessToken.value) return null;
    const me = await authService.fetchMe();
    setUser(me);
    return me;
  }

  function hasPermission(perm: string): boolean {
    if (isAdmin.value) return true;
    return permissions.value.includes(perm);
  }

  function logout() {
    accessToken.value = null;
    user.value = null;
    localStorage.removeItem('access_token');
    localStorage.removeItem('user_id_str');
  }

  return {
    accessToken,
    user,
    isAuthenticated,
    displayName,
    roles,
    isAdmin,
    permissions,
    setToken,
    setUser,
    login,
    loadMe,
    hasPermission,
    logout,
  };
});
