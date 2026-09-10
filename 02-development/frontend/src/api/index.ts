import { httpClient } from './httpClient'
import { mockClient } from './mockClient'
import type { ApiClient } from './types'

/** The single seam between the app and its backend.
 *
 *  The live backend is the default. Set VITE_USE_MOCK_API=true to run the UI
 *  against the in-memory mock instead — useful for styling work, or when the
 *  server isn't up. Nothing outside this directory knows which is in play.
 */
const useMock = import.meta.env.VITE_USE_MOCK_API === 'true'

export const api: ApiClient = useMock ? mockClient : httpClient

export { API_BASE_URL } from './httpClient'
export * from './types'
export * from './validation'
