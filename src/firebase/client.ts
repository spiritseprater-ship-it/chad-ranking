/**
 * Firebase client initialisation (Phase 2 entry point).
 *
 * - Uses the public web config from VITE_FIREBASE_* variables.
 * - Never imports or expects service-account credentials. Admin privileges are
 *   granted only by trusted backend operations, never by this module.
 * - SDK modules are imported dynamically so Phase 1 does not ship Firebase
 *   code in the main bundle.
 *
 * Firebase web config is not a secret and is not a security boundary.
 * Firestore/Storage Security Rules and server-side validation are.
 */

import type { FirebaseApp } from 'firebase/app'
import type { Auth } from 'firebase/auth'
import type { Firestore } from 'firebase/firestore'
import { firebaseConfig, isFirebaseConfigured } from '@/config/env'
import { AppError } from '@/services/errors'

let appPromise: Promise<FirebaseApp> | null = null
let authPromise: Promise<Auth> | null = null
let dbPromise: Promise<Firestore> | null = null

function assertConfigured(): void {
  if (!isFirebaseConfigured) {
    throw new AppError('backend-unconfigured')
  }
}

export async function getFirebaseApp(): Promise<FirebaseApp> {
  assertConfigured()
  if (!appPromise) {
    appPromise = (async () => {
      const { initializeApp, getApps, getApp } = await import('firebase/app')
      return getApps().length > 0 ? getApp() : initializeApp(firebaseConfig)
    })()
  }
  return appPromise
}

/** Firebase Authentication — email/password provider (Phase 2). */
export async function getFirebaseAuth(): Promise<Auth> {
  if (!authPromise) {
    authPromise = (async () => {
      const [{ getAuth }, app] = await Promise.all([
        import('firebase/auth'),
        getFirebaseApp(),
      ])
      return getAuth(app)
    })()
  }
  return authPromise
}

/** Cloud Firestore — leaderboard and profile data (Phase 2). */
export async function getFirestoreDb(): Promise<Firestore> {
  if (!dbPromise) {
    dbPromise = (async () => {
      const [{ getFirestore }, app] = await Promise.all([
        import('firebase/firestore'),
        getFirebaseApp(),
      ])
      return getFirestore(app)
    })()
  }
  return dbPromise
}

/**
 * Firebase Storage is NOT imported in Phase 1.
 *
 * Cloud Storage for Firebase has required the Blaze (billing) plan since
 * 3 February 2026, so it is not part of the zero-cost baseline. Phase 2 will
 * either (a) store compressed images as Firestore data (free Spark quota) or
 * (b) use Storage only after the owner explicitly enables billing. See
 * docs/FREE_TIER.md.
 */
export const storageNote =
  'Firebase Storage requires the Blaze plan since 3 February 2026 and is not enabled in this project.'
