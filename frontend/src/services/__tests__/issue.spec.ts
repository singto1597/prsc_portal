import { describe, it, expect, beforeEach, vi } from 'vitest'

// mock axios instance — ทดสอบเฉพาะ service layer ไม่ต้องมี backend จริง
const { getMock, patchMock, postMock, deleteMock } = vi.hoisted(() => ({
  getMock: vi.fn<(url: string, config?: unknown) => Promise<unknown>>(),
  patchMock: vi.fn<(url: string, data?: unknown) => Promise<unknown>>(),
  postMock: vi.fn<(url: string, data?: unknown) => Promise<unknown>>(),
  deleteMock: vi.fn<(url: string) => Promise<unknown>>(),
}))
vi.mock('@/services/api', () => ({
  default: { get: getMock, patch: patchMock, post: postMock, delete: deleteMock },
}))

import { listIssues, updateIssue, createComment, updateComment, deleteComment } from '@/services/issue'

describe('issue services (รายการ/แก้ไขเรื่อง + คอมเมนต์)', () => {
  beforeEach(() => {
    getMock.mockReset()
    patchMock.mockReset()
    postMock.mockReset()
    deleteMock.mockReset()
  })

  it('listIssues → GET /api/issues พร้อม params และ unwrap เป็น IssueListResponse (envelope)', async () => {
    const fakeRes = {
      items: [{ id: 1, title: 'เรื่องแรก' }],
      total: 42,
      page: 2,
      page_size: 20,
      pages: 3,
    }
    getMock.mockResolvedValue(fakeRes)

    const result = await listIssues({
      received: true,
      q: 'พัดลม',
      sort: 'asc',
      limit: 20,
      offset: 20,
    })

    expect(getMock).toHaveBeenCalledTimes(1)
    expect(getMock).toHaveBeenCalledWith('/api/issues', {
      params: { received: true, q: 'พัดลม', sort: 'asc', limit: 20, offset: 20 },
    })
    expect(result).toEqual(fakeRes)
  })

  it('updateIssue → PATCH /api/issues/{id} (ต้องมี prefix /api)', async () => {
    const fakeIssue = { id: 7, title: 'แก้ไขแล้ว' }
    patchMock.mockResolvedValue(fakeIssue)

    const result = await updateIssue(7, { title: 'แก้ไขแล้ว', is_anonymous: false })

    expect(patchMock).toHaveBeenCalledTimes(1)
    expect(patchMock).toHaveBeenCalledWith('/api/issues/7', {
      title: 'แก้ไขแล้ว',
      is_anonymous: false,
    })
    expect(result).toEqual(fakeIssue)
  })

  it('createComment → POST /api/issues/{id}/comments', async () => {
    const fakeComment = { id: 1, body: 'รับทราบ' }
    postMock.mockResolvedValue(fakeComment)

    const result = await createComment(7, 'รับทราบ')

    expect(postMock).toHaveBeenCalledWith('/api/issues/7/comments', { body: 'รับทราบ' })
    expect(result).toEqual(fakeComment)
  })

  it('updateComment → PATCH /api/issues/{id}/comments/{cid}', async () => {
    const fakeComment = { id: 1, body: 'แก้แล้ว' }
    patchMock.mockResolvedValue(fakeComment)

    const result = await updateComment(7, 1, 'แก้แล้ว')

    expect(patchMock).toHaveBeenCalledWith('/api/issues/7/comments/1', { body: 'แก้แล้ว' })
    expect(result).toEqual(fakeComment)
  })

  it('deleteComment → DELETE /api/issues/{id}/comments/{cid}', async () => {
    deleteMock.mockResolvedValue({ status: 'ok' })

    await deleteComment(7, 1)

    expect(deleteMock).toHaveBeenCalledWith('/api/issues/7/comments/1')
  })
})
