import { createRouter, createWebHistory } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import MainLayout from '@/layouts/MainLayout.vue';

/**
 * หน้าแรกหลัง login ตามบทบาท:
 * - นักเรียน (ไม่มีสิทธิ์รับเรื่อง): ไปหน้า "แจ้งปัญหา" ทันที (ภารกิจหลัก)
 * - ผู้มี Dashboard: ไปแดชบอร์ด
 * - ระดับอื่น (หัวหน้าห้อง/ประธานระดับ/สภา): ไป "เรื่องที่รับ"
 */
function getHomeRoute(): { name: string } {
  const auth = useAuthStore();
  if (auth.hasPermission('VIEW_DASHBOARD')) return { name: 'dashboard' };
  if (auth.hasPermission('RECEIVE_ISSUES')) return { name: 'received-issues' };
  return { name: 'new-issue' }; // นักเรียน → แจ้งปัญหาก่อน
}

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/auth/Login.vue'),
      meta: { requiresAuth: false }
    },
    {
      path: '/',
      component: MainLayout,
      meta: { requiresAuth: true },
      redirect: () => getHomeRoute(),
      children: [
        {
          path: 'dashboard',
          name: 'dashboard',
          component: () => import('@/views/Dashboard.vue'),
          meta: { requiresAuth: true, requiresPermission: 'VIEW_DASHBOARD' },
        },
        {
          path: 'profile',
          name: 'profile',
          component: () => import('@/views/Profile.vue'),
        },
        {
          path: 'issues/new',
          name: 'new-issue',
          component: () => import('@/views/issues/NewIssue.vue'),
        },
        {
          path: 'issues/mine',
          name: 'my-issues',
          component: () => import('@/views/issues/MyIssues.vue'),
        },
        {
          path: 'issues/received',
          name: 'received-issues',
          component: () => import('@/views/issues/ReceivedIssues.vue'),
        },
        {
          path: 'issues/:id',
          name: 'issue-detail',
          component: () => import('@/views/issues/IssueDetail.vue'),
        },
        {
          path: 'students',
          name: 'students',
          component: () => import('@/views/students/StudentList.vue'),
          meta: { requiresAuth: true, requiresPermission: 'MANAGE_STUDENTS' },
        },
        {
          path: 'students/import',
          name: 'import-students',
          component: () => import('@/views/students/ImportStudents.vue'),
          meta: { requiresAuth: true, requiresPermission: 'MANAGE_STUDENTS' },
        },
      ]
    }
  ],
});

router.beforeEach(async (to) => {
  const authStore = useAuthStore();
  const isAuthenticated = authStore.isAuthenticated;

  if (to.meta.requiresAuth && !isAuthenticated) {
    return { name: 'login' };
  }
  if (to.path === '/login' && isAuthenticated) {
    return { name: 'dashboard' };
  }

  // ตรวจ permission ถ้า route ต้องการ (ต้อง load user ก่อน)
  const needPermission = to.meta.requiresPermission as string | undefined;
  if (needPermission && isAuthenticated) {
    if (!authStore.user) {
      try { await authStore.loadMe(); } catch { /* ignore */ }
    }
    if (!authStore.hasPermission(needPermission)) {
      // ไม่มีสิทธิ์ → ไปหน้าแรกที่เข้าได้ตามบทบาท
      return getHomeRoute();
    }
  }

  return true;
});

export default router;
