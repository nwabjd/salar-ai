import React, { useEffect, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { Calendar, FileText, LogOut, MemoryStick, MessageCircle, Mic2, Monitor, Send, Sparkles, X, MessageSquare } from 'lucide-react'
import LiquidEther from './effects/LiquidEther.jsx'
import MagicRings from './effects/MagicRings.jsx'
import Strands from './effects/Strands.jsx'
import { AccessState, clearSession, saveSession, storedSession } from './access'
import { supabase } from './lib/supabase'
import { Conversation, Message, SalarApi } from './api'
import { PricingPage } from './components/PricingPage'
import './theme.css'
import './styles.css'
import './landing.css'
import SalaarLanding from './components/SalaarLanding'

const api = new SalarApi()

async function reBridgeIfPossible(): Promise<boolean> {
  if (!supabase) return false
  try {
    const { data } = await supabase.auth.getSession()
    if (!data.session?.access_token) return false
    const result = await api.supabaseLogin(data.session.access_token)
    await saveSession(result.access_token)
    return true
  } catch {
    return false
  }
}

type Usage = { plan: string; limit: number | null; used: number; reset_at: string; exempt: boolean }

function Loader() {
  return <main className="loader">
    <div className="loader-effect"><Strands colors={["#F97316","#7C3AED","#06B6D4"]} count={3} speed={0.5} amplitude={1} waviness={1} thickness={0.7} glow={2.6} taper={3} spread={1} intensity={0.6} saturation={1.5} opacity={1} scale={1.5} glass={false} refraction={1} dispersion={1} glassSize={1}/></div>
    <div className="loader-copy"><p>SALAR</p><span>INITIALIZING PRIVATE INTELLIGENCE</span></div>
  </main>
}

function App() {
  const [ready, setReady] = useState(false)
  const [access, setAccess] = useState<AccessState>('checking')
  const [live, setLive] = useState(false)
  const [usage, setUsage] = useState<Usage | null>(null)
  const [showPricing, setShowPricing] = useState(false)

  useEffect(() => { const timer = setTimeout(() => setReady(true), 800); return () => clearTimeout(timer) }, [])

  useEffect(() => {
    let stopped = false
    storedSession().then(async token => {
      if (stopped) return
      if (!token) { setAccess('signed-out'); return }
      api.token = token
      try {
        await api.validateSession()
        if (!stopped) setAccess('connected')
      } catch {
        const healed = await reBridgeIfPossible()
        if (stopped) return
        if (healed) {
          setAccess('connected')
        } else {
          await clearSession(); api.token = ''
          setAccess('signed-out')
        }
      }
    })
    return () => { stopped = true }
  }, [])

  useEffect(() => {
    if (access !== 'connected') return
    let stopped = false
    const refresh = () => { api.usage().then(u => { if (!stopped) setUsage(u) }).catch(() => {}) }
    refresh()
    const timer = setInterval(refresh, 30000)
    return () => { stopped = true; clearInterval(timer) }
  }, [access])

  useEffect(() => {
    if (access !== 'connected') return
    let stopped = false
    let failures = 0
    async function check() {
      try {
        await api.validateSession()
        failures = 0
      } catch (reason) {
        const msg = String(reason)
        if (msg.includes('401') || msg.includes('Authentication') || msg.includes('invalid') || msg.includes('expired')) {
          const healed = await reBridgeIfPossible()
          if (stopped) return
          if (healed) {
            failures = 0
          } else if (++failures >= 2) {
            await clearSession(); api.token = ''
            setAccess('signed-out'); setUsage(null)
            return
          }
        }
      }
      if (!stopped) setTimeout(check, 5000)
    }
    check()
    return () => { stopped = true }
  }, [access])

  async function handleSignOut() {
    if (supabase) await supabase.auth.signOut()
    await clearSession()
    api.token = ''
    setUsage(null)
    setAccess('signed-out')
  }

  if (!ready) return <Loader/>
  if (access !== 'connected') return <SalaarLanding onEnterApp={() => setAccess('connected')}/>

  return <><main className={`app-shell${live ? ' live-open' : ''}`}>
    <div className="liquid-stage"><LiquidEther colors={['#5227FF','#FF9FFC','#B497CF']} mouseForce={20} cursorSize={100} isViscous={false} viscous={30} iterationsViscous={32} iterationsPoisson={32} resolution={0.5} isBounce={false} autoDemo autoSpeed={0.5} autoIntensity={2.2} takeoverDuration={0.25} autoResumeDelay={3000} autoRampDuration={0.6}/></div>
    <header className="topbar">
      <div className="brand"><div className="salar-glyph">S</div><div><b>SALAR</b><small>PERSONAL INTELLIGENCE</small></div></div>
      <nav className="topnav">
        {usage && <button className="usage-chip" onClick={() => setShowPricing(true)} title="Plan & billing"><Sparkles size={12}/><b>{usage.used.toLocaleString()}</b> / {usage.limit === null ? 'unlimited' : usage.limit.toLocaleString()} <small>{usage.plan.toUpperCase()}</small></button>}
      </nav>
      <div className="topbar-actions">
        <button className="connection" onClick={() => setLive(true)}><Mic2 size={13}/> LIVE</button>
        <button className="connection signout" onClick={handleSignOut}><LogOut size={13}/> SIGN OUT</button>
      </div>
    </header>
    <section className="workspace chat-workspace">
      <div className="chat-column"><Chat connected onLive={() => setLive(true)}/></div>
      <StatusRail/>
      {showPricing && <div className="pricing-overlay"><button className="pricing-close" onClick={() => setShowPricing(false)} aria-label="Close plan & billing"><X/></button><PricingPage connected/></div>}
    </section>
  </main>{live && <Live connected onClose={() => setLive(false)}/>}</>
}

function Chat({ connected, onLive }: { connected: boolean; onLive: () => void }) {
  const [conversation, setConversation] = useState<Conversation | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [streaming, setStreaming] = useState('')
  const [toolActivity, setToolActivity] = useState('')
  const streamBuf = useRef('')
  const end = useRef<HTMLDivElement>(null)
  const messagesRef = useRef<HTMLDivElement>(null)
  useEffect(() => { if (!connected) return; api.conversations().then(async list => { const item = list[0] || await api.createConversation(); setConversation(item); if (list[0]) setMessages((await api.conversation(item.id)).messages || []) }).catch(e => setError(e.message)) }, [connected])
  useEffect(() => { end.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, streaming, toolActivity])
  function send() {
    if (!input.trim() || !conversation || busy) return
    const content = input; setInput(''); setBusy(true); setStreaming(''); setToolActivity(''); streamBuf.current = ''
    const userMsg: Message = { id: 'tmp-' + Date.now(), role: 'user', content, created_at: new Date().toISOString() }
    setMessages(current => [...current, userMsg])
    let done = false
    const finish = () => { if (done) return; done = true; setStreaming(''); streamBuf.current = ''; setToolActivity(''); setBusy(false) }
    api.chatStream(conversation.id, content,
      (token) => { streamBuf.current += token; setStreaming(streamBuf.current); setToolActivity('') },
      (messageId, createdAt) => {
        const reply = streamBuf.current
        setMessages(current => [...current.slice(0, -1), userMsg, { id: messageId, role: 'assistant', content: reply, created_at: createdAt }])
        finish()
      },
      (err) => {
        console.error('Stream failed:', err)
        if (streamBuf.current) {
          const reply = streamBuf.current
          setMessages(current => [...current.slice(0, -1), userMsg, { id: 'err-' + Date.now(), role: 'assistant', content: reply + '\n\n[Stream interrupted]', created_at: new Date().toISOString() }])
        } else {
          setError('Connection lost — try again')
          setMessages(current => current.filter(m => m.id !== userMsg.id))
        }
        finish()
      },
      (toolName, args) => { setToolActivity(`Using ${toolName}…`) },
      (toolName, result) => { setToolActivity(`Completed ${toolName}`) },
    )
  }
  return <div className={`chat-view${messages.length ? ' has-messages' : ''}`}><div className="hero"><span className="eyebrow">COORDINATED INTELLIGENCE</span><h1>{messages.length ? 'Command stream' : 'What shall we accomplish?'}</h1><p>Private intelligence, memory, knowledge, and your connected devices—coordinated from one place.</p></div>    <div className="messages" ref={messagesRef}><div className="messages-spacer"/>{messages.map(message => <article key={message.id} className={message.role}><span>{message.role === 'assistant' ? 'SALAR' : 'YOU'}</span><p>{message.content}</p></article>)}{streaming && <article className="assistant thinking"><span>SALAR</span><p>{streaming}</p></article>}{toolActivity && !streaming && <article className="assistant thinking tool-activity"><span>SALAR</span><p className="tool-hint">{toolActivity}</p></article>}{busy && !streaming && !toolActivity && <article className="assistant thinking"><span>SALAR</span><p>Reasoning across your private context…</p></article>}<div ref={end}/></div>{error && <div className="toast">{error}</div>}<div className="composer"><button className="icon-control live-control" onClick={onLive} title="Enter Live mode"><Mic2/></button><textarea value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }} placeholder="Ask, create, search, or control…" disabled={!connected} rows={1}/><button className="icon-control send-control" onClick={send} disabled={!connected || busy || !input.trim()} title="Send command"><Send/></button></div></div>
}

