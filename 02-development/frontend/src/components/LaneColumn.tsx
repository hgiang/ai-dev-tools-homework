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
    <section
      className={`lane${isOver ? ' lane--over' : ''}`}
      data-lane={lane.id}
      aria-label={lane.name}
    >
      <header className="lane__head">
        <span className="lane__mark" aria-hidden="true" />
        <h2 className="lane__name">{lane.name}</h2>
        <span className="lane__count">
          {String(lane.cards.length).padStart(2, '0')}
        </span>
      </header>

      <div className="lane__body" ref={setNodeRef}>
        <SortableContext
          items={lane.cards.map((c) => c.id)}
          strategy={verticalListSortingStrategy}
        >
          {lane.cards.map((card, index) => (
            <CardTile key={card.id} card={card} index={index} onOpen={onOpen} />
          ))}
        </SortableContext>

        {lane.cards.length === 0 && !composing && (
          <p className="lane__empty">Empty lane</p>
        )}

        {composing ? (
          <CardComposer
            lane={lane.id}
            onSubmit={onCreate}
            onCancel={() => setComposing(false)}
          />
        ) : (
          <button className="lane__add" onClick={() => setComposing(true)}>
            <span aria-hidden="true">+</span> Add card
          </button>
        )}
      </div>
    </section>
  )
}
