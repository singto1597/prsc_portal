import { describe, it, expect, beforeEach, vi } from 'vitest'

// mock axios instance — ทดสอบเฉพาะ service layer ไม่ต้องมี backend จริง
const { patchMock, postMock, deleteMock } = vi.hoisted(() => ({
  patchMock: vi.fn<(url: string, data?: unknown) => Promise<unknown>>(),
  postMock: vi.fn<(url: string, data?: unknown) => Promise<unknown>>(),
  deleteMock: vi.fn<(url: string) => Promise<unknown>>(),
}))
vi.mock('@/services/api', () => ({
  default: { patch: patchMock, post: postMock, delete: deleteMock },
}))

import { updateIssue, createComment, updateComment, deleteComment } from '@/services/issue'

describe('issue services (แก้ไขเรื่อง + คอมเมนต์)', () => {
  beforeEach(() => {
    patchMock.mockReset()
    postMock.mockReset()
    deleteMock.mockReset()
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
