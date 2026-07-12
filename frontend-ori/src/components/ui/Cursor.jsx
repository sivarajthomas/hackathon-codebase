import { useEffect, useRef, useState } from 'react'

// Custom cinematic cursor: a soft glowing dot with a trailing ring that
// enlarges over interactive elements. Hidden on touch devices via CSS.
export default function Cursor() {
  const dotRef = useRef(null)
  const ringRef = useRef(null)
  const [hidden, setHidden] = useState(false)

  useEffect(() => {
    // Skip on coarse pointers (touch).
    if (window.matchMedia('(hover: none)').matches) {
      setHidden(true)
      return
    }

    const dot = dotRef.current
    const ring = ringRef.current
    let mouseX = window.innerWidth / 2
    let mouseY = window.innerHeight / 2
    let ringX = mouseX
    let ringY = mouseY
    let raf

    const onMove = (e) => {
      mouseX = e.clientX
      mouseY = e.clientY
      dot.style.transform = `translate3d(${mouseX}px, ${mouseY}px, 0) translate(-50%, -50%)`
    }

    const loop = () => {
      ringX += (mouseX - ringX) * 0.18
      ringY += (mouseY - ringY) * 0.18
      ring.style.transform = `translate3d(${ringX}px, ${ringY}px, 0) translate(-50%, -50%)`
      raf = requestAnimationFrame(loop)
    }
    loop()

    const setHover = (state) => () => ring.classList.toggle('cursor-hover', state)
    const interactive = 'a, button, [data-cursor="hover"], input, textarea'

    const onOver = (e) => {
      if (e.target.closest(interactive)) ring.classList.add('cursor-hover')
    }
    const onOut = (e) => {
      if (e.target.closest(interactive)) ring.classList.remove('cursor-hover')
    }

    window.addEventListener('mousemove', onMove, { passive: true })
    document.addEventListener('mouseover', onOver)
    document.addEventListener('mouseout', onOut)

    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseover', onOver)
      document.removeEventListener('mouseout', onOut)
    }
  }, [])

  if (hidden) return null

  return (
    <>
      <div
        ref={dotRef}
        className="pointer-events-none fixed left-0 top-0 z-[100] h-1.5 w-1.5 rounded-full bg-white mix-blend-difference"
      />
      <div
        ref={ringRef}
        className="cursor-ring pointer-events-none fixed left-0 top-0 z-[99] h-8 w-8 rounded-full border border-white/40 transition-[width,height,background-color,border-color] duration-300 ease-out"
        style={{ boxShadow: '0 0 20px rgba(255,181,0,0.25)' }}
      />
      <style>{`
        .cursor-ring.cursor-hover {
          width: 3.5rem;
          height: 3.5rem;
          background: rgba(255,181,0,0.08);
          border-color: rgba(255,181,0,0.6);
        }
      `}</style>
    </>
  )
}
