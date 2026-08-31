import React, { useState } from 'react'
import { motion } from 'framer-motion'
import { Settings, Zap, Shield, Database, Terminal, Globe, Palette, Bell, Key, Trash2, Save, RotateCcw } from 'lucide-react'

/* ============================================================
   SYSTEM VIEW — Global settings, preferences, integrations.
   Tabs: General, AI Models, Integrations, Appearance, Security, Advanced.
   ============================================================ */

type SystemTab = 'general' | 'models' | 'integrations' | 'appearance' | 'security' | 'advanced'

const TAB_CONFIG: { id: SystemTab; label: string; icon: React.ReactNode }[] = [
  { id: 'general', label: 'General', icon: <Settings size={15} /> },
  { id: 'models', label: 'AI Models', icon: <Zap size={15} /> },
  { id: 'integrations', label: 'Integrations', icon: <Globe size={15} /> },
  { id: 'appearance', label: 'Appearance', icon: <Palette size={15} /> },
  { id: 'security', label: 'Security', icon: <Shield size={15} /> },
  { id: 'advanced', label: 'Advanced', icon: <Terminal size={15} /> },
]

export function SystemView({ api }: { api: any }) {
  const [activeTab, setActiveTab] = useState<SystemTab>('general')

  return (
    <div style={{
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      gap: 0,
      overflow: 'hidden',
    }}>
      {/* Tab bar */}
      <motion.div
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
        style={{
          display: 'flex',
          gap: 4,
          padding: '8px',
          background: 'var(--nova-glass)',
          border: '1px solid var(--nova-line)',
          borderRadius: 16,
          margin: '24px 32px 0',
          backdropFilter: 'blur(20px)',
          overflowX: 'auto',
        }}
      >
        {TAB_CONFIG.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              flex: '0 0 auto',
              display: 'flex', alignItems: 'center', gap: 8,
              padding: '10px 18px', borderRadius: 10,
              border: 'none', background: activeTab === tab.id ? 'rgba(96,239,255,.12)' : 'transparent',
              color: activeTab === tab.id ? 'var(--nova-cyan)' : 'var(--nova-lunar)',
              fontSize: 12.5, fontWeight: activeTab === tab.id ? 600 : 400,
              cursor: 'pointer', whiteSpace: 'nowrap', transition: 'all 0.18s',
            }}
          >
            {tab.icon} {tab.label}
          </button>
        ))}
      </motion.div>

      {/* Content */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1], delay: 0.06 }}
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          gap: 20,
          padding: '24px 32px',
          overflow: 'auto',
        }}
      >
        {activeTab === 'general' && <GeneralTab />}
        {activeTab === 'models' && <ModelsTab />}
        {activeTab === 'integrations' && <IntegrationsTab />}
        {activeTab === 'appearance' && <AppearanceTab />}
        {activeTab === 'security' && <SecurityTab />}
        {activeTab === 'advanced' && <AdvancedTab />}
      </motion.div>
    </div>
  )
}

/* ---- General ---- */
function GeneralTab() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 720 }}>
      <section style={{ background: 'var(--nova-glass)', border: '1px solid var(--nova-line)', borderRadius: 16, padding: 24 }}>
        <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 20 }}>General Settings</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <SettingRow label="Auto-start with system" description="Launch Salaar when you log in" type="toggle" defaultChecked />
          <SettingRow label="Check for updates" description="Automatically check for new versions" type="toggle" defaultChecked />
          <SettingRow label="Send anonymous usage data" description="Help improve Salaar with anonymous telemetry" type="toggle" />
          <SettingRow label="Default language" description="Interface language" type="select" options={['English', 'Spanish', 'French', 'German', 'Japanese', 'Chinese']} defaultValue="English" />
          <SettingRow label="Startup view" description="Which view opens by default" type="select" options={['Home', 'Quantum', 'Missions', 'Spaces', 'Agents', 'Memory', 'Devices']} defaultValue="Home" />
        </div>
      </section>

      <section style={{ background: 'var(--nova-glass)', border: '1px solid var(--nova-line)', borderRadius: 16, padding: 24 }}>
        <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 20 }}>Data & Storage</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <SettingRow label="Conversation history" description="Retain conversations for context" type="select" options={['30 days', '90 days', '1 year', 'Forever']} defaultValue="90 days" />
          <SettingRow label="Memory sync" description="Sync memories across devices" type="toggle" defaultChecked />
          <SettingRow label="Cache size" description="Local cache for offline use" type="select" options={['1 GB', '5 GB', '10 GB', 'Unlimited']} defaultValue="5 GB" />
          <div style={{ display: 'flex', gap: 12, paddingTop: 8 }}>
            <button style={{ flex: 1, padding: '12px', borderRadius: 10, border: '1px solid rgba(255,113,133,.3)', background: 'rgba(255,113,133,.08)', color: '#ff7185', fontWeight: 500, cursor: 'pointer' }}>
              <Trash2 size={16} /> Clear All Cache
            </button>
            <button style={{ flex: 1, padding: '12px', borderRadius: 10, border: '1px solid var(--nova-line)', background: 'transparent', color: 'var(--nova-white)', fontWeight: 500, cursor: 'pointer' }}>
              <RotateCcw size={16} /> Reset to Defaults
            </button>
          </div>
        </div>
      </section>
    </div>
  )
}

