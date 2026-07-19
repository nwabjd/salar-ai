import React, { useEffect, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { Brain, ChevronRight, FileText, Globe2, MemoryStick, Menu, Mic2, Monitor, Plus, Send, Settings, Sparkles, Unplug, X } from 'lucide-react'
import LiquidEther from './effects/LiquidEther.jsx'
import MagicRings from './effects/MagicRings.jsx'
import { AccessState, clearSession, isDesktop, resolveAccessState, saveSession, storedSession } from './access'
import { Conversation, DEFAULT_API, Device, DocumentItem, Memory, Message, SalarApi } from './api'
import './theme.css'
import './styles.css'

type View = 'home' | 'memory' | 'documents' | 'devices' | 'settings'
const api = new SalarApi()
const previewShell = new URLSearchParams(location.search).get('preview') === 'dashboard'

function Loader() {
  return <main className="loader"><div className="strand strand-a"/><div className="strand strand-b"/><div className="strand strand-c"/><p>SALAR</p><span>INITIALIZING PRIVATE INTELLIGENCE</span></main>
}

function PairingPortal({ onConnected }: { onConnected: () => void }) {
  const [code, setCode] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  async function pair(event: React.FormEvent) {
    event.preventDefault()
    if (code.length !== 6) return setError('Enter the six-digit code shown by SALAR Desktop.')
    setBusy(true); setError('')
    try {
      const result = await api.redeemPairingCode(code, navigator.userAgent.includes('iPhone') ? 'JD iPhone' : 'Web browser', navigator.userAgent.includes('iPhone') ? 'ios' : 'web')
      saveSession(result.access_token); onConnected()
    } catch (reason) { setError((reason as Error).message) } finally { setBusy(false) }
  }
  return <main className="pairing-screen">
    <div className="pairing-ether"><LiquidEther colors={['#5227FF','#FF9FFC','#B497CF']} mouseForce={20} cursorSize={100} resolution={0.5} autoDemo autoSpeed={0.5} autoIntensity={2.2}/></div>
    <form className="pairing-panel" onSubmit={pair}>
      <div className="salar-glyph">S</div><span className="eyebrow">PRIVATE DEVICE LINK</span>
      <h1>Pair with SALAR</h1><p>On SALAR Desktop, open Settings and choose “Pair a device.”</p>
      <label>Six-digit code<input autoFocus inputMode="numeric" maxLength={6} value={code} onChange={e => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))} placeholder="000000"/></label>
      {error && <div className="inline-error">{error}</div>}
      <button disabled={busy || code.length !== 6}>{busy ? 'Pairing…' : 'Pair device'} <ChevronRight size={17}/></button>
      <small>Codes expire after five minutes · {api.baseUrl}</small>
    </form>
  </main>
}

function App() {
  const desktop = isDesktop() || previewShell
  const [ready, setReady] = useState(false)
  const [access, setAccess] = useState<AccessState>(() => resolveAccessState({ desktop, token: storedSession() }))
  const [view, setView] = useState<View>('home')
  const [live, setLive] = useState(false)
  const [menu, setMenu] = useState(false)
  useEffect(() => { const timer = setTimeout(() => setReady(true), 1700); return () => clearTimeout(timer) }, [])
  useEffect(() => {
    if (access !== 'connected') return
    api.validateSession().catch(() => { clearSession(); api.token = ''; setAccess(desktop ? 'desktop-disconnected' : 'pairing') })
  }, [access, desktop])
  useEffect(() => {
    const invoke = (window as any).__TAURI_INTERNALS__?.invoke
    const token = storedSession()
    if (access !== 'connected' || !invoke || !token) return
    let stopped = false, timer = 0
    async function poll() {
      try {
        const command = await api.nextDeviceCommand(token)
        if (command) {
          try { const data = await invoke('execute_device_command', { kind: command.kind, payload: command.payload }); await api.completeDeviceCommand(command.id, token, { ok: true, detail: 'Executed by SALAR Desktop', data }) }
          catch (reason) { await api.completeDeviceCommand(command.id, token, { ok: false, detail: String(reason) }) }
        }
      } catch { /* connection indicator handles offline state */ }
      finally { if (!stopped) timer = window.setTimeout(poll, 1800) }
    }
    poll(); return () => { stopped = true; clearTimeout(timer) }
  }, [access])
  if (!ready) return <Loader/>
  if (!desktop && access === 'pairing') return <PairingPortal onConnected={() => setAccess('connected')}/>
  if (live) return <Live connected={access === 'connected'} onClose={() => setLive(false)}/>
  const nav = [['home', Sparkles, 'Intelligence'], ['memory', MemoryStick, 'Memory'], ['documents', FileText, 'Documents'], ['devices', Monitor, 'Devices'], ['settings', Settings, 'Settings']] as const
  return <main className="app-shell">
    <div className="liquid-stage"><LiquidEther colors={['#5227FF','#FF9FFC','#B497CF']} mouseForce={20} cursorSize={100} isViscous={false} viscous={30} iterationsViscous={32} iterationsPoisson={32} resolution={0.5} isBounce={false} autoDemo autoSpeed={0.5} autoIntensity={2.2} takeoverDuration={0.25} autoResumeDelay={3000} autoRampDuration={0.6}/></div>
    <header className="topbar"><button className="mobile-menu" onClick={() => setMenu(!menu)}><Menu/></button><div className="brand"><div className="salar-glyph">S</div><div><b>SALAR</b><small>PERSONAL INTELLIGENCE</small></div></div><nav className="topnav">{nav.slice(0, 4).map(([id,,label]) => <button key={id} className={view === id ? 'active' : ''} onClick={() => setView(id)}>{label}</button>)}</nav><button className={`connection ${access}`} onClick={() => setView('settings')}><i/>{access === 'connected' ? 'SECURE LINK' : 'CONNECT'}</button></header>
    <aside className={menu ? 'open' : ''}>{nav.map(([id, Icon, label]) => <button key={id} className={view === id ? 'active' : ''} onClick={() => { setView(id); setMenu(false) }}><Icon size={17}/><span>{label}</span></button>)}</aside>
    <section className="workspace">
      {view === 'home' && <Chat connected={access === 'connected'} onLive={() => setLive(true)} onConnect={() => setView('settings')}/>} 
      {view === 'memory' && <Memories connected={access === 'connected'}/>}
      {view === 'documents' && <Documents connected={access === 'connected'}/>}
      {view === 'devices' && <Devices connected={access === 'connected'}/>}
      {view === 'settings' && <SettingsPage access={access} onAccess={setAccess}/>} 
    </section>
  </main>
}

