import { isDemoPreviewEnabled, isFirebaseConfigured } from '@/config/env'
import type { BackendMode, Services } from '@/types/services'
import { demoBackend } from './demo'
import { firebaseBackend } from './firebase'
import { unconfiguredBackend } from './unconfigured'

/**
 * Backend selection is intentionally explicit:
 *   Firebase configured  -> firebase service layer (Phase 2 implementation)
 *   demo flag enabled    -> clearly labelled in-memory sample data
 *   otherwise            -> every action fails with a setup message
 *
 * A production build never falls back to demo data silently.
 */
export const backendMode: BackendMode = isFirebaseConfigured
  ? 'firebase'
  : isDemoPreviewEnabled
    ? 'demo'
    : 'unconfigured'

export const services: Services =
  backendMode === 'firebase'
    ? firebaseBackend
    : backendMode === 'demo'
      ? demoBackend
      : unconfiguredBackend

export type { Services, BackendMode } from '@/types/services'