/* ---- AI Models ---- */
function ModelsTab() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 720 }}>
      <section style={{ background: 'var(--nova-glass)', border: '1px solid var(--nova-line)', borderRadius: 16, padding: 24 }}>
        <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 20 }}>Primary Models</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <ModelRow name="Coding & Tools" model="poolside/laguna-xs-2.1" status="Active" primary />
          <ModelRow name="Deep Reasoning" model="nvidia/nemotron-3.5-ultra" status="Available" />
          <ModelRow name="Multimodal" model="nvidia/nemotron-3.5-omni" status="Available" />
          <ModelRow name="Fast Chat" model="meta/llama-3.1-8b-instruct" status="Available" />
        </div>
        <div style={{ marginTop: 20, padding: 16, borderRadius: 12, background: 'rgba(96,239,255,.06)', border: '1px solid rgba(96,239,255,.15)' }}>
          <p style={{ fontSize: 13, color: 'var(--nova-cyan)', margin: 0 }}>Auto-routing enabled — Salaar selects the best model for each task.</p>
        </div>
      </section>

      <section style={{ background: 'var(--nova-glass)', border: '1px solid var(--nova-line)', borderRadius: 16, padding: 24 }}>
        <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 20 }}>Routing Rules</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <RoutingRule trigger="Code / Tools" target="Laguna XS" />
          <RoutingRule trigger="Deep Analysis" target="Nemotron 3.5 Ultra" />
          <RoutingRule trigger="Images / Voice" target="Nemotron 3.5 Omni" />
          <RoutingRule trigger="Quick Chat" target="Llama 3.1 8B" />
        </div>
        <button style={{ marginTop: 16, padding: '12px 20px', borderRadius: 10, border: 'none', background: 'linear-gradient(135deg, var(--nova-cyan), #6a7bff)', color: '#051018', fontWeight: 600, cursor: 'pointer' }}>
          <Save size={16} /> Save Routing Config
        </button>
      </section>
    </div>
  )
}

function ModelRow({ name, model, status, primary }: { name: string; model: string; status: string; primary?: boolean }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, padding: '16px', borderRadius: 12, background: primary ? 'rgba(96,239,255,.06)' : 'rgba(255,255,255,.02)', border: primary ? '1px solid rgba(96,239,255,.15)' : '1px solid var(--nova-line)' }}>
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
          <span style={{ fontSize: 14, fontWeight: 600 }}>{name}</span>
          {primary && <span style={{ fontSize: 10, padding: '2px 8px', borderRadius: 6, background: 'rgba(96,239,255,.15)', color: 'var(--nova-cyan)', fontWeight: 600 }}>Primary</span>}
        </div>
        <code style={{ fontSize: 12, color: 'var(--nova-lunar)', fontFamily: 'var(--nova-font-mono)' }}>{model}</code>
      </div>
      <span style={{ fontSize: 11, fontWeight: 500, padding: '4px 10px', borderRadius: 6,
        background: status === 'Active' ? 'rgba(120,244,197,.12)' : 'rgba(255,255,255,.06)',
        color: status === 'Active' ? 'var(--nova-mint)' : 'var(--nova-lunar)' }}>
        {status}
      </span>
    </div>
  )
}

function RoutingRule({ trigger, target }: { trigger: string; target: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px', borderRadius: 10, background: 'rgba(255,255,255,.02)', border: '1px solid var(--nova-line)' }}>
      <span style={{ fontSize: 13, color: 'var(--nova-white)' }}>{trigger}</span>
      <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--nova-cyan)' }}>{target}</span>
    </div>
  )
}

/* ---- Integrations ---- */
function IntegrationsTab() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 720 }}>
      <section style={{ background: 'var(--nova-glass)', border: '1px solid var(--nova-line)', borderRadius: 16, padding: 24 }}>
        <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 20 }}>Connected Services</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <IntegrationRow name="GitHub" description="Repositories, issues, PRs" status="connected" />
          <IntegrationRow name="GitLab" description="Projects, merge requests" status="disconnected" />
          <IntegrationRow name="Linear" description="Issues, projects, cycles" status="connected" />
          <IntegrationRow name="Notion" description="Pages, databases, docs" status="disconnected" />
          <IntegrationRow name="Slack" description="Channels, DMs, notifications" status="disconnected" />
          <IntegrationRow name="Jira" description="Issues, boards, sprints" status="disconnected" />
        </div>
      </section>
    </div>
  )
}

