import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Monitor, Smartphone, Cpu, Wifi, CheckCircle, AlertCircle, XCircle, RefreshCw, Settings, Zap, HardDrive } from 'lucide-react'

/* ============================================================
   DEVICES VIEW — Connected devices & health.
   Lists all registered devices with status, capabilities, actions.
   ============================================================ */

interface Device {
  id: string
  name: string
  type: 'desktop' | 'mobile' | 'server'
  status: 'online' | 'offline' | 'busy' | 'error'
  last_seen: string
  capabilities: string[]
  specs: { cpu: string; ram: string; gpu?: string }
}

const MOCK_DEVICES: Device[] = [
  { id: 'dev-1', name: 'Salaar Workstation', type: 'desktop', status: 'online', last_seen: new Date().toISOString(), capabilities: ['nim-runner', 'voice', 'file-ops', 'browser'], specs: { cpu: 'AMD Ryzen 9 7950X', ram: '128GB DDR5', gpu: 'RTX 4090' } },
  { id: 'dev-2', name: 'MacBook Pro M3', type: 'desktop', status: 'busy', last_seen: new Date().toISOString(), capabilities: ['nim-runner', 'voice', 'file-ops'], specs: { cpu: 'Apple M3 Max', ram: '96GB Unified', gpu: 'M3 Max GPU' } },
  { id: 'dev-3', name: 'iPhone 15 Pro', type: 'mobile', status: 'online', last_seen: new Date(Date.now() - 3600000).toISOString(), capabilities: ['voice', 'notifications'], specs: { cpu: 'A17 Pro', ram: '8GB' } },
  { id: 'dev-4', name: 'H100 Cloud Node', type: 'server', status: 'online', last_seen: new Date().toISOString(), capabilities: ['nim-runner', 'training', 'inference'], specs: { cpu: 'Intel Xeon Platinum', ram: '2TB', gpu: '8x H100' } },
  { id: 'dev-5', name: 'Old Laptop', type: 'desktop', status: 'offline', last_seen: new Date(Date.now() - 86400000 * 3).toISOString(), capabilities: ['file-ops'], specs: { cpu: 'Intel i5-8250U', ram: '16GB' } },
]

const STATUS_ICONS = {
  online: <CheckCircle size={14} style={{ color: 'var(--nova-mint)' }} />,
  busy: <Zap size={14} style={{ color: 'var(--nova-amber)' }} />,
  offline: <XCircle size={14} style={{ color: 'var(--nova-lunar)', opacity: 0.5 }} />,
  error: <AlertCircle size={14} style={{ color: 'var(--nova-coral)' }} />,
}

const TYPE_ICONS = {
  desktop: <Monitor size={14} />,
  mobile: <Smartphone size={14} />,
  server: <Cpu size={14} />,
}

