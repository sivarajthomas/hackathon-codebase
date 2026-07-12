import { useEffect, useState } from 'react'
import { Routes, Route, useLocation } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import Home from './pages/Home'
import AgentPage from './pages/AgentPage'
import Navbar from './components/ui/Navbar'
import Loader from './components/ui/Loader'
import { TransitionProvider } from './components/ui/TransitionProvider'
import { useSmoothScroll } from './hooks/useSmoothScroll'

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
          path="/"
          element={
            <Page>
              <Home />
            </Page>
          }
        />
        <Route
          path="/agent/:slug"
          element={
            <Page>
              <AgentPage />
            </Page>
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
      {!isAgentPage && <Navbar />}
      <AnimatedRoutes />
    </TransitionProvider>
  )
}
