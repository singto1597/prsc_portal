import { describe, it, expect, beforeEach, vi } from 'vitest'

// mock axios instance — ทดสอบเฉพาะ service layer ไม่ต้องมี backend จริง
const { getMock, postMock } = vi.hoisted(() => ({
  getMock: vi.fn<(url: string, config?: unknown) => Promise<unknown>>(),
  postMock: vi.fn<(url: string, data?: unknown) => Promise<unknown>>(),
}))
vi.mock('@/services/api', () => ({
  default: { get: getMock, post: postMock },
}))

import { listBoards, getBoard, submitVote, addComment } from '@/services/board'
import { approveToPublic } from '@/services/issue'

describe('board services (PIRI Vote + PIRI Talk)', () => {
  beforeEach(() => {
    getMock.mockReset()
    postMock.mockReset()
  })

  it('listBoards → GET /api/boards พร้อม params (ประเภท/ค้นหา/แบ่งหน้า) และ unwrap envelope', async () => {
    const fakeRes = { items: [{ id: 1, title: 'บอร์ดแรก' }], total: 5, page: 1, page_size: 12, pages: 1 }
    getMock.mockResolvedValue(fakeRes)

    const result = await listBoards({ board_type: 'vote', q: 'พัดลม', limit: 12, offset: 0 })

    expect(getMock).toHaveBeenCalledWith('/api/boards', {
      params: { board_type: 'vote', q: 'พัดลม', limit: 12, offset: 0 },
    })
    expect(result).toEqual(fakeRes)
  })

  it('getBoard → GET /api/boards/{id}', async () => {
    const fake = { id: 7, board_type: 'talk', title: 'บอร์ดพูดคุย', choices: [], comments: [] }
    getMock.mockResolvedValue(fake)

    const result = await getBoard(7)

    expect(getMock).toHaveBeenCalledWith('/api/boards/7')
    expect(result).toEqual(fake)
  })

  it('submitVote → POST /api/boards/{id}/vote ส่ง choice_id', async () => {
    const fake = { status: 'ok', vote_id: 1, board_id: 7, choice_id: 2, choice_text: 'ตัวเลือก B' }
    postMock.mockResolvedValue(fake)

    const result = await submitVote(7, 2)

    expect(postMock).toHaveBeenCalledWith('/api/boards/7/vote', { choice_id: 2 })
    expect(result).toEqual(fake)
  })

  it('addComment → POST /api/boards/{id}/comments ส่ง body + parent_id', async () => {
    const fake = { id: 9, body: 'เห็นด้วย', parent_comment_id: 3, replies: [] }
    postMock.mockResolvedValue(fake)

    const root = await addComment(7, 'เห็นด้วย')
    expect(postMock).toHaveBeenCalledWith('/api/boards/7/comments', { body: 'เห็นด้วย', parent_id: null })

    postMock.mockReset()
    postMock.mockResolvedValue(fake)
    await addComment(7, 'เห็นด้วย', 3)
    expect(postMock).toHaveBeenCalledWith('/api/boards/7/comments', { body: 'เห็นด้วย', parent_id: 3 })
    expect(root).toEqual(fake)
  })

  it('approveToPublic → POST /api/issues/{id}/approve-to-public (vote board ส่ง vote_choices)', async () => {
    postMock.mockResolvedValue({ board_id: 11, status: 'approved' })

    const result = await approveToPublic(5, {
      board_type: 'vote',
      vote_choices: ['ตัวเลือก A', 'ตัวเลือก B'],
      allow_comments: true,
    })

    expect(postMock).toHaveBeenCalledWith('/api/issues/5/approve-to-public', {
      board_type: 'vote',
      vote_choices: ['ตัวเลือก A', 'ตัวเลือก B'],
      allow_comments: true,
    })
    expect(result).toEqual({ board_id: 11, status: 'approved' })
  })

  it('approveToPublic → talk board ส่ง allow_comments (ไม่ต้องส่ง vote_choices)', async () => {
    postMock.mockResolvedValue({ board_id: 12, status: 'approved' })

    const result = await approveToPublic(5, { board_type: 'talk', allow_comments: false })

    expect(postMock).toHaveBeenCalledWith('/api/issues/5/approve-to-public', {
      board_type: 'talk',
      allow_comments: false,
    })
    expect(result.board_id).toBe(12)
  })
})
