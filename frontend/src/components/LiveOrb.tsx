import React, { useCallback, useEffect, useRef, useState } from 'react'

type OrbState = 'idle' | 'listening' | 'thinking' | 'speaking'

interface LiveOrbProps {
  size?: number
  state?: OrbState
  className?: string
  onVoiceDetected?: (detected: boolean) => void
  onClick?: () => void
}

export function LiveOrb({
  size = 360,
  state: externalState,
  className = '',
  onVoiceDetected,
  onClick,
}: LiveOrbProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const animationRef = useRef<number | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const microphoneRef = useRef<MediaStreamAudioSourceNode | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const volumeRef = useRef(0)
  const smoothVolumeRef = useRef(0)
  const [active, setActive] = useState(false)
  const [internalState, setInternalState] = useState<OrbState>('idle')

  const state = externalState ?? internalState

  const startMicrophone = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      })
      streamRef.current = stream
      const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext
      const audioContext = new AudioContextClass()
      audioContextRef.current = audioContext
      const analyser = audioContext.createAnalyser()
      analyser.fftSize = 512
      analyser.smoothingTimeConstant = 0.82
      analyserRef.current = analyser
      const microphone = audioContext.createMediaStreamSource(stream)
      microphone.connect(analyser)
      microphoneRef.current = microphone
      if (audioContext.state === 'suspended') await audioContext.resume()
      setActive(true)
      if (!externalState) setInternalState('listening')
    } catch (error) {
      console.error('Unable to access microphone:', error)
    }
  }, [externalState])

  const stopMicrophone = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop())
    microphoneRef.current?.disconnect()
    analyserRef.current?.disconnect()
    if (audioContextRef.current) audioContextRef.current.close()
    streamRef.current = null
    microphoneRef.current = null
    analyserRef.current = null
    audioContextRef.current = null
    volumeRef.current = 0
    smoothVolumeRef.current = 0
    setActive(false)
    if (!externalState) setInternalState('idle')
  }, [externalState])

  const toggleLiveMode = useCallback(() => {
    if (onClick) { onClick(); return }
    if (active) stopMicrophone(); else startMicrophone()
  }, [active, startMicrophone, stopMicrophone, onClick])

  const updateAudio = useCallback(() => {
    const analyser = analyserRef.current
    if (!analyser) { volumeRef.current *= 0.92; return }
    const data = new Uint8Array(analyser.frequencyBinCount)
    analyser.getByteFrequencyData(data)
    let sum = 0
    for (let i = 0; i < data.length; i++) sum += data[i]
    const average = sum / data.length / 255
    const amplified = Math.min(1, average * 3.2)
    volumeRef.current = amplified
    smoothVolumeRef.current += (amplified - smoothVolumeRef.current) * 0.12
    const detected = smoothVolumeRef.current > 0.055
    onVoiceDetected?.(detected)
  }, [onVoiceDetected])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const gl = canvas.getContext('webgl', { alpha: true, antialias: true })
    if (!gl) return

    const vertexShaderSource = `
      attribute vec2 position;
      varying vec2 vUv;
      void main() {
        vUv = position * 0.5 + 0.5;
        gl_Position = vec4(position, 0.0, 1.0);
      }
    `

    const fragmentShaderSource = `
      precision highp float;
      varying vec2 vUv;
      uniform float uTime;
      uniform float uVolume;
      uniform float uActive;
      uniform float uState;

      float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123); }

      float noise(vec2 p) {
        vec2 i = floor(p);
        vec2 f = fract(p);
        f = f * f * (3.0 - 2.0 * f);
        return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), f.x), mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), f.x), f.y);
      }

      float fbm(vec2 p) {
        float value = 0.0;
        value += noise(p) * 0.50;
        value += noise(p * 2.0) * 0.25;
        value += noise(p * 4.0) * 0.125;
        value += noise(p * 8.0) * 0.0625;
        return value;
      }

      void main() {
        vec2 uv = vUv * 2.0 - 1.0;
        float dist = length(uv);
        float radius = 0.72;
        float n = fbm(uv * 2.8 + vec2(uTime * 0.18, uTime * 0.12));
        float deformation = n * (0.025 + uVolume * 0.18);
        float edge = smoothstep(radius + deformation, radius - 0.035, dist);
        float fresnel = pow(1.0 - edge, 2.2);
        float energy = smoothstep(0.05, 0.8, uVolume);

        vec3 cyan = vec3(0.05, 0.90, 1.00);
        vec3 violet = vec3(0.45, 0.18, 1.00);
        vec3 blue = vec3(0.08, 0.35, 1.00);

        float colorMix = 0.5 + 0.5 * sin(uTime * 0.6 + uv.x * 3.0 + n * 4.0);
        vec3 color = mix(cyan, violet, colorMix);
        color = mix(color, blue, n * 0.45);
        color *= 0.72 + energy * 0.9;

        float core = 1.0 - smoothstep(0.0, radius, dist);
        color += cyan * core * 0.22;
        color += mix(cyan, violet, 0.5) * fresnel * (0.35 + energy * 1.8);

        float glow = exp(-dist * (4.0 - energy * 1.2));
        color += violet * glow * 0.16;

        float alpha = edge * 0.96 + fresnel * 0.18;
        float pulse = sin(uTime * 4.0) * uVolume * 0.035;
        color += cyan * pulse;

        gl_FragColor = vec4(color, alpha);
      }
    `

    const compileShader = (type: number, source: string) => {
      const shader = gl.createShader(type)!
      gl.shaderSource(shader, source)
      gl.compileShader(shader)
      return shader
    }

    const vertexShader = compileShader(gl.VERTEX_SHADER, vertexShaderSource)
    const fragmentShader = compileShader(gl.FRAGMENT_SHADER, fragmentShaderSource)
    const program = gl.createProgram()!
    gl.attachShader(program, vertexShader)
    gl.attachShader(program, fragmentShader)
    gl.linkProgram(program)
    gl.useProgram(program)

    const buffer = gl.createBuffer()
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer)
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]), gl.STATIC_DRAW)

    const position = gl.getAttribLocation(program, 'position')
    gl.enableVertexAttribArray(position)
    gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0)

    const timeLocation = gl.getUniformLocation(program, 'uTime')
    const volumeLocation = gl.getUniformLocation(program, 'uVolume')
    const activeLocation = gl.getUniformLocation(program, 'uActive')
    const stateLocation = gl.getUniformLocation(program, 'uState')

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      const rect = canvas.getBoundingClientRect()
      canvas.width = rect.width * dpr
      canvas.height = rect.height * dpr
      gl.viewport(0, 0, canvas.width, canvas.height)
    }
    resize()
    const resizeObserver = new ResizeObserver(resize)
    resizeObserver.observe(canvas)

    const startTime = performance.now()

    const render = (now: number) => {
      const elapsed = (now - startTime) / 1000
      updateAudio()
      const volume = smoothVolumeRef.current
      let stateValue = 0
      if (state === 'listening') stateValue = 1
      if (state === 'thinking') stateValue = 2
      if (state === 'speaking') stateValue = 3

      const animationTime = elapsed + volume * elapsed * 0.15
      gl.uniform1f(timeLocation, animationTime)
      gl.uniform1f(volumeLocation, volume)
      gl.uniform1f(activeLocation, active ? 1 : 0)
      gl.uniform1f(stateLocation, stateValue)
      gl.clearColor(0, 0, 0, 0)
      gl.clear(gl.COLOR_BUFFER_BIT)
      gl.drawArrays(gl.TRIANGLES, 0, 6)
      animationRef.current = requestAnimationFrame(render)
    }

    animationRef.current = requestAnimationFrame(render)

    return () => {
      if (animationRef.current) cancelAnimationFrame(animationRef.current)
      resizeObserver.disconnect()
      gl.deleteProgram(program)
      gl.deleteShader(vertexShader)
      gl.deleteShader(fragmentShader)
      gl.deleteBuffer(buffer)
    }
  }, [active, state, updateAudio])

  useEffect(() => { return () => { stopMicrophone() } }, [stopMicrophone])

  const glowScale = 1 + smoothVolumeRef.current * 0.35

  return (
    <div
      className={`relative flex items-center justify-center ${className}`}
      style={{ width: size, height: size }}
    >
      {/* Ambient glow */}
      <div
        className="absolute inset-[18%] rounded-full pointer-events-none"
        style={{
          background: 'radial-gradient(circle, rgba(91,220,255,.65), rgba(124,58,237,.35), transparent 70%)',
          filter: 'blur(60px)',
          opacity: 0.4,
          transform: `scale(${glowScale})`,
          transition: 'transform 0.15s ease-out',
        }}
      />

      {/* WebGL Orb */}
      <canvas
        ref={canvasRef}
        className="relative z-10 w-full h-full cursor-pointer"
        onClick={toggleLiveMode}
        aria-label={active ? 'Stop live voice mode' : 'Start live voice mode'}
      />

      {/* Status pill */}
      <div
        className={`
          absolute bottom-3 left-1/2 -translate-x-1/2 z-20
          flex items-center gap-2 rounded-full
          border border-white/10 bg-black/40 backdrop-blur-xl
          px-4 py-2 text-xs text-white/70
          transition-all duration-500
          ${active ? 'opacity-100 scale-100' : 'opacity-60 scale-95'}
        `}
      >
        <span
          className={`h-2 w-2 rounded-full transition-all duration-300 ${
            active ? 'bg-cyan-300 shadow-[0_0_12px_rgba(103,232,249,.9)]' : 'bg-white/30'
          }`}
        />
        {active ? 'LIVE' : 'TAP TO SPEAK'}
      </div>
    </div>
  )
}