export function DevicesView({ api }: { api: any }) {
  const [devices, setDevices] = useState<Device[]>(MOCK_DEVICES)
  const [refreshing, setRefreshing] = useState(false)

  useEffect(() => {
    // In real app: fetch devices from API
    const interval = setInterval(() => {
      // Simulate status changes
      setDevices(prev => prev.map(d => ({
        ...d,
        status: d.status === 'busy' && Math.random() > 0.7 ? 'online' : d.status,
        last_seen: d.status === 'online' ? new Date().toISOString() : d.last_seen,
      })))
    }, 5000)
    return () => clearInterval(interval)
  }, [])

  const handleRefresh = async () => {
    setRefreshing(true)
    // In real app: await api.refreshDevices()
    await new Promise(r => setTimeout(r, 800))
    setRefreshing(false)
  }

  const handleRemove = async (id: string) => {
    // In real app: await api.removeDevice(id)
    setDevices(prev => prev.filter(d => d.id !== id))
  }

  const handleConfigure = (device: Device) => {
    // In real app: open config modal
    alert(`Configure ${device.name} — opens device settings modal`)
  }

  return (
    <div style={{
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      gap: 16,
      padding: '24px 32px',
      overflow: 'auto',
    }}>
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
        style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16 }}
      >
        <div>
          <h1 style={{ fontSize: 'clamp(28px, 3.5vw, 36px)', fontWeight: 300, letterSpacing: '-0.03em' }}>Devices</h1>
          <p style={{ fontSize: 13.5, color: 'var(--nova-lunar)', marginTop: 4 }}>
            {devices.filter(d => d.status === 'online').length} online · {devices.filter(d => d.status === 'busy').length} busy · {devices.filter(d => d.status === 'offline').length} offline
          </p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '10px 16px', borderRadius: 12,
            background: 'var(--nova-glass)', border: '1px solid var(--nova-line)',
            color: 'var(--nova-white)', fontWeight: 500, fontSize: 13, cursor: 'pointer',
            backdropFilter: 'blur(12px)',
          }}
        >
          <RefreshCw size={16} style={{ animation: refreshing ? 'spin 1s linear infinite' : 'none' }} />
          Refresh
        </button>
      </motion.div>

      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>

      {/* Device grid */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1], delay: 0.08 }}
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
          gap: 16,
        }}
      >
        <AnimatePresence mode="popLayout">
          {devices.map((device, i) => (
            <motion.article
              key={device.id}
              layout
              initial={{ opacity: 0, y: 16, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, x: 20, scale: 0.98 }}
              transition={{ duration: 0.3, delay: i * 0.04 }}
              style={{
                display: 'flex', flexDirection: 'column', gap: 14,
                padding: '20px', borderRadius: 16,
                background: 'var(--nova-glass)', border: '1px solid var(--nova-line)',
                backdropFilter: 'blur(12px)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <div style={{ width: 44, height: 44, borderRadius: 12, display: 'grid', placeItems: 'center',
                    background: device.status === 'online' ? 'rgba(120,244,197,.12)' : device.status === 'busy' ? 'rgba(255,204,117,.12)' : 'rgba(255,255,255,.04)',
                    border: `1px solid ${device.status === 'online' ? 'rgba(120,244,197,.3)' : device.status === 'busy' ? 'rgba(255,204,117,.3)' : 'var(--nova-line)'}` }}>
                    {TYPE_ICONS[device.type]}
                  </div>
                  <div>
                    <h3 style={{ fontSize: 16, fontWeight: 600, color: 'var(--nova-white)' }}>{device.name}</h3>
                    <p style={{ fontSize: 12, color: 'var(--nova-lunar)', textTransform: 'capitalize' }}>{device.type}</p>
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  {STATUS_ICONS[device.status]}
                  <span style={{ fontSize: 11.5, fontWeight: 500, color: device.status === 'online' ? 'var(--nova-mint)' : device.status === 'busy' ? 'var(--nova-amber)' : 'var(--nova-lunar)', textTransform: 'capitalize' }}>
                    {device.status}
                  </span>
                </div>
              </div>

              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {device.capabilities.map(cap => (
                  <span key={cap} style={{ fontSize: 10.5, padding: '4px 10px', borderRadius: 8, background: 'rgba(96,239,255,.08)', color: 'var(--nova-cyan)', fontWeight: 500 }}>
                    {cap}
                  </span>
                ))}
              </div>

              <div style={{ borderTop: '1px solid var(--nova-line)', paddingTop: 12, display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12, color: 'var(--nova-lunar)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Cpu size={14} style={{ opacity: 0.5 }} />
                  <span>{device.specs.cpu}</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <HardDrive size={14} style={{ opacity: 0.5 }} />
                  <span>{device.specs.ram}</span>
                </div>
                {device.specs.gpu && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Zap size={14} style={{ opacity: 0.5 }} />
                    <span>{device.specs.gpu}</span>
                  </div>
                )}
              </div>

              <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
                <button
                  onClick={() => handleConfigure(device)}
                  style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, padding: '10px 12px', borderRadius: 10, border: '1px solid var(--nova-line)', background: 'transparent', color: 'var(--nova-white)', fontSize: 12.5, fontWeight: 500, cursor: 'pointer' }}
                >
                  <Settings size={14} /> Configure
                </button>
                <button
                  onClick={() => handleRemove(device.id)}
                  style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, padding: '10px 12px', borderRadius: 10, border: '1px solid rgba(255,113,133,.3)', background: 'rgba(255,113,133,.08)', color: '#ff7185', fontSize: 12.5, fontWeight: 500, cursor: 'pointer' }}
                >
                  <XCircle size={14} /> Remove
                </button>
              </div>

              <p style={{ fontSize: 10.5, color: 'var(--nova-lunar)', opacity: 0.6 }}>
                Last seen: {new Date(device.last_seen).toLocaleString()}
              </p>
            </motion.article>
          ))}
        </AnimatePresence>
      </motion.div>

      {devices.length === 0 && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 16, color: 'var(--nova-lunar)' }}
        >
          <Monitor size={64} style={{ opacity: 0.3 }} />
          <p style={{ fontSize: 16 }}>No devices connected</p>
          <p style={{ fontSize: 13 }}>Click the + button in the rail to add a device</p>
        </motion.div>
      )}
    </div>
  )
}