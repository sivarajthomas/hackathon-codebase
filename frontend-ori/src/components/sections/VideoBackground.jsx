import { useState } from 'react'

// Full-screen looping background for an agent page. Attempts to autoplay a
// muted, looping video from /videos/{slug}.mp4. If none exists (as in this
// starter), it gracefully falls back to an animated gradient + ambient blobs
// so the page always looks alive. Drop real MP4s into /public/videos to enable.
export default function VideoBackground({ agent }) {
  const [videoOk, setVideoOk] = useState(true)

  return (
    <div className="fixed inset-0 -z-0 bg-[#faf7f2]">
      {videoOk && (
        <video
          className="h-full w-full object-cover opacity-30"
          autoPlay
          muted
          loop
          playsInline
          preload="metadata"
          onError={() => setVideoOk(false)}
        >
          <source src={`/videos/${agent.slug}.mp4`} type="video/mp4" />
        </video>
      )}

      {/* Soft accent wash in the agent color (light theme). */}
      <div
        className="absolute left-[8%] top-[10%] h-[40vmax] w-[40vmax] animate-float rounded-full opacity-20 blur-[130px]"
        style={{ background: agent.accent }}
      />
      <div
        className="absolute right-[4%] bottom-[8%] h-[34vmax] w-[34vmax] animate-float rounded-full opacity-15 blur-[130px]"
        style={{ background: agent.accent, animationDelay: '2s' }}
      />

      {/* Subtle grid + white wash to keep the chat crisp and legible. */}
      <div className="absolute inset-0 bg-grid-lines [background-size:60px_60px] opacity-[0.5]" />
      <div className="absolute inset-0 bg-gradient-to-b from-white/70 via-white/60 to-white/80" />
    </div>
  )
}
