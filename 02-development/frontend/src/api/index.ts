import { mockClient } from './mockClient'
import type { ApiClient } from './types'

/** The single seam between the app and its backend.
 *
 *  Phase 1 (now): backed by an in-memory mock, so the whole UI is usable
 *  before a server exists.
 *  Phase 2: swap this one binding for an HTTP client generated from
 *  openapi.yaml. Nothing outside this directory changes.
 */
export const api: ApiClient = mockClient

export * from './types'
export * from './validation'
