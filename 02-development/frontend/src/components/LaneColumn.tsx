import { useDroppable } from '@dnd-kit/core'
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable'
import { useState } from 'react'
import type { Card, CardCreate, Lane } from '../api'
import { CardComposer } from './CardComposer'
import { CardTile } from './CardTile'

interface Props {
  lane: Lane
  onCreate: (input: CardCreate) => Promise<void>
  onOpen: (card: Card) => void
}

export function LaneColumn({ lane, onCreate, onOpen }: Props) {
  const [composing, setComposing] = useState(false)
  const { setNodeRef, isOver } = useDroppable({
    id: `lane-${lane.id}`,
    data: { lane: lane.id },
  })

  return (
    <section className={`lane${isOver ? ' lane--over' : ''}`} aria-label={lane.name}>
      <header className="lane__head">
        <h2 className="lane__name">{lane.name}</h2>
        <span className="lane__count">{lane.cards.length}</span>
      </header>

      <div className="lane__body" ref={setNodeRef}>
        <SortableContext
          items={lane.cards.map((c) => c.id)}
          strategy={verticalListSortingStrategy}
        >
          {lane.cards.map((card) => (
            <CardTile key={card.id} card={card} onOpen={onOpen} />
          ))}
        </SortableContext>

        {lane.cards.length === 0 && !composing && (
          <p className="lane__empty">Nothing here yet.</p>
        )}

        {composing ? (
          <CardComposer
            lane={lane.id}
            onSubmit={onCreate}
            onCancel={() => setComposing(false)}
          />
        ) : (
          <button className="lane__add" onClick={() => setComposing(true)}>
            + Add card
          </button>
        )}
      </div>
    </section>
  )
}
