import React, { useEffect, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { Brain, ChevronRight, FileText, Globe2, MemoryStick, Menu, Mic2, Monitor, Plus, Send, Settings, Sparkles, Unplug, X } from 'lucide-react'
import { MessageCircle } from 'lucide-react'
import { Mail } from 'lucide-react'
import { Activity } from 'lucide-react'
import { Calendar } from 'lucide-react'
import { FolderOpen } from 'lucide-react'
import { Code } from 'lucide-react'
import { CheckSquare, Bell, BookOpen, Zap } from 'lucide-react'
import { MessageSquare } from 'lucide-react'
import LiquidEther from './effects/LiquidEther.jsx'
import MagicRings from './effects/MagicRings.jsx'
import Strands from './effects/Strands.jsx'
import { AccessState, clearSession, isDesktop, resolveAccessState, saveSession, storedSession } from './access'
import { Conversation, DEFAULT_API, Device, DocumentItem, Memory, Message, SalarApi } from './api'
import { WorkspaceSelector } from './components/WorkspaceSelector'
import './components/WorkspaceSelector.css'
import TaskManager from './components/TaskManager'
import { ReminderPanel } from './components/ReminderPanel'
import KnowledgeBase from './components/KnowledgeBase'
import WorkflowPanel from './components/WorkflowPanel'
import './theme.css'
import './styles.css'

type View = 'home' | 'memory' | 'documents' | 'devices' | 'whatsapp' | 'email' | 'monitor' | 'calendar' | 'files' | 'code' | 'tasks' | 'reminders' | 'knowledge' | 'workflows' | 'settings'
const api = new SalarApi()
const previewShell = new URLSearchParams(location.search).get('preview') === 'dashboard'

function Loader() {
  return <main className="loader">
    <div className="loader-effect"><Strands colors={["#F97316","#7C3AED","#06B6D4"]} count={3} speed={0.5} amplitude={1} waviness={1} thickness={0.7} glow={2.6} taper={3} spread={1} intensity={0.6} saturation={1.5} opacity={1} scale={1.5} glass={false} refraction={1} dispersion={1} glassSize={1}/></div>
    <div className="loader-copy"><p>SALAR</p><span>INITIALIZING PRIVATE INTELLIGENCE</span></div>
  </main>
}

function PairingPortal({ onConnected }: { onConnected: () => void }) {
  const [mode, setMode] = useState<'code' | 'login'>('code')
  const [code, setCode] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [url, setUrl] = useState(api.baseUrl)
  async function pair(event: React.FormEvent) {
    event.preventDefault()
    if (code.length !== 6) return setError('Enter the six-digit code shown by SALAR Desktop.')
    setBusy(true); setError(''); api.baseUrl = url.replace(/\/$/, ''); localStorage.setItem('salar.apiUrl', api.baseUrl)
    try {
      const result = await api.redeemPairingCode(code, navigator.userAgent.includes('iPhone') ? 'JD iPhone' : 'Web browser', navigator.userAgent.includes('iPhone') ? 'ios' : 'web')
      await saveSession(result.access_token); onConnected()
    } catch (reason) { setError((reason as Error).message) } finally { setBusy(false) }
  }
  async function login(event: React.FormEvent) {
    event.preventDefault()
    if (!email || !password) return setError('Enter your email and password.')
    setBusy(true); setError(''); api.baseUrl = url.replace(/\/$/, ''); localStorage.setItem('salar.apiUrl', api.baseUrl)
    try {
      const result = await api.login(email, password)
      await saveSession(result.access_token); onConnected()
    } catch (reason) { setError((reason as Error).message) } finally { setBusy(false) }
  }
  return <main className="pairing-screen">
    <div className="pairing-ether"><LiquidEther colors={['#5227FF','#FF9FFC','#B497CF']} mouseForce={20} cursorSize={100} resolution={0.5} autoDemo autoSpeed={0.5} autoIntensity={2.2}/></div>
    <form className="pairing-panel" onSubmit={mode === 'code' ? pair : login}>
      <div className="salar-glyph">S</div>
      <span className="eyebrow">{mode === 'code' ? 'PRIVATE DEVICE LINK' : 'SECURE LOGIN'}</span>
      <h1>{mode === 'code' ? 'Pair with SALAR' : 'Log in'}</h1>
      <p>{mode === 'code' ? 'On SALAR Desktop, open Settings and choose “Pair a device.”' : 'Use your admin account to access SALAR directly.'}</p>
      {mode === 'code' ? (
        <label>Six-digit code<input autoFocus inputMode="numeric" maxLength={6} value={code} onChange={e => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))} placeholder="000000"/></label>
      ) : (
        <><label>Email<input autoFocus type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="admin@example.com"/></label><label>Password<input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Your password"/></label></>
      )}
      {error && <div className="inline-error">{error}</div>}
      <button disabled={busy || (mode === 'code' ? code.length !== 6 : !email || !password)}>{busy ? (mode === 'code' ? 'Pairing…' : 'Logging in…') : (mode === 'code' ? 'Pair device' : 'Log in')} <ChevronRight size={17}/></button>
      <button type="button" className="text-action" style={{margin:'14px auto 0'}} onClick={() => { setMode(mode === 'code' ? 'login' : 'code'); setError('') }}>{mode === 'code' ? 'Log in with email instead' : 'Use a pairing code instead'}</button>
      <label style={{marginTop:14}}>Backend URL<input value={url} onChange={e => setUrl(e.target.value)} placeholder="http://127.0.0.1:8000" style={{fontSize:9,textAlign:'center',letterSpacing:'.05em'}}/></label>
    </form>
  </main>
}

