/** Deterministic chip color per label text, so a tag always looks the same. */
export function labelHue(label: string): number {
  let hash = 0
  for (let i = 0; i < label.length; i += 1) {
    hash = (hash * 31 + label.toLowerCase().charCodeAt(i)) % 360
  }
  return hash
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
  return new Date(y, m - 1, d).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
  })
}
