import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  closestCorners,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core'
import { sortableKeyboardCoordinates } from '@dnd-kit/sortable'
import { useState } from 'react'
import type { Card, LaneId } from './api'
import { CardDetail } from './components/CardDetail'
import { LaneColumn } from './components/LaneColumn'
import { useBoard } from './hooks/useBoard'

export default function App() {
  const {
    board,
    loading,
    error,
    dismissError,
    createCard,
    updateCard,
    deleteCard,
    moveCard,
  } = useBoard()
  const [openCardId, setOpenCardId] = useState<string | null>(null)

  const sensors = useSensors(
    // A small distance threshold keeps a click on a card from starting a drag.
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )

  const cards = board?.lanes.flatMap((l) => l.cards) ?? []
  const openCard = cards.find((c) => c.id === openCardId) ?? null

  function handleDragEnd({ active, over }: DragEndEvent) {
    if (!over || !board) return

    const dragged = cards.find((c) => c.id === active.id)
    if (!dragged) return

    // Dropped on a lane's empty area, or on another card.
    const overLane = over.data.current?.lane as LaneId | undefined
    if (!overLane) return

    const target = board.lanes.find((l) => l.id === overLane)
    if (!target) return

    let position: number
    if (over.id === `lane-${overLane}`) {
      position = target.cards.length
    } else {
      const index = target.cards.findIndex((c) => c.id === over.id)
      if (index === -1) return
      // The server removes the card before re-inserting, so the index of the
      // card dropped onto is already the desired final position.
      position = index
    }

    if (dragged.lane === overLane && dragged.position === position) return
    void moveCard(dragged.id, overLane, position)
  }

  return (
    <div className="app">
      <header className="app__head">
        <h1 className="app__title">Laneway</h1>
        <p className="app__tagline">One board. Three lanes. Nothing else.</p>
      </header>

      {error && (
        <div className="banner banner--error" role="alert">
          <span>{error}</span>
          <button className="btn btn--icon" onClick={dismissError} aria-label="Dismiss">
            ×
          </button>
        </div>
      )}

      {loading && !board ? (
        <p className="app__loading">Loading the board…</p>
      ) : (
        board && (
          <DndContext
            sensors={sensors}
            collisionDetection={closestCorners}
            onDragEnd={handleDragEnd}
          >
            <main className="board">
              {board.lanes.map((lane) => (
                <LaneColumn
                  key={lane.id}
                  lane={lane}
                  onCreate={createCard}
                  onOpen={(card: Card) => setOpenCardId(card.id)}
                />
              ))}
            </main>
          </DndContext>
        )
      )}

      {openCard && (
        <CardDetail
          card={openCard}
          onSave={updateCard}
          onDelete={deleteCard}
          onClose={() => setOpenCardId(null)}
        />
      )}
    </div>
  )
}
