import {
  ApiError,
  type ApiClient,
  type Board,
  type Card,
  type CardCreate,
  type CardMove,
  type CardUpdate,
} from './types'

/** Where the backend lives. Override with VITE_API_BASE_URL for other
 *  environments; the default is the local uvicorn from the README. */
export const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api'

interface ValidationDetail {
  loc: Array<string | number>
  msg: string
  type: string
}

/** Turns FastAPI's validation payload into { field: message }, so the UI can
 *  show "Title must not be blank" rather than a raw 422. */
function fieldsFrom(detail: ValidationDetail[]): Record<string, string> {
  const fields: Record<string, string> = {}
  for (const item of detail) {
    // loc is ["body", "title"] — the field name is the last segment.
    const name = String(item.loc[item.loc.length - 1] ?? 'body')
    // Pydantic prefixes custom validator messages with "Value error, ".
    const message = item.msg.replace(/^Value error,\s*/, '')
    if (!(name in fields)) fields[name] = message
  }
  return fields
}

async function toApiError(response: Response): Promise<ApiError> {
  let body: unknown
  try {
    body = await response.json()
  } catch {
    return new ApiError(response.statusText || 'Request failed', response.status)
  }

  const detail = (body as { detail?: unknown }).detail

  if (Array.isArray(detail)) {
    const fields = fieldsFrom(detail as ValidationDetail[])
    const first = Object.values(fields)[0] ?? 'Validation failed'
    return new ApiError(first, response.status, fields)
  }

  if (typeof detail === 'string') {
    return new ApiError(detail, response.status)
  }

  return new ApiError(response.statusText || 'Request failed', response.status)
}

/** `body` is a plain object here, not a BodyInit — request() serializes it. */
type Init = Omit<RequestInit, 'body'> & { body?: unknown }

async function request<T>(path: string, init?: Init): Promise<T> {
  const { body, ...rest } = init ?? {}

  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...rest,
      headers: body === undefined ? rest.headers : {
        'Content-Type': 'application/json',
        ...rest.headers,
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    // A network-level failure, not an HTTP status — the server is likely down.
    throw new ApiError('Cannot reach the server. Is the backend running?', 0)
  }

  if (!response.ok) throw await toApiError(response)
  if (response.status === 204) return undefined as T

  return (await response.json()) as T
}

export const httpClient: ApiClient = {
  getBoard: () => request<Board>('/board'),

  createCard: (input: CardCreate) =>
    request<Card>('/cards', { method: 'POST', body: input }),

  updateCard: (id: string, input: CardUpdate) =>
    request<Card>(`/cards/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      body: input,
    }),

  moveCard: (id: string, input: CardMove) =>
    request<Card>(`/cards/${encodeURIComponent(id)}/move`, {
      method: 'POST',
      body: input,
    }),

  deleteCard: (id: string) =>
    request<void>(`/cards/${encodeURIComponent(id)}`, { method: 'DELETE' }),
}
