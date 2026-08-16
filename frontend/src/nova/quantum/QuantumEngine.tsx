import React, { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  BarChart2, 
  Cpu, 
  Activity, 
  Shield, 
  Workflow, 
  Globe, 
  Zap, 
  Send, 
  Mic, 
  Compass, 
  Clock, 
  Bell, 
  Users, 
  Search,
  Sparkles,
  Key,
  FolderTree,
  Dna
} from 'lucide-react'
import { SalarApi } from '../../api'

interface QuantumEngineProps {
  api: SalarApi
  onExitNova?: () => void
}

export default function QuantumEngine({ api, onExitNova }: QuantumEngineProps) {
  const [activeTab, setActiveTab] = useState('DASHBOARD')
  const [input, setInput] = useState('')
  const [response, setResponse] = useState('How can I assist you today?')
  const [isThinking, setIsThinking] = useState(false)
  const [isListening, setIsListening] = useState(false)
  const [telemetry, setTelemetry] = useState({
    cpu: 32.5,
    gpu: 44.2,
    memory: 64.1,
    temp: 41.2,
    activeAgents: 5,
    uptime: '12D 6H 24M'
  })

  // Real-time telemetry updates
  useEffect(() => {
    const fetchTelemetry = async () => {
      try {
        const stats = await api.monitorProcesses()
        const totalCpu = stats.processes.reduce((sum, p) => sum + p.cpu_percent, 0)
        const totalMem = stats.processes.reduce((sum, p) => sum + p.memory_percent, 0)
        setTelemetry(prev => ({
          ...prev,
          cpu: Math.min(99, Math.max(12, Math.round(totalCpu))),
          memory: Math.min(99, Math.max(15, Math.round(totalMem)))
        }))
      } catch (e) {
        console.error('Telemetry fetch failed', e)
      }
    }
    fetchTelemetry()
    const timer = setInterval(fetchTelemetry, 10000)
    return () => clearInterval(timer)
  }, [api])

  const handleSendCommand = async () => {
    if (!input.trim()) return
    setIsThinking(true)
    setResponse('Processing your request across the quantum node...')
    try {
      const convs = await api.conversations()
      const conv = convs[0] || await api.createConversation()
      
      let replyBuffer = ''
      await api.chatStream(
        conv.id,
        input,
        (token) => {
          replyBuffer += token
          setResponse(replyBuffer)
        },
        () => {
          setIsThinking(false)
        },
        (err) => {
          setIsThinking(false)
          setResponse(`Quantum core exception: ${err.message}`)
        }
      )
    } catch (err: any) {
      setIsThinking(false)
      setResponse(`Failed to establish quantum node communication: ${err.message}`)
    }
    setInput('')
  }

  return (
    <div className="quantum-app-shell" style={{
      width: '100vw',
      height: '100vh',
      padding: '20px',
      display: 'grid',
      gridTemplateColumns: '235px minmax(0, 1fr)',
      gap: '16px',
      background: 'radial-gradient(circle at 50% -10%,rgba(255,255,255,.95),transparent 40%), radial-gradient(circle at 87% 68%,rgba(214,188,151,.11),transparent 28%), linear-gradient(135deg,#f4f0e9,#eee7de)',
      color: 'var(--ink)',
      fontFamily: 'Inter, Segoe UI, system-ui, sans-serif'
    }}>
      
      {/* LEFT SIDEBAR */}
      <aside className="quantum-sidebar" style={{
        minHeight: 'calc(100vh - 40px)',
        padding: '14px 12px 12px',
        border: '1px solid rgba(255,255,255,.55)',
        borderRadius: '20px',
        background: 'linear-gradient(180deg,rgba(250,247,242,.82),rgba(241,235,226,.72))',
        boxShadow: '0 10px 45px rgba(70,50,30,.05), inset 0 1px 0 rgba(255,255,255,.7)',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between'
      }}>
        <div>
          {/* Logo Area */}
          <div className="brand" style={{ height: '94px', display: 'flex', alignItems: 'center', gap: '12px', padding: '8px 9px 12px' }}>
            <div className="brand-mark" style={{ width: '70px', height: '70px', position: 'relative', display: 'grid', placeItems: 'center', flex: 'none' }}>
              <span className="orbit orbit-a" style={{ position: 'absolute', inset: '5px', border: '1px solid rgba(178,139,86,.55)', borderRadius: '50%' }}></span>
              <span className="orbit orbit-b" style={{ position: 'absolute', inset: '10px', transform: 'rotate(55deg)', borderStyle: 'dashed', opacity: 0.65, borderRadius: '50%', border: '1px solid rgba(178,139,86,.55)' }}></span>
              <div className="brand-core" style={{
                width: '48px', height: '48px', borderRadius: '50%',
                display: 'grid', placeItems: 'center',
                color: '#5c421f', fontWeight: 900, fontSize: '34px',
                background: 'radial-gradient(circle at 35% 30%,#fff9ed,#d3b17d 78%)',
                border: '1px solid rgba(134,96,51,.30)',
                boxShadow: '0 4px 18px rgba(154,108,57,.20), inset 0 0 0 5px rgba(255,255,255,.5)'
              }}>S</div>
            </div>
            <div className="brand-copy">
              <div className="brand-name" style={{ fontSize: '28px', lineHeight: 1, fontWeight: 800, letterSpacing: '.02em' }}>SALAAR</div>
              <div className="brand-sub" style={{ fontSize: '9px', fontWeight: 700, letterSpacing: '.08em', marginTop: '7px', whiteSpace: 'nowrap' }}>QUANTUM INTELLIGENCE</div>
            </div>
          </div>

          {/* Navigation */}
          <nav className="nav" style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '5px' }}>
            {[
              { id: 'DASHBOARD', label: 'DASHBOARD', icon: '▦' },
              { id: 'INTELLIGENCE', label: 'INTELLIGENCE', icon: '◉' },
              { id: 'NEURAL', label: 'NEURAL NETWORK', icon: '⌬' },
              { id: 'AUTOMATION', label: 'AUTOMATION', icon: '⚙' },
              { id: 'SECURITY', label: 'SECURITY', icon: '◇' }
            ].map(item => (
              <button 
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`nav-item ${activeTab === item.id ? 'active' : ''}`}
                style={{
                  height: '46px', padding: '0 16px', borderRadius: '13px',
                  display: 'flex', alignItems: 'center', gap: '14px',
                  border: 'none', width: '100%', textAlign: 'left',
                  textDecoration: 'none', color: activeTab === item.id ? '#fff' : '#282725', 
                  fontWeight: 650, fontSize: '12px',
                  background: activeTab === item.id ? 'linear-gradient(135deg,#8c6e49,#c5a473 65%,#b9925e)' : 'transparent',
                  boxShadow: activeTab === item.id ? '0 8px 18px rgba(137,100,58,.19),inset 0 1px 0 rgba(255,255,255,.25)' : 'none',
                  cursor: 'pointer',
                  transition: '.18s ease'
                }}
              >
                <span className="nav-icon" style={{ fontSize: '20px', width: '21px', textAlign: 'center' }}>{item.icon}</span>
                <span>{item.label}</span>
              </button>
            ))}
          </nav>
        </div>

        {/* Sidebar Bottom Telemetry */}
        <div className="sidebar-bottom" style={{ display: 'grid', gap: '10px' }}>
          <section className="side-status" style={{
            borderRadius: '14px', background: 'rgba(248,244,238,.76)', border: '1px solid rgba(97,76,54,.08)',
            boxShadow: 'inset 0 1px 0 rgba(255,255,255,.72)', padding: '13px 13px 11px'
          }}>
            <div className="side-status-head" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '8px', fontWeight: 800, letterSpacing: '.03em' }}>
              <span>SYSTEM STATUS</span>
              <span className="status-pill" style={{ padding: '4px 7px', borderRadius: '999px', background: '#d5e9dc', color: '#2d7158', fontSize: '7px' }}>● OPTIMAL</span>
            </div>
            <div className="status-list" style={{ marginTop: '10px', display: 'grid', gap: '6px', fontSize: '9px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>♨ Core Temp</span><b>{telemetry.temp} °C</b></div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>◉ Quantum Cores</span><b>32 / 64</b></div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>▤ Memory Usage</span><b>{telemetry.memory} %</b></div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>◌ CPU Usage</span><b>{telemetry.cpu} %</b></div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>◈ GPU Usage</span><b>{telemetry.gpu} %</b></div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>◫ Uptime</span><b>{telemetry.uptime}</b></div>
            </div>
          </section>

          <section className="quantum-link" style={{
            height: '58px', padding: '10px 12px', display: 'flex', alignItems: 'center', gap: '10px',
            borderRadius: '14px', background: 'rgba(248,244,238,.76)', border: '1px solid rgba(97,76,54,.08)',
            boxShadow: 'inset 0 1px 0 rgba(255,255,255,.72)'
          }}>
            <div className="link-orb" style={{ width: '34px', height: '34px', borderRadius: '50%', display: 'grid', placeItems: 'center', border: '1px solid #c4a16d', color: '#a47a44', background: '#f6ecdd' }}>◎</div>
            <div>
              <b style={{ display: 'block', fontSize: '9px', letterSpacing: '.03em' }}>QUANTUM LINK</b>
              <small style={{ display: 'block', color: '#2f765d', fontSize: '8px', marginTop: '4px', fontWeight: 700 }}>STABLE CONNECTION</small>
            </div>
          </section>
        </div>
      </aside>

      {/* RIGHT CONTENT */}
      <main className="quantum-main" style={{
        minWidth: 0,
        display: 'grid',
        gridTemplateRows: '76px minmax(0, 1fr) 104px',
        gap: '12px'
      }}>
        
        {/* TOP STATUS BAR */}
        <header className="topbar" style={{
          borderRadius: '17px', background: 'rgba(249,247,243,.85)', border: '1px solid rgba(255,255,255,.72)',
          boxShadow: '0 10px 28px rgba(65,48,29,.08), inset 0 1px 0 rgba(255,255,255,.65)', padding: '0 18px',
          display: 'grid', gridTemplateColumns: '1.7fr .85fr .85fr .85fr .95fr 1.6fr',
          alignItems: 'center', gap: 0
        }}>
          <div className="top-title">
            <h1 style={{ fontSize: '20px', margin: '0 0 4px', fontWeight: 800, letterSpacing: '.01em' }}>SALAAR – QUANTUM INTELLIGENCE</h1>
            <p style={{ margin: 0, fontSize: '11px', color: '#44403b' }}>AI COMMAND &amp; CONTROL CENTER</p>
          </div>

          <div className="top-metric" style={{ height: '44px', borderLeft: '1px solid var(--line)', paddingLeft: '19px', display: 'flex', justifyContent: 'center', flexDirection: 'column' }}>
            <span style={{ fontSize: '7px', color: '#6a655f', marginBottom: '6px' }}>⌘ &nbsp; AI MODE</span>
            <strong style={{ fontSize: '9px', color: 'var(--green)' }}>QUANTUM MODE</strong>
          </div>
          <div className="top-metric" style={{ height: '44px', borderLeft: '1px solid var(--line)', paddingLeft: '19px', display: 'flex', justifyContent: 'center', flexDirection: 'column' }}>
            <span style={{ fontSize: '7px', color: '#6a655f', marginBottom: '6px' }}>⌬ &nbsp; QUANTUM STATE</span>
            <strong style={{ fontSize: '9px', color: 'var(--green)' }}>STABLE</strong>
          </div>
          <div className="top-metric" style={{ height: '44px', borderLeft: '1px solid var(--line)', paddingLeft: '19px', display: 'flex', justifyContent: 'center', flexDirection: 'column' }}>
            <span style={{ fontSize: '7px', color: '#6a655f', marginBottom: '6px' }}>◉ &nbsp; SYSTEM UPTIME</span>
            <b style={{ fontSize: '11px' }}>{telemetry.uptime}</b>
          </div>
          <div className="top-clock" style={{ height: '44px', borderLeft: '1px solid var(--line)', paddingLeft: '19px', display: 'flex', justifyContent: 'center', flexDirection: 'column' }}>
            <span style={{ fontSize: '7px', color: '#6a655f', marginBottom: '6px' }}>{new Date().toLocaleDateString(undefined, { weekday: 'short', year: 'numeric', month: 'short', day: 'numeric' })}</span>
            <b style={{ fontSize: '14px' }}>{new Date().toLocaleTimeString()}</b>
          </div>

          <div className="top-actions" style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '10px' }}>
            <button className="circle-btn" style={{
              width: '42px', height: '42px', borderRadius: '50%', border: '1px solid rgba(103,82,60,.14)',
              background: '#f8f4ee', display: 'grid', placeItems: 'center', fontSize: '16px', color: '#302b25', cursor: 'pointer'
            }} onClick={onExitNova}>Classic</button>
          </div>
        </header>

        {/* MAIN WORKSPACE */}
        <section className="dashboard" style={{
          display: 'grid',
          gridTemplateColumns: '1.22fr .92fr .9fr .95fr',
          gridTemplateRows: 'minmax(375px, 1.28fr) minmax(226px, .72fr)',
          gap: '8px',
          minHeight: 0
        }}>
          
          {/* Global Activity Map */}
          <article className="panel activity-panel" style={{
            minWidth: 0, minHeight: 0, borderRadius: '15px', overflow: 'hidden',
            border: '1px solid rgba(96,77,56,.10)',
            background: 'linear-gradient(180deg,rgba(249,247,243,.94),rgba(237,230,221,.92))',
            boxShadow: '0 8px 24px rgba(56,42,29,.07),inset 0 1px 0 rgba(255,255,255,.65)'
          }}>
            <div className="panel-head" style={{ height: '52px', padding: '14px 16px 7px', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div><h2 style={{ fontSize: '11px', margin: 0, fontWeight: 800, letterSpacing: '.015em' }}>GLOBAL ACTIVITY</h2><p style={{ fontSize: '7.5px', color: '#6b655e', margin: '3px 0 0' }}>REAL-TIME FEED</p></div>
              <span className="live-pill" style={{ fontSize: '7px', fontWeight: 800, padding: '5px 8px', borderRadius: '999px', background: '#f4e0be', color: '#3c3328' }}>● LIVE</span>
            </div>
            
            <div className="world-visual" style={{ height: 'calc(100% - 158px)', minHeight: '205px', padding: '0 10px' }}>
              {/* World SVG Map */}
              <svg viewBox="0 0 640 290" className="world-svg" style={{ width: '100%', height: '100%', filter: 'drop-shadow(0 10px 14px rgba(105,83,56,.10))' }}>
                <defs>
                  <radialGradient id="mapGlow">
                    <stop offset="0%" stopColor="#f1d6a5" stopOpacity=".9"/>
                    <stop offset="100%" stopColor="#c39c65" stopOpacity="0"/>
                  </radialGradient>
                  <pattern id="dots" width="6" height="6" patternUnits="userSpaceOnUse">
                    <circle cx="2" cy="2" r="1.35" fill="#4e4b47" opacity=".62"/>
                  </pattern>
                </defs>
                <g fill="url(#dots)" opacity=".95">
                  <path d="M38 75l62-34 59 4 32 29-31 17-4 28-28 20-11 39-36-11-15-28-33-9-7-29z"/>
                  <path d="M170 154l25 9 17 30 14 48-23 24-17-33-19-43z"/>
                  <path d="M271 59l45-28 70 5 21 17 55-2 78 27 51 32-23 31-48 5-42 25-35-11-27 29-21-18-25 18-29-14-18-33-42-22-21-33z"/>
                </g>
                <g stroke="#c7a46f" fill="none" opacity=".4">
                  <path d="M89 103 Q320 -20 553 130"/>
                  <path d="M86 105 Q342 260 570 126"/>
                  <path d="M199 158 Q350 48 528 124"/>
                </g>
                <g fill="#e7c78e">
                  <circle cx="92" cy="102" r="4"/>
                  <circle cx="198" cy="158" r="3.5"/>
                  <circle cx="359" cy="108" r="4"/>
                </g>
              </svg>
            </div>

            <div className="dark-metrics four" style={{
              height: '106px', background: 'linear-gradient(180deg,#252626,#111212)',
              display: 'grid', alignItems: 'center', padding: '14px 10px', gridTemplateColumns: 'repeat(4,1fr)'
            }}>
              <div style={{ height: '78px', padding: '3px 13px', borderRight: '1px solid rgba(255,255,255,.07)' }}>
                <span style={{ display: 'block', color: '#bbb4aa', fontSize: '8px' }}>REQUESTS</span>
                <b style={{ display: 'block', color: '#fff', fontSize: '14px', marginTop: '10px' }}>12.48 M</b>
              </div>
              <div style={{ height: '78px', padding: '3px 13px', borderRight: '1px solid rgba(255,255,255,.07)' }}>
                <span style={{ display: 'block', color: '#bbb4aa', fontSize: '8px' }}>DATA IN</span>
                <b style={{ display: 'block', color: '#fff', fontSize: '14px', marginTop: '10px' }}>2.14 TB</b>
              </div>
              <div style={{ height: '78px', padding: '3px 13px', borderRight: '1px solid rgba(255,255,255,.07)' }}>
                <span style={{ display: 'block', color: '#bbb4aa', fontSize: '8px' }}>DATA OUT</span>
                <b style={{ display: 'block', color: '#fff', fontSize: '14px', marginTop: '10px' }}>1.67 TB</b>
              </div>
              <div style={{ height: '78px', padding: '3px 13px' }}>
                <span style={{ display: 'block', color: '#bbb4aa', fontSize: '8px' }}>LATENCY</span>
                <b style={{ display: 'block', color: '#fff', fontSize: '14px', marginTop: '10px' }}>23 ms</b>
              </div>
            </div>
          </article>

          {/* Central AI Intelligence Core */}
          <article className="panel core-panel" style={{
            gridColumn: '2 / 4', gridRow: 1,
            borderRadius: '15px', overflow: 'hidden',
            border: '1px solid rgba(96,77,56,.10)',
            background: 'radial-gradient(circle at 53% 47%,#e8dfd4 0,#d9d0c5 22%,#bab1a6 52%,#a59d94 68%,#dad3ca 100%)',
            boxShadow: '0 8px 24px rgba(56,42,29,.07),inset 0 1px 0 rgba(255,255,255,.65)'
          }}>
            <div className="panel-head core-head" style={{ position: 'relative', zIndex: 3, height: '52px', padding: '14px 16px 7px', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div><h2 style={{ fontSize: '11px', margin: 0, fontWeight: 800, letterSpacing: '.015em' }}>AI INTELLIGENCE CORE</h2><p style={{ fontSize: '7.5px', color: '#6b655e', margin: '3px 0 0' }}>QUANTUM NEURAL PROCESSOR</p></div>
              <span className="active-pill" style={{ fontSize: '7px', fontWeight: 800, padding: '5px 8px', borderRadius: '999px', background: '#285f4d', color: '#e9fff3' }}>● ACTIVE</span>
            </div>

            <div className="core-stage" style={{ height: 'calc(100% - 125px)', minHeight: '265px', display: 'grid', gridTemplateColumns: '92px 1fr 92px', alignItems: 'center', padding: '0 10px', position: 'relative' }}>
              <div className="core-side left-side" style={{ display: 'grid', gap: '10px', zIndex: 4 }}>
                <div className="micro-card" style={{ height: '58px', border: '1px solid rgba(67,60,53,.11)', borderRadius: '9px', background: 'rgba(224,218,209,.42)', padding: '9px 7px', position: 'relative', boxShadow: 'inset 0 1px 0 rgba(255,255,255,.28)' }}>
                  <span style={{ fontSize: '6.3px', fontWeight: 700, color: '#373431', display: 'block' }}>THINKING DEPTH</span>
                  <b style={{ fontSize: '14px', display: 'block', marginTop: '6px' }}>8.6 / 10</b>
                </div>
                <div className="micro-card" style={{ height: '58px', border: '1px solid rgba(67,60,53,.11)', borderRadius: '9px', background: 'rgba(224,218,209,.42)', padding: '9px 7px', position: 'relative', boxShadow: 'inset 0 1px 0 rgba(255,255,255,.28)' }}>
                  <span style={{ fontSize: '6.3px', fontWeight: 700, color: '#373431', display: 'block' }}>LEARNING RATE</span>
                  <b style={{ fontSize: '14px', display: 'block', marginTop: '6px' }}>0.091</b>
                </div>
              </div>

              {/* Glowing Orb Animation */}
              <div className="quantum-core" style={{ height: '100%', position: 'relative', display: 'grid', placeItems: 'center' }}>
                <div className="core-sphere pulse" style={{
                  width: '190px', height: '190px', borderRadius: '50%', position: 'relative', zIndex: 3,
                  background: 'radial-gradient(circle at 49% 42%,rgba(211,181,132,.08),transparent 24%), radial-gradient(circle at 50% 50%,#151617 0,#24201b 52%,#d8c8af 62%,rgba(255,255,255,.8) 64%,rgba(184,151,106,.22) 69%,transparent 72%)',
                  boxShadow: '0 0 0 1px rgba(255,255,255,.75), 0 0 22px rgba(255,241,213,.75), 0 0 60px rgba(192,154,100,.28), inset 0 0 38px rgba(213,171,110,.22)'
                }}>
                  <div className="sphere-grid" style={{ position: 'absolute', inset: '26px', borderRadius: '50%', opacity: 0.82, background: 'repeating-radial-gradient(ellipse at 50% 50%,transparent 0 14px,rgba(208,172,117,.22) 15px 16px)' }}></div>
                  <span className="core-letter" style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', color: 'rgba(222,187,132,.22)', fontSize: '52px', fontWeight: 800 }}>S</span>
                </div>
              </div>

              <div className="core-side right-side" style={{ display: 'grid', gap: '10px', zIndex: 4 }}>
                <div className="micro-card" style={{ height: '58px', border: '1px solid rgba(67,60,53,.11)', borderRadius: '9px', background: 'rgba(224,218,209,.42)', padding: '9px 7px', position: 'relative', boxShadow: 'inset 0 1px 0 rgba(255,255,255,.28)' }}>
                  <span style={{ fontSize: '6.3px', fontWeight: 700, color: '#373431', display: 'block' }}>CONTEXT WINDOW</span>
                  <b style={{ fontSize: '14px', display: 'block', marginTop: '6px' }}>128K</b>
                </div>
                <div className="micro-card" style={{ height: '58px', border: '1px solid rgba(67,60,53,.11)', borderRadius: '9px', background: 'rgba(224,218,209,.42)', padding: '9px 7px', position: 'relative', boxShadow: 'inset 0 1px 0 rgba(255,255,255,.28)' }}>
                  <span style={{ fontSize: '6.3px', fontWeight: 700, color: '#373431', display: 'block' }}>DECISION CONFIDENCE</span>
                  <b style={{ fontSize: '14px', display: 'block', marginTop: '6px' }}>97.2%</b>
                </div>
              </div>
            </div>

            <div className="core-metrics" style={{ height: '73px', display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: '8px', padding: '8px 10px', background: 'rgba(26,27,27,.93)' }}>
              <div style={{ border: '1px solid rgba(255,255,255,.09)', borderRadius: '8px', padding: '10px', color: 'white' }}>
                <span style={{ fontSize: '6px', color: '#bdb6ac', display: 'block' }}>PROCESSING POWER</span>
                <b style={{ fontSize: '13px', display: 'block', marginTop: '10px' }}>2.48 PFLOPS</b>
              </div>
              <div style={{ border: '1px solid rgba(255,255,255,.09)', borderRadius: '8px', padding: '10px', color: 'white' }}>
                <span style={{ fontSize: '6px', color: '#bdb6ac', display: 'block' }}>RESPONSE TIME</span>
                <b style={{ fontSize: '13px', display: 'block', marginTop: '10px' }}>18 ms</b>
              </div>
              <div style={{ border: '1px solid rgba(255,255,255,.09)', borderRadius: '8px', padding: '10px', color: 'white' }}>
                <span style={{ fontSize: '6px', color: '#bdb6ac', display: 'block' }}>ACTIVE AGENTS</span>
                <b style={{ fontSize: '13px', display: 'block', marginTop: '10px' }}>16</b>
              </div>
              <div style={{ border: '1px solid rgba(255,255,255,.09)', borderRadius: '8px', padding: '10px', color: 'white' }}>
                <span style={{ fontSize: '6px', color: '#bdb6ac', display: 'block' }}>TASKS QUEUED</span>
                <b style={{ fontSize: '13px', display: 'block', marginTop: '10px' }}>7</b>
              </div>
            </div>
          </article>

          {/* Performance/Accuracy Card */}
          <article className="panel accuracy-panel" style={{
            minWidth: 0, minHeight: 0, borderRadius: '15px', overflow: 'hidden',
            border: '1px solid rgba(96,77,56,.10)',
            background: 'linear-gradient(180deg,rgba(249,247,243,.94),rgba(237,230,221,.92))',
            boxShadow: '0 8px 24px rgba(56,42,29,.07),inset 0 1px 0 rgba(255,255,255,.65)'
          }}>
            <div className="panel-head" style={{ height: '52px', padding: '14px 16px 7px', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div><h2 style={{ fontSize: '11px', margin: 0, fontWeight: 800, letterSpacing: '.015em' }}>PREDICTION ACCURACY</h2><p style={{ fontSize: '7.5px', color: '#6b655e', margin: '3px 0 0' }}>MODEL PERFORMANCE</p></div>
            </div>
            <div className="accuracy-body" style={{ display: 'grid', gridTemplateColumns: '44% 56%', alignItems: 'center', height: 'calc(100% - 52px)', padding: '4px 16px 13px' }}>
              <div className="donut" style={{
                width: '120px', height: '120px', borderRadius: '50%',
                background: 'conic-gradient(#d1ad77 0 93.8%, #161616 93.8% 100%)',
                display: 'grid', placeItems: 'center', boxShadow: 'inset 0 0 0 1px rgba(0,0,0,.08),0 7px 18px rgba(65,50,30,.08)'
              }}>
                <div className="donut-inner" style={{ width: '90px', height: '94px', borderRadius: '50%', background: '#f6f2eb', display: 'grid', placeContent: 'center', textAlign: 'center' }}>
                  <b style={{ fontSize: '21px' }}>93.8%</b>
                  <span style={{ fontSize: '9px', fontWeight: 700 }}>ACCURACY</span>
                </div>
              </div>
              <div className="accuracy-list" style={{ display: 'grid', gap: '15px', fontSize: '8px' }}>
                <div><span>Reasoning</span> <b>93.6%</b></div>
                <div><span>Forecasting</span> <b>93.2%</b></div>
                <div><span>NLP</span> <b>94.1%</b></div>
              </div>
            </div>
          </article>

          {/* Predictions Panel */}
          <article className="panel dark-panel predictions-panel" style={{
            gridColumn: 1, gridRow: 2,
            minWidth: 0, minHeight: 0, borderRadius: '15px', overflow: 'hidden',
            background: 'linear-gradient(150deg,#242525,#151616)', border: '1px solid rgba(255,255,255,.08)',
            boxShadow: '0 12px 28px rgba(0,0,0,.17),inset 0 1px 0 rgba(255,255,255,.03)', color: 'white'
          }}>
            <div className="panel-head dark" style={{ height: '52px', padding: '14px 16px 7px' }}>
              <div><h2 style={{ fontSize: '11px', margin: 0, fontWeight: 800, letterSpacing: '.015em' }}>TOP PREDICTIONS</h2><p style={{ fontSize: '7.5px', color: '#9a948c', margin: '3px 0 0' }}>CONFIDENCE SCORE</p></div>
            </div>
            <div className="prediction-bars" style={{ padding: '0 14px 10px', display: 'grid', gap: '10px' }}>
              {[
                { name: 'Market Trend', val: '94%' },
                { name: 'User Growth', val: '92%' },
                { name: 'System Load', val: '90%' }
              ].map(pred => (
                <div key={pred.name} style={{ display: 'grid', gridTemplateColumns: '92px 1fr 28px', gap: '8px', alignItems: 'center', fontSize: '7px' }}>
                  <span>{pred.name}</span>
                  <i style={{ height: '2px', background: '#4a4a48', display: 'block', position: 'relative' }}>
                    <u style={{ display: 'block', height: '2px', background: '#d7ac6f', width: pred.val }}></u>
                  </i>
                  <b>{pred.val}</b>
                </div>
              ))}
            </div>
          </article>

          {/* Knowledge Graph Connections */}
          <article className="panel dark-panel knowledge-panel" style={{
            gridColumn: 2, gridRow: 2,
            minWidth: 0, minHeight: 0, borderRadius: '15px', overflow: 'hidden',
            background: 'linear-gradient(150deg,#242525,#151616)', border: '1px solid rgba(255,255,255,.08)',
            boxShadow: '0 12px 28px rgba(0,0,0,.17),inset 0 1px 0 rgba(255,255,255,.03)', color: 'white'
          }}>
            <div className="panel-head dark" style={{ height: '52px', padding: '14px 16px 7px' }}>
              <div><h2 style={{ fontSize: '11px', margin: 0, fontWeight: 800, letterSpacing: '.015em' }}>KNOWLEDGE GRAPH</h2><p style={{ fontSize: '7.5px', color: '#9a948c', margin: '3px 0 0' }}>CONNECTIONS &amp; ENTITIES</p></div>
            </div>
            <div className="knowledge-graph" style={{ height: '116px', padding: '0 14px' }}>
              <svg viewBox="0 0 520 190" style={{ width: '100%', height: '100%' }}>
                <g stroke="#8f7757" strokeWidth="1.2" opacity=".6">
                  <line x1="70" y1="125" x2="160" y2="70"/>
                  <line x1="160" y1="70" x2="242" y2="110"/>
                  <line x1="242" y1="110" x2="340" y2="65"/>
                </g>
                <g fill="#c8a56f" stroke="#f4dfbd" strokeWidth="2">
                  <circle cx="70" cy="125" r="8"/>
                  <circle cx="160" cy="70" r="7"/>
                  <circle cx="242" cy="110" r="10"/>
                  <circle cx="340" cy="65" r="8"/>
                </g>
              </svg>
            </div>
          </article>

          {/* Resource Monitor */}
          <article className="panel dark-panel resource-panel" style={{
            gridColumn: 3, gridRow: 2,
            minWidth: 0, minHeight: 0, borderRadius: '15px', overflow: 'hidden',
            background: 'linear-gradient(150deg,#242525,#151616)', border: '1px solid rgba(255,255,255,.08)',
            boxShadow: '0 12px 28px rgba(0,0,0,.17),inset 0 1px 0 rgba(255,255,255,.03)', color: 'white'
          }}>
            <div className="panel-head dark" style={{ height: '52px', padding: '14px 16px 7px' }}>
              <div><h2 style={{ fontSize: '11px', margin: 0, fontWeight: 800, letterSpacing: '.015em' }}>RESOURCE MONITOR</h2><p style={{ fontSize: '7.5px', color: '#9a948c', margin: '3px 0 0' }}>REAL-TIME USAGE</p></div>
            </div>
            <div className="resource-rings" style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: '6px', padding: '0 13px' }}>
              <div className="mini-ring" style={{ position: 'relative', borderRadius: '50%', background: `conic-gradient(#c9a56e ${telemetry.cpu}%,#4d4d49 0)`, display: 'grid', placeContent: 'center', aspectRatio: 1 }}>
                <b style={{ fontSize: '11px', zIndex: 2 }}>{telemetry.cpu}%</b>
              </div>
              <div className="mini-ring" style={{ position: 'relative', borderRadius: '50%', background: `conic-gradient(#c9a56e ${telemetry.gpu}%,#4d4d49 0)`, display: 'grid', placeContent: 'center', aspectRatio: 1 }}>
                <b style={{ fontSize: '11px', zIndex: 2 }}>{telemetry.gpu}%</b>
              </div>
              <div className="mini-ring" style={{ position: 'relative', borderRadius: '50%', background: `conic-gradient(#c9a56e ${telemetry.memory}%,#4d4d49 0)`, display: 'grid', placeContent: 'center', aspectRatio: 1 }}>
                <b style={{ fontSize: '11px', zIndex: 2 }}>{telemetry.memory}%</b>
              </div>
              <div className="mini-ring" style={{ position: 'relative', borderRadius: '50%', background: `conic-gradient(#c9a56e 52%,#4d4d49 0)`, display: 'grid', placeContent: 'center', aspectRatio: 1 }}>
                <b style={{ fontSize: '11px', zIndex: 2 }}>52%</b>
              </div>
            </div>
          </article>

          {/* Security Center */}
          <article className="panel dark-panel security-panel" style={{
            gridColumn: 4, gridRow: 2,
            minWidth: 0, minHeight: 0, borderRadius: '15px', overflow: 'hidden',
            background: 'linear-gradient(150deg,#242525,#151616)', border: '1px solid rgba(255,255,255,.08)',
            boxShadow: '0 12px 28px rgba(0,0,0,.17),inset 0 1px 0 rgba(255,255,255,.03)', color: 'white'
          }}>
            <div className="panel-head dark" style={{ height: '52px', padding: '14px 16px 7px' }}>
              <div><h2 style={{ fontSize: '11px', margin: 0, fontWeight: 800, letterSpacing: '.015em' }}>SECURITY CENTER</h2><p style={{ fontSize: '7.5px', color: '#9a948c', margin: '3px 0 0' }}>THREAT MONITORING</p></div>
            </div>
            <div className="security-body" style={{ height: '105px', display: 'grid', gridTemplateColumns: '55% 45%', alignItems: 'center', padding: '0 12px' }}>
              <div className="security-radar" style={{ width: '130px', height: '130px', position: 'relative', margin: 'auto', display: 'grid', placeItems: 'center' }}>
                <div className="radar-ring rr1" style={{ position: 'absolute', border: '1px solid rgba(207,172,116,.35)', borderRadius: '50%', inset: '11px' }}></div>
                <div className="radar-ring rr2" style={{ position: 'absolute', border: '1px solid rgba(207,172,116,.35)', borderRadius: '50%', inset: '28px' }}></div>
                <div className="shield" style={{ fontSize: '44px', color: '#fff', filter: 'drop-shadow(0 0 12px rgba(235,202,148,.48))' }}>◇</div>
              </div>
              <div className="security-stats" style={{ display: 'grid', gap: '3px' }}>
                <span style={{ fontSize: '6px', color: '#aaa49a', marginTop: '4px' }}>RISK LEVEL</span>
                <b className="green" style={{ color: '#62c194', fontSize: '13px' }}>LOW</b>
              </div>
            </div>
          </article>
        </section>

        {/* BOTTOM COMMAND CONSOLE */}
        <footer className="command-console" style={{
          minHeight: '104px', borderRadius: '17px',
          background: 'rgba(248,245,240,.88)', border: '1px solid rgba(255,255,255,.7)',
          boxShadow: '0 10px 28px rgba(65,48,29,.08), inset 0 1px 0 rgba(255,255,255,.65)', padding: '12px 16px',
          display: 'grid', gridTemplateColumns: '290px minmax(260px,1fr) 46px 46px 240px', gap: '12px', alignItems: 'center'
        }}>
          <div className="assistant-mini" style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
            <div className="mini-orbit" style={{
              width: '64px', height: '64px', borderRadius: '50%', display: 'grid', placeItems: 'center',
              fontSize: '29px', fontWeight: 800, color: '#c09a64', background: '#24211d', border: '7px double #c7a46d',
              boxShadow: '0 0 0 6px rgba(207,178,133,.15)'
            }}>S</div>
            <div>
              <b style={{ display: 'block', fontSize: '11px' }}>System Response Node</b>
              <span style={{ display: 'block', fontSize: '9px', color: '#443f39', marginTop: '5px' }}>{response}</span>
            </div>
          </div>
          <label className="command-input" style={{
            height: '36px', border: '1px solid rgba(109,88,65,.12)', borderRadius: '999px',
            display: 'flex', alignItems: 'center', padding: '0 17px', background: '#f3eee7'
          }}>
            <input 
              type="text" 
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSendCommand()}
              placeholder="Ask anything or give a command..." 
              style={{ border: 0, outline: 0, background: 'transparent', width: '100%', fontSize: '11px', color: '#403b35' }}
            />
          </label>
          <button className="command-icon" style={{ width: '44px', height: '44px', borderRadius: '50%', border: '1px solid rgba(104,83,61,.13)', background: '#f7f3ed', fontSize: '17px', cursor: 'pointer' }} onClick={() => setIsListening(!isListening)}>{isListening ? '●' : '♩'}</button>
          <button className="command-icon" style={{ width: '44px', height: '44px', borderRadius: '50%', border: '1px solid rgba(104,83,61,.13)', background: '#f7f3ed', fontSize: '17px' }}>⌁</button>
          <button className="send-btn" onClick={handleSendCommand} style={{
            height: '47px', border: 0, borderRadius: '999px', padding: '0 8px 0 28px',
            background: 'linear-gradient(135deg,#29241e,#151412)', color: '#fff', fontSize: '11px', fontWeight: 800,
            boxShadow: '0 9px 22px rgba(56,39,24,.18)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer'
          }}>
            SEND COMMAND 
            <span style={{ width: '37px', height: '37px', borderRadius: '50%', background: '#f4eee5', color: '#27221c', display: 'grid', placeItems: 'center', fontSize: '16px', marginLeft: '12px' }}>➤</span>
          </button>
        </footer>
      </main>
    </div>
  )
}
