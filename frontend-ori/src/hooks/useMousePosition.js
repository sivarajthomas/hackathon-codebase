import { useEffect, useRef, useState } from 'react'

// Tracks normalized mouse position (-1..1) for parallax effects.
// Uses a ref for high-frequency reads (e.g. inside R3F frame loops) and
// optional state for React-driven components.
export function useMousePosition({ withState = false } = {}) {
  const ref = useRef({ x: 0, y: 0 })
  const [pos, setPos] = useState({ x: 0, y: 0 })

  useEffect(() => {
    const handle = (e) => {
      const x = (e.clientX / window.innerWidth) * 2 - 1
      const y = -((e.clientY / window.innerHeight) * 2 - 1)
      ref.current = { x, y }
      if (withState) setPos({ x, y })
    }
    window.addEventListener('mousemove', handle, { passive: true })
    return () => window.removeEventListener('mousemove', handle)
  }, [withState])

  return { ref, pos }
}
