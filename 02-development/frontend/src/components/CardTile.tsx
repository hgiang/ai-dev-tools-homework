import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import type { CSSProperties } from 'react'
import type { Card } from '../api'
import { cardHue, dueState, formatDue, labelHue } from '../lib/labels'

interface Props {
  card: Card
  index: number
  onOpen: (card: Card) => void
}

export function CardTile({ card, index, onOpen }: Props) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: card.id, data: { lane: card.lane } })

  const hue = cardHue(card)
  const due = dueState(card.due_date, card.lane === 'done')

  // The drag transform lives on the shell; the entrance animation lives on the
  // card inside it, so a CSS animation can never fight dnd-kit for `transform`.
  const shellStyle: CSSProperties = {
    transform: CSS.Translate.toString(transform),
    transition,
  }
  const cardStyle = { '--i': index, ...(hue !== null && { '--hue': hue }) } as CSSProperties

  return (
    <div
      ref={setNodeRef}
      className={`shell${isDragging ? ' shell--dragging' : ''}`}
      style={shellStyle}
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
      <article className={`card${hue === null ? ' card--plain' : ''}`} style={cardStyle}>
        <h3 className="card__title">{card.title}</h3>

        {card.description && <p className="card__desc">{card.description}</p>}

        {(card.labels.length > 0 || card.due_date) && (
          <footer className="card__meta">
            {card.labels.map((label) => (
              <span
                key={label}
                className="chip"
                style={{ '--hue': labelHue(label) } as CSSProperties}
              >
                {label}
              </span>
            ))}
            {card.due_date && (
              <span className={`due due--${due}`}>
                {due === 'overdue' && <i className="due__dot" aria-hidden="true" />}
                {formatDue(card.due_date)}
              </span>
            )}
          </footer>
        )}
      </article>
    </div>
  )
}
