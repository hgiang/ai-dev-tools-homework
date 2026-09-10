import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import type { Card } from '../api'
import { dueState, formatDue, labelHue } from '../lib/labels'

interface Props {
  card: Card
  onOpen: (card: Card) => void
}

export function CardTile({ card, onOpen }: Props) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: card.id, data: { lane: card.lane } })

  const due = dueState(card.due_date, card.lane === 'done')

  return (
    <article
      ref={setNodeRef}
      className={`card${isDragging ? ' card--dragging' : ''}`}
      style={{ transform: CSS.Translate.toString(transform), transition }}
      {...attributes}
      {...listeners}
      onClick={() => onOpen(card)}
      onKeyDown={(event) => {
        if (event.key === 'Enter') {
          event.preventDefault()
          onOpen(card)
        }
      }}
      aria-label={card.title}
    >
      <h3 className="card__title">{card.title}</h3>

      {card.description && <p className="card__desc">{card.description}</p>}

      {(card.labels.length > 0 || card.due_date) && (
        <footer className="card__meta">
          {card.labels.map((label) => (
            <span
              key={label}
              className="chip"
              style={{
                background: `hsl(${labelHue(label)} 70% 92%)`,
                color: `hsl(${labelHue(label)} 55% 28%)`,
              }}
            >
              {label}
            </span>
          ))}
          {card.due_date && (
            <span className={`due due--${due}`}>{formatDue(card.due_date)}</span>
          )}
        </footer>
      )}
    </article>
  )
}
