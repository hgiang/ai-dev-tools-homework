import { useEffect, useState } from 'react'
import { LANE_NAMES, type Card, type CardUpdate } from '../api'

interface Props {
  card: Card
  onSave: (id: string, input: CardUpdate) => Promise<void>
  onDelete: (id: string) => Promise<void>
  onClose: () => void
}

export function CardDetail({ card, onSave, onDelete, onClose }: Props) {
  const [title, setTitle] = useState(card.title)
  const [description, setDescription] = useState(card.description)
  const [labels, setLabels] = useState(card.labels.join(', '))
  const [dueDate, setDueDate] = useState(card.due_date ?? '')
  const [confirmingDelete, setConfirmingDelete] = useState(false)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  const canSave = title.trim().length > 0 && !busy

  async function save() {
    if (!canSave) return
    setBusy(true)
    try {
      await onSave(card.id, {
        title,
        description,
        labels: labels.split(',').map((s) => s.trim()).filter(Boolean),
        due_date: dueDate || null,
      })
      onClose()
    } catch {
      // Error is shown by the board banner; keep the panel open.
    } finally {
      setBusy(false)
    }
  }

  async function remove() {
    setBusy(true)
    try {
      await onDelete(card.id)
      onClose()
    } catch {
      setBusy(false)
    }
  }

  return (
    <div className="overlay" onClick={onClose} role="presentation">
      <div
        className="panel"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Card details"
      >
        <header className="panel__head">
          <span className="panel__lane">{LANE_NAMES[card.lane]}</span>
          <button className="btn btn--icon" onClick={onClose} aria-label="Close">
            ×
          </button>
        </header>

        <label className="field">
          <span>Title</span>
          <input
            value={title}
            maxLength={200}
            onChange={(event) => setTitle(event.target.value)}
          />
        </label>

        <label className="field">
          <span>Description</span>
          <textarea
            value={description}
            maxLength={2000}
            rows={5}
            onChange={(event) => setDescription(event.target.value)}
          />
        </label>

        <label className="field">
          <span>Labels</span>
          <input
            value={labels}
            placeholder="Comma separated"
            onChange={(event) => setLabels(event.target.value)}
          />
        </label>

        <label className="field">
          <span>Due date</span>
          <input
            type="date"
            value={dueDate}
            onChange={(event) => setDueDate(event.target.value)}
          />
        </label>

        <footer className="panel__actions">
          <button className="btn btn--primary" onClick={() => void save()} disabled={!canSave}>
            {busy ? 'Saving…' : 'Save'}
          </button>
          <button className="btn" onClick={onClose}>
            Cancel
          </button>
          <span className="panel__spacer" />
          {confirmingDelete ? (
            <>
              <button className="btn btn--danger" onClick={() => void remove()} disabled={busy}>
                Delete for good
              </button>
              <button className="btn" onClick={() => setConfirmingDelete(false)}>
                Keep
              </button>
            </>
          ) : (
            <button className="btn btn--quiet" onClick={() => setConfirmingDelete(true)}>
              Delete
            </button>
          )}
        </footer>
      </div>
    </div>
  )
}