function IntegrationRow({ name, description, status }: { name: string; description: string; status: 'connected' | 'disconnected' }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px', borderRadius: 12, background: 'rgba(255,255,255,.02)', border: '1px solid var(--nova-line)' }}>
      <div>
        <div style={{ fontSize: 15, fontWeight: 600 }}>{name}</div>
        <div style={{ fontSize: 12, color: 'var(--nova-lunar)' }}>{description}</div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span style={{ fontSize: 11, fontWeight: 500, padding: '4px 10px', borderRadius: 6,
          background: status === 'connected' ? 'rgba(120,244,197,.12)' : 'rgba(255,255,255,.06)',
          color: status === 'connected' ? 'var(--nova-mint)' : 'var(--nova-lunar)' }}>
        {status === 'connected' ? 'Connected' : 'Connect'}
      </span>
        <button style={{ padding: 6, borderRadius: 8, background: 'transparent', border: 'none', color: 'var(--nova-lunar)', cursor: 'pointer', opacity: 0.6 }}>
          <Key size={14} />
        </button>
      </div>
    </div>
  )
}

/* ---- Appearance ---- */
function AppearanceTab() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 720 }}>
      <section style={{ background: 'var(--nova-glass)', border: '1px solid var(--nova-line)', borderRadius: 16, padding: 24 }}>
        <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 20 }}>Theme</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <SettingRow label="Color theme" description="Global color scheme" type="select" options={['Light (White + #e61359)', 'Dark (Void + Cyan)', 'Auto (System)']} defaultValue="Light (White + #e61359)" />
          <SettingRow label="Accent color" description="Primary brand color" type="select" options={['Pink #e61359', 'Cyan #60efff', 'Violet #a879ff', 'Mint #78f4c5', 'Amber #ffcc75', 'Coral #ff7185']} defaultValue="Pink #e61359" />
          <SettingRow label="Font family" description="Interface typeface" type="select" options={['Inter (Default)', 'Space Grotesk', 'JetBrains Mono', 'System UI']} defaultValue="Inter (Default)" />
          <SettingRow label="UI density" description="Spacing and sizing" type="select" options={['Compact', 'Comfortable (Default)', 'Spacious']} defaultValue="Comfortable (Default)" />
          <SettingRow label="Animations" description="Motion and transitions" type="select" options={['Full', 'Reduced', 'Off']} defaultValue="Full" />
        </div>
      </section>

      <section style={{ background: 'var(--nova-glass)', border: '1px solid var(--nova-line)', borderRadius: 16, padding: 24 }}>
        <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 20 }}>Orb Style</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <SettingRow label="Core visualization" description="Center orb appearance" type="select" options={['Crystalline', 'Plasma', 'Hologram', 'Minimal']} defaultValue="Crystalline" />
          <SettingRow label="Orbit rings" description="Show rotating rings around orb" type="toggle" defaultChecked />
          <SettingRow label="Particle trails" description="Show particle effects on interaction" type="toggle" defaultChecked />
          <SettingRow label="Glow intensity" description="Orb ambient glow strength" type="select" options={['Subtle', 'Normal', 'Bright']} defaultValue="Normal" />
        </div>
      </section>
    </div>
  )
}

/* ---- Security ---- */
function SecurityTab() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 720 }}>
      <section style={{ background: 'var(--nova-glass)', border: '1px solid var(--nova-line)', borderRadius: 16, padding: 24 }}>
        <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 20 }}>Authentication</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <SettingRow label="Two-factor authentication" description="Require 2FA for sign-in" type="toggle" defaultChecked />
          <SettingRow label="Session timeout" description="Auto-sign out after inactivity" type="select" options={['15 minutes', '1 hour', '4 hours', '24 hours', 'Never']} defaultValue="4 hours" />
          <SettingRow label="Device verification" description="Approve new device sign-ins" type="toggle" defaultChecked />
          <div style={{ paddingTop: 8 }}>
            <button style={{ padding: '12px 20px', borderRadius: 10, border: '1px solid var(--nova-line)', background: 'transparent', color: 'var(--nova-white)', fontWeight: 500, cursor: 'pointer' }}>
              <Key size={16} /> Manage Active Sessions
            </button>
          </div>
        </div>
      </section>

      <section style={{ background: 'var(--nova-glass)', border: '1px solid var(--nova-line)', borderRadius: 16, padding: 24 }}>
        <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 20 }}>Data Protection</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <SettingRow label="Encrypt local data" description="AES-256 encryption for stored data" type="toggle" defaultChecked />
          <SettingRow label="Require biometric for sensitive actions" description="Confirm with fingerprint/Face ID" type="toggle" />
          <SettingRow label="Auto-lock on away" description="Lock Salaar when you step away" type="toggle" defaultChecked />
        </div>
      </section>
    </div>
  )
}

