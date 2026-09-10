export type LaneId = 'todo' | 'doing' | 'done'

export const LANE_ORDER: LaneId[] = ['todo', 'doing', 'done']

export const LANE_NAMES: Record<LaneId, string> = {
  todo: 'To Do',
  doing: 'In Progress',
  done: 'Done',
}

export interface Card {
  id: string
  title: string
  description: string
  labels: string[]
  due_date: string | null
  lane: LaneId
  position: number
  created_at: string
  updated_at: string
}

export interface Lane {
  id: LaneId
  name: string
  cards: Card[]
}

export interface Board {
  lanes: Lane[]
}

export interface CardCreate {
  title: string
  description?: string
  labels?: string[]
  due_date?: string | null
  lane?: LaneId
}

export type CardUpdate = Partial<Omit<CardCreate, 'lane'>>

export interface CardMove {
  lane: LaneId
  position: number
}

/** Every backend interaction the app performs. Implemented by the mock now, by
 *  HTTP later — nothing outside src/api/ knows which. */
export interface ApiClient {
  getBoard(): Promise<Board>
  createCard(input: CardCreate): Promise<Card>
  updateCard(id: string, input: CardUpdate): Promise<Card>
  moveCard(id: string, input: CardMove): Promise<Card>
  deleteCard(id: string): Promise<void>
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly fields?: Record<string, string>,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}