function App() {
  const desktop = isDesktop() || previewShell
  const [ready, setReady] = useState(false)
  const [access, setAccess] = useState<AccessState>(() => resolveAccessState({ desktop, token: localStorage.getItem('salar.deviceSession') || localStorage.getItem('salar.token') || '' }))
  const [view, setView] = useState<View>('home')
  const [live, setLive] = useState(false)
  const [menu, setMenu] = useState(false)
  const [workspaceId, setWorkspaceId] = useState<string | null>(null)

  useEffect(() => { const timer = setTimeout(() => setReady(true), 800); return () => clearTimeout(timer) }, [])
  useEffect(() => {
    if (!desktop) return
    storedSession().then(token => {
      if (token) {
        api.token = token
        setAccess('connected')
      }
    })
  }, [desktop])
  useEffect(() => {
    if (access !== 'connected') return
    let stopped = false
    async function check() {
      try { await api.validateSession() }
      catch (reason) {
        const msg = String(reason)
        if (msg.includes('401') || msg.includes('Authentication') || msg.includes('invalid') || msg.includes('expired')) {
          await clearSession(); api.token = ''
          if (!stopped) setAccess(desktop ? 'desktop-disconnected' : 'pairing')
        }
      }
      if (!stopped) setTimeout(check, 5000)
    }
    check()
    return () => { stopped = true }
  }, [access, desktop])
  useEffect(() => {
    const invoke = (window as any).__TAURI_INTERNALS__?.invoke
    if (access !== 'connected' || !invoke) return
    let stopped = false, timer = 0
    async function poll() {
      try {
        const saved = await storedSession()
        if (!saved) return
        const command = await api.nextDeviceCommand(saved)
        if (command) {
          try { const data = await invoke('execute_device_command', { kind: command.kind, payload: command.payload }); await api.completeDeviceCommand(command.id, saved, { ok: true, detail: 'Executed by SALAR Desktop', data }) }
          catch (reason) { await api.completeDeviceCommand(command.id, saved, { ok: false, detail: String(reason) }) }
        }
      } catch { /* connection indicator handles offline state */ }
      finally { if (!stopped) timer = window.setTimeout(poll, 1800) }
    }
    poll(); return () => { stopped = true; clearTimeout(timer) }
  }, [access])
  if (!ready) return <Loader/>
  if (!desktop && access === 'pairing') return <PairingPortal onConnected={() => setAccess('connected')}/>
  const nav = [['home', Sparkles, 'Intelligence'], ['memory', MemoryStick, 'Memory'], ['documents', FileText, 'Documents'], ['devices', Monitor, 'Devices'], ['whatsapp', MessageCircle, 'WhatsApp'], ['email', Mail, 'Email'], ['monitor', Activity, 'Monitor'], ['calendar', Calendar, 'Calendar'], ['files', FolderOpen, 'Files'], ['code', Code, 'Code'], ['tasks', CheckSquare, 'Tasks'], ['reminders', Bell, 'Reminders'], ['knowledge', BookOpen, 'Knowledge'], ['workflows', Zap, 'Workflows'], ['settings', Settings, 'Settings']] as const
  return <><main className={`app-shell${live ? ' live-open' : ''}`}>
    <div className="liquid-stage"><LiquidEther colors={['#5227FF','#FF9FFC','#B497CF']} mouseForce={20} cursorSize={100} isViscous={false} viscous={30} iterationsViscous={32} iterationsPoisson={32} resolution={0.5} isBounce={false} autoDemo autoSpeed={0.5} autoIntensity={2.2} takeoverDuration={0.25} autoResumeDelay={3000} autoRampDuration={0.6}/></div>
    <header className="topbar"><button className="mobile-menu" onClick={() => setMenu(!menu)}><Menu/></button><div className="brand"><div className="salar-glyph">S</div><div><b>SALAR</b><small>PERSONAL INTELLIGENCE</small></div></div><nav className="topnav">{nav.slice(0, 4).map(([id,,label]) => <button key={id} className={view === id ? 'active' : ''} onClick={() => setView(id)}>{label}</button>)}</nav><WorkspaceSelector current={workspaceId} onChange={setWorkspaceId}/><button className={`connection ${access}`} onClick={() => setView('settings')}><i/>{access === 'connected' ? 'SECURE LINK' : 'CONNECT'}</button></header>
    <aside className={menu ? 'open' : ''}>{nav.map(([id, Icon, label]) => <button key={id} className={view === id ? 'active' : ''} onClick={() => { setView(id); setMenu(false) }}><Icon size={17}/><span>{label}</span></button>)}</aside>
    <section className="workspace">
      {view === 'home' && <Chat connected={access === 'connected'} onLive={() => setLive(true)} onConnect={() => setView('settings')}/>} 
      {view === 'memory' && <Memories connected={access === 'connected'}/>}
      {view === 'documents' && <Documents connected={access === 'connected'}/>}
      {view === 'devices' && <Devices connected={access === 'connected'}/>}
      {view === 'whatsapp' && <WhatsApp connected={access === 'connected'}/>}
      {view === 'email' && <Email connected={access === 'connected'}/>}
      {view === 'monitor' && <SystemMonitor connected={access === 'connected'}/>}
      {view === 'calendar' && <CalendarView connected={access === 'connected'}/>}
      {view === 'files' && <FileManager connected={access === 'connected'}/>}
      {view === 'code' && <CodeInterpreter connected={access === 'connected'}/>}
      {view === 'tasks' && <TaskManager workspaceId={workspaceId}/>}
      {view === 'reminders' && <ReminderPanel workspaceId={workspaceId}/>}
      {view === 'knowledge' && <KnowledgeBase workspaceId={workspaceId}/>}
      {view === 'workflows' && <WorkflowPanel workspaceId={workspaceId}/>}
      {view === 'settings' && <SettingsPage access={access} onAccess={setAccess}/>} 
    </section>
  </main>{live && <Live connected={access === 'connected'} onClose={() => setLive(false)}/>}</>
}

function Chat({ connected, onLive, onConnect }: { connected: boolean; onLive: () => void; onConnect: () => void }) {
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
  return <div className={`chat-view${messages.length ? ' has-messages' : ''}`}><div className="hero"><span className="eyebrow">COORDINATED INTELLIGENCE</span><h1>{messages.length ? 'Command stream' : 'What shall we accomplish?'}</h1><p>Private intelligence, memory, knowledge, and your connected devices—coordinated from one place.</p></div>    <div className="messages" ref={messagesRef}><div className="messages-spacer"/>{messages.map(message => <article key={message.id} className={message.role}><span>{message.role === 'assistant' ? 'SALAR' : 'YOU'}</span><p>{message.content}</p></article>)}{streaming && <article className="assistant thinking"><span>SALAR</span><p>{streaming}</p></article>}{toolActivity && !streaming && <article className="assistant thinking tool-activity"><span>SALAR</span><p className="tool-hint">{toolActivity}</p></article>}{busy && !streaming && !toolActivity && <article className="assistant thinking"><span>SALAR</span><p>Reasoning across your private context…</p></article>}<div ref={end}/></div>{error && <div className="toast">{error}</div>}<div className="composer"><button className="icon-control live-control" onClick={onLive} title="Enter Live mode"><Mic2/></button><textarea value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }} placeholder={connected ? 'Ask, create, search, or control…' : 'Connect SALAR in Settings to begin…'} disabled={!connected} rows={1}/><button className="icon-control send-control" onClick={send} disabled={!connected || busy || !input.trim()} title="Send command"><Send/></button></div></div>
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
      }, 10000)

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
      const text = await api.stt(blob, true)
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

