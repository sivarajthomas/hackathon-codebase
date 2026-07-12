import { Suspense, useRef, useState } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { AdaptiveDpr, AdaptiveEvents, Environment, PerformanceMonitor } from '@react-three/drei'
import * as THREE from 'three'
import ParticleField from './ParticleField'
import LogisticsNetwork from './LogisticsNetwork'
import FloatingGlass from './FloatingGlass'
import LightBeams from './LightBeams'
import Effects from './Effects'
import { useMousePosition } from '../../hooks/useMousePosition'

// Camera rig: eases toward a target driven by scroll progress (0..1) and the
// mouse for parallax. Scroll advances the "camera journey" through the scene.
function CameraRig({ scrollRef, mouse }) {
  const { camera } = useThree()
  const target = useRef(new THREE.Vector3())

  useFrame(() => {
    const p = scrollRef?.current ?? 0
    const m = mouse.current

    // Journey path: dolly forward + drift down/side as user scrolls.
    const tx = m.x * 1.2 + Math.sin(p * Math.PI) * 0.8
    const ty = m.y * 0.8 - p * 1.6
    const tz = 7 - p * 3.5

    target.current.set(tx, ty, tz)
    camera.position.lerp(target.current, 0.05)
    camera.lookAt(0, -p * 1.2, -2)
  })

  return null
}

function SceneContents({ scrollRef, quality, setQuality }) {
  const { ref: mouse } = useMousePosition()

  return (
    <>
      <PerformanceMonitor
        onDecline={() => setQuality('low')}
        onIncline={() => setQuality('high')}
      />
      <color attach="background" args={['#0c0a09']} />
      <fog attach="fog" args={['#0c0a09', 8, 24]} />

      <ambientLight intensity={0.4} />
      <pointLight position={[6, 4, 4]} intensity={40} color="#ffb500" />
      <pointLight position={[-6, -2, 2]} intensity={30} color="#3d7bff" />
      <pointLight position={[0, 3, -6]} intensity={20} color="#ff8a3d" />

      <CameraRig scrollRef={scrollRef} mouse={mouse} />
      <ParticleField count={quality === 'low' ? 600 : 1200} mouse={mouse} />
      <LogisticsNetwork mouse={mouse} quality={quality} />
      <LightBeams />

      <Suspense fallback={null}>
        <FloatingGlass mouse={mouse} />
        <Environment preset="night" />
      </Suspense>

      <Effects quality={quality} />
      <AdaptiveDpr pixelated />
      <AdaptiveEvents />
    </>
  )
}

// Fixed full-viewport canvas that sits behind all page content.
export default function Scene({ scrollRef }) {
  const [quality, setQuality] = useState('high')

  return (
    <div className="fixed inset-0 z-0">
      <Canvas
        dpr={[1, 1.8]}
        gl={{
          antialias: false,
          powerPreference: 'high-performance',
          alpha: false,
          stencil: false,
        }}
        camera={{ position: [0, 0, 7], fov: 50, near: 0.1, far: 40 }}
      >
        <SceneContents scrollRef={scrollRef} quality={quality} setQuality={setQuality} />
      </Canvas>
      {/* Vignette + gradient wash to marry the canvas with the UI. */}
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_30%,transparent_40%,rgba(12,10,9,0.65)_100%)]" />
    </div>
  )
}
