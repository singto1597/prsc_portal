import api from './api'
import type {
  BoardComment,
  BoardDetail,
  BoardListResponse,
  BoardType,
  VoteResult,
} from '@/types/board'

// PIRI Boards API (feed โหวต/พูดคุยสาธารณะ) — view ห้ามเรียก api.* ตรง ๆ ต้องผ่าน services นี้

export async function listBoards(params: {
  board_type?: BoardType
  q?: string
  limit?: number
  offset?: number
}): Promise<BoardListResponse> {
  return (await api.get('/api/boards', { params })) as BoardListResponse
}

export async function getBoard(id: number): Promise<BoardDetail> {
  return (await api.get(`/api/boards/${id}`)) as BoardDetail
}

export async function submitVote(boardId: number, choice_id: number): Promise<VoteResult> {
  return (await api.post(`/api/boards/${boardId}/vote`, { choice_id })) as VoteResult
}

export async function addComment(
  boardId: number,
  body: string,
  parent_id?: number | null,
): Promise<BoardComment> {
  return (await api.post(`/api/boards/${boardId}/comments`, {
    body,
    parent_id: parent_id ?? null,
  })) as BoardComment
}
