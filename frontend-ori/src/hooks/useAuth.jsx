import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { login as apiLogin, getMe } from '../lib/api'

// Persisted auth session: JWT + user profile (role, allowed agents).
const STORAGE_KEY = 'ii_auth'

const AuthContext = createContext(null)

function readSession() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function writeSession(session) {
  try {
    if (session) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(session))
      // Back-compat marker used by older guards.
      localStorage.setItem('ii_user', JSON.stringify({ userId: session.user?.username, at: Date.now() }))
    } else {
      localStorage.removeItem(STORAGE_KEY)
      localStorage.removeItem('ii_user')
    }
  } catch {
    /* ignore storage failures (private mode, etc.) */
  }
}

export function AuthProvider({ children }) {
  const [session, setSession] = useState(() => readSession())

  useEffect(() => {
    writeSession(session)
  }, [session])

  // Revalidate the token on boot; drop the session if it has expired.
  useEffect(() => {
    if (!session?.token) return
    let alive = true
    getMe()
      .then((me) => {
        if (alive && me) setSession((s) => (s ? { ...s, user: { ...s.user, ...me } } : s))
      })
      .catch(() => {
        if (alive) setSession(null)
      })
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const value = useMemo(
    () => ({
      token: session?.token || null,
      user: session?.user || null,
      role: session?.user?.role || null,
      allowedAgents: session?.user?.allowed_agents || [],
      isAuthenticated: !!session?.token,
      async login(username, password) {
        const data = await apiLogin(username, password)
        setSession({ token: data.access_token, user: data.user })
        return data.user
      },
      logout() {
        setSession(null)
      },
    }),
    [session],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider')
  return ctx
}

// Read the current bearer token outside React (used by the API client).
export function getStoredToken() {
  return readSession()?.token || null
}
