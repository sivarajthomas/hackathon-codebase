import { useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'

// Vertical animated light beams that sweep and pulse to add cinematic depth.
function Beam({ position, color, speed = 1, height = 18 }) {
  const ref = useRef(null)
  const mat = useMemo(
    () =>
      new THREE.ShaderMaterial({
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
        side: THREE.DoubleSide,
        uniforms: {
          uTime: { value: 0 },
          uColor: { value: new THREE.Color(color) },
        },
        vertexShader: /* glsl */ `
          varying vec2 vUv;
          void main() {
            vUv = uv;
            gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
          }
        `,
        fragmentShader: /* glsl */ `
          uniform float uTime;
          uniform vec3 uColor;
          varying vec2 vUv;
          void main() {
            float edge = smoothstep(0.5, 0.0, abs(vUv.x - 0.5));
            float vertical = smoothstep(0.0, 0.3, vUv.y) * smoothstep(1.0, 0.6, vUv.y);
            float pulse = 0.6 + 0.4 * sin(uTime * ${speed.toFixed(2)} + vUv.y * 6.0);
            float a = edge * vertical * pulse * 0.5;
            gl_FragColor = vec4(uColor, a);
          }
        `,
      }),
    [color, speed]
  )

  useFrame((state) => {
    mat.uniforms.uTime.value = state.clock.elapsedTime
    if (ref.current) {
      ref.current.rotation.z = Math.sin(state.clock.elapsedTime * 0.1 * speed) * 0.08
    }
  })

  return (
    <mesh ref={ref} position={position} material={mat}>
      <planeGeometry args={[1.4, height]} />
    </mesh>
  )
}

export default function LightBeams() {
  return (
    <group position={[0, 0, -6]}>
      <Beam position={[-5, 0, 0]} color="#ffb500" speed={0.8} />
      <Beam position={[0, 0, -2]} color="#3d7bff" speed={1.2} height={22} />
      <Beam position={[5, 0, -1]} color="#ff8a3d" speed={0.6} />
    </group>
  )
}
