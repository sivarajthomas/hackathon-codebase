import { useEffect, useState } from 'react'
import { Routes, Route, useLocation, Navigate } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import Home from './pages/Home'
import AgentPage from './pages/AgentPage'
import Login from './pages/Login'
import Navbar from './components/ui/Navbar'
import Loader from './components/ui/Loader'
import { TransitionProvider } from './components/ui/TransitionProvider'
import { useSmoothScroll } from './hooks/useSmoothScroll'

// True when a login session exists in local storage.
function isAuthenticated() {
  try {
    return !!localStorage.getItem('ii_user')
  } catch {
    return false
  }
}

// Gate protected pages: send unauthenticated visitors to the login screen.
function RequireAuth({ children }) {
  return isAuthenticated() ? children : <Navigate to="/login" replace />
}

// Fade wrapper for route content so navigation never feels abrupt.
function Page({ children }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.5, ease: 'easeInOut' }}
    >
      {children}
    </motion.div>
  )
}

function AnimatedRoutes() {
  const location = useLocation()
  return (
    <AnimatePresence mode="wait">
      <Routes location={location} key={location.pathname}>
        <Route
          path="/login"
          element={
            <Page>
              <Login />
            </Page>
          }
        />
        <Route
          path="/"
          element={
            <RequireAuth>
              <Page>
                <Home />
              </Page>
            </RequireAuth>
          }
        />
        <Route
          path="/agent/:slug"
          element={
            <RequireAuth>
              <Page>
                <AgentPage />
              </Page>
            </RequireAuth>
          }
        />
      </Routes>
    </AnimatePresence>
  )
}

export default function App() {
  useSmoothScroll()
  const { pathname } = useLocation()
  const isAgentPage = pathname.startsWith('/agent')
  const isLoginPage = pathname.startsWith('/login')
  const [booting, setBooting] = useState(true)
  const [progress, setProgress] = useState(0)

  useEffect(() => {
    // Simulated boot progress; resolves on window load or a max timeout.
    let p = 0
    const interval = setInterval(() => {
      p = Math.min(95, p + Math.random() * 18)
      setProgress(p)
    }, 160)

    const finish = () => {
      clearInterval(interval)
      setProgress(100)
      setTimeout(() => setBooting(false), 500)
    }

    if (document.readyState === 'complete') {
      setTimeout(finish, 700)
    } else {
      window.addEventListener('load', finish, { once: true })
      // Safety net so we never hang on the loader.
      setTimeout(finish, 3500)
    }

    return () => clearInterval(interval)
  }, [])

  return (
    <TransitionProvider>
      <div className="noise-overlay" aria-hidden />
      <AnimatePresence>{booting && <Loader progress={progress} />}</AnimatePresence>
      {!isAgentPage && !isLoginPage && <Navbar />}
      <AnimatedRoutes />
    </TransitionProvider>
  )
}