function Chat({ connected, onLive, onConnect }: { connected: boolean; onLive: () => void; onConnect: () => void }) {
  const [conversation, setConversation] = useState<Conversation | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const end = useRef<HTMLDivElement>(null)
  useEffect(() => { if (!connected) return; api.conversations().then(async list => { const item = list[0] || await api.createConversation(); setConversation(item); if (list[0]) setMessages((await api.conversation(item.id)).messages || []) }).catch(e => setError(e.message)) }, [connected])
  useEffect(() => end.current?.scrollIntoView({ behavior: 'smooth' }), [messages])
  async function send() { if (!input.trim() || !conversation || busy) return; const content = input; setInput(''); setBusy(true); try { const result = await api.chat(conversation.id, content); setMessages(current => [...current, result.user_message, result.assistant_message]) } catch (reason) { setError((reason as Error).message) } finally { setBusy(false) } }
  return <div className="chat-view"><div className="hero"><span className="eyebrow">COORDINATED INTELLIGENCE</span><h1>{messages.length ? 'Command stream' : 'What shall we accomplish?'}</h1><p>Private intelligence, memory, knowledge, and your connected devices—coordinated from one place.</p>{!connected && <button className="text-action" onClick={onConnect}><Unplug size={15}/> Connect the private backend</button>}</div><div className="messages">{messages.map(message => <article key={message.id} className={message.role}><span>{message.role === 'assistant' ? 'SALAR' : 'YOU'}</span><p>{message.content}</p></article>)}{busy && <article className="assistant thinking"><span>SALAR</span><p>Reasoning across your private context…</p></article>}<div ref={end}/></div>{error && <div className="toast">{error}</div>}<div className="composer"><button className="icon-control live-control" onClick={onLive} title="Enter Live mode"><Mic2/></button><textarea value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }} placeholder={connected ? 'Ask, create, search, or control…' : 'Connect SALAR in Settings to begin…'} disabled={!connected} rows={1}/><button className="icon-control send-control" onClick={send} disabled={!connected || busy || !input.trim()} title="Send command"><Send/></button></div></div>
}

function Live({ connected, onClose }: { connected: boolean; onClose: () => void }) {
  const [heard, setHeard] = useState(connected ? 'Listening for your command…' : 'Connect SALAR before using Live Mode.')
  const [reply, setReply] = useState('')
  useEffect(() => { if (!connected) return; let active = true, conversationId = ''; const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition; if (!SpeechRecognition) { setHeard('Voice recognition is unavailable on this device.'); return } const recognition = new SpeechRecognition(); recognition.continuous = true; recognition.interimResults = true; api.createConversation('Live session').then(c => conversationId = c.id); recognition.onresult = async (event: any) => { for (let index = event.resultIndex; index < event.results.length; index++) { const text = event.results[index][0].transcript; setHeard(text); if (event.results[index].isFinal && conversationId) { const result = await api.chat(conversationId, text); if (!active) return; setReply(result.assistant_message.content); speechSynthesis.cancel(); speechSynthesis.speak(new SpeechSynthesisUtterance(result.assistant_message.content)) } } }; recognition.start(); return () => { active = false; recognition.stop(); speechSynthesis.cancel() } }, [connected])
  return <main className="live"><div className="rings"><MagicRings color="#fc42ff" colorTwo="#42fcff" ringCount={6} speed={1} attenuation={10} lineThickness={2} baseRadius={0.35} radiusStep={0.1} scaleRate={0.1} opacity={1} blur={0} noiseAmount={0.1} rotation={0} ringGap={1.5} fadeIn={0.7} fadeOut={0.5} followMouse={false} mouseInfluence={0.2} hoverScale={1.2} parallax={0.05} clickBurst={false}/></div><button className="close" onClick={onClose}><X/></button><div className="live-copy"><span className="eyebrow">LIVE MODE · CONTINUOUS</span><h1>SALAR is listening</h1><p>{heard}</p>{reply && <blockquote>{reply}</blockquote>}</div></main>
}

