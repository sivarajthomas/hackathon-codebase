import { useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'

// A living logistics network: glowing hub nodes connected by curved shipping
// routes, with bright "packages" traveling along them. Rendered with cheap
// additive lines + points so it stays lightweight and smooth at 60fps.

const ACCENTS = ['#ffb500', '#3d7bff', '#ff8a3d', '#22c55e']

function makeNodes(count, radius) {
  // Distribute hub nodes on a wide, slightly flattened disc (map-like plane
  // tilted in 3D) with some depth jitter.
  const nodes = []
  for (let i = 0; i < count; i++) {
    const a = Math.random() * Math.PI * 2
    const r = Math.sqrt(Math.random()) * radius
    nodes.push(
      new THREE.Vector3(
        Math.cos(a) * r,
        (Math.random() - 0.5) * 3.5,
        Math.sin(a) * r * 0.7 - 2
      )
    )
  }
  return nodes
}

export default function LogisticsNetwork({ mouse, quality = 'high' }) {
  const group = useRef(null)
  const packRef = useRef(null)

  const nodeCount = quality === 'low' ? 16 : 26
  const routeCount = quality === 'low' ? 14 : 22

  const { nodes, routes, nodeGeo, packGeo, packCurves } = useMemo(() => {
    const nodes = makeNodes(nodeCount, 8)

    // Build routes between nearby-ish random node pairs as quadratic arcs that
    // bow upward, evoking flight/shipping paths.
    const routes = []
    for (let i = 0; i < routeCount; i++) {
      const a = nodes[Math.floor(Math.random() * nodes.length)]
      const b = nodes[Math.floor(Math.random() * nodes.length)]
      if (a === b) continue
      const mid = a.clone().add(b).multiplyScalar(0.5)
      mid.y += a.distanceTo(b) * 0.35 + 1
      routes.push(new THREE.QuadraticBezierCurve3(a.clone(), mid, b.clone()))
    }

    // Node points geometry.
    const np = new Float32Array(nodes.length * 3)
    nodes.forEach((n, i) => {
      np[i * 3] = n.x
      np[i * 3 + 1] = n.y
      np[i * 3 + 2] = n.z
    })
    const nodeGeo = new THREE.BufferGeometry()
    nodeGeo.setAttribute('position', new THREE.BufferAttribute(np, 3))

    // Traveling packages: one per route, we animate their position each frame.
    const pp = new Float32Array(routes.length * 3)
    const packGeo = new THREE.BufferGeometry()
    packGeo.setAttribute('position', new THREE.BufferAttribute(pp, 3))

    return { nodes, routes, nodeGeo, packGeo, packCurves: routes }
  }, [nodeCount, routeCount])

  // Route line objects (memoized).
  const routeLines = useMemo(() => {
    return routes.map((curve, i) => {
      const pts = curve.getPoints(40)
      const geo = new THREE.BufferGeometry().setFromPoints(pts)
      const color = new THREE.Color(ACCENTS[i % ACCENTS.length])
      const mat = new THREE.LineBasicMaterial({
        color,
        transparent: true,
        opacity: 0.18,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      })
      return { object: new THREE.Line(geo, mat), key: i }
    })
  }, [routes])

  const nodeMat = useMemo(
    () =>
      new THREE.PointsMaterial({
        size: 0.16,
        color: new THREE.Color('#ffcf5a'),
        transparent: true,
        opacity: 0.9,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
        sizeAttenuation: true,
      }),
    []
  )

  const packMat = useMemo(
    () =>
      new THREE.PointsMaterial({
        size: 0.22,
        color: new THREE.Color('#ffffff'),
        transparent: true,
        opacity: 1,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
        sizeAttenuation: true,
      }),
    []
  )

  useFrame((state) => {
    const t = state.clock.elapsedTime

    if (group.current) {
      group.current.rotation.y = t * 0.03
      const m = mouse?.current || { x: 0, y: 0 }
      group.current.rotation.x += (m.y * 0.12 - group.current.rotation.x) * 0.04
      group.current.position.x += (m.x * 0.5 - group.current.position.x) * 0.03
    }

    // Advance packages along their routes.
    if (packRef.current) {
      const arr = packRef.current.geometry.attributes.position.array
      for (let i = 0; i < packCurves.length; i++) {
        const speed = 0.06 + (i % 5) * 0.015
        const u = (t * speed + i * 0.13) % 1
        const p = packCurves[i].getPoint(u)
        arr[i * 3] = p.x
        arr[i * 3 + 1] = p.y
        arr[i * 3 + 2] = p.z
      }
      packRef.current.geometry.attributes.position.needsUpdate = true
    }
  })

  return (
    <group ref={group}>
      {routeLines.map(({ object, key }) => (
        <primitive key={key} object={object} />
      ))}
      <points geometry={nodeGeo} material={nodeMat} />
      <points ref={packRef} geometry={packGeo} material={packMat} />
    </group>
  )
}