/* ---- Advanced ---- */
function AdvancedTab() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 720 }}>
      <section style={{ background: 'var(--nova-glass)', border: '1px solid var(--nova-line)', borderRadius: 16, padding: 24 }}>
        <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 20 }}>Developer</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <SettingRow label="Developer mode" description="Enable debug features" type="toggle" />
          <SettingRow label="Log level" description="Verbosity of internal logs" type="select" options={['Error', 'Warn', 'Info', 'Debug', 'Trace']} defaultValue="Info" />
          <SettingRow label="Show performance overlay" description="FPS, memory, latency metrics" type="toggle" />
        </div>
      </section>

      <section style={{ background: 'var(--nova-glass)', border: '1px solid var(--nova-line)', borderRadius: 16, padding: 24 }}>
        <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 20 }}>Danger Zone</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px', borderRadius: 12, background: 'rgba(255,113,133,.06)', border: '1px solid rgba(255,113,133,.15)' }}>
            <div>
              <div style={{ fontSize: 14, fontWeight: 600, color: '#ff7185' }}>Reset Salaar</div>
              <div style={{ fontSize: 12, color: 'var(--nova-lunar)' }}>Clear all data, settings, and memories</div>
            </div>
            <button style={{ padding: '10px 18px', borderRadius: 10, border: '1px solid rgba(255,113,133,.3)', background: 'rgba(255,113,133,.08)', color: '#ff7185', fontWeight: 600, cursor: 'pointer' }}>
              <Trash2 size={16} /> Reset Everything
            </button>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px', borderRadius: 12, background: 'rgba(255,204,117,.06)', border: '1px solid rgba(255,204,117,.15)' }}>
            <div>
              <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--nova-amber)' }}>Export Data</div>
              <div style={{ fontSize: 12, color: 'var(--nova-lunar)' }}>Download all conversations and memories</div>
            </div>
            <button style={{ padding: '10px 18px', borderRadius: 10, border: '1px solid rgba(255,204,117,.3)', background: 'rgba(255,204,117,.08)', color: 'var(--nova-amber)', fontWeight: 600, cursor: 'pointer' }}>
              <Database size={16} /> Export
            </button>
          </div>
        </div>
      </section>
    </div>
  )
}

/* ---- Shared Setting Row ---- */
function SettingRow({ label, description, type, options, defaultValue, defaultChecked }: {
  label: string
  description: string
  type: 'toggle' | 'select'
  options?: string[]
  defaultValue?: string
  defaultChecked?: boolean
}) {
  const [checked, setChecked] = useState(defaultChecked || false)
  const [value, setValue] = useState(defaultValue || options?.[0] || '')

  if (type === 'toggle') {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16 }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 14, fontWeight: 500 }}>{label}</div>
          <div style={{ fontSize: 12, color: 'var(--nova-lunar)' }}>{description}</div>
        </div>
        <button
          onClick={() => setChecked(!checked)}
          role="switch"
          aria-checked={checked}
          style={{
            width: 48, height: 28, borderRadius: 14,
            background: checked ? 'linear-gradient(135deg, var(--nova-cyan), #6a7bff)' : 'rgba(255,255,255,.08)',
            border: checked ? 'none' : '1px solid var(--nova-line)',
            position: 'relative', cursor: 'pointer',
          }}
        >
          <span style={{
            position: 'absolute', top: 2, left: checked ? 24 : 2,
            width: 24, height: 24, borderRadius: '50%',
            background: 'white', boxShadow: '0 2px 6px rgba(0,0,0,.2)',
            transition: 'left 0.18s',
          }} />
        </button>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16 }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 14, fontWeight: 500 }}>{label}</div>
          <div style={{ fontSize: 12, color: 'var(--nova-lunar)' }}>{description}</div>
        </div>
        <select
          value={value}
          onChange={e => setValue(e.target.value)}
          style={{
            flex: '0 0 220px', minWidth: 180,
            padding: '10px 14px', borderRadius: 10,
            border: '1px solid var(--nova-line)',
            background: 'rgba(255,255,255,.04)',
            color: 'var(--nova-white)',
            fontSize: 13, fontFamily: 'inherit',
            outline: 'none', cursor: 'pointer',
          }}
        >
          {options?.map(opt => <option key={opt} value={opt}>{opt}</option>)}
        </select>
      </div>
    </div>
  )
}