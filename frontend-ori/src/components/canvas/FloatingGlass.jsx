import { useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import { Float, MeshTransmissionMaterial, RoundedBox } from '@react-three/drei'
import * as THREE from 'three'

// A cluster of floating glass panels/holograms that catch light and refract
// the scene. Kept lightweight: few meshes, moderate transmission samples.
function GlassPanel({ position, rotation, scale, color, mouse }) {
  const ref = useRef(null)

  useFrame((state) => {
    if (!ref.current) return
    const m = mouse?.current || { x: 0, y: 0 }
    ref.current.rotation.y +=
      (rotation[1] + m.x * 0.3 - ref.current.rotation.y) * 0.03
    ref.current.rotation.x +=
      (rotation[0] + m.y * 0.2 - ref.current.rotation.x) * 0.03
  })

  return (
    <Float speed={1.4} rotationIntensity={0.4} floatIntensity={0.8}>
      <RoundedBox
        ref={ref}
        args={[1.6, 2.2, 0.06]}
        radius={0.12}
        smoothness={6}
        position={position}
        rotation={rotation}
        scale={scale}
      >
        <MeshTransmissionMaterial
          samples={4}
          resolution={256}
          thickness={0.6}
          roughness={0.12}
          transmission={1}
          ior={1.3}
          chromaticAberration={0.06}
          anisotropy={0.2}
          distortion={0.2}
          distortionScale={0.3}
          temporalDistortion={0.1}
          color={color}
          attenuationColor={color}
          attenuationDistance={2}
          background={new THREE.Color('#05060a')}
        />
      </RoundedBox>
    </Float>
  )
}

export default function FloatingGlass({ mouse }) {
  return (
    <group>
      <GlassPanel
        position={[-3.4, 0.4, -1]}
        rotation={[0.1, 0.4, 0.05]}
        scale={0.9}
        color="#ffd77a"
        mouse={mouse}
      />
      <GlassPanel
        position={[3.6, -0.6, -2]}
        rotation={[-0.1, -0.5, -0.08]}
        scale={1.05}
        color="#8fb4ff"
        mouse={mouse}
      />
      <GlassPanel
        position={[0.6, 1.6, -3.5]}
        rotation={[0.2, 0.1, 0.12]}
        scale={0.7}
        color="#ffffff"
        mouse={mouse}
      />
    </group>
  )
}
