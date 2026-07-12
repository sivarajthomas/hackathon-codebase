import { useEffect, useRef } from 'react'
import { motion } from 'framer-motion'
import MagneticButton from '../ui/MagneticButton'

const container = {
  hidden: {},
  show: {
    transition: { staggerChildren: 0.1, delayChildren: 0.4 },
  },
}

const item = {
  hidden: { opacity: 0, y: 40, filter: 'blur(12px)' },
  show: {
    opacity: 1,
    y: 0,
    filter: 'blur(0px)',
    transition: { duration: 1, ease: [0.22, 1, 0.36, 1] },
  },
}

export default function Hero() {
  const videoRef = useRef(null)

  const scrollToAgents = () => {
    window.__lenis?.scrollTo('#agents', { duration: 1.6 })
  }

  // Play the hero video with sound once, then mute it. Browsers block
  // unmuted autoplay, so we try immediately and fall back to unmuting on the
  // first user interaction — after one pass the audio mutes automatically.
  useEffect(() => {
    const v = videoRef.current
    if (!v) return
    let done = false
    let muteTimer

    const playOnceWithSound = () => {
      if (done || !videoRef.current) return
      done = true
      const el = videoRef.current
      el.muted = false
      el.volume = 1
      el.play().catch(() => {})
      const dur = Number.isFinite(el.duration) && el.duration > 0 ? el.duration : 8
      const remaining = Math.max(1, dur - el.currentTime)
      muteTimer = setTimeout(() => {
        if (videoRef.current) videoRef.current.muted = true
      }, remaining * 1000 + 200)
      window.removeEventListener('pointerdown', playOnceWithSound)
      window.removeEventListener('keydown', playOnceWithSound)
    }

    // Attempt straight away (works if the browser allows it)…
    v.muted = false
    v.play().then(() => playOnceWithSound()).catch(() => {
      // …otherwise stay muted-autoplay and wait for the first interaction.
      v.muted = true
      v.play().catch(() => {})
      window.addEventListener('pointerdown', playOnceWithSound, { once: true })
      window.addEventListener('keydown', playOnceWithSound, { once: true })
    })

    return () => {
      clearTimeout(muteTimer)
      window.removeEventListener('pointerdown', playOnceWithSound)
      window.removeEventListener('keydown', playOnceWithSound)
    }
  }, [])

  return (
    <section className="relative flex min-h-screen flex-col items-center px-4 pb-16 pt-24 text-center">
      {/* Cinematic looping hero video — 16:9 card so it fills with no cropping */}
      <div className="relative z-0 aspect-video w-full max-w-6xl overflow-hidden rounded-[2rem] shadow-[0_25px_70px_-30px_rgba(43,24,16,0.5)]">
        <video
          ref={videoRef}
          className="h-full w-full rounded-[2rem] object-cover"
          autoPlay
          muted
          loop
          playsInline
          preload="auto"
        >
          <source src="/hero.mp4" type="video/mp4" />
        </video>
      </div>

      {/* Primary action below the video */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, delay: 0.6, ease: [0.22, 1, 0.36, 1] }}
        className="relative z-10 mt-10"
      >
        <MagneticButton
          onClick={scrollToAgents}
          className="group rounded-full bg-brand-gold px-8 py-4 text-sm font-semibold text-brand-brownDeep shadow-glow transition-shadow hover:shadow-glow-violet"
        >
          Explore Agents
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="transition-transform group-hover:translate-x-0.5">
            <path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </MagneticButton>
      </motion.div>

      {/* Scroll cue */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1.6, duration: 1 }}
        className="absolute bottom-8 left-1/2 -translate-x-1/2"
      >
        <div className="flex flex-col items-center gap-2 text-brand-brown/50">
          <span className="text-[10px] uppercase tracking-[0.3em]">Scroll</span>
          <span className="flex h-9 w-5 items-start justify-center rounded-full border border-brand-brown/25 p-1">
            <motion.span
              animate={{ y: [0, 10, 0] }}
              transition={{ duration: 1.8, repeat: Infinity, ease: 'easeInOut' }}
              className="h-1.5 w-1.5 rounded-full bg-brand-gold"
            />
          </span>
        </div>
      </motion.div>
    </section>
  )
}
