import React from 'react'
import { motion } from 'framer-motion'
import { Code2, FlaskConical, Palette, Briefcase, User, Cpu, ArrowRight, Plus } from 'lucide-react'

/* ============================================================
   SPACES OVERVIEW — spatial environment, not a file manager.
   Top: "Your Spaces"
   Large featured active Space.
   Below: 3–6 recently used Spaces.
   ============================================================ */

export type SpaceKind = 'development' | 'research' | 'creative' | 'business' | 'personal' | 'device'

export interface SpaceInfo {
  kind: SpaceKind
  name: string
  purpose: string
  lastActivity: string
  mission?: string
  agents?: string[]
}

export const DEFAULT_SPACES: SpaceInfo[] = [
  {
    kind: 'development',
    name: 'Development',
    purpose: 'Code, build, and ship.',
    lastActivity: 'Active now',
    mission: 'Salaar Nova redesign',
    agents: ['Architect', 'Engineer'],
  },
  {
    kind: 'research',
    name: 'Research',
    purpose: 'Synthesize sources into knowledge.',
    lastActivity: '2 hours ago',
    agents: ['Researcher'],
  },
  {
    kind: 'creative',
    name: 'Creative',
    purpose: 'Design, generate, and visualize.',
    lastActivity: 'Yesterday',
    agents: ['Designer'],
  },
  {
    kind: 'business',
    name: 'Business',
    purpose: 'Email, meetings, and documents.',
    lastActivity: 'Yesterday',
    mission: 'Nova launch plan',
    agents: ['Organizer'],
  },
  {
    kind: 'personal',
    name: 'Personal',
    purpose: 'Daily life, reminders, plans.',
    lastActivity: '3 days ago',
  },
  {
    kind: 'device',
    name: 'Device Control',
    purpose: 'Run your connected world.',
    lastActivity: 'Today',
    mission: 'Health check',
    agents: ['Automation'],
  },
]

const KIND_ICON: Record<SpaceKind, React.ReactNode> = {
  development: <Code2 size={22} strokeWidth={1.5}/>,
  research: <FlaskConical size={22} strokeWidth={1.5}/>,
  creative: <Palette size={22} strokeWidth={1.5}/>,
  business: <Briefcase size={22} strokeWidth={1.5}/>,
  personal: <User size={22} strokeWidth={1.5}/>,
  device: <Cpu size={22} strokeWidth={1.5}/>,
}

interface SpacesOverviewProps {
  spaces?: SpaceInfo[]
  onOpenSpace: (kind: SpaceKind) => void
  onCreateSpace?: () => void
}

export default function SpacesOverview({
  spaces = DEFAULT_SPACES,
  onOpenSpace,
  onCreateSpace,
}: SpacesOverviewProps) {
  const featured = spaces.find(s => s.mission) ?? spaces[0]
  const rest = spaces.filter(s => s !== featured).slice(0, 5)

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      style={{
        flex: 1,
        overflowY: 'auto',
        padding: 'clamp(24px, 5vh, 48px) clamp(24px, 4vw, 64px)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', marginBottom: 24 }}>
        <div>
          <div className="nova-meta" style={{ color: 'var(--nova-violet)', marginBottom: 6 }}>SPATIAL LAYER</div>
          <h1 style={{ margin: 0, fontSize: 'clamp(28px, 3.6vw, 40px)', fontWeight: 300, letterSpacing: '-0.03em', color: 'var(--nova-white)' }}>
            Your Spaces
          </h1>
        </div>
        {onCreateSpace && (
          <button onClick={onCreateSpace} style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '9px 18px', borderRadius: 12,
            background: 'var(--nova-glass)', border: '1px solid var(--nova-line-cyan)',
            color: 'var(--nova-cyan)', cursor: 'pointer', fontSize: 12, fontWeight: 600,
          }}>
            <Plus size={15}/> New Space
          </button>
        )}
      </div>

      {/* Featured space */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.08 }}
        onClick={() => onOpenSpace(featured.kind)}
        className="nova-intel-glass"
        style={{
          padding: '26px 30px', cursor: 'pointer',
          marginBottom: 20,
          display: 'flex', alignItems: 'center', gap: 22,
        }}
      >
        <div style={{
          width: 64, height: 64, borderRadius: 18, flexShrink: 0,
          display: 'grid', placeItems: 'center',
          background: 'linear-gradient(135deg, rgba(96,239,255,.14), rgba(168,121,255,.14))',
          border: '1px solid var(--nova-line-cyan)',
          color: 'var(--nova-cyan)',
        }}>
          {KIND_ICON[featured.kind]}
        </div>
        <div style={{ flex: 1 }}>
          <div className="nova-meta" style={{ color: 'var(--nova-cyan)', marginBottom: 4 }}>FEATURED SPACE</div>
          <h2 style={{ margin: 0, fontSize: 'clamp(20px, 2.4vw, 26px)', fontWeight: 400, letterSpacing: '-0.02em', color: 'var(--nova-white)' }}>
            {featured.name}
          </h2>
          <p style={{ margin: '6px 0 0', fontSize: 13, color: 'var(--nova-lunar)' }}>
            {featured.purpose}{featured.mission ? ` — Active mission: ${featured.mission}` : ''}
          </p>
        </div>
        {featured.agents && featured.agents.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, alignItems: 'flex-end' }}>
            {featured.agents.map(a => (
              <span key={a} style={{
                fontSize: 10, letterSpacing: '.1em', textTransform: 'uppercase', color: 'var(--nova-violet)',
                padding: '3px 9px', borderRadius: 8, border: '1px solid var(--nova-line-violet)',
              }}>
                {a}
              </span>
            ))}
          </div>
        )}
        <span style={{ color: 'var(--nova-cyan)', opacity: 0.8 }}><ArrowRight size={18}/></span>
      </motion.div>

      {/* Recent spaces grid */}
      <div className="nova-meta" style={{ marginBottom: 12 }}>RECENTLY USED</div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: 14 }}>
        {rest.map((s, i) => (
          <motion.button
            key={s.kind}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 + i * 0.05 }}
            whileHover={{ y: -3 }}
            onClick={() => onOpenSpace(s.kind)}
            style={{
              display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 8,
              padding: '18px 20px', textAlign: 'left',
              background: 'var(--nova-glass)', border: '1px solid var(--nova-line)',
              borderRadius: 16, cursor: 'pointer',
            }}
          >
            <div style={{
              width: 44, height: 44, borderRadius: 13,
              display: 'grid', placeItems: 'center',
              background: 'linear-gradient(135deg, rgba(96,239,255,.08), rgba(168,121,255,.08))',
              border: '1px solid var(--nova-line)',
              color: 'var(--nova-lunar)',
            }}>
              {KIND_ICON[s.kind]}
            </div>
            <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--nova-white)' }}>{s.name}</div>
            <div style={{ fontSize: 12, color: 'var(--nova-lunar)', lineHeight: 1.4 }}>{s.purpose}</div>
            <div style={{ fontSize: 10.5, color: 'var(--nova-violet)', letterSpacing: '.06em', marginTop: 2 }}>
              {s.lastActivity.toUpperCase()}
            </div>
          </motion.button>
        ))}
      </div>
    </motion.div>
  )
}
