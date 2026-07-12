import { useMemo, useRef } from 'react'
import { motion } from 'framer-motion'

// A button that magnetically follows the cursor when hovered, then springs
// back. Works for both <button> and <a>/router links via `as`.
export default function MagneticButton({
  children,
  className = '',
  strength = 0.35,
  as: Comp = 'button',
  ...props
}) {
  const ref = useRef(null)
  const inner = useRef(null)

  const handleMove = (e) => {
    const el = ref.current
    if (!el) return
    const rect = el.getBoundingClientRect()
    const x = e.clientX - rect.left - rect.width / 2
    const y = e.clientY - rect.top - rect.height / 2
    el.style.transform = `translate(${x * strength}px, ${y * strength}px)`
    if (inner.current) {
      inner.current.style.transform = `translate(${x * strength * 0.4}px, ${y * strength * 0.4}px)`
    }
  }

  const reset = () => {
    const el = ref.current
    if (el) el.style.transform = 'translate(0,0)'
    if (inner.current) inner.current.style.transform = 'translate(0,0)'
  }

  const MotionComp = useMemo(() => motion(Comp), [Comp])

  return (
    <MotionComp
      ref={ref}
      onMouseMove={handleMove}
      onMouseLeave={reset}
      className={`relative inline-flex items-center justify-center transition-transform duration-300 ease-out ${className}`}
      data-cursor="hover"
      {...props}
    >
      <span ref={inner} className="inline-flex items-center gap-2 transition-transform duration-300 ease-out">
        {children}
      </span>
    </MotionComp>
  )
}
