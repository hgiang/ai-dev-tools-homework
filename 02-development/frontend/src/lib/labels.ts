import type { Card } from '../api'

/** Deterministic hue per label text, so a tag always wears the same colour.
 *  Skips the 55–75° band, where yellows go muddy against a dark ground. */
export function labelHue(label: string): number {
  let hash = 0
  for (let i = 0; i < label.length; i += 1) {
    hash = (hash * 31 + label.toLowerCase().charCodeAt(i)) % 2147483647
  }
  const hue = hash % 340
  return hue >= 55 ? hue + 20 : hue
}

/** A card takes its colour from its first label. Unlabelled cards stay neutral. */
export function cardHue(card: Card): number | null {
  const first = card.labels[0]
  return first ? labelHue(first) : null
}

export type DueState = 'none' | 'overdue' | 'today' | 'upcoming'

export function dueState(dueDate: string | null, done: boolean): DueState {
  if (!dueDate) return 'none'
  const today = new Date().toISOString().slice(0, 10)
  if (dueDate === today) return done ? 'upcoming' : 'today'
  if (dueDate < today) return done ? 'upcoming' : 'overdue'
  return 'upcoming'
}

export function formatDue(dueDate: string): string {
  const [y, m, d] = dueDate.split('-').map(Number)
  return new Date(y, m - 1, d)
    .toLocaleDateString('en-GB', { month: 'short', day: '2-digit' })
    .toUpperCase()
}