function WhatsApp({ connected }: { connected: boolean }) {
  const [status, setStatus] = useState<'unknown' | 'waiting_scan' | 'connected' | 'unreachable'>('unknown')
  const [qrData, setQrData] = useState('')
  const [chats, setChats] = useState<{ jid: string; name: string; lastMessage: string | null }[]>([])
  const [selectedChat, setSelectedChat] = useState('')
  const [messages, setMessages] = useState<{ id: string; fromMe: boolean; text: string; senderName: string }[]>([])
  const [sendTo, setSendTo] = useState('')
  const [sendText, setSendText] = useState('')
  const [chatInput, setChatInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [loadingChats, setLoadingChats] = useState(false)
  const [loadingMessages, setLoadingMessages] = useState(false)
  const [autoReply, setAutoReply] = useState(false)
  const [passMessages, setPassMessages] = useState<Array<{ id: number; detail: any; time: string }>>([])
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!connected) return
    let stopped = false
    async function poll() {
      try {
        const s = await api.whatsappStatus()
        if (stopped) return
        setStatus(s.status as any)
        if (s.status === 'waiting_scan') {
          try { const qr = await api.whatsappQR(); if (!stopped) setQrData(qr.qr) } catch {}
        } else {
          setQrData('')
          if (s.status === 'connected' && !loadingChats) loadChats()
        }
      } catch {}
      if (!stopped) setTimeout(poll, 3000)
    }
    poll()
    api.whatsappAutoReplyGet().then(r => { if (!stopped) setAutoReply(r.enabled) }).catch(() => {})
    api.whatsappPassMessages().then(r => { if (!stopped) setPassMessages(r.messages || []) }).catch(() => {})
    return () => { stopped = true }
  }, [connected])

  async function loadChats() {
    setLoadingChats(true)
    try { const list = await api.whatsappChats(); setChats(list) } catch {}
    setLoadingChats(false)
  }

  async function loadMessages(jid: string) {
    setSelectedChat(jid); setLoadingMessages(true); setMessages([])
    try { const msgs = await api.whatsappMessages(jid); setMessages(msgs) } catch {}
    setLoadingMessages(false)
  }

  async function sendDM() {
    if (!sendTo.trim() || !sendText.trim()) return
    setBusy(true); setError('')
    try { await api.whatsappSend(sendTo.trim(), sendText.trim()); setSendText('') }
    catch (e) { setError((e as Error).message) }
    setBusy(false)
  }

  async function sendChatMessage() {
    if (!selectedChat || !chatInput.trim()) return
    setBusy(true); setError(''); setChatInput('')
    try { await api.whatsappSend(selectedChat, chatInput.trim()); setTimeout(() => loadMessages(selectedChat), 1000) }
    catch (e) { setError((e as Error).message) }
    setBusy(false)
  }

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  async function toggleAutoReply() {
    const next = !autoReply
    setAutoReply(next)
    try { await api.whatsappAutoReplySet(next) } catch { setAutoReply(!next) }
  }

  return <Page title="WhatsApp" subtitle="Connect your WhatsApp to read and send messages through SALAR.">
    {error && <div className="inline-error">{error}</div>}
    {status === 'unknown' && <div className="loading-hint">Connecting to WhatsApp bridge…</div>}
    {status === 'unreachable' && <div className="wa-reconnect-section">
      <p>WhatsApp is not connected. Make sure the WhatsApp bridge is running.</p>
      <button className="primary" onClick={async () => { setStatus('unknown'); try { const s = await api.whatsappStatus(); setStatus(s.status as any) } catch { setStatus('unreachable') } }}>Try again</button>
    </div>}
    {status === 'waiting_scan' && <div className="wa-qr-section">
      <p>Open WhatsApp on your phone → <strong>Settings → Linked Devices → Link a Device</strong></p>
      {qrData ? <div className="wa-qr-box"><img src={`https://api.qrserver.com/v1/create-qr-code/?size=220x220&data=${encodeURIComponent(qrData)}`} alt="Scan this QR code" width={220}/></div> : <div className="loading-hint">Generating QR code…</div>}
    </div>}
    {status === 'connected' && <div className="wa-connected-badge">WhatsApp connected</div>}
    {status === 'connected' && <div className="wa-autoreply-row">
      <label className="wa-autoreply-toggle">
        <span>AI Auto-Reply</span>
        <button className={autoReply ? 'toggle active' : 'toggle'} onClick={toggleAutoReply}>
          {autoReply ? 'ON' : 'OFF'}
        </button>
      </label>
      <small>{autoReply ? 'SALAR will reply to incoming messages automatically' : 'Auto-reply is off'}</small>
    </div>}
    {status === 'connected' && <div className="wa-logout-row">
      <button className="wa-logout-btn" onClick={async () => { if (confirm('Disconnect this WhatsApp? You will need to scan the QR code again.')) { await api.whatsappLogout(); setStatus('unreachable'); setQrData(''); setChats([]); setMessages([]) } }}>Change WhatsApp account</button>
    </div>}
    {status === 'connected' && passMessages.filter(m => !m.detail.acknowledged).length > 0 && <div className="wa-pass-section">
      <label>Messages for you</label>
      {passMessages.filter(m => !m.detail.acknowledged).map(m => <div key={m.id} className="wa-pass-msg">
        <strong>{m.detail.sender_name}</strong>
        <p>{m.detail.message}</p>
        <small>{m.time}</small>
        <button onClick={async () => { await api.whatsappPassMessageAck(String(m.id)); setPassMessages(prev => prev.map(p => p.id === m.id ? { ...p, detail: { ...p.detail, acknowledged: true } } : p)) }}>Got it</button>
      </div>)}
    </div>}
    {status === 'connected' && <div className="wa-layout">
      <div className="wa-sidebar">
        <button className="wa-refresh" onClick={loadChats} disabled={loadingChats}>{loadingChats ? 'Loading…' : 'Refresh chats'}</button>
        <label>Send direct message<small>Enter phone number with country code</small></label>
        <input value={sendTo} onChange={e => setSendTo(e.target.value)} placeholder="1234567890"/>
        <textarea value={sendText} onChange={e => setSendText(e.target.value)} rows={2} placeholder="Message…"/>
        <button className="primary" disabled={busy || !sendTo.trim() || !sendText.trim()} onClick={sendDM}>{busy ? 'Sending…' : 'Send message'}</button>
        <div className="wa-chat-list">
          {chats.map(c => <button key={c.jid} className={selectedChat === c.jid ? 'active' : ''} onClick={() => loadMessages(c.jid)}>
            <strong>{c.name || c.jid.split('@')[0]}</strong><small>{c.lastMessage || 'No messages yet'}</small>
          </button>)}
          {!chats.length && !loadingChats && <p className="wa-empty">No chats yet</p>}
        </div>
      </div>
      <div className="wa-chat-panel">
        {selectedChat ? <>
          <div className="wa-chat-header"><strong>{chats.find(c => c.jid === selectedChat)?.name || selectedChat.split('@')[0]}</strong></div>
          <div className="wa-messages">
            {loadingMessages && <div className="loading-hint">Loading messages…</div>}
            {messages.map(m => <div key={m.id} className={m.fromMe ? 'wa-msg me' : 'wa-msg'}>
              {!m.fromMe && <small>{m.senderName || m.fromMe}</small>}
              <span>{m.text}</span>
            </div>)}
            <div ref={endRef}/>
          </div>
          <div className="wa-input-bar">
            <input value={chatInput} onChange={e => setChatInput(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') sendChatMessage() }} placeholder="Type a message…"/>
            <button className="icon-control" onClick={sendChatMessage} disabled={busy || !chatInput.trim()}><Send size={16}/></button>
          </div>
        </> : <div className="wa-empty-chat"><MessageCircle size={48} opacity={0.3}/><p>Select a chat to start messaging</p></div>}
      </div>
    </div>}
  </Page>
}

function Email({ connected }: { connected: boolean }) {
  const [connected2, setConnected2] = useState(false)
  const [address, setAddress] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [folders, setFolders] = useState<{ folder: string; total: number; unread: number }[]>([])
  const [selectedFolder, setSelectedFolder] = useState('INBOX')
  const [emails, setEmails] = useState<{ id: string; from: string; subject: string; date: string }[]>([])
  const [selectedEmail, setSelectedEmail] = useState<{ id: string; from: string; to: string; subject: string; body: string; date: string } | null>(null)
  const [loadingEmails, setLoadingEmails] = useState(false)
  const [sendMode, setSendMode] = useState(false)
  const [sendTo, setSendTo] = useState('')
  const [sendSubject, setSendSubject] = useState('')
  const [sendBody, setSendBody] = useState('')
  const [sending, setSending] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')

  useEffect(() => {
    if (!connected) return
    api.emailStatus().then(s => { setConnected2(s.connected); if (s.connected) loadFolders() }).catch(() => {})
  }, [connected])

  async function connect() {
    setBusy(true); setError('')
    try {
      const result = await api.emailConnect({ address, password })
      setConnected2(true); setFolders(result.folders); setPassword('')
    } catch (e) { setError((e as Error).message) }
    setBusy(false)
  }

  async function loadFolders() {
    try { const result = await api.emailFolders(); setFolders(result.folders) } catch {}
  }

  async function loadEmails(folder: string, query?: string) {
    setSelectedFolder(folder); setSelectedEmail(null); setLoadingEmails(true)
    try {
      const result = await api.emailSearch(folder, query || 'ALL', 30)
      setEmails(result.emails)
    } catch (e) { setError((e as Error).message) }
    setLoadingEmails(false)
  }

  async function readEmail(id: string) {
    try { const email = await api.emailRead(id, selectedFolder); setSelectedEmail(email) } catch (e) { setError((e as Error).message) }
  }

  async function sendEmail() {
    if (!sendTo || !sendSubject || !sendBody) return
    setSending(true); setError('')
    try {
      await api.emailSend(sendTo, sendSubject, sendBody)
      setSendMode(false); setSendTo(''); setSendSubject(''); setSendBody('')
    } catch (e) { setError((e as Error).message) }
    setSending(false)
  }

  async function searchEmails() {
    if (!searchQuery.trim()) return loadEmails(selectedFolder)
    setLoadingEmails(true)
    try {
      const result = await api.emailSearch(selectedFolder, `OR SUBJECT "${searchQuery}" FROM "${searchQuery}"`, 30)
      setEmails(result.emails)
    } catch (e) { setError((e as Error).message) }
    setLoadingEmails(false)
  }

  if (!connected2) return <Page title="Email" subtitle="Connect your email to read, search, and send through SALAR.">
    <div className="email-connect">
      {error && <div className="inline-error">{error}</div>}
      <label>Email address<input type="email" value={address} onChange={e => setAddress(e.target.value)} placeholder="you@gmail.com"/></label>
      <label>Password / App password<input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="For Gmail, use an App Password"/></label>
      <small style={{fontSize:8,color:'var(--muted)',margin:'-4px 0 8px',display:'block'}}>Gmail users: enable 2FA, then generate an App Password at myaccount.google.com/apppasswords</small>
      <button className="primary" disabled={busy || !address || !password} onClick={connect}>{busy ? 'Connecting…' : 'Connect email'}</button>
    </div>
  </Page>

  return <Page title="Email" subtitle="Read, search, and send emails through SALAR.">
    <div className="email-layout">
      <div className="email-sidebar">
        <button className="primary" onClick={() => { setSendMode(true); setSelectedEmail(null) }}><Plus size={14}/> Compose</button>
        <div className="email-search"><input value={searchQuery} onChange={e => setSearchQuery(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') searchEmails() }} placeholder="Search…"/><button onClick={searchEmails}>Go</button></div>
        <div className="email-folder-list">
          {folders.map(f => <button key={f.folder} className={selectedFolder === f.folder ? 'active' : ''} onClick={() => loadEmails(f.folder)}>
            {f.folder} {f.unread > 0 && <span className="email-unread-badge">{f.unread}</span>}
          </button>)}
        </div>
      </div>
      <div className="email-main">
        {sendMode ? <div className="email-compose">
          <div className="email-compose-header"><strong>New message</strong><button onClick={() => setSendMode(false)}>Cancel</button></div>
          <input value={sendTo} onChange={e => setSendTo(e.target.value)} placeholder="To"/>
          <input value={sendSubject} onChange={e => setSendSubject(e.target.value)} placeholder="Subject"/>
          <textarea value={sendBody} onChange={e => setSendBody(e.target.value)} rows={12} placeholder="Write your message…"/>
          <button className="primary" disabled={sending || !sendTo || !sendSubject || !sendBody} onClick={sendEmail}>{sending ? 'Sending…' : 'Send'}</button>
        </div> : selectedEmail ? <div className="email-detail">
          <button className="email-back" onClick={() => setSelectedEmail(null)}>← Back</button>
          <h3>{selectedEmail.subject}</h3>
          <div className="email-meta"><strong>{selectedEmail.from}</strong><small>{selectedEmail.date}</small></div>
          <p>{selectedEmail.body}</p>
        </div> : <div className="email-list">
          {loadingEmails && <div className="loading-hint">Loading…</div>}
          {!loadingEmails && !emails.length && <div className="wa-empty">No emails in this folder</div>}
          {emails.map(e => <button key={e.id} className="email-item" onClick={() => readEmail(e.id)}>
            <div className="email-item-from">{e.from.split('<')[0].trim()}</div>
            <div className="email-item-subject">{e.subject}</div>
            <div className="email-item-date">{e.date?.split(',').pop()?.trim() || ''}</div>
          </button>)}
        </div>}
      </div>
    </div>
  </Page>
}

function SystemMonitor({ connected }: { connected: boolean }) {
  const [snap, setSnap] = useState<any>(null)
  const [history, setHistory] = useState<{ time: number; cpu: number; mem: number; netRecv: number; netSent: number }[]>([])
  const [processes, setProcesses] = useState<{ pid: number; name: string; cpu_percent: number; memory_percent: number }[]>([])
  const [showProcs, setShowProcs] = useState(false)

  useEffect(() => {
    if (!connected) return
    const stop = api.monitorStream((data) => {
      setSnap(data)
      setHistory(prev => {
        const next = [...prev, { time: data.timestamp, cpu: data.cpu.percent, mem: data.memory.percent, netRecv: data.network.rate_recv || 0, netSent: data.network.rate_sent || 0 }]
        return next.slice(-60)
      })
    })
    return () => stop()
  }, [connected])

  async function loadProcesses() {
    try { const r = await api.monitorProcesses(); setProcesses(r.processes) } catch {}
  }

  function fmtUptime(s: number) {
    const d = Math.floor(s / 86400); const h = Math.floor((s % 86400) / 3600); const m = Math.floor((s % 3600) / 60)
    return `${d}d ${h}h ${m}m`
  }

  function fmtBytes(b: number) {
    if (b < 1024**2) return `${(b/1024).toFixed(1)} KB`
    if (b < 1024**3) return `${(b/1024**2).toFixed(1)} MB`
    return `${(b/1024**3).toFixed(2)} GB`
  }

  if (!connected) return <Page title="System Monitor" subtitle="Real-time system health dashboard."><p>Connect to your backend to monitor system resources.</p></Page>
  if (!snap) return <Page title="System Monitor" subtitle="Real-time system health dashboard."><div className="loading-hint">Connecting to monitor stream…</div></Page>

  const cpuHistory = history.map(h => h.cpu)
  const memHistory = history.map(h => h.mem)

  return <Page title="System Monitor" subtitle={`${snap.os.hostname} · ${snap.os.system} ${fmtUptime(snap.os.uptime_seconds)} uptime`}>
    <div className="mon-grid">
      <div className="mon-card">
        <div className="mon-card-header"><Activity size={14}/><span>CPU</span><span className="mon-value">{snap.cpu.percent}%</span></div>
        <div className="mon-bar"><div className="mon-bar-fill cpu" style={{ width: `${snap.cpu.percent}%` }}/></div>
        <div className="mon-card-detail">{snap.cpu.cores_logical} cores · {snap.cpu.freq_mhz ? `${snap.cpu.freq_mhz} MHz` : ''}</div>
        <div className="mon-sparkline">{cpuHistory.map((v, i) => <div key={i} className="mon-spark-bar cpu" style={{ height: `${v}%` }}/>)}</div>
      </div>
      <div className="mon-card">
        <div className="mon-card-header"><MemoryStick size={14}/><span>Memory</span><span className="mon-value">{snap.memory.percent}%</span></div>
        <div className="mon-bar"><div className="mon-bar-fill mem" style={{ width: `${snap.memory.percent}%` }}/></div>
        <div className="mon-card-detail">{snap.memory.used_gb} / {snap.memory.total_gb} GB</div>
        <div className="mon-sparkline">{memHistory.map((v, i) => <div key={i} className="mon-spark-bar mem" style={{ height: `${v}%` }}/>)}</div>
      </div>
      {snap.disk.partitions.map((p: any) => <div key={p.mountpoint} className="mon-card">
        <div className="mon-card-header"><FileText size={14}/><span>{p.device}</span><span className="mon-value">{p.percent}%</span></div>
        <div className="mon-bar"><div className="mon-bar-fill disk" style={{ width: `${p.percent}%` }}/></div>
        <div className="mon-card-detail">{p.used_gb} / {p.total_gb} GB · {p.mountpoint}</div>
      </div>)}
      <div className="mon-card">
        <div className="mon-card-header"><Globe2 size={14}/><span>Network</span></div>
        <div className="mon-net">
          <div><small>↓</small> {snap.network.rate_recv_human || '0 B/s'}</div>
          <div><small>↑</small> {snap.network.rate_sent_human || '0 B/s'}</div>
        </div>
        <div className="mon-card-detail">Total sent: {fmtBytes(snap.network.bytes_sent)} · recv: {fmtBytes(snap.network.bytes_recv)}</div>
      </div>
      <div className="mon-card mon-card-full">
        <div className="mon-card-header"><Monitor size={14}/><span>Processes</span><span className="mon-value">{snap.processes.total} total</span></div>
        <button className="mon-proc-toggle" onClick={() => { setShowProcs(!showProcs); if (!showProcs) loadProcesses() }}>{showProcs ? 'Hide' : 'Show top processes'}</button>
        {showProcs && <div className="mon-proc-list">
          <div className="mon-proc-row mon-proc-header"><span>Name</span><span>CPU%</span><span>MEM%</span></div>
          {(processes.length ? processes : snap.processes.top_cpu.map((p: any) => ({ ...p, memory_percent: 0 }))).slice(0, 15).map((p: any) => <div key={p.pid} className="mon-proc-row">
            <span>{p.name}</span><span>{p.cpu_percent}%</span><span>{p.memory_percent}%</span>
          </div>)}
        </div>}
      </div>
    </div>
  </Page>
}

function CalendarView({ connected }: { connected: boolean }) {
  const [feeds, setFeeds] = useState<{ name: string; url: string; color: string }[]>([])
  const [events, setEvents] = useState<any[]>([])
  const [todayEvents, setTodayEvents] = useState<any[]>([])
  const [feedName, setFeedName] = useState('')
  const [feedUrl, setFeedUrl] = useState('')
  const [showAdd, setShowAdd] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!connected) return
    loadData()
  }, [connected])

  async function loadData() {
    setLoading(true)
    try {
      const [f, t, e] = await Promise.all([
        api.calendarFeeds(),
        api.calendarToday(),
        api.calendarEvents(0, 14),
      ])
      setFeeds(f.feeds); setTodayEvents(t.events); setEvents(e.events)
    } catch {}
    setLoading(false)
  }

  async function addFeed() {
    if (!feedName || !feedUrl) return
    setError('')
    try {
      await api.calendarAddFeed(feedName, feedUrl)
      setFeedName(''); setFeedUrl(''); setShowAdd(false)
      loadData()
    } catch (e) { setError((e as Error).message) }
  }

  function fmtDate(iso: string) {
    if (!iso) return ''
    try {
      const d = new Date(iso)
      if (isNaN(d.getTime())) return iso
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
    } catch { return iso }
  }

  function groupByDay(evts: any[]) {
    const groups: Record<string, any[]> = {}
    for (const e of evts) {
      const day = e.start ? new Date(e.start).toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' }) : 'Other'
      if (!groups[day]) groups[day] = []
      groups[day].push(e)
    }
    return groups
  }

  return <Page title="Calendar" subtitle="Your schedule across all connected calendars.">
    {error && <div className="inline-error">{error}</div>}
    <div className="cal-toolbar">
      <button className="primary" onClick={() => setShowAdd(!showAdd)}><Plus size={14}/> Add calendar feed</button>
      <button onClick={loadData} disabled={loading}>{loading ? 'Loading…' : 'Refresh'}</button>
    </div>
    {showAdd && <div className="cal-add-form">
      <input value={feedName} onChange={e => setFeedName(e.target.value)} placeholder="Calendar name (e.g., Personal)"/>
      <input value={feedUrl} onChange={e => setFeedUrl(e.target.value)} placeholder="iCal URL (.ics)"/>
      <button className="primary" onClick={addFeed}>Add</button>
      <button onClick={() => setShowAdd(false)}>Cancel</button>
    </div>}
    <div className="cal-feeds">{feeds.map(f => <div key={f.name} className="cal-feed-tag" style={{ borderLeftColor: f.color }}>{f.name}</div>)}</div>
    {todayEvents.length > 0 && <div className="cal-section">
      <h3>Today</h3>
      {todayEvents.map((e, i) => <div key={i} className="cal-event today" style={{ borderLeftColor: e.color || '#5227FF' }}>
        <div className="cal-event-time">{e.all_day ? 'All day' : fmtDate(e.start)}</div>
        <div className="cal-event-summary">{e.summary}</div>
        {e.location && <div className="cal-event-location">{e.location}</div>}
      </div>)}
    </div>}
    <div className="cal-section">
      <h3>Upcoming events</h3>
      {loading && <div className="loading-hint">Loading…</div>}
      {!loading && !events.length && <p style={{fontSize:10,color:'var(--muted)'}}>No events. Add a calendar feed to get started.</p>}
      {Object.entries(groupByDay(events)).map(([day, evts]) => <div key={day}>
        <div className="cal-day-header">{day}</div>
        {evts.map((e, i) => <div key={i} className="cal-event" style={{ borderLeftColor: e.color || '#5227FF' }}>
          <div className="cal-event-time">{e.all_day ? 'All day' : fmtDate(e.start)}</div>
          <div className="cal-event-summary">{e.summary}</div>
          {e.location && <div className="cal-event-location">{e.location}</div>}
        </div>)}
      </div>)}
    </div>
  </Page>
}

