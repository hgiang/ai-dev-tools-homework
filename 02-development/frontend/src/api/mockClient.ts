import {
  ApiError,
  LANE_NAMES,
  LANE_ORDER,
  type ApiClient,
  type Board,
  type Card,
  type CardCreate,
  type CardMove,
  type CardUpdate,
  type LaneId,
} from './types'
import {
  normalizeDescription,
  normalizeDueDate,
  normalizeLabels,
  normalizeTitle,
} from './validation'

/** Simulated network latency, so the UI's loading and optimistic paths are
 *  exercised in the prototype rather than only in production. */
const LATENCY_MS = 120

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function today(offsetDays = 0): string {
  const d = new Date()
  d.setDate(d.getDate() + offsetDays)
  return d.toISOString().slice(0, 10)
}

function nowIso(): string {
  return new Date().toISOString()
}

let idCounter = 0

function nextId(): string {
  idCounter += 1
  return `card-${idCounter}`
}

function seed(): Card[] {
  const rows: Array<Omit<Card, 'id' | 'position' | 'created_at' | 'updated_at'>> = [
    {
      title: 'Write the product spec',
      description: 'One board, three lanes, drag and drop. Committed to _docs/specs.md.',
      labels: ['docs'],
      due_date: today(-3),
      lane: 'done',
    },
    {
      title: 'Set up the repository',
      description: 'Spec, .gitignore, README and AGENTS.md, pushed to GitHub.',
      labels: ['chore'],
      due_date: null,
      lane: 'done',
    },
    {
      title: 'Build the frontend prototype',
      description: 'React + Vite + TypeScript, every backend call behind src/api/.',
      labels: ['frontend', 'in-flight'],
      due_date: today(),
      lane: 'doing',
    },
    {
      title: 'Draft openapi.yaml',
      description: 'Derive the contract from what the prototype actually calls.',
      labels: ['api'],
      due_date: today(1),
      lane: 'todo',
    },
    {
      title: 'FastAPI backend with a mock repository',
      description: 'Tests first, then the endpoints. Managed with uv.',
      labels: ['backend', 'tests'],
      due_date: today(2),
      lane: 'todo',
    },
    {
      title: 'Swap the mock store for SQLAlchemy',
      description: 'Keep the app database-agnostic behind the repository interface.',
      labels: ['backend', 'database'],
      due_date: today(-1),
      lane: 'todo',
    },
  ]

  const byLane: Record<LaneId, number> = { todo: 0, doing: 0, done: 0 }
  return rows.map((row) => ({
    ...row,
    id: nextId(),
    position: byLane[row.lane]++,
    created_at: nowIso(),
    updated_at: nowIso(),
  }))
}

/** In-memory store. Lives for the lifetime of the page — a refresh resets it,
 *  which is exactly the limitation the real backend removes. */
let cards: Card[] = seed()

function laneCards(lane: LaneId): Card[] {
  return cards
    .filter((c) => c.lane === lane)
    .sort((a, b) => a.position - b.position)
}

/** Rewrite positions in a lane to contiguous 0..n-1, as the server does. */
function renormalize(lane: LaneId): void {
  laneCards(lane).forEach((card, index) => {
    card.position = index
  })
}

function find(id: string): Card {
  const card = cards.find((c) => c.id === id)
  if (!card) throw new ApiError(`Card ${id} not found`, 404)
  return card
}

function clone(card: Card): Card {
  return { ...card, labels: [...card.labels] }
}

export const mockClient: ApiClient = {
  async getBoard(): Promise<Board> {
    await sleep(LATENCY_MS)
    return {
      lanes: LANE_ORDER.map((id) => ({
        id,
        name: LANE_NAMES[id],
        cards: laneCards(id).map(clone),
      })),
    }
  },

  async createCard(input: CardCreate): Promise<Card> {
    await sleep(LATENCY_MS)
    const lane = input.lane ?? 'todo'
    const card: Card = {
      id: nextId(),
      title: normalizeTitle(input.title),
      description: normalizeDescription(input.description),
      labels: normalizeLabels(input.labels),
      due_date: normalizeDueDate(input.due_date),
      lane,
      position: laneCards(lane).length,
      created_at: nowIso(),
      updated_at: nowIso(),
    }
    cards.push(card)
    return clone(card)
  },

  async updateCard(id: string, input: CardUpdate): Promise<Card> {
    await sleep(LATENCY_MS)
    const card = find(id)
    if (input.title !== undefined) card.title = normalizeTitle(input.title)
    if (input.description !== undefined) {
      card.description = normalizeDescription(input.description)
    }
    if (input.labels !== undefined) card.labels = normalizeLabels(input.labels)
    if (input.due_date !== undefined) {
      card.due_date = normalizeDueDate(input.due_date)
    }
    card.updated_at = nowIso()
    return clone(card)
  },

  async moveCard(id: string, input: CardMove): Promise<Card> {
    await sleep(LATENCY_MS)
    const card = find(id)
    const from = card.lane
    const to = input.lane

    const target = laneCards(to).filter((c) => c.id !== id)
    const index = Math.max(0, Math.min(input.position, target.length))

    card.lane = to
    card.updated_at = nowIso()
    target.splice(index, 0, card)
    target.forEach((c, i) => {
      c.position = i
    })
    if (from !== to) renormalize(from)

    return clone(card)
  },

  async deleteCard(id: string): Promise<void> {
    await sleep(LATENCY_MS)
    const card = find(id)
    cards = cards.filter((c) => c.id !== card.id)
    renormalize(card.lane)
  },
}