function Memories({ connected }: { connected: boolean }) { const [items, setItems] = useState<Memory[]>([]); useEffect(() => { if (connected) api.memories().then(setItems) }, [connected]); return <Page title="Memory" subtitle="Facts and decisions SALAR carries forward."><div className="grid">{items.map(item => <Card key={item.id} icon={<Brain/>} title={item.title} text={item.content}/>)}<Card icon={<Plus/>} title={connected ? 'Add through conversation' : 'Backend disconnected'} text={connected ? 'Ask SALAR to remember anything important.' : 'Provision this device in Settings.'}/></div></Page> }
function Documents({ connected }: { connected: boolean }) { const [items, setItems] = useState<DocumentItem[]>([]), input = useRef<HTMLInputElement>(null); useEffect(() => { if (connected) api.documents().then(setItems) }, [connected]); async function add(file?: File) { if (file) { const uploaded = await api.upload(file); setItems(current => [uploaded, ...current]) } } return <Page title="Knowledge" subtitle="Search documents, notes, and source code.">{connected && <button className="primary" onClick={() => input.current?.click()}><Plus size={16}/> Index document</button>}<input ref={input} hidden type="file" onChange={e => add(e.target.files?.[0])}/><div className="grid">{items.map(item => <Card key={item.id} icon={<FileText/>} title={item.filename} text={item.media_type}/>)}</div></Page> }
function Devices({ connected }: { connected: boolean }) { const [items, setItems] = useState<Device[]>([]); useEffect(() => { if (connected) api.devices().then(setItems) }, [connected]); return <Page title="Connected devices" subtitle="Permission-aware control through your private backend."><div className="grid">{items.map(item => <Card key={item.id} icon={<Monitor/>} title={item.name} text={`${item.platform} · ${item.last_seen_at ? 'online recently' : 'registered'}`}/>)}{!items.length && <Card icon={<Globe2/>} title={connected ? 'No command devices linked' : 'Backend disconnected'} text={connected ? 'SALAR Desktop registers automatically after provisioning.' : 'Open Settings to connect this installation.'}/>}</div></Page> }

function SettingsPage({ access, onAccess }: { access: AccessState; onAccess: (state: AccessState) => void }) {
  const [url, setUrl] = useState(localStorage.getItem('salar.apiUrl') || DEFAULT_API)
  const [key, setKey] = useState('')
  const [pairing, setPairing] = useState<{ code: string; expires_at: string } | null>(null)
  const [notice, setNotice] = useState('')
  async function provision() { try { localStorage.setItem('salar.apiUrl', url); api.baseUrl = url.replace(/\/$/, ''); const result = await api.provisionDesktop(key); saveSession(result.access_token); setKey(''); onAccess('connected'); setNotice('This desktop is securely connected.') } catch (reason) { setNotice((reason as Error).message) } }
  async function createCode() { try { setPairing(await api.createPairingCode()) } catch (reason) { setNotice((reason as Error).message) } }
  return <Page title="Settings" subtitle="One private backend across desktop, web, and iPhone."><section className="settings-card"><label>Public API address<input value={url} onChange={e => setUrl(e.target.value)} placeholder="https://api.yourdomain.com"/></label>{access !== 'connected' ? <><label>One-time provisioning key<input type="password" value={key} onChange={e => setKey(e.target.value)} placeholder="From your private backend .env"/></label><button className="primary" disabled={!key} onClick={provision}>Connect this desktop</button><p>The key is exchanged for a revocable machine credential and is never stored.</p></> : <><div className="connected-row"><i/> Desktop session active</div><button className="primary" onClick={createCode}>Pair another device</button>{pairing && <div className="pairing-code"><span>{pairing.code}</span><small>Expires in five minutes</small></div>}<button className="text-action danger" onClick={() => { clearSession(); api.token = ''; onAccess('desktop-disconnected') }}>Disconnect this desktop</button></>}{notice && <div className="notice">{notice}</div>}</section></Page>
}

function Page({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) { return <div className="page"><span className="eyebrow">SALAR WORKSPACE</span><h1>{title}</h1><p>{subtitle}</p>{children}</div> }
function Card({ icon, title, text }: { icon: React.ReactNode; title: string; text: string }) { return <article className="card"><div>{icon}</div><h3>{title}</h3><p>{text}</p></article> }

createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>)
