import { useCallback, useEffect, useState } from 'react'
import {
  ApiError,
  api,
  type Board,
  type Card,
  type CardCreate,
  type CardUpdate,
  type LaneId,
} from '../api'

interface UseBoard {
  board: Board | null
  loading: boolean
  error: string | null
  dismissError: () => void
  createCard: (input: CardCreate) => Promise<void>
  updateCard: (id: string, input: CardUpdate) => Promise<void>
  deleteCard: (id: string) => Promise<void>
  moveCard: (id: string, lane: LaneId, position: number) => Promise<void>
}

function messageOf(err: unknown): string {
  if (err instanceof ApiError) {
    const fields = err.fields
    if (fields) {
      const first = Object.values(fields)[0]
      if (first) return first
    }
    return err.message
  }
  return err instanceof Error ? err.message : 'Something went wrong'
}

/** Applies a move to a board snapshot, so the UI can show the result before the
 *  server confirms it. */
function applyMove(board: Board, id: string, lane: LaneId, position: number): Board {
  let moved: Card | undefined
  const stripped = board.lanes.map((l) => {
    const kept: Card[] = []
    for (const card of l.cards) {
      if (card.id === id) moved = card
      else kept.push(card)
    }
    return { ...l, cards: kept }
  })
  if (!moved) return board

  const card: Card = { ...moved, lane }
  return {
    lanes: stripped.map((l) => {
      if (l.id !== lane) return l
      const cards = [...l.cards]
      cards.splice(Math.max(0, Math.min(position, cards.length)), 0, card)
      return { ...l, cards: cards.map((c, i) => ({ ...c, position: i })) }
    }),
  }
}

export function useBoard(): UseBoard {
  const [board, setBoard] = useState<Board | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      setBoard(await api.getBoard())
      setError(null)
    } catch (err) {
      setError(messageOf(err))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const run = useCallback(
    async (action: () => Promise<unknown>) => {
      try {
        await action()
        setBoard(await api.getBoard())
        setError(null)
      } catch (err) {
        setError(messageOf(err))
        throw err
      }
    },
    [],
  )

  const createCard = useCallback(
    (input: CardCreate) => run(() => api.createCard(input)),
    [run],
  )

  const updateCard = useCallback(
    (id: string, input: CardUpdate) => run(() => api.updateCard(id, input)),
    [run],
  )

  const deleteCard = useCallback(
    (id: string) => run(() => api.deleteCard(id)),
    [run],
  )

  const moveCard = useCallback(
    async (id: string, lane: LaneId, position: number) => {
      const previous = board
      if (previous) setBoard(applyMove(previous, id, lane, position))
      try {
        await api.moveCard(id, { lane, position })
        setBoard(await api.getBoard())
        setError(null)
      } catch (err) {
        // Roll back to the server's truth rather than trusting the guess.
        if (previous) setBoard(previous)
        setError(messageOf(err))
      }
    },
    [board],
  )

  return {
    board,
    loading,
    error,
    dismissError: () => setError(null),
    createCard,
    updateCard,
    deleteCard,
    moveCard,
  }
}
