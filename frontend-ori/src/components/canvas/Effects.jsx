import { EffectComposer, Bloom, DepthOfField, Vignette, Noise } from '@react-three/postprocessing'
import { BlendFunction } from 'postprocessing'

// Post-processing stack: bloom for neon glow, depth-of-field for cinematic
// focus, subtle vignette + film grain. Tuned to stay performant.
export default function Effects({ quality = 'high' }) {
  if (quality === 'low') {
    return (
      <EffectComposer multisampling={0}>
        <Bloom intensity={0.6} luminanceThreshold={0.35} luminanceSmoothing={0.9} mipmapBlur />
        <Vignette eskil={false} offset={0.3} darkness={0.7} />
      </EffectComposer>
    )
  }

  return (
    <EffectComposer multisampling={2}>
      <DepthOfField focusDistance={0.012} focalLength={0.045} bokehScale={3} height={480} />
      <Bloom intensity={0.85} luminanceThreshold={0.3} luminanceSmoothing={0.9} mipmapBlur radius={0.7} />
      <Noise premultiply blendFunction={BlendFunction.SOFT_LIGHT} opacity={0.18} />
      <Vignette eskil={false} offset={0.28} darkness={0.72} />
    </EffectComposer>
  )
}