function Live({ connected, onClose }: { connected: boolean; onClose: () => void }) {
  const [phase, setPhase] = useState<'idle' | 'listening' | 'thinking' | 'speaking'>('idle')
  const [volume, setVolume] = useState(0)
  const [transcript, setTranscript] = useState('')
  const [liveError, setLiveError] = useState('')
  const [history, setHistory] = useState<Array<{ role: 'user' | 'salar'; text: string }>>([])
  const [toolActivity, setToolActivity] = useState('')
  const [textInput, setTextInput] = useState('')
  const [showTextInput, setShowTextInput] = useState(false)
  const phaseRef = useRef<'idle' | 'listening' | 'thinking' | 'speaking'>('idle')
  const stoppedRef = useRef(false)
  const conversationId = useRef('')
  const streamRef = useRef<MediaStream | null>(null)
  const audioCtxRef = useRef<AudioContext | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const monitorRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const silenceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const fixedRecordRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const liveTextRef = useRef('')
  const playingRef = useRef(false)
  const ttsQueueRef = useRef<string[]>([])
  const ttsInFlightRef = useRef(false)
  const sentenceBufRef = useRef('')
  const historyEndRef = useRef<HTMLDivElement>(null)

  function setPhaseFast(p: 'idle' | 'listening' | 'thinking' | 'speaking') {
    phaseRef.current = p
    setPhase(p)
  }

  function teardown() {
    stoppedRef.current = true
    if (monitorRef.current) { clearInterval(monitorRef.current); monitorRef.current = null }
    cleanupRecording()
    if (audioCtxRef.current && audioCtxRef.current.state !== 'closed') {
      audioCtxRef.current.close().catch(() => {})
    }
    audioCtxRef.current = null
    if (streamRef.current) { streamRef.current.getTracks().forEach(t => t.stop()); streamRef.current = null }
    stopAllAudio()
  }

  function cleanupRecording() {
    if (silenceRef.current) { clearTimeout(silenceRef.current); silenceRef.current = null }
    if (fixedRecordRef.current) { clearTimeout(fixedRecordRef.current); fixedRecordRef.current = null }
    if (recorderRef.current && recorderRef.current.state !== 'inactive') {
      try { recorderRef.current.stop() } catch {}
    }
    recorderRef.current = null
    chunksRef.current = []
  }

  function stopAllAudio() {
    playingRef.current = false
    ttsQueueRef.current = []
    ttsInFlightRef.current = false
    sentenceBufRef.current = ''
  }

  async function ensureMic() {
    if (streamRef.current && streamRef.current.active) return streamRef.current
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }
    })
    streamRef.current = stream
    if (!audioCtxRef.current || audioCtxRef.current.state === 'closed') {
      audioCtxRef.current = new AudioContext()
    }
    if (audioCtxRef.current.state === 'suspended') await audioCtxRef.current.resume()
    const source = audioCtxRef.current.createMediaStreamSource(stream)
    const analyser = audioCtxRef.current.createAnalyser()
    analyser.fftSize = 512
    source.connect(analyser)
    analyserRef.current = analyser
    return stream
  }

  function startRecording() {
    if (stoppedRef.current || phaseRef.current !== 'listening') return
    if (recorderRef.current && recorderRef.current.state === 'recording') return

    ensureMic().then(stream => {
      if (stoppedRef.current || phaseRef.current !== 'listening') return
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : 'audio/webm'
      const recorder = new MediaRecorder(stream, { mimeType })
      recorderRef.current = recorder
      chunksRef.current = []

      recorder.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data) }
      recorder.onstop = () => {
        if (stoppedRef.current) return
        if (phaseRef.current !== 'listening') return
        const chunks = [...chunksRef.current]
        chunksRef.current = []
        if (silenceRef.current) { clearTimeout(silenceRef.current); silenceRef.current = null }
        if (fixedRecordRef.current) { clearTimeout(fixedRecordRef.current); fixedRecordRef.current = null }
        if (chunks.length === 0) {
          setTimeout(() => { if (phaseRef.current === 'listening' && !stoppedRef.current) startRecording() }, 300)
          return
        }
        const blob = new Blob(chunks, { type: mimeType })
        if (blob.size < 500) {
          setTimeout(() => { if (phaseRef.current === 'listening' && !stoppedRef.current) startRecording() }, 300)
          return
        }
        recorderRef.current = null
        sendChunkForStt(blob)
      }

      recorder.start(500)

      fixedRecordRef.current = setTimeout(() => {
        if (recorder.state === 'recording') recorder.stop()
      }, 5000)

    }).catch(e => {
      console.error('Mic failed:', e)
      setLiveError('Microphone access denied.')
      setPhaseFast('idle')
    })
  }

  async function sendChunkForStt(blob: Blob) {
    if (stoppedRef.current || phaseRef.current !== 'listening') return
    setPhaseFast('thinking')
    setTranscript('...')
    try {
      const text = await api.stt(blob)
      if (stoppedRef.current) return
      if (text.trim()) {
        liveTextRef.current = text.trim()
        setTranscript(text.trim())
        setHistory(prev => [...prev, { role: 'user', text: text.trim() }])
        processUserSpeech(text.trim())
      } else {
        setTranscript('')
        setPhaseFast('listening')
        startRecording()
      }
    } catch (e) {
      console.error('STT failed:', e)
      if (!stoppedRef.current) {
        setTranscript('')
        setPhaseFast('listening')
        startRecording()
      }
    }
  }

  function flushSentence() {
    const buf = sentenceBufRef.current.trim()
    sentenceBufRef.current = ''
    if (buf.length > 3) {
      ttsQueueRef.current.push(buf)
      drainTtsQueue()
    }
  }

  async function drainTtsQueue() {
    if (ttsInFlightRef.current || ttsQueueRef.current.length === 0) return
    ttsInFlightRef.current = true
    while (ttsQueueRef.current.length > 0 && !stoppedRef.current) {
      const text = ttsQueueRef.current.shift()!
      try {
        const blob = await api.tts(text, true)
        if (stoppedRef.current) break
        setPhaseFast('speaking')
        await playTtsBlob(blob)
      } catch (e) {
        console.error('TTS failed:', e)
      }
    }
    ttsInFlightRef.current = false
  }

  function processUserSpeech(text: string) {
    if (stoppedRef.current || !conversationId.current) return
    ttsQueueRef.current = []
    ttsInFlightRef.current = false
    sentenceBufRef.current = ''
    setToolActivity('')
    stopAllAudio()

    let fullResponse = ''

    api.chatStream(
      conversationId.current,
      text,
      (token) => {
        if (stoppedRef.current) return
        fullResponse += token
        setTranscript(fullResponse)

        sentenceBufRef.current += token
        const buf = sentenceBufRef.current
        const sentEnd = buf.search(/[.!?]\s/)
        if (sentEnd !== -1 || buf.length > 150) {
          const cutAt = sentEnd !== -1 ? sentEnd + 1 : buf.length
          const complete = buf.slice(0, cutAt)
          sentenceBufRef.current = buf.slice(cutAt)
          ttsQueueRef.current.push(complete)
          drainTtsQueue()
        }
      },
      () => {
        if (stoppedRef.current) return
        flushSentence()
        if (fullResponse.trim()) {
          setHistory(prev => [...prev, { role: 'salar', text: fullResponse.trim() }])
        }
        if (ttsQueueRef.current.length === 0 && !ttsInFlightRef.current) {
          ttsQueueRef.current.push(fullResponse.trim())
          drainTtsQueue()
        }
        const checkDone = () => {
          if (stoppedRef.current) return
          if (ttsInFlightRef.current || ttsQueueRef.current.length > 0) {
            setTimeout(checkDone, 100)
            return
          }
          setTranscript('')
          setToolActivity('')
          setPhaseFast('listening')
          startRecording()
        }
        checkDone()
      },
      (err) => {
        console.error('Live stream error:', err)
        if (!stoppedRef.current) {
          setTranscript('')
          setToolActivity('')
          setPhaseFast('listening')
          startRecording()
        }
      },
      (toolName, args) => { setToolActivity(`Using ${toolName}…`) },
      (toolName, result) => { setToolActivity(`Completed ${toolName}`) },
      true,
    )
  }

  function handleTextSubmit() {
    if (!textInput.trim()) return
    const text = textInput.trim()
    setTextInput('')
    setHistory(prev => [...prev, { role: 'user', text }])
    setPhaseFast('thinking')
    setTranscript(text)
    processUserSpeech(text)
  }

  async function playTtsBlob(blob: Blob): Promise<void> {
    if (stoppedRef.current) return
    playingRef.current = true

    try {
      const arrayBuf = await blob.arrayBuffer()
      if (stoppedRef.current) return
      const ctx = audioCtxRef.current
      if (!ctx || ctx.state === 'closed') { playingRef.current = false; return }
      if (ctx.state === 'suspended') await ctx.resume()

      const audioBuf = await ctx.decodeAudioData(arrayBuf)
      if (stoppedRef.current) return

      const source = ctx.createBufferSource()
      source.buffer = audioBuf
      source.connect(ctx.destination)
      await new Promise<void>((res) => {
        source.onended = () => res()
        source.start(0)
      })
    } catch (e) {
      console.error('TTS playback failed:', e)
    } finally {
      playingRef.current = false
    }
  }

  useEffect(() => {
    if (!connected) return
    stoppedRef.current = false
    setLiveError('')
    setTranscript('')
    setHistory([])
    setToolActivity('')
    ensureMic().then(() => {
      if (stoppedRef.current) return
      const data = new Uint8Array(analyserRef.current!.frequencyBinCount)
      monitorRef.current = setInterval(() => {
        if (!analyserRef.current || stoppedRef.current) return
        analyserRef.current.getByteFrequencyData(data)
        let sum = 0
        for (let i = 0; i < data.length; i++) sum += data[i]
        const avg = sum / data.length
        setVolume(avg)

        if (phaseRef.current === 'speaking' && playingRef.current && avg > 15) {
          stopAllAudio()
          if (streamRef.current) { streamRef.current.getTracks().forEach(t => t.stop()); streamRef.current = null }
          if (audioCtxRef.current && audioCtxRef.current.state !== 'closed') {
            audioCtxRef.current.close().catch(() => {})
          }
          audioCtxRef.current = null
          setPhaseFast('listening')
          startRecording()
          return
        }

        if (phaseRef.current === 'listening' && recorderRef.current?.state === 'recording') {
          if (avg > 10) {
            if (silenceRef.current) { clearTimeout(silenceRef.current); silenceRef.current = null }
          } else if (!silenceRef.current) {
            silenceRef.current = setTimeout(() => {
              if (recorderRef.current?.state === 'recording') recorderRef.current.stop()
            }, 600)
          }
        }
      }, 80)
      api.createConversation('Live session').then(c => {
        conversationId.current = c.id
        if (!stoppedRef.current) {
          setPhaseFast('listening')
          startRecording()
        }
      }).catch(e => {
        setLiveError('Session failed: ' + e.message)
        setPhaseFast('idle')
      })
    }).catch(e => {
      console.error('Mic failed:', e)
      setLiveError('Microphone access denied.')
      setPhaseFast('idle')
    })
    return () => { stoppedRef.current = true; teardown() }
  }, [connected])

  useEffect(() => {
    historyEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [history])

  function handleClose() {
    stoppedRef.current = true
    teardown()
    onClose()
  }

  const label = phase === 'idle' ? 'Starting…' : phase === 'listening' ? 'Listening…' : phase === 'thinking' ? 'Thinking…' : 'Speaking…'

  return <main className="live">
    <div className="rings"><MagicRings color="#fc42ff" colorTwo="#42fcff" ringCount={6} speed={1} attenuation={10} lineThickness={2} baseRadius={0.35} radiusStep={0.1} scaleRate={0.1} blur={0} noiseAmount={0.1} rotation={0} ringGap={1.5} fadeIn={0.7} fadeOut={0.5} followMouse={false} mouseInfluence={0.2} hoverScale={1.2} parallax={0.05} clickBurst={false} phase={phase} volume={volume}/></div>
    <button className="close" onClick={handleClose}><X/></button>
    <div className="live-history">
      {history.map((h, i) => <div key={i} className={`live-msg ${h.role}`}>
        <span className="live-msg-role">{h.role === 'user' ? 'You' : 'SALAR'}</span>
        <p>{h.text}</p>
      </div>)}
      <div ref={historyEndRef}/>
    </div>
    <div className="live-copy">
      <span className="live-label">{label}</span>
      {toolActivity && <p className="live-tool">{toolActivity}</p>}
      {liveError && <p className="live-heard" style={{color:'#ff6b6b'}}>{liveError}</p>}
      {transcript && <p className="live-heard">{transcript}</p>}
    </div>
    <div className="live-controls">
      <button className="live-text-toggle" onClick={() => setShowTextInput(!showTextInput)} title="Type instead of speak">
        <MessageSquare size={16}/>
      </button>
      {showTextInput && <div className="live-text-input">
        <input value={textInput} onChange={e => setTextInput(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') handleTextSubmit() }} placeholder="Type a message…" disabled={phase === 'thinking' || phase === 'speaking'}/>
        <button onClick={handleTextSubmit} disabled={!textInput.trim() || phase === 'thinking' || phase === 'speaking'}><Send size={14}/></button>
      </div>}
    </div>
  </main>
}

function StatusCard({ icon, title, hint, dot }: { icon: React.ReactNode; title: string; hint: string; dot?: string }) {
  return <div className="rail-card">
    <div className="rail-head">
      <span className="rail-title">{icon}{title}</span>
      {dot && <i className="rail-dot" style={{ background: dot }}/>}
    </div>
    <div className="rail-value">{hint}</div>
  </div>
}

function UsageRail({ usage }: { usage: Usage | null }) {
  const limit = usage?.limit ?? null
  const used = usage?.used ?? 0
  const pct = limit ? Math.min(100, Math.round((used / limit) * 100)) : 0
  const plan = usage?.plan ?? 'free'
  const label = limit === null ? `${used.toLocaleString()} messages` : `${used.toLocaleString()} / ${limit.toLocaleString()}`
  return <div className="rail-card usage-rail">
    <div className="rail-head">
      <span className="rail-title"><Sparkles size={14}/>Usage</span>
      <span className="plan-badge">{plan}</span>
    </div>
    <div className="rail-value">{label}</div>
    <div className="usage-rail-bar"><i style={{ width: `${pct}%` }}/></div>
    <div className="rail-hint">{usage?.reset_at ? `Resets ${new Date(usage.reset_at).toLocaleDateString()}` : 'Monthly message allowance'}</div>
  </div>
}

function StatusRail() {
  const [whatsapp, setWhatsapp] = useState('Checking…')
  const [whatsappDot, setWhatsappDot] = useState('#88818f')
  const [calendarToday, setCalendarToday] = useState('…')
  const [memories, setMemories] = useState('…')
  const [documents, setDocuments] = useState('…')
  const [devices, setDevices] = useState('…')
  const [usage, setUsage] = useState<Usage | null>(null)

  useEffect(() => {
    let stopped = false
    const loadAll = async () => {
      const [w, c, m, d, v, u] = await Promise.allSettled([
        api.whatsappStatus(), api.calendarToday(), api.memories(), api.documents(), api.devices(), api.usage(),
      ])
      if (stopped) return
      if (w.status === 'fulfilled') {
        const st = w.value.status
        const map: Record<string, string> = { connected: 'Connected', waiting_scan: 'Needs QR scan', logged_out: 'Re-link required', unreachable: 'Bridge offline' }
        setWhatsapp(map[st] || 'Not linked')
        setWhatsappDot(st === 'connected' ? '#70e5aa' : st === 'waiting_scan' || st === 'logged_out' ? '#f5c15c' : '#88818f')
      }
      if (c.status === 'fulfilled') setCalendarToday(`${c.value.events?.length ?? 0} today`)
      if (m.status === 'fulfilled') setMemories(`${m.value.length} memories`)
      if (d.status === 'fulfilled') setDocuments(`${d.value.length} documents`)
      if (v.status === 'fulfilled') setDevices(`${v.value.length} linked`)
      if (u.status === 'fulfilled') setUsage(u.value)
    }
    loadAll()
    const timer = setInterval(loadAll, 20000)
    return () => { stopped = true; clearInterval(timer) }
  }, [])

  return <aside className="status-rail">
    <UsageRail usage={usage}/>
    <StatusCard title="WhatsApp" hint={whatsapp} dot={whatsappDot} icon={<MessageCircle size={14}/>}/>
    <StatusCard title="Calendar" hint={calendarToday} icon={<Calendar size={14}/>}/>
    <StatusCard title="Memory" hint={memories} icon={<MemoryStick size={14}/>}/>
    <StatusCard title="Knowledge" hint={documents} icon={<FileText size={14}/>}/>
    <StatusCard title="Devices" hint={devices} icon={<Monitor size={14}/>}/>
  </aside>
}

createRoot(document.getElementById('root')!).render(<App/>)
