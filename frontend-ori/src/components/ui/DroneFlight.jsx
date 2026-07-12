import { useEffect, useState } from 'react'
import { motion, useAnimationControls } from 'framer-motion'

// A courier drone that launches the instant an agent card is clicked. It rises
// out of the card, carries across the page transition, hovers over the prompt
// box while dropping the instruction one bold-black letter at a time, then
// glides to the send button and disappears. It lives in the TransitionProvider
// so it survives the route change from the landing page to the agent page.
export default function DroneFlight({ origin, accent = '#ffb500', text, promptRef, onComplete }) {
  const controls = useAnimationControls()
  const [letters, setLetters] = useState([]) // { id, char, fromX, fromY, toX, toY }
  const [fade, setFade] = useState(false)

  useEffect(() => {
    let cancelled = false
    const wait = (ms) => new Promise((r) => setTimeout(r, ms))

    // Wait until the destination prompt box + send button exist in the DOM.
    const waitForTargets = async () => {
      for (let i = 0; i < 100; i++) {
        if (cancelled) return null
        const p = promptRef.current
        const inputEl = p?.inputEl
        const sendEl = p?.sendEl
        if (inputEl && sendEl && inputEl.getBoundingClientRect().width > 0) return p
        await wait(50)
      }
      return promptRef.current
    }

    const run = async () => {
      // 1. Pop out of the clicked card, small and glowing.
      await controls.set({ x: origin.x - 28, y: origin.y - 22, opacity: 0, scale: 0.3, rotate: -10 })
      if (cancelled) return
      await controls.start({
        opacity: 1,
        scale: 0.7,
        y: origin.y - 90,
        transition: { duration: 0.5, ease: [0.22, 1, 0.36, 1] },
      })

      // 2. Wait for the agent page to mount behind the transition overlay.
      const targets = await waitForTargets()
      if (cancelled) return
      if (!targets?.inputEl || !targets?.sendEl) {
        targets?.setPlaceholder?.(text)
        onComplete?.()
        return
      }

      const input = targets.inputEl.getBoundingClientRect()
      const btn = targets.sendEl.getBoundingClientRect()
      const hoverX = input.left + 10
      const hoverY = input.top - 78
      const dropFromY = hoverY + 34
      const lineY = input.top + input.height / 2 - 9
      const startTextX = input.left + 20
      const charW = 7.9
      const charX = (i) => startTextX + i * charW

      // 3. Fly to hover above the prompt box.
      await controls.start({
        x: hoverX,
        y: hoverY,
        scale: 1,
        rotate: 0,
        transition: { duration: 0.9, ease: [0.22, 1, 0.36, 1] },
      })
      if (cancelled) return

      // Clear the box's default placeholder so it doesn't sit behind the
      // incoming bold letters.
      targets.onWriteStart?.()

      // 4. Split the instruction into a few parcels. The drone drops each one;
      //    it bursts open and the letters inside jump into place, so the whole
      //    sentence comes together from just 3-4 packages.
      const chars = text.split('')
      const parcelCount = Math.min(4, Math.max(3, Math.ceil(chars.length / 9)))
      const perParcel = Math.ceil(chars.length / parcelCount)

      for (let k = 0; k < parcelCount; k++) {
        if (cancelled) return
        const start = k * perParcel
        if (start >= chars.length) break
        const end = Math.min(start + perParcel, chars.length)
        const groupLetters = []
        for (let i = start; i < end; i++) groupLetters.push({ char: chars[i], toX: charX(i) })

        const midX = charX((start + end) / 2)
        const dropX = Math.max(startTextX, midX + (Math.random() * 40 - 20))
        const droneX = Math.min(Math.max(dropX - 14, input.left), input.right - 60)

        // Fly above the drop point, then release the parcel.
        await controls.start({
          x: droneX,
          y: hoverY,
          transition: { duration: 0.4, ease: [0.22, 1, 0.36, 1] },
        })
        if (cancelled) return
        setLetters((prev) => [
          ...prev,
          {
            id: `p${k}`,
            fromX: droneX + 20,
            fromY: dropFromY,
            dropX,
            toY: lineY,
            letters: groupLetters,
          },
        ])
        await wait(300)
      }

      // 5. Let the last parcel burst and its letters settle, then hand the
      //    text to the input box.
      await wait(950)
      if (cancelled) return
      targets.setPlaceholder?.(text)
      setFade(true)

      // 6. Glide to the send button and dive in.
      await controls.start({
        x: btn.left + btn.width / 2 - 26,
        y: btn.top - 48,
        rotate: 8,
        transition: { duration: 0.7, ease: [0.65, 0, 0.35, 1] },
      })
      if (cancelled) return
      await controls.start({
        x: btn.left + btn.width / 2 - 26,
        y: btn.top - 14,
        scale: 0.2,
        opacity: 0,
        transition: { duration: 0.45, ease: 'easeIn' },
      })
      onComplete?.()
    }

    run()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <>
      {/* Parcels dropped by the drone: each falls, bursts, and its letter
          converges into place to spell out the instruction. */}
      <motion.div
        className="pointer-events-none fixed inset-0 z-[190]"
        animate={{ opacity: fade ? 0 : 1 }}
        transition={{ duration: 0.3 }}
      >
        {letters.map((l) => (
          <Parcel key={l.id} {...l} accent={accent} />
        ))}
      </motion.div>

      {/* The drone itself */}
      <motion.div
        className="pointer-events-none fixed left-0 top-0 z-[200]"
        animate={controls}
        initial={{ opacity: 0 }}
        style={{ willChange: 'transform' }}
        aria-hidden="true"
      >
        <motion.div
          animate={{ y: [0, -3, 0] }}
          transition={{ duration: 1.4, repeat: Infinity, ease: 'easeInOut' }}
        >
          <svg width="56" height="44" viewBox="0 0 56 44" fill="none">
            <ellipse cx="28" cy="30" rx="16" ry="4" fill={accent} opacity="0.18" />
            <line x1="18" y1="18" x2="8" y2="10" stroke="#2b1810" strokeWidth="2" strokeLinecap="round" />
            <line x1="38" y1="18" x2="48" y2="10" stroke="#2b1810" strokeWidth="2" strokeLinecap="round" />
            <motion.g
              style={{ originX: '8px', originY: '10px' }}
              animate={{ rotate: 360 }}
              transition={{ duration: 0.18, repeat: Infinity, ease: 'linear' }}
            >
              <ellipse cx="8" cy="10" rx="9" ry="2.4" fill={accent} opacity="0.55" />
            </motion.g>
            <motion.g
              style={{ originX: '48px', originY: '10px' }}
              animate={{ rotate: -360 }}
              transition={{ duration: 0.18, repeat: Infinity, ease: 'linear' }}
            >
              <ellipse cx="48" cy="10" rx="9" ry="2.4" fill={accent} opacity="0.55" />
            </motion.g>
            <rect x="18" y="14" width="20" height="12" rx="6" fill="#2b1810" />
            <circle cx="28" cy="20" r="3" fill={accent} />
            <g>
              <rect x="23" y="27" width="10" height="7" rx="1.4" fill="#fff" stroke={accent} strokeWidth="1" />
              <path d="M23.4 27.6l4.6 3 4.6-3" stroke={accent} strokeWidth="1" fill="none" strokeLinecap="round" />
            </g>
          </svg>
        </motion.div>
      </motion.div>
    </>
  )
}

// One dropped parcel: it falls to a scattered spot, bursts open with a few
// shards, then the group of letters inside jumps into place to help assemble
// the full sentence.
function Parcel({ fromX, fromY, dropX, toY, letters, accent }) {
  const [phase, setPhase] = useState('fall') // 'fall' | 'break' | 'letters'

  useEffect(() => {
    const t1 = setTimeout(() => setPhase('break'), 440)
    const t2 = setTimeout(() => setPhase('letters'), 640)
    return () => {
      clearTimeout(t1)
      clearTimeout(t2)
    }
  }, [])

  // Shards for the burst, spread out in a small radial pattern.
  const shards = [
    { dx: -16, dy: -14 },
    { dx: 16, dy: -12 },
    { dx: -12, dy: 14 },
    { dx: 14, dy: 14 },
    { dx: 0, dy: -20 },
    { dx: -20, dy: 2 },
  ]

  return (
    <>
      {/* Falling parcel */}
      {phase === 'fall' && (
        <motion.div
          className="fixed left-0 top-0 select-none"
          initial={{ x: fromX, y: fromY, opacity: 0, scale: 0.5, rotate: -30 }}
          animate={{
            x: dropX,
            y: toY - 2,
            opacity: 1,
            scale: 1,
            rotate: 16,
            transition: { duration: 0.44, ease: [0.5, 0, 0.9, 0.4] },
          }}
        >
          <svg width="26" height="23" viewBox="0 0 26 23" fill="none">
            <rect x="1" y="6" width="24" height="16" rx="2" fill="#c8894a" />
            <rect x="1" y="6" width="24" height="5" rx="2" fill="#a86a34" />
            <rect x="10" y="6" width="6" height="16" fill={accent} opacity="0.85" />
            <path d="M1 8.5h24" stroke={accent} strokeWidth="1.4" opacity="0.85" />
          </svg>
        </motion.div>
      )}

      {/* Burst shards */}
      {phase === 'break' &&
        shards.map((s, i) => (
          <motion.span
            key={i}
            className="fixed left-0 top-0 rounded-[1px]"
            style={{ width: 5, height: 5, background: i % 2 ? accent : '#c8894a' }}
            initial={{ x: dropX + 10, y: toY + 2, opacity: 1, scale: 1 }}
            animate={{
              x: dropX + 10 + s.dx,
              y: toY + 2 + s.dy,
              opacity: 0,
              scale: 0.3,
              rotate: 140,
              transition: { duration: 0.26, ease: 'easeOut' },
            }}
          />
        ))}

      {/* Letters jumping out of the parcel into their final places */}
      {phase === 'letters' &&
        letters.map((l, i) => (
          <motion.span
            key={i}
            className="fixed left-0 top-0 select-none font-bold text-black"
            style={{ fontSize: 14, whiteSpace: 'pre' }}
            initial={{ x: dropX + 8, y: toY, opacity: 0, scale: 1.6 }}
            animate={{
              x: l.toX,
              y: [toY, toY - 26, toY],
              opacity: [0, 1, 1],
              scale: [1.6, 1.1, 1],
              transition: { duration: 0.5, delay: i * 0.045, ease: [0.34, 1.3, 0.64, 1] },
            }}
          >
            {l.char}
          </motion.span>
        ))}
    </>
  )
}
