import { ApiError } from './types'

export const TITLE_MAX = 200
export const DESCRIPTION_MAX = 2000
export const LABEL_MAX = 30
export const LABELS_MAX = 10

/** Mirrors the server-side rules in _docs/specs.md section 3. */
export function normalizeTitle(raw: string): string {
  const title = raw.trim()
  if (!title) {
    throw new ApiError('Validation failed', 422, { title: 'Title is required' })
  }
  if (title.length > TITLE_MAX) {
    throw new ApiError('Validation failed', 422, {
      title: `Title must be at most ${TITLE_MAX} characters`,
    })
  }
  return title
}

export function normalizeDescription(raw: string | undefined): string {
  const description = (raw ?? '').trim()
  if (description.length > DESCRIPTION_MAX) {
    throw new ApiError('Validation failed', 422, {
      description: `Description must be at most ${DESCRIPTION_MAX} characters`,
    })
  }
  return description
}

export function normalizeLabels(raw: string[] | undefined): string[] {
  const seen = new Set<string>()
  const labels: string[] = []
  for (const item of raw ?? []) {
    const label = item.trim()
    if (!label) continue
    if (label.length > LABEL_MAX) {
      throw new ApiError('Validation failed', 422, {
        labels: `Each label must be at most ${LABEL_MAX} characters`,
      })
    }
    const key = label.toLowerCase()
    if (seen.has(key)) continue
    seen.add(key)
    labels.push(label)
  }
  if (labels.length > LABELS_MAX) {
    throw new ApiError('Validation failed', 422, {
      labels: `At most ${LABELS_MAX} labels`,
    })
  }
  return labels
}

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/

export function normalizeDueDate(raw: string | null | undefined): string | null {
  if (raw === null || raw === undefined || raw === '') return null
  if (!DATE_RE.test(raw) || Number.isNaN(Date.parse(raw))) {
    throw new ApiError('Validation failed', 422, {
      due_date: 'Due date must be a valid YYYY-MM-DD date',
    })
  }
  return raw
}
