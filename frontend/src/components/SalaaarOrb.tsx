import React, { useRef, useEffect } from 'react'
import * as THREE from 'three'

type OrbState = 'idle' | 'listening' | 'thinking' | 'speaking' | 'muted'

interface SalaaarOrbProps {
  size?: number
  state?: OrbState
  micVolume?: number
  aiVolume?: number
  className?: string
  onClick?: () => void
}

const ORB_VS = `
varying vec3 vNormal;
varying vec3 vViewPos;
varying vec3 vWorldPos;
varying vec2 vUv;
varying vec3 vSpherePos;
void main(){
  vUv = uv;
  vSpherePos = normalize(position);
  vec4 worldPos = modelMatrix * vec4(position, 1.0);
  vWorldPos = worldPos.xyz;
  vNormal = normalize(normalMatrix * normal);
  vec4 mvPos = modelViewMatrix * vec4(position, 1.0);
  vViewPos = -mvPos.xyz;
  gl_Position = projectionMatrix * mvPos;
}
`

const ORB_FS = `
uniform float uTime;
uniform float uIntensity;
varying vec3 vNormal;
varying vec3 vViewPos;
varying vec3 vWorldPos;
varying vec2 vUv;
varying vec3 vSpherePos;

float ribbonSDF(vec3 p, float time, float offset, float freq, float amp) {
  float phi = atan(p.z, p.x);
  float theta = acos(clamp(p.y, -1.0, 1.0));
  float target = 1.5708 + sin(phi * freq + time * 0.08 + offset) * amp;
  float d = abs(theta - target);
  d = min(d, 6.28318 - d);
  return d;
}

void main() {
  vec3 N = normalize(vNormal);
  vec3 V = normalize(vViewPos);
  vec3 P = normalize(vSpherePos);

  float fresnel = pow(1.0 - max(dot(N, V), 0.0), 3.0);

  float d1 = ribbonSDF(P, uTime, 0.0, 1.5, 0.65);
  float d2 = ribbonSDF(P, uTime, 2.2, 1.1, 0.5);
  float d = min(d1, d2);

  float ribbonWidth = 0.18;
  float edge = smoothstep(0.0, ribbonWidth, d);
  float edgeBright = smoothstep(ribbonWidth * 0.9, ribbonWidth * 0.1, d);

  vec3 darkBlue = vec3(0.02, 0.06, 0.18);
  vec3 midBlue = vec3(0.08, 0.35, 0.9);
  vec3 brightBlue = vec3(0.35, 0.75, 1.0);

  vec3 ribbonColor = mix(darkBlue, midBlue, 1.0 - edge);
  ribbonColor = mix(ribbonColor, brightBlue, edgeBright * 0.5);

  float ribbonAlpha = (1.0 - edge) * (0.4 + uIntensity * 0.3);
  ribbonAlpha += edgeBright * 0.2;

  vec3 sphereColor = vec3(0.01, 0.02, 0.04);

  vec3 rimColor = vec3(0.1, 0.4, 0.85);
  sphereColor += rimColor * fresnel * 0.5;

  vec3 L = normalize(vec3(1.0, 0.5, 1.0));
  vec3 H = normalize(L + V);
  float spec = pow(max(dot(N, H), 0.0), 80.0);
  sphereColor += vec3(0.3, 0.6, 1.0) * spec * 0.4;

  vec3 finalColor = mix(sphereColor, ribbonColor, ribbonAlpha);

  finalColor += brightBlue * edgeBright * fresnel * 0.3 * uIntensity;

  gl_FragColor = vec4(finalColor, 0.93 + fresnel * 0.07);
}
`

export function SalaaarOrb({ size = 200, state = 'idle', micVolume = 0, aiVolume = 0, className = '', onClick }: SalaaarOrbProps) {
  const mountRef = useRef<HTMLDivElement>(null)
  const stateRef = useRef({ state, micVolume, aiVolume })
  stateRef.current = { state, micVolume, aiVolume }

  useEffect(() => {
    if (!mountRef.current) return
    const container = mountRef.current

    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.setSize(size, size)
    renderer.setClearColor(0x000000, 0)
    container.appendChild(renderer.domElement)

    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(28, 1, 0.1, 100)
    camera.position.z = 5.5

    const orbGeo = new THREE.SphereGeometry(1.5, 96, 96)
    const orbMat = new THREE.ShaderMaterial({
      vertexShader: ORB_VS,
      fragmentShader: ORB_FS,
      uniforms: {
        uTime: { value: 0 },
        uIntensity: { value: 0.15 },
      },
      transparent: true,
      side: THREE.FrontSide,
    })
    scene.add(new THREE.Mesh(orbGeo, orbMat))

    const clock = new THREE.Clock()
    let alive = true

    function animate() {
      if (!alive) return
      requestAnimationFrame(animate)
      const t = clock.getElapsedTime()

      orbMat.uniforms.uTime.value = t

      const s = stateRef.current.state
      const vol = Math.max(stateRef.current.micVolume, stateRef.current.aiVolume)
      const target = s === 'idle' ? 0.15 : 0.5 + vol * 0.5
      orbMat.uniforms.uIntensity.value += (target - orbMat.uniforms.uIntensity.value) * 0.03

      renderer.render(scene, camera)
    }

    animate()

    return () => {
      alive = false
      container.removeChild(renderer.domElement)
      renderer.dispose()
      orbGeo.dispose()
      orbMat.dispose()
    }
  }, [size])

  return (
    <div
      ref={mountRef}
      className={className}
      style={{ width: size, height: size, cursor: 'pointer' }}
      onClick={onClick}
      role="button"
      aria-label={state !== 'idle' ? 'Stop live voice' : 'Start live voice'}
    />
  )
}
