import { describe, it, expect, beforeEach, vi } from 'vitest'

// mock axios instance — ทดสอบเฉพาะ service layer ไม่ต้องมี backend จริง
const { getMock, postMock } = vi.hoisted(() => ({
  getMock: vi.fn<(url: string, config?: unknown) => Promise<unknown>>(),
  postMock: vi.fn<(url: string, data?: unknown) => Promise<unknown>>(),
}))
vi.mock('@/services/api', () => ({
  default: { get: getMock, post: postMock },
}))

import {
  listBoards,
  getBoard,
  submitVote,
  addComment,
  reportComment,
  hideComment,
  hideBoard,
  listReports,
  resolveReport,
} from '@/services/board'
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

  it('reportComment → POST /api/boards/{id}/comments/{cid}/report ส่งเหตุผล + detail', async () => {
    postMock.mockResolvedValue({ id: 9, board_id: 7, comment_id: 3, status: 'open' })

    const result = await reportComment(7, 3, { reason: 'bullying', detail: 'ด่าซ้ำๆ' })

    expect(postMock).toHaveBeenCalledWith('/api/boards/7/comments/3/report', {
      reason: 'bullying',
      detail: 'ด่าซ้ำๆ',
    })
    expect(result.status).toBe('open')
  })

  it('hideComment → POST /api/boards/{id}/comments/{cid}/hide ส่งเหตุผล', async () => {
    postMock.mockResolvedValue({ status: 'hidden', board_id: 7, comment_id: 3, hidden_count: 1 })

    const result = await hideComment(7, 3, 'กลั่นแกล้ง')

    expect(postMock).toHaveBeenCalledWith('/api/boards/7/comments/3/hide', { reason: 'กลั่นแกล้ง' })
    expect(result.hidden_count).toBe(1)
  })

  it('hideBoard → POST /api/boards/{id}/hide', async () => {
    postMock.mockResolvedValue({ status: 'hidden', board_id: 7 })

    const result = await hideBoard(7, 'สแปม')

    expect(postMock).toHaveBeenCalledWith('/api/boards/7/hide', { reason: 'สแปม' })
    expect(result.status).toBe('hidden')
  })

  it('listReports → GET /api/boards/reports พร้อม params (status/reason/q/แบ่งหน้า)', async () => {
    const fake = { items: [{ id: 1, board_title: 'บอร์ด' }], total: 5, page: 1, page_size: 15, pages: 1 }
    getMock.mockResolvedValue(fake)

    const result = await listReports({ status: 'open', reason: 'spam', q: 'ลิงก์', limit: 15, offset: 0 })

    expect(getMock).toHaveBeenCalledWith('/api/boards/reports', {
      params: { status: 'open', reason: 'spam', q: 'ลิงก์', limit: 15, offset: 0 },
    })
    expect(result).toEqual(fake)
  })

  it('resolveReport → POST /api/boards/reports/{id}/resolve (hide ส่ง note)', async () => {
    postMock.mockResolvedValue({ report_id: 4, status: 'resolved', hidden_count: 1 })

    const result = await resolveReport(4, 'hide', 'ยืนยันว่าผิดจริง')

    expect(postMock).toHaveBeenCalledWith('/api/boards/reports/4/resolve', {
      action: 'hide',
      note: 'ยืนยันว่าผิดจริง',
    })
    expect(result.status).toBe('resolved')
  })

  it('resolveReport → dismiss ไม่ส่ง note ถ้าไม่มี', async () => {
    postMock.mockResolvedValue({ report_id: 4, status: 'dismissed' })

    await resolveReport(4, 'dismiss')

    expect(postMock).toHaveBeenCalledWith('/api/boards/reports/4/resolve', { action: 'dismiss', note: undefined })
  })
})
