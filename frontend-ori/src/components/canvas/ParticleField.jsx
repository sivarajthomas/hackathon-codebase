import { useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'

// A large depth-distributed field of ambient "data dust" — subtle gold + blue
// motes that read as flowing logistics telemetry. Responds to the shared mouse
// ref for parallax.
export default function ParticleField({ count = 1200, mouse }) {
  const points = useRef(null)

  const { positions, sizes, phases } = useMemo(() => {
    const positions = new Float32Array(count * 3)
    const sizes = new Float32Array(count)
    const phases = new Float32Array(count)
    for (let i = 0; i < count; i++) {
      // Distribute in a wide, deep volume with a soft central bias.
      const r = Math.pow(Math.random(), 0.6) * 14
      const theta = Math.random() * Math.PI * 2
      const y = (Math.random() - 0.5) * 16
      positions[i * 3] = Math.cos(theta) * r
      positions[i * 3 + 1] = y
      positions[i * 3 + 2] = Math.sin(theta) * r - 4
      sizes[i] = Math.random() * 0.06 + 0.015
      phases[i] = Math.random() * Math.PI * 2
    }
    return { positions, sizes, phases }
  }, [count])

  const geo = useMemo(() => {
    const g = new THREE.BufferGeometry()
    g.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    g.setAttribute('size', new THREE.BufferAttribute(sizes, 1))
    g.setAttribute('phase', new THREE.BufferAttribute(phases, 1))
    return g
  }, [positions, sizes, phases])

  const material = useMemo(
    () =>
      new THREE.ShaderMaterial({
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
        uniforms: {
          uTime: { value: 0 },
          uColorA: { value: new THREE.Color('#ffb500') },
          uColorB: { value: new THREE.Color('#3d7bff') },
        },
        vertexShader: /* glsl */ `
          attribute float size;
          attribute float phase;
          uniform float uTime;
          varying float vAlpha;
          varying float vMix;
          void main() {
            vec3 p = position;
            p.y += sin(uTime * 0.3 + phase) * 0.4;
            p.x += cos(uTime * 0.2 + phase) * 0.3;
            vMix = clamp((p.y + 8.0) / 16.0, 0.0, 1.0);
            vec4 mv = modelViewMatrix * vec4(p, 1.0);
            gl_PointSize = size * (300.0 / -mv.z);
            vAlpha = smoothstep(20.0, 4.0, -mv.z);
            gl_Position = projectionMatrix * mv;
          }
        `,
        fragmentShader: /* glsl */ `
          uniform vec3 uColorA;
          uniform vec3 uColorB;
          varying float vAlpha;
          varying float vMix;
          void main() {
            vec2 uv = gl_PointCoord - 0.5;
            float d = length(uv);
            float glow = smoothstep(0.5, 0.0, d);
            vec3 col = mix(uColorA, uColorB, vMix);
            gl_FragColor = vec4(col, glow * vAlpha * 0.9);
          }
        `,
      }),
    []
  )

  useFrame((state, delta) => {
    material.uniforms.uTime.value = state.clock.elapsedTime
    if (points.current) {
      points.current.rotation.y += delta * 0.02
      // Parallax lean toward mouse.
      const m = mouse?.current || { x: 0, y: 0 }
      points.current.rotation.x += (m.y * 0.15 - points.current.rotation.x) * 0.05
      points.current.position.x += (m.x * 0.6 - points.current.position.x) * 0.04
    }
  })

  return <points ref={points} geometry={geo} material={material} />
}
