import { describe, it, expect, beforeEach, vi } from 'vitest';

// mock axios instance — ทดสอบเฉพาะ service layer ไม่ต้องมี backend จริง
const { getMock } = vi.hoisted(() => ({ getMock: vi.fn<() => Promise<Blob>>() }));
vi.mock('@/services/api', () => ({
  default: { get: getMock },
}));

import { downloadImportTemplate } from '@/services/student';

describe('downloadImportTemplate', () => {
  beforeEach(() => {
    getMock.mockReset();
  });

  it('เรียก GET /api/import-student-template ด้วย responseType blob (ต้องมี prefix /api)', async () => {
    const fakeXlsx = { type: 'application/octet-stream' } as Blob;
    getMock.mockResolvedValue(fakeXlsx);

    const result = await downloadImportTemplate();

    expect(getMock).toHaveBeenCalledTimes(1);
    // 🔍 path ต้องขึ้นต้น /api (บทเรียน skills.md — ลืม prefix แล้วได้ 404) + ต้องเป็น blob (ไฟล์ binary)
    expect(getMock).toHaveBeenCalledWith('/api/import-student-template', { responseType: 'blob' });
    expect(result).toBe(fakeXlsx);
  });
});
