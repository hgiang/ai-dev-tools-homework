import { useState } from 'react'
import type { CardCreate, LaneId } from '../api'

interface Props {
  lane: LaneId
  onSubmit: (input: CardCreate) => Promise<void>
  onCancel: () => void
}

export function CardComposer({ lane, onSubmit, onCancel }: Props) {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [labels, setLabels] = useState('')
  const [dueDate, setDueDate] = useState('')
  const [busy, setBusy] = useState(false)

  const canSave = title.trim().length > 0 && !busy

  async function save() {
    if (!canSave) return
    setBusy(true)
    try {
      await onSubmit({
        lane,
        title,
        description,
        labels: labels.split(',').map((s) => s.trim()).filter(Boolean),
        due_date: dueDate || null,
      })
      onCancel()
    } catch {
      // The board surfaces the error; keep the composer open with its content.
    } finally {
      setBusy(false)
    }
  }

  return (
    <form
      className="composer"
      onSubmit={(event) => {
        event.preventDefault()
        void save()
      }}
      onKeyDown={(event) => {
        if (event.key === 'Escape') onCancel()
      }}
    >
      <input
        className="composer__title"
        placeholder="Card title"
        value={title}
        maxLength={200}
        autoFocus
        onChange={(event) => setTitle(event.target.value)}
      />
      <textarea
        className="composer__desc"
        placeholder="Description (optional)"
        value={description}
        maxLength={2000}
        rows={2}
        onChange={(event) => setDescription(event.target.value)}
      />
      <input
        className="composer__labels"
        placeholder="Labels, comma separated"
        value={labels}
        onChange={(event) => setLabels(event.target.value)}
      />
      <input
        className="composer__due"
        type="date"
        value={dueDate}
        onChange={(event) => setDueDate(event.target.value)}
      />
      <div className="composer__actions">
        <button type="submit" className="btn btn--primary" disabled={!canSave}>
          {busy ? 'Adding…' : 'Add card'}
        </button>
        <button type="button" className="btn" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  )
}
