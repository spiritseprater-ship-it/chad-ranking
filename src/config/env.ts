/**
 * Environment helpers.
 *
 * Only `VITE_*` values are exposed to the browser. Firebase web config is
 * public by design; security depends on Firestore/Storage rules and the
 * trusted backend, never on hiding these values.
 */

const value = (key: keyof ImportMetaEnv): string =>
  (import.meta.env[key] ?? '').trim()

export const firebaseConfig = {
  apiKey: value('VITE_FIREBASE_API_KEY'),
  authDomain: value('VITE_FIREBASE_AUTH_DOMAIN'),
  projectId: value('VITE_FIREBASE_PROJECT_ID'),
  storageBucket: value('VITE_FIREBASE_STORAGE_BUCKET'),
  messagingSenderId: value('VITE_FIREBASE_MESSAGING_SENDER_ID'),
  appId: value('VITE_FIREBASE_APP_ID'),
} as const

export const isFirebaseConfigured =
  firebaseConfig.apiKey.length > 0 &&
  firebaseConfig.projectId.length > 0 &&
  firebaseConfig.appId.length > 0

/** Sample data is opt-in and never used when Firebase is configured. */
export const isDemoPreviewEnabled =
  value('VITE_ENABLE_DEMO_PREVIEW').toLowerCase() === 'true'

export const basePath = import.meta.env.BASE_URL

/** React Router basename (no trailing slash). */
export const routerBasename = basePath.replace(/\/$/, '') || '/'

export const isDev = import.meta.env.DEV

export const appVersion = '0.1.0-phase1'