function FileManager({ connected }: { connected: boolean }) {
  const [path, setPath] = useState('')
  const [items, setItems] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [selected, setSelected] = useState<string | null>(null)
  const [selectedInfo, setSelectedInfo] = useState<any>(null)
  const [editorContent, setEditorContent] = useState('')
  const [editing, setEditing] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<any[]>([])
  const [error, setError] = useState('')
  const [newFolder, setNewFolder] = useState('')
  const [showNewFolder, setShowNewFolder] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => { if (connected) loadDir(path) }, [connected])

  async function loadDir(p: string) {
    setLoading(true); setError('')
    try { const r = await api.fileList(p); setItems(r.items); setPath(r.path) }
    catch (e) { setError((e as Error).message) }
    setLoading(false)
  }

  async function openItem(item: any) {
    if (item.is_dir) { loadDir(item.path) }
    else {
      setSelected(item.path); setSelectedInfo(item)
      if (item.is_text) {
        try { const r = await api.fileRead(item.path); setEditorContent(r.content); setEditing(item.path) }
        catch (e) { setError((e as Error).message) }
      }
    }
  }

  function goUp() { const parts = path.split('/').filter(Boolean); parts.pop(); loadDir(parts.join('/')) }

  async function doSearch() {
    if (!searchQuery) return setSearchResults([])
    try { const r = await api.fileSearch(searchQuery); setSearchResults(r.results) }
    catch (e) { setError((e as Error).message) }
  }

  async function saveFile() {
    if (!editing) return
    try { await api.fileWrite(editing, editorContent); setEditing(null) }
    catch (e) { setError((e as Error).message) }
  }

  async function deleteItem(p: string) {
    if (!confirm('Delete this item?')) return
    try { await api.fileDelete(p); setSelected(null); loadDir(path) }
    catch (e) { setError((e as Error).message) }
  }

  async function createFolder() {
    if (!newFolder) return
    try { await api.fileMkdir(path ? `${path}/${newFolder}` : newFolder); setNewFolder(''); setShowNewFolder(false); loadDir(path) }
    catch (e) { setError((e as Error).message) }
  }

  function uploadFile() { inputRef.current?.click() }
  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]; if (!file) return
    try { await api.fileUpload(path, file); loadDir(path) }
    catch (err) { setError((err as Error).message) }
    e.target.value = ''
  }

  function iconFor(item: any) {
    if (item.is_dir) return '📁'
    const ext = item.extension
    if (['.py', '.js', '.ts', '.tsx', '.jsx'].includes(ext)) return '📜'
    if (['.md', '.txt', '.rst'].includes(ext)) return '📝'
    if (['.json', '.yaml', '.yml', '.toml'].includes(ext)) return '⚙️'
    if (['.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp'].includes(ext)) return '🖼️'
    if (['.mp3', '.wav', '.ogg', '.flac'].includes(ext)) return '🎵'
    if (['.mp4', '.avi', '.mkv', '.mov'].includes(ext)) return '🎬'
    if (['.zip', '.tar', '.gz', '.7z', '.rar'].includes(ext)) return '📦'
    if (['.pdf'].includes(ext)) return '📄'
    if (['.exe', '.msi', '.bat', '.sh'].includes(ext)) return '⚡'
    return '📄'
  }

  return <Page title="File Manager" subtitle={`Browsing: /${path || 'home'}`}>
    {error && <div className="inline-error">{error}</div>}
    <div className="fm-toolbar">
      <button onClick={goUp} disabled={!path}>↑ Up</button>
      <input className="fm-path" value={path} onChange={e => setPath(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') loadDir(path) }} placeholder="/path/to/dir"/>
      <button onClick={() => loadDir(path)}>Go</button>
      <div className="fm-search"><input value={searchQuery} onChange={e => setSearchQuery(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') doSearch() }} placeholder="Search files…"/><button onClick={doSearch}>🔍</button></div>
      <button onClick={() => setShowNewFolder(!showNewFolder)}>+ Folder</button>
      <button onClick={uploadFile}>↑ Upload</button>
      <input ref={inputRef} hidden type="file" onChange={handleUpload}/>
    </div>
    {showNewFolder && <div className="fm-new-folder"><input value={newFolder} onChange={e => setNewFolder(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') createFolder() }} placeholder="Folder name"/><button onClick={createFolder}>Create</button></div>}
    {searchResults.length > 0 && <div className="fm-search-results"><h4>Search results ({searchResults.length})</h4>{searchResults.map(r => <button key={r.path} onClick={() => { setSearchResults([]); openItem(r) }}>{iconFor(r)} {r.name} <small>{r.path}</small></button>)}</div>}
    <div className="fm-layout">
      <div className="fm-list">
        {loading && <div className="loading-hint">Loading…</div>}
        {!loading && !items.length && <div className="wa-empty">Empty directory</div>}
        {items.map(item => <button key={item.path} className={`fm-item ${selected === item.path ? 'active' : ''}`} onClick={() => openItem(item)}>
          <span className="fm-icon">{iconFor(item)}</span>
          <div className="fm-item-info"><span className="fm-item-name">{item.name}</span><small>{item.is_dir ? 'folder' : item.size_human}</small></div>
        </button>)}
      </div>
      <div className="fm-preview">
        {editing ? <div className="fm-editor">
          <div className="fm-editor-header"><strong>{editing.split('/').pop()}</strong><div><button onClick={saveFile} className="primary">Save</button><button onClick={() => setEditing(null)}>Close</button></div></div>
          <textarea value={editorContent} onChange={e => setEditorContent(e.target.value)} spellCheck={false}/>
        </div> : selectedInfo ? <div className="fm-detail">
          <h3>{iconFor(selectedInfo)} {selectedInfo.name}</h3>
          <div className="fm-detail-row"><small>Type</small><span>{selectedInfo.mime}</span></div>
          <div className="fm-detail-row"><small>Size</small><span>{selectedInfo.size_human}</span></div>
          <div className="fm-detail-row"><small>Modified</small><span>{new Date(selectedInfo.modified).toLocaleString()}</span></div>
          <div className="fm-detail-row"><small>Path</small><span>{selectedInfo.path}</span></div>
          <div className="fm-detail-actions"><button onClick={() => { if (selectedInfo.is_text) { api.fileRead(selectedInfo.path).then(r => { setEditorContent(r.content); setEditing(selectedInfo.path) }) } }}>Edit</button><a href={api.fileDownload(selectedInfo.path)} target="_blank" rel="noreferrer"><button>Download</button></a><button className="danger" onClick={() => deleteItem(selectedInfo.path)}>Delete</button></div>
        </div> : <div className="fm-empty-select"><FolderOpen size={48} opacity={0.2}/><p>Select a file to preview</p></div>}
      </div>
    </div>
  </Page>
}

function CodeInterpreter({ connected }: { connected: boolean }) {
  const [code, setCode] = useState('print("Hello from SALAR!")')
  const [language, setLanguage] = useState('python')
  const [output, setOutput] = useState<{ stdout: string; stderr: string; status: string; exit_code: number } | null>(null)
  const [running, setRunning] = useState(false)
  const [history, setHistory] = useState<{ language: string; status: string; stdout: string; stderr: string; exit_code: number }[]>([])

  async function run() {
    if (!code.trim()) return
    setRunning(true); setOutput(null)
    try {
      const result = await api.codeExecute(code, language)
      setOutput(result)
      setHistory(prev => [{ ...result, language }, ...prev].slice(0, 20))
    } catch (e) { setOutput({ stdout: '', stderr: (e as Error).message, status: 'error', exit_code: -1 }) }
    setRunning(false)
  }

  const presets: Record<string, string> = {
    'Hello World': 'print("Hello, World!")',
    'System Info': 'import platform, os\nprint(f"OS: {platform.system()} {platform.release()}")\nprint(f"Python: {platform.python_version()}")\nprint(f"CWD: {os.getcwd()}")',
    'Math': 'import math\nfor n in range(2, 20):\n    print(f"{n}: {\"prime\" if all(n % i != 0 for i in range(2, int(math.sqrt(n))+1)) else \"composite\"}")',
    'File List': 'import os\nfor f in sorted(os.listdir(".")):\n    print(f"  {\"📁\" if os.path.isdir(f) else \"📄\"} {f}")',
    'JSON': 'import json\ndata = {"name": "SALAR", "version": "1.0", "features": ["chat", "email", "calendar", "monitor"]}\nprint(json.dumps(data, indent=2))',
  }

  const jsPresets: Record<string, string> = {
    'Hello World': 'console.log("Hello, World!")',
    'Date/Time': 'console.log("Now:", new Date().toLocaleString())\nconsole.log("UTC:", new Date().toUTCString())',
    'Object': 'const data = { name: "SALAR", version: "1.0", features: ["chat", "email"] };\nconsole.log(JSON.stringify(data, null, 2));',
    'Array': 'const nums = [1,2,3,4,5,6,7,8,9,10];\nconsole.log("Squares:", nums.map(n => n*n));\nconsole.log("Evens:", nums.filter(n => n%2===0));',
  }

  const currentPresets = language === 'python' ? presets : jsPresets

  return <Page title="Code Interpreter" subtitle="Run Python and JavaScript in a sandboxed environment.">
    <div className="code-layout">
      <div className="code-editor">
        <div className="code-toolbar">
          <select value={language} onChange={e => setLanguage(e.target.value)}>
            <option value="python">Python</option>
            <option value="javascript">JavaScript</option>
          </select>
          <div className="code-presets">{Object.keys(currentPresets).map(k => <button key={k} onClick={() => setCode(currentPresets[k])}>{k}</button>)}</div>
          <button className="primary" onClick={run} disabled={running || !code.trim()}>{running ? 'Running…' : '▶ Run'}</button>
        </div>
        <textarea className="code-textarea" value={code} onChange={e => setCode(e.target.value)} spellCheck={false} placeholder="Write your code here…"/>
      </div>
      <div className="code-output">
        <h4>Output {output && <span className={`code-status ${output.status}`}>{output.status === 'ok' ? '✓ Success' : output.status === 'timeout' ? '⏱ Timeout' : '✗ Error'}</span>}</h4>
        {output ? <pre className="code-result">{output.stdout || ''}{output.stderr ? `\n--- stderr ---\n${output.stderr}` : ''}</pre> : <p style={{fontSize:9,color:'var(--muted)'}}>Run code to see output here</p>}
        {history.length > 1 && <div className="code-history">
          <h4>History</h4>
          {history.slice(1).map((h, i) => <div key={i} className="code-history-item">
            <span className={`code-status ${h.status}`}>{h.status}</span>
            <small>{h.language}</small>
            <span className="code-history-preview">{(h.stdout || h.stderr || '').slice(0, 80)}</span>
          </div>)}
        </div>}
      </div>
    </div>
  </Page>
}

function Memories({ connected }: { connected: boolean }) { const [items, setItems] = useState<Memory[]>([]); const [loading, setLoading] = useState(true); useEffect(() => { if (connected) { setLoading(true); api.memories().then(setItems).finally(() => setLoading(false)) } else { setLoading(false) } }, [connected]); return <Page title="Memory" subtitle="Facts and decisions SALAR carries forward."><div className="grid">{loading && <div className="loading-hint">Loading…</div>}{items.map(item => <Card key={item.id} icon={<Brain/>} title={item.title} text={item.content}/>)}<Card icon={<Plus/>} title={connected ? 'Add through conversation' : 'Backend disconnected'} text={connected ? 'Ask SALAR to remember anything important.' : 'Provision this device in Settings.'}/></div></Page> }
function Documents({ connected }: { connected: boolean }) { const [items, setItems] = useState<DocumentItem[]>([]); const [loading, setLoading] = useState(true); const input = useRef<HTMLInputElement>(null); useEffect(() => { if (connected) { setLoading(true); api.documents().then(setItems).finally(() => setLoading(false)) } else { setLoading(false) } }, [connected]); async function add(file?: File) { if (file) { try { const uploaded = await api.upload(file); setItems(current => [uploaded, ...current]) } catch (e) { console.error('Upload failed:', e) } } } return <Page title="Knowledge" subtitle="Search documents, notes, and source code.">{connected && <button className="primary" onClick={() => input.current?.click()}><Plus size={16}/> Index document</button>}<input ref={input} hidden type="file" onChange={e => add(e.target.files?.[0])}/><div className="grid">{loading && <div className="loading-hint">Loading…</div>}{items.map(item => <Card key={item.id} icon={<FileText/>} title={item.filename} text={item.media_type}/>)}</div></Page> }
function Devices({ connected }: { connected: boolean }) { const [items, setItems] = useState<Device[]>([]); const [loading, setLoading] = useState(true); useEffect(() => { if (connected) { setLoading(true); api.devices().then(setItems).finally(() => setLoading(false)) } else { setLoading(false) } }, [connected]); return <Page title="Connected devices" subtitle="Permission-aware control through your private backend."><div className="grid">{loading && <div className="loading-hint">Loading…</div>}{items.map(item => <Card key={item.id} icon={<Monitor/>} title={item.name} text={`${item.platform} · ${item.last_seen_at ? 'online recently' : 'registered'}`}/>)}{!items.length && !loading && <Card icon={<Globe2/>} title={connected ? 'No command devices linked' : 'Backend disconnected'} text={connected ? 'SALAR Desktop registers automatically after provisioning.' : 'Open Settings to connect this installation.'}/>}</div></Page> }

function SettingsPage({ access, onAccess }: { access: AccessState; onAccess: (state: AccessState) => void }) {
  const [tab, setTab] = useState<'connection' | 'alerts'>('connection')
  const [url, setUrl] = useState(localStorage.getItem('salar.apiUrl') || DEFAULT_API)
  const [key, setKey] = useState('')
  const [pairing, setPairing] = useState<{ code: string; expires_at: string } | null>(null)
  const [notice, setNotice] = useState('')
  const [rules, setRules] = useState<any[]>([])
  const [triggered, setTriggered] = useState<any[]>([])
  const [ruleName, setRuleName] = useState('')
  const [ruleType, setRuleType] = useState('disk_usage')
  const [ruleThreshold, setRuleThreshold] = useState('90')
  const [ruleSeverity, setRuleSeverity] = useState('warning')
  const [loadingAlerts, setLoadingAlerts] = useState(false)

  async function provision() { try { localStorage.setItem('salar.apiUrl', url); api.baseUrl = url.replace(/\/$/, ''); const result = await api.provisionDesktop(key); await saveSession(result.access_token); setKey(''); onAccess('connected'); setNotice('This desktop is securely connected.') } catch (reason) { setNotice((reason as Error).message) } }
  async function createCode() { try { setPairing(await api.createPairingCode()); setNotice('') } catch (reason) { setNotice((reason as Error).message) } }

  async function loadAlerts() {
    setLoadingAlerts(true)
    try {
      const [r, t] = await Promise.all([api.alertRules(), api.alertTriggered()])
      setRules(r.rules); setTriggered(t.alerts)
    } catch {}
    setLoadingAlerts(false)
  }

  async function addRule() {
    if (!ruleName) return
    const config: any = { threshold: parseInt(ruleThreshold) || 90, cooldown: 3600 }
    if (ruleType === 'service_down') config.url = ruleThreshold
    try { await api.alertCreate(ruleName, ruleType, config, ruleSeverity); setRuleName(''); loadAlerts() } catch {}
  }

  function fmtTime(ts: number) { try { return new Date(ts * 1000).toLocaleString() } catch { return '' } }

  return <Page title="Settings" subtitle="One private backend across desktop, web, and iPhone.">
    <div className="settings-tabs">
      <button className={tab === 'connection' ? 'active' : ''} onClick={() => setTab('connection')}>Connection</button>
      <button className={tab === 'alerts' ? 'active' : ''} onClick={() => { setTab('alerts'); loadAlerts() }}>Alerts</button>
    </div>
    {tab === 'connection' && <section className="settings-card"><label>Public API address<input value={url} onChange={e => setUrl(e.target.value)} placeholder="http://127.0.0.1:8000"/></label>{access !== 'connected' ? <><label>One-time provisioning key<input type="password" value={key} onChange={e => setKey(e.target.value)} placeholder="From your private backend .env"/></label><button className="primary" disabled={!key} onClick={provision}>Connect this desktop</button><p>The key is exchanged for a revocable machine credential and is never stored.</p></> : <><div className="connected-row"><i/> Desktop session active</div><button className="text-action danger" onClick={async () => { await clearSession(); api.token = ''; onAccess('desktop-disconnected') }}>Disconnect this desktop</button></>}<hr className="settings-divider"/><label>Pair another device<small className="settings-hint">Generate a 6-digit code to log in from a browser or phone.</small></label><button className="primary" onClick={createCode}>Generate pairing code</button>{pairing && <div className="pairing-code"><span>{pairing.code}</span><small>Expires in five minutes · Enter this on your device</small></div>}{notice && <div className="notice">{notice}</div>}</section>}
    {tab === 'alerts' && <section className="settings-card">
      <h3 style={{fontSize:12,margin:'0 0 12px'}}>Alert Rules</h3>
      <div className="alert-add-form">
        <input value={ruleName} onChange={e => setRuleName(e.target.value)} placeholder="Rule name"/>
        <select value={ruleType} onChange={e => setRuleType(e.target.value)}>
          <option value="disk_usage">Disk usage</option>
          <option value="cpu_usage">CPU usage</option>
          <option value="memory_usage">Memory usage</option>
          <option value="service_down">Service down (URL)</option>
        </select>
        <input value={ruleThreshold} onChange={e => setRuleThreshold(e.target.value)} placeholder={ruleType === 'service_down' ? 'URL' : 'Threshold %'} style={{maxWidth:100}}/>
        <select value={ruleSeverity} onChange={e => setRuleSeverity(e.target.value)}>
          <option value="info">Info</option>
          <option value="warning">Warning</option>
          <option value="critical">Critical</option>
        </select>
        <button className="primary" onClick={addRule}>Add</button>
      </div>
      {loadingAlerts && <div className="loading-hint">Loading…</div>}
      <div className="alert-rules-list">
        {rules.map(r => <div key={r.id} className="alert-rule">
          <div className="alert-rule-info"><strong>{r.name}</strong><small>{r.type} · {r.severity} · {r.enabled ? 'ON' : 'OFF'}</small></div>
          <div className="alert-rule-actions">
            <button onClick={() => api.alertToggle(r.id, !r.enabled).then(loadAlerts)}>{r.enabled ? 'Disable' : 'Enable'}</button>
            <button className="danger" onClick={() => api.alertDelete(r.id).then(loadAlerts)}>Delete</button>
          </div>
        </div>)}
        {!rules.length && !loadingAlerts && <p style={{fontSize:9,color:'var(--muted)',padding:'8px 0'}}>No alert rules configured. Add one above.</p>}
      </div>
      {triggered.length > 0 && <><h3 style={{fontSize:12,margin:'16px 0 8px'}}>Triggered Alerts</h3>
        <div className="alert-triggered-list">
          {triggered.reverse().map(a => <div key={a.id} className={`alert-triggered ${a.severity} ${a.acknowledged ? 'acked' : ''}`}>
            <div className="alert-triggered-header"><span className={`alert-severity ${a.severity}`}>{a.severity}</span><small>{a.time_str}</small></div>
            <div className="alert-triggered-msg">{a.message}</div>
            {!a.acknowledged && <button onClick={() => api.alertAcknowledge(a.id).then(loadAlerts)}>Acknowledge</button>}
          </div>)}
        </div>
      </>}
    </section>}
  </Page>
}

function Page({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) { return <div className="page"><span className="eyebrow">SALAR WORKSPACE</span><h1>{title}</h1><p>{subtitle}</p>{children}</div> }
function Card({ icon, title, text }: { icon: React.ReactNode; title: string; text: string }) { return <article className="card"><div>{icon}</div><h3>{title}</h3><p>{text}</p></article> }

if ('serviceWorker' in navigator) { window.addEventListener('load', () => { navigator.serviceWorker.getRegistration().then(reg => { if (reg) reg.update() }) }) }

createRoot(document.getElementById('root')!).render(<App/>)
