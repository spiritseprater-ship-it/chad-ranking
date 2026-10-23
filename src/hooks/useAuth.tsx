import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { services } from '@/services'
import type { AuthSnapshot, CurrentUser } from '@/types/domain'

interface AuthContextValue extends AuthSnapshot {
  signUp: (input: {
    username: string
    email: string
    password: string
  }) => Promise<CurrentUser>
  signIn: (input: { identifier: string; password: string }) => Promise<CurrentUser>
  signOut: () => Promise<void>
  isAdmin: boolean
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [snapshot, setSnapshot] = useState<AuthSnapshot>({
    status: 'loading',
    user: null,
  })

  useEffect(() => {
    let active = true
    const unsubscribe = services.auth.subscribe((next) => {
      if (active) setSnapshot(next)
    })
    return () => {
      active = false
      unsubscribe()
    }
  }, [])

  const signUp = useCallback(
    async (input: { username: string; email: string; password: string }) =>
      services.auth.signUp(input),
    [],
  )
  const signIn = useCallback(
    async (input: { identifier: string; password: string }) =>
      services.auth.signIn(input),
    [],
  )
  const signOut = useCallback(async () => {
    await services.auth.signOut()
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      ...snapshot,
      signUp,
      signIn,
      signOut,
      isAdmin: snapshot.user?.role === 'admin',
    }),
    [snapshot, signUp, signIn, signOut],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used inside <AuthProvider>')
  }
  return context
}
