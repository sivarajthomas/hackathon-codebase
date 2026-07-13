import { useEffect } from 'react'
import { useParams, Navigate } from 'react-router-dom'
import { getAgent } from '../data/agents'
import VideoBackground from '../components/sections/VideoBackground'
import ChatPanel from '../components/chat/ChatPanel'
import { useAuth } from '../hooks/useAuth'

// Full-screen, app-like environment for a single agent: a subtle looping
// logistics background behind a large sidebar + conversation workspace.
export default function AgentPage() {
  const { slug } = useParams()
  const agent = getAgent(slug)
  const { allowedAgents } = useAuth()

  useEffect(() => {
    window.__lenis?.scrollTo(0, { immediate: true })
  }, [slug])

  if (!agent) return <Navigate to="/" replace />
  // Enforce role-based agent visibility (e.g. customers cannot open Prevent).
  if (allowedAgents && allowedAgents.length && !allowedAgents.includes(agent.slug)) {
    return <Navigate to="/" replace />
  }

  return (
    <div className="relative h-[100dvh] w-full overflow-hidden">
      <VideoBackground agent={agent} />
      <div className="relative z-10 h-full">
        <ChatPanel agent={agent} />
      </div>
    </div>
  )
}

