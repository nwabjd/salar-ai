import React, { useState, useEffect, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  LayoutDashboard,
  Brain,
  Target,
  Layers,
  Database,
  Users,
  Monitor,
  Zap,
  Shield,
  Settings,
  Cpu,
  Search,
  Bell,
  Mic,
  Send,
  Activity,
  Wifi,
  Server,
  Thermometer,
  Clock,
  Network,
  RefreshCw,
  ArrowUpRight,
  Sparkles,
  Terminal
} from 'lucide-react';
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer
} from 'recharts';
import { AmbientBackground } from './components/AmbientBackground';
import { EnhancedQuantumCore } from './components/EnhancedQuantumCore';
import { Waveform } from './components/Waveform';
import { LiveMetric, TypingIndicator } from './components/LiveMetric';
import { ThinkingSkull, type SkullState } from './components/ThinkingSkull';
import { SalarApi } from '../../api';
import { isDesktop, getLiveMetrics } from '../../access';
import './quantum-engine.css';

// ============================================================================
// TYPES
// ============================================================================

type NavItem = {
  id: string;
  label: string;
  icon: React.ElementType;
};

type CoreState = 'idle' | 'listening' | 'thinking' | 'planning' | 'acting' | 'verifying' | 'complete' | 'warning' | 'error';

type Agent = {
  id: string;
  name: string;
  role: string;
  status: 'active' | 'idle' | 'busy';
  avatar: string;
};

type SystemStatus = {
  coreTemp: number;
  quantumCores: { active: number; total: number };
  memoryUsage: number;
  cpuUsage: number;
  gpuUsage: number;
  uptime: string;
};

// ============================================================================
// CONSTANTS
// ============================================================================

const NAV_ITEMS: NavItem[] = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { id: 'intelligence', label: 'Intelligence', icon: Brain },
  { id: 'agents', label: 'Agents', icon: Users },
  { id: 'missions', label: 'Missions', icon: Target },
  { id: 'security', label: 'Security', icon: Shield },
  { id: 'system', label: 'System', icon: Settings },
];

const AGENTS: Agent[] = [
  { id: '1', name: 'Optimizer', role: 'System Optimization', status: 'active', avatar: 'O' },
  { id: '2', name: 'Researcher', role: 'Data Analysis', status: 'busy', avatar: 'R' },
  { id: '3', name: 'Analyst', role: 'Pattern Recognition', status: 'active', avatar: 'A' },
  { id: '4', name: 'Guardian', role: 'Security Monitor', status: 'active', avatar: 'G' },
  { id: '5', name: 'Architect', role: 'System Design', status: 'idle', avatar: 'R' },
  { id: '6', name: 'Synthesizer', role: 'Content Generation', status: 'busy', avatar: 'S' },
];

const COLORS = {
  gold: '#C9A56E',
  champagne: '#D9C09A',
  paleGold: '#E7D6B7',
  goldHighlight: '#F2E5CC',
  green: '#2F6E59',
  softGreen: '#78A891',
  amber: '#C58A42',
  coral: '#B95750',
};

// ============================================================================
// STATUS DOT
// ============================================================================

const StatusDot: React.FC<{ status: 'green' | 'amber' | 'coral' | 'pulse-green'; size?: number }> = ({ status, size = 8 }) => (
  <span className={`status-dot ${status}`} style={{ width: size, height: size }} />
);

// ============================================================================
// ANIMATED WORLD MAP
// ============================================================================

const WorldMap: React.FC = () => {
  const [activePoints, setActivePoints] = useState<{ x: number; y: number }[]>([]);
  const [packets, setPackets] = useState<{ from: number; to: number; progress: number }[]>([]);

  useEffect(() => {
    const generatePoints = () => {
      const points = Array.from({ length: 18 }, () => ({
        x: 10 + Math.random() * 80,
        y: 15 + Math.random() * 70,
      }));
      setActivePoints(points);
    };
    generatePoints();
    const interval = setInterval(generatePoints, 4000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const generatePackets = () => {
      if (activePoints.length < 2) return;
      const newPacket = {
        from: Math.floor(Math.random() * activePoints.length),
        to: Math.floor(Math.random() * activePoints.length),
        progress: 0,
      };
      setPackets(prev => [...prev.slice(-4), newPacket]);
    };
    const interval = setInterval(generatePackets, 1500);
    return () => clearInterval(interval);
  }, [activePoints]);

  useEffect(() => {
    const tick = setInterval(() => {
      setPackets(prev => prev
        .map(p => ({ ...p, progress: p.progress + 0.04 }))
        .filter(p => p.progress < 1)
      );
    }, 30);
    return () => clearInterval(tick);
  }, []);

  return (
    <div className="relative w-full h-full">
      <svg className="w-full h-full" viewBox="0 0 800 400" preserveAspectRatio="xMidYMid meet">
        <defs>
          <radialGradient id="mapGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor={COLORS.gold} stopOpacity="0.15" />
            <stop offset="100%" stopColor={COLORS.gold} stopOpacity="0" />
          </radialGradient>
          <filter id="mapBlur">
            <feGaussianBlur stdDeviation="2" />
          </filter>
        </defs>

        {/* Background glow */}
        <rect width="800" height="400" fill="url(#mapGlow)" />

        {/* Grid */}
        <g opacity="0.15">
          {Array.from({ length: 20 }).map((_, i) => (
            <line
              key={`v-${i}`}
              x1={i * 40} y1={0} x2={i * 40} y2={400}
              stroke={COLORS.gold}
              strokeWidth="0.5"
              strokeDasharray="2 4"
            />
          ))}
          {Array.from({ length: 10 }).map((_, i) => (
            <line
              key={`h-${i}`}
              x1={0} y1={i * 40} x2={800} y2={i * 40}
              stroke={COLORS.gold}
              strokeWidth="0.5"
              strokeDasharray="2 4"
            />
          ))}
        </g>

        {/* Continent silhouettes (stylized) */}
        <g opacity="0.25" fill={COLORS.gold}>
          <path d="M120,80 Q150,60 200,70 T280,100 T340,90 T400,110 T460,100 T520,120 T580,110 T640,130 T700,120 L720,140 Q680,160 640,150 T580,170 T520,160 T460,180 T400,170 T340,190 T280,180 T220,200 T160,190 L140,170 Q130,130 120,80 Z" />
          <path d="M150,220 Q200,200 260,210 T340,230 T420,220 T500,240 T580,230 T660,250 L680,270 Q640,290 580,280 T500,300 T420,290 T340,310 T260,300 T180,320 L160,300 Q140,260 150,220 Z" />
        </g>

        {/* Connections */}
        {activePoints.map((point, i) =>
          activePoints.slice(i + 1, i + 4).map((target, j) => (
            <motion.line
              key={`line-${i}-${j}`}
              x1={point.x * 8}
              y1={point.y * 4}
              x2={target.x * 8}
              y2={target.y * 4}
              stroke={COLORS.gold}
              strokeWidth="0.5"
              initial={{ opacity: 0 }}
              animate={{ opacity: [0, 0.3, 0] }}
              transition={{ duration: 3, repeat: Infinity, delay: (i * 0.3 + j * 0.2) % 2 }}
            />
          ))
        )}

        {/* Traveling packets */}
        {packets.map((packet, i) => {
          if (activePoints.length < 2) return null;
          const from = activePoints[packet.from % activePoints.length];
          const to = activePoints[packet.to % activePoints.length];
          const x = from.x * 8 + (to.x * 8 - from.x * 8) * packet.progress;
          const y = from.y * 4 + (to.y * 4 - from.y * 4) * packet.progress;
          return (
            <motion.g key={`packet-${i}-${packet.progress}`}>
              <circle cx={x} cy={y} r="4" fill={COLORS.goldHighlight} filter="url(#mapBlur)" />
              <circle cx={x} cy={y} r="2" fill={COLORS.gold} />
              <motion.circle
                cx={x}
                cy={y}
                r="6"
                fill="none"
                stroke={COLORS.gold}
                strokeWidth="1"
                animate={{ opacity: [0.6, 0], r: [6, 10] }}
                transition={{ duration: 0.8 }}
              />
            </motion.g>
          );
        })}

        {/* Active points */}
        {activePoints.map((point, i) => (
          <motion.g key={i}>
            <motion.circle
              cx={point.x * 8}
              cy={point.y * 4}
              r="3"
              fill={COLORS.gold}
              initial={{ scale: 0, opacity: 0 }}
              animate={{ scale: [1, 1.3, 1], opacity: [0.6, 1, 0.6] }}
              transition={{ duration: 2.5, repeat: Infinity, delay: i * 0.15 }}
            />
            <motion.circle
              cx={point.x * 8}
              cy={point.y * 4}
              r="8"
              fill="none"
              stroke={COLORS.gold}
              strokeWidth="0.8"
              animate={{ scale: [1, 1.8, 1], opacity: [0.4, 0, 0.4] }}
              transition={{ duration: 2.5, repeat: Infinity, delay: i * 0.15 }}
            />
          </motion.g>
        ))}
      </svg>

      <div className="absolute top-3 right-3 flex items-center gap-2 px-3 py-1.5 rounded-full glass-dark">
        <motion.div
          className="w-2 h-2 rounded-full bg-red-500"
          animate={{ opacity: [1, 0.3, 1] }}
          transition={{ duration: 1, repeat: Infinity }}
        />
        <span className="text-[10px] font-semibold uppercase tracking-wider text-white/80">LIVE FEED</span>
      </div>
    </div>
  );
};

// ============================================================================
// AGENT NETWORK
// ============================================================================

const AgentNetwork: React.FC<{ agents: Agent[] }> = ({ agents }) => {
  const centerX = 150;
  const centerY = 150;
  const radius = 80;

  return (
    <svg className="w-full h-full" viewBox="0 0 300 300">
      <defs>
        <radialGradient id="agentGlow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor={COLORS.gold} stopOpacity="0.4" />
          <stop offset="100%" stopColor={COLORS.gold} stopOpacity="0" />
        </radialGradient>
        <filter id="agentBlur">
          <feGaussianBlur stdDeviation="2" />
        </filter>
      </defs>

      {/* Background glow */}
      <circle cx={centerX} cy={centerY} r="120" fill="url(#agentGlow)" />

      {/* Rotating orbital rings */}
      <motion.circle
        cx={centerX} cy={centerY} r={radius + 20}
        fill="none"
        stroke={COLORS.gold}
        strokeWidth="0.5"
        strokeDasharray="4 6"
        opacity="0.3"
        animate={{ rotate: 360 }}
        transition={{ duration: 30, repeat: Infinity, ease: 'linear' }}
        style={{ transformOrigin: `${centerX}px ${centerY}px` }}
      />
      <motion.circle
        cx={centerX} cy={centerY} r={radius}
        fill="none"
        stroke={COLORS.champagne}
        strokeWidth="0.8"
        strokeDasharray="2 8"
        opacity="0.4"
        animate={{ rotate: -360 }}
        transition={{ duration: 25, repeat: Infinity, ease: 'linear' }}
        style={{ transformOrigin: `${centerX}px ${centerY}px` }}
      />

      {/* Connection lines with flowing data */}
      {agents.map((_, i) => {
        const angle = (i * 60 - 90) * (Math.PI / 180);
        const x = centerX + radius * Math.cos(angle);
        const y = centerY + radius * Math.sin(angle);
        return (
          <g key={`line-${i}`}>
            <line
              x1={centerX} y1={centerY}
              x2={x} y2={y}
              stroke={COLORS.gold}
              strokeWidth="1"
              opacity="0.2"
            />
            <motion.circle r="2" fill={COLORS.goldHighlight} filter="url(#agentBlur)">
              <animateMotion
                dur="2s"
                repeatCount="indefinite"
                path={`M${centerX},${centerY} L${x},${y}`}
                begin={`${i * 0.3}s`}
              />
            </motion.circle>
          </g>
        );
      })}

      {/* Center hub */}
      <motion.circle
        cx={centerX} cy={centerY} r="28"
        fill={COLORS.gold}
        opacity="0.15"
        animate={{ scale: [1, 1.1, 1] }}
        transition={{ duration: 2, repeat: Infinity }}
      />
      <motion.circle
        cx={centerX} cy={centerY} r="20"
        fill="none"
        stroke={COLORS.gold}
        strokeWidth="2"
        animate={{ rotate: 360 }}
        transition={{ duration: 8, repeat: Infinity, ease: 'linear' }}
        strokeDasharray="6 3"
        style={{ transformOrigin: `${centerX}px ${centerY}px` }}
      />
      <text x={centerX} y={centerY + 5} textAnchor="middle" fill={COLORS.gold} fontSize="14" fontWeight="700">S</text>

      {/* Agent nodes */}
      {agents.map((agent, i) => {
        const angle = (i * 60 - 90) * (Math.PI / 180);
        const x = centerX + radius * Math.cos(angle);
        const y = centerY + radius * Math.sin(angle);
        const isActive = agent.status === 'active' || agent.status === 'busy';
        const nodeColor = isActive ? COLORS.gold : 'rgba(255,255,255,0.25)';

        return (
          <motion.g
            key={agent.id}
            initial={{ opacity: 0, scale: 0 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.5, delay: i * 0.1 }}
          >
            {isActive && (
              <motion.circle
                cx={x} cy={y} r="18"
                fill={COLORS.gold}
                opacity="0.15"
                animate={{ scale: [1, 1.4, 1], opacity: [0.15, 0, 0.15] }}
                transition={{ duration: 2, repeat: Infinity, delay: i * 0.2 }}
              />
            )}
            <motion.circle
              cx={x} cy={y} r="13"
              fill="rgba(20, 20, 20, 0.6)"
              stroke={nodeColor}
              strokeWidth="1.5"
              animate={isActive ? { scale: [1, 1.05, 1] } : {}}
              transition={{ duration: 2, repeat: Infinity, delay: i * 0.25 }}
            />
            <text x={x} y={y + 4} textAnchor="middle" fill={nodeColor} fontSize="10" fontWeight="700">
              {agent.avatar}
            </text>
            <text x={x} y={y + 30} textAnchor="middle" fill="rgba(245, 242, 236, 0.7)" fontSize="8" fontWeight="500">
              {agent.name}
            </text>
          </motion.g>
        );
      })}
    </svg>
  );
};

// ============================================================================
// KNOWLEDGE GRAPH
// ============================================================================

const KnowledgeGraph: React.FC = () => {
  const [nodes, setNodes] = useState<{ x: number; y: number; size: number }[]>([]);

  useEffect(() => {
    const generateNodes = () => {
      const newNodes = Array.from({ length: 14 }, (_, i) => ({
        x: 15 + ((i * 37) % 70),
        y: 15 + ((i * 53) % 70),
        size: 3 + ((i * 7) % 5),
      }));
      setNodes(newNodes);
    };
    generateNodes();
    const interval = setInterval(generateNodes, 6000);
    return () => clearInterval(interval);
  }, []);

  return (
    <svg className="w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="xMidYMid meet">
      <defs>
        <filter id="nodeGlow">
          <feGaussianBlur stdDeviation="0.4" />
        </filter>
      </defs>

      {/* Connection lines */}
      {nodes.map((node, i) =>
        nodes.slice(i + 1, i + 4).map((target, j) => {
          const dist = Math.sqrt((node.x - target.x) ** 2 + (node.y - target.y) ** 2);
          if (dist > 35) return null;
          return (
            <motion.line
              key={`${i}-${j}`}
              x1={node.x} y1={node.y}
              x2={target.x} y2={target.y}
              stroke={COLORS.gold}
              strokeWidth="0.2"
              initial={{ opacity: 0 }}
              animate={{ opacity: [0, 0.3, 0] }}
              transition={{ duration: 3, repeat: Infinity, delay: (i * 0.2 + j * 0.3) % 2 }}
            />
          );
        })
      )}

      {/* Nodes */}
      {nodes.map((node, i) => (
        <motion.g key={i}>
          <motion.circle
            cx={node.x} cy={node.y}
            r={node.size / 2}
            fill={COLORS.gold}
            filter="url(#nodeGlow)"
            animate={{
              scale: [1, 1.15, 1],
              opacity: [0.7, 1, 0.7],
            }}
            transition={{
              duration: 3 + (i % 3),
              repeat: Infinity,
              delay: i * 0.15,
              ease: 'easeInOut',
            }}
            style={{ transformOrigin: `${node.x}px ${node.y}px` }}
          />
          <motion.circle
            cx={node.x} cy={node.y}
            r={node.size}
            fill="none"
            stroke={COLORS.gold}
            strokeWidth="0.15"
            animate={{
              scale: [1, 2, 1],
              opacity: [0.3, 0, 0.3],
            }}
            transition={{
              duration: 3 + (i % 3),
              repeat: Infinity,
              delay: i * 0.15,
              ease: 'easeOut',
            }}
            style={{ transformOrigin: `${node.x}px ${node.y}px` }}
          />
        </motion.g>
      ))}
    </svg>
  );
};

// ============================================================================
// SECURITY SHIELD
// ============================================================================

const SecurityShield: React.FC = () => {
  return (
    <svg className="w-full h-full" viewBox="0 0 200 200">
      <defs>
        <linearGradient id="shieldGradient" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor={COLORS.green} stopOpacity="0.5" />
          <stop offset="100%" stopColor={COLORS.green} stopOpacity="0.1" />
        </linearGradient>
        <filter id="shieldGlow">
          <feGaussianBlur stdDeviation="3" />
        </filter>
      </defs>

      {/* Outer defense rings */}
      {[90, 75, 60].map((r, i) => (
        <motion.circle
          key={i}
          cx="100" cy="100" r={r}
          fill="none"
          stroke={COLORS.green}
          strokeWidth="0.8"
          strokeDasharray={i === 0 ? '6 4' : i === 1 ? '10 6' : '3 5'}
          opacity={0.3 - i * 0.05}
          animate={{ rotate: i % 2 === 0 ? 360 : -360 }}
          transition={{ duration: 15 + i * 5, repeat: Infinity, ease: 'linear' }}
          style={{ transformOrigin: '100px 100px' }}
        />
      ))}

      {/* Radar sweep */}
      <motion.line
        x1="100" y1="100"
        x2="100" y2="30"
        stroke={COLORS.green}
        strokeWidth="1.5"
        opacity="0.5"
        filter="url(#shieldGlow)"
        animate={{ rotate: 360 }}
        transition={{ duration: 4, repeat: Infinity, ease: 'linear' }}
        style={{ transformOrigin: '100px 100px' }}
      />

      {/* Shield body */}
      <motion.path
        d="M100 30 L140 50 L140 100 Q140 150 100 175 Q60 150 60 100 L60 50 Z"
        fill="url(#shieldGradient)"
        stroke={COLORS.green}
        strokeWidth="2"
        animate={{ scale: [1, 1.02, 1] }}
        transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
        style={{ transformOrigin: '100px 100px' }}
      />

      {/* Inner check/star */}
      <motion.path
        d="M100 70 L105 85 L120 85 L108 95 L112 110 L100 100 L88 110 L92 95 L80 85 L95 85 Z"
        fill={COLORS.softGreen}
        filter="url(#shieldGlow)"
        animate={{ opacity: [0.6, 1, 0.6] }}
        transition={{ duration: 2, repeat: Infinity }}
      />

      {/* Threat particles being blocked */}
      {Array.from({ length: 6 }).map((_, i) => {
        const angle = (i * 60) * (Math.PI / 180);
        const startX = 100 + 120 * Math.cos(angle);
        const startY = 100 + 120 * Math.sin(angle);
        return (
          <motion.circle
            key={i}
            r="2"
            fill={COLORS.coral}
            initial={{ x: startX, y: startY, opacity: 1 }}
            animate={{
              x: [startX, 100 + 50 * Math.cos(angle), startX],
              y: [startY, 100 + 50 * Math.sin(angle), startY],
              opacity: [0.8, 0, 0.8],
            }}
            transition={{ duration: 3, repeat: Infinity, delay: i * 0.5 }}
          />
        );
      })}
    </svg>
  );
};

// ============================================================================
// PANEL WRAPPER (for entrance animation)
// ============================================================================

const AnimatedPanel: React.FC<{
  children: React.ReactNode;
  delay?: number;
  dark?: boolean;
  elevated?: boolean;
  className?: string;
}> = ({ children, delay = 0, dark = false, elevated = true, className = '' }) => (
  <motion.div
    className={`${elevated ? (dark ? 'dark-card-elevated' : 'light-card-elevated') : (dark ? 'dark-card' : 'light-card')} ${className}`}
    initial={{ opacity: 0, y: 16, scale: 0.98 }}
    animate={{ opacity: 1, y: 0, scale: 1 }}
    transition={{ duration: 0.6, delay, ease: [0.2, 0.8, 0.2, 1] }}
    whileHover={{ y: -3, transition: { duration: 0.3 } }}
  >
    {children}
  </motion.div>
);

// ============================================================================
// MAIN APP
// ============================================================================

interface QuantumEngineProps {
  api: SalarApi;
  onExitQuantum?: () => void;
}

const QuantumEngine: React.FC<QuantumEngineProps> = ({ api, onExitQuantum }) => {
  const [activeNav, setActiveNav] = useState('dashboard');
  const [coreState, setCoreState] = useState<CoreState>('idle');
  const [currentTime, setCurrentTime] = useState(new Date());
  const [commandInput, setCommandInput] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [responseText, setResponseText] = useState('');
  const [showResponse, setShowResponse] = useState(false);
  const [systemStatus, setSystemStatus] = useState<SystemStatus>({
    coreTemp: 41.2,
    quantumCores: { active: 32, total: 64 },
    memoryUsage: 67.4,
    cpuUsage: 38.6,
    gpuUsage: 44.8,
    uptime: '—',
  });
  const [liveRequests, setLiveRequests] = useState(12.48);
  const [latency, setLatency] = useState(23);
  const [liveAgents, setLiveAgents] = useState<Agent[]>(AGENTS);
  const [unreadCount, setUnreadCount] = useState(0);
  const [alertCount, setAlertCount] = useState(0);
  const [diskPct, setDiskPct] = useState(52);
  const [searchQuery, setSearchQuery] = useState('');
  const [activityPeriod, setActivityPeriod] = useState<'Day' | 'Week' | 'Month'>('Day');
  const [predictions, setPredictions] = useState<any[]>([]);
  const [knowledgeStats, setKnowledgeStats] = useState({ topics: 0, docs: 0, chunks: 0 });
  const conversationRef = useRef<{ id: string } | null>(null);
  const micRef = useRef<MediaRecorder | null>(null);
  const micChunksRef = useRef<Blob[]>([]);

  useEffect(() => {
    const interval = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const states: CoreState[] = ['idle', 'listening', 'thinking', 'planning', 'acting', 'verifying', 'complete'];
    let index = 0;
    const interval = setInterval(() => {
      if (!showResponse) setCoreState(states[index % states.length]);
      index++;
    }, 4000);
    return () => clearInterval(interval);
  }, [showResponse]);

  // Real-time backend telemetry
  useEffect(() => {
    const loadSystem = async () => {
      try {
        const [perf, snapshot, agents, unread, alerts, predictive, topics] = await Promise.allSettled([
          api.systemPerf(),
          api.monitorSnapshot(),
          api.swarmAgents(),
          api.notificationUnreadCount(),
          api.alertTriggered(10, true),
          api.predictiveNow(),
          api.knowledgeTopics(),
        ]);

        // Desktop: also pull live metrics from the local machine via Tauri
        if (isDesktop()) {
          const local = await getLiveMetrics();
          if (local) {
            setSystemStatus(prev => ({
              ...prev,
              cpuUsage: local.cpu_percent,
              memoryUsage: local.memory_percent,
              quantumCores: { active: local.cpu_count, total: local.cpu_count },
              uptime: formatUptime(local.uptime_seconds),
            }));
            if (local.disk_percent) setDiskPct(Math.round(local.disk_percent));
          }
        }

        if (perf.status === 'fulfilled') {
          const p = perf.value;
          if (p?.cpu && p?.memory) {
            const activeCores = p.cpu.cores ?? 32;
            setSystemStatus(prev => ({
              ...prev,
              cpuUsage: p.cpu.percent ?? prev.cpuUsage,
              memoryUsage: p.memory.percent ?? prev.memoryUsage,
              quantumCores: { active: Math.min(activeCores, 64), total: 64 },
              uptime: formatUptime(p.uptime_seconds),
            }));
            if (p.disk?.percent) setDiskPct(Math.round(p.disk.percent));
          }
        }
        if (snapshot.status === 'fulfilled' && snapshot.value) {
          const s = snapshot.value;
          setSystemStatus(prev => ({
            ...prev,
            cpuUsage: s.cpu?.percent ?? prev.cpuUsage,
            memoryUsage: s.memory?.percent ?? prev.memoryUsage,
            uptime: s.os?.uptime_seconds ? formatUptime(s.os.uptime_seconds) : prev.uptime,
          }));
        }
        if (agents.status === 'fulfilled' && agents.value?.agents?.length) {
          setLiveAgents(agents.value.agents.slice(0, 6).map((a: any, i: number) => ({
            id: a.name,
            name: a.name,
            role: a.description || a.purpose || 'AI Agent',
            status: (i % 3 === 1 ? 'busy' : i % 4 === 3 ? 'idle' : 'active') as Agent['status'],
            avatar: (a.name || 'A')[0],
          })));
        }
        if (unread.status === 'fulfilled' && unread.value?.unread_count) setUnreadCount(unread.value.unread_count);
        if (alerts.status === 'fulfilled' && alerts.value?.alerts?.length) setAlertCount(alerts.value.alerts.length);
        if (predictive.status === 'fulfilled' && predictive.value?.suggestions?.length) {
          setPredictions(predictive.value.suggestions.slice(0, 4));
        }
        if (topics.status === 'fulfilled' && topics.value?.clusters) {
          setKnowledgeStats(prev => ({ ...prev, topics: topics.value.clusters.length ?? 0 }));
        }
      } catch {
        /* keep defaults */
      }
    };
    loadSystem();
    const timer = setInterval(loadSystem, 10000);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api]);

  useEffect(() => {
    const timer = setInterval(() => {
      setLiveRequests(prev => Math.max(5, prev + (Math.random() - 0.3) * 0.05));
      setLatency(prev => Math.max(15, Math.min(35, prev + (Math.random() - 0.5) * 3)));
    }, 3000);
    return () => clearInterval(timer);
  }, []);

  const handleSendCommand = useCallback(async () => {
    if (!commandInput.trim()) return;
    const input = commandInput.trim();
    setShowResponse(true);
    setResponseText('Analyzing your request…');
    setCoreState('thinking');
    setCommandInput('');
    try {
      if (!conversationRef.current) {
        const convs = await api.conversations();
        conversationRef.current = convs[0] || (await api.createConversation());
      }
      let buf = '';
      setCoreState('acting');
      await api.chatStream(
        conversationRef.current.id,
        input,
        (token) => {
          buf += token;
          setResponseText(buf);
        },
        () => {
          setCoreState('complete');
          setTimeout(() => {
            setCoreState('idle');
            setShowResponse(false);
          }, 4000);
        },
        (err) => {
          setResponseText(`Command failed: ${err.message}`);
          setCoreState('error');
          setTimeout(() => {
            setCoreState('idle');
            setShowResponse(false);
          }, 4000);
        },
      );
    } catch (e: any) {
      setResponseText(`Command failed: ${e?.message || 'network error'}`);
      setCoreState('error');
      setTimeout(() => {
        setCoreState('idle');
        setShowResponse(false);
      }, 4000);
    }
  }, [commandInput, api]);

  const handleQuickAction = useCallback(async (action: string) => {
    setShowResponse(true);
    setCoreState('thinking');
    setResponseText('Executing…');
    try {
      let message = '';
      switch (action) {
        case 'New Analysis':
          await api.coreRun('Analyze current system state and knowledge', 'analysis');
          message = 'Analysis task dispatched to the agent core.';
          break;
        case 'Deep Research': {
          const docs = await api.knowledgeDocs();
          message = `Research ready. ${docs.length} documents indexed across the knowledge base.`;
          break;
        }
        case 'Optimize System': {
          const procs = await api.monitorProcesses();
          const top = procs.processes.slice(0, 3).map(p => p.name).join(', ') || 'none';
          message = `Optimization survey complete. Top consumers: ${top}.`;
          break;
        }
        case 'Generate Report': {
          const [stats, missions] = await Promise.allSettled([api.taskStats(), api.missions()]);
          const s = stats.status === 'fulfilled' ? stats.value : {};
          const m = missions.status === 'fulfilled' ? missions.value : [];
          message = `Report compiled: ${s.total ?? 0} tasks, ${s.active ?? 0} active, ${m.length} missions.`;
          break;
        }
        case 'Security Scan': {
          const scan = await api.privacyScan();
          message = `Security scan complete. ${scan?.findings?.length ?? scan?.total ?? 0} findings reviewed.`;
          break;
        }
        case 'Clear Memory': {
          const mem = await api.memories();
          message = `Memory audit done. ${mem.length} long-term memories retained.`;
          break;
        }
        default:
          message = 'Action complete.';
      }
      setResponseText(message);
      setCoreState('complete');
    } catch (e: any) {
      setResponseText(`Action failed: ${e?.message || 'network error'}`);
      setCoreState('error');
    }
    setTimeout(() => {
      setCoreState('idle');
      setShowResponse(false);
    }, 4000);
  }, [api]);

  const toggleMic = useCallback(() => {
    if (isListening) {
      micRef.current?.stop();
      setIsListening(false);
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      setShowResponse(true);
      setResponseText('Microphone access is not supported in this browser.');
      return;
    }
    navigator.mediaDevices
      .getUserMedia({ audio: true })
      .then(async (stream) => {
        const recorder = new MediaRecorder(stream);
        micChunksRef.current = [];
        recorder.ondataavailable = (e) => { if (e.data.size > 0) micChunksRef.current.push(e.data); };
        recorder.onstop = async () => {
          stream.getTracks().forEach(t => t.stop());
          const blob = new Blob(micChunksRef.current, { type: 'audio/webm' });
          if (blob.size === 0) return;
          try {
            const text = await api.stt(blob);
            if (text?.trim()) {
              setCommandInput(text.trim());
              setShowResponse(true);
              setResponseText(`Heard: "${text.trim()}"`);
            }
          } catch (e: any) {
            setShowResponse(true);
            setResponseText(`Voice capture failed: ${e?.message || 'STT error'}`);
          }
        };
        recorder.start();
        micRef.current = recorder;
        setIsListening(true);
      })
      .catch(() => {
        setShowResponse(true);
        setResponseText('Microphone access was denied.');
      });
  }, [isListening, api]);

  const runSearch = useCallback(async () => {
    if (!searchQuery.trim()) return;
    try {
      const results = await api.searchKnowledge(searchQuery, 5);
      const items = results?.results ?? results ?? [];
      const text = Array.isArray(items)
        ? items.map((r: any) => `• ${r.title || r.filename || 'Result'}`).join('\n')
        : 'No results found.';
      setResponseText(`Search: ${searchQuery}\n${text}`);
      setShowResponse(true);
    } catch (e: any) {
      setResponseText(`Search failed: ${e?.message || 'network error'}`);
      setShowResponse(true);
    }
  }, [searchQuery, api]);

  const formatUptime = (secs: number) => {
    if (!secs) return '—';
    const d = Math.floor(secs / 86400);
    const h = Math.floor((secs % 86400) / 3600);
    const m = Math.floor((secs % 3600) / 60);
    return `${d}D ${h}H ${m}M`;
  };

  const formatTime = (date: Date) =>
    date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true });

  const formatDate = (date: Date) =>
    date.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' });

  const predictionData = predictions.length > 0
    ? predictions.map((p: any, i: number) => ({
        name: p.title || p.name || `Prediction ${i + 1}`,
        value: typeof p.confidence === 'number' ? p.confidence : Math.max(80, 96 - i * 2),
      }))
    : [
        { name: 'NLP Understanding', value: 94.1 },
        { name: 'Reasoning', value: 93.6 },
        { name: 'Forecasting', value: 93.2 },
        { name: 'Anomaly Detection', value: 91.8 },
        { name: 'General Knowledge', value: 95.9 },
      ];

  const resourceData = [
    { name: 'CPU', value: Math.round(systemStatus.cpuUsage), fill: COLORS.gold },
    { name: 'GPU', value: Math.round(systemStatus.gpuUsage), fill: COLORS.champagne },
    { name: 'Memory', value: Math.round(systemStatus.memoryUsage), fill: COLORS.paleGold },
    { name: 'Disk', value: diskPct, fill: COLORS.softGreen },
  ];

  const activityData = Array.from({ length: 24 }, (_, i) => ({
    time: `${i}:00`,
    requests: Math.floor(800 + Math.random() * 400 + Math.sin(i / 3) * 200),
    latency: Math.floor(15 + Math.random() * 15),
  }));

  const topPredictions = predictions.length > 0
    ? predictions.map((p: any) => ({
        label: p.title || p.name || 'Prediction',
        value: typeof p.confidence === 'number' ? Math.round(p.confidence) : 90,
      }))
    : [
        { label: 'Market Trend (Q3)', value: 94 },
        { label: 'User Growth', value: 92 },
        { label: 'System Load', value: 90 },
        { label: 'Security Risk', value: 87 },
      ];

  const riskLevel = alertCount === 0 ? 'LOW' : alertCount < 4 ? 'MEDIUM' : 'HIGH';
  const riskColor = alertCount === 0 ? COLORS.green : alertCount < 4 ? COLORS.amber : COLORS.coral;

  return (
    <div className="h-screen w-screen overflow-hidden flex relative" style={{ background: 'var(--quantum-ivory)' }}>
      {/* Ambient animated background */}
      <AmbientBackground />

      {/* ==========================================================================
          LEFT SIDEBAR
      ========================================================================== */}
      <motion.aside
        className="w-[250px] flex flex-col border-r relative z-10"
        style={{
          background: 'rgba(245, 240, 233, 0.75)',
          backdropFilter: 'blur(24px)',
          borderColor: 'rgba(60, 50, 40, 0.07)',
        }}
        initial={{ x: -20, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        transition={{ duration: 0.6, ease: [0.2, 0.8, 0.2, 1] }}
      >
        {/* Logo */}
        <div className="p-5 pb-4">
          <div className="flex items-center gap-3 mb-1">
            <motion.div
              className="relative w-12 h-12"
              animate={{ rotate: 360 }}
              transition={{ duration: 25, repeat: Infinity, ease: 'linear' }}
            >
              <svg viewBox="0 0 48 48" className="w-full h-full">
                <circle cx="24" cy="24" r="22" fill="none" stroke={COLORS.gold} strokeWidth="1.5" opacity="0.3" />
                <motion.circle
                  cx="24" cy="24" r="18"
                  fill="none" stroke={COLORS.gold} strokeWidth="1" strokeDasharray="4 2"
                  animate={{ rotate: -360 }}
                  transition={{ duration: 15, repeat: Infinity, ease: 'linear' }}
                  style={{ transformOrigin: '24px 24px' }}
                />
                <circle cx="24" cy="24" r="12" fill={COLORS.gold} opacity="0.9" />
                <motion.circle
                  cx="24" cy="24" r="12"
                  fill={COLORS.goldHighlight} opacity="0.5"
                  animate={{ scale: [1, 1.1, 1] }}
                  transition={{ duration: 2, repeat: Infinity }}
                  style={{ transformOrigin: '24px 24px' }}
                />
                <text x="24" y="28" textAnchor="middle" fill="#141414" fontSize="14" fontWeight="700">S</text>
              </svg>
            </motion.div>
            <div>
              <h1 className="text-lg font-bold" style={{ color: 'var(--text-main)' }}>SALAAR</h1>
              <p className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
                Quantum Engine
              </p>
            </div>
          </div>
          <div className="mt-2 flex items-center gap-2">
            <motion.span
              className="px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider"
              style={{
                background: `linear-gradient(135deg, ${COLORS.gold}, ${COLORS.champagne})`,
                color: '#141414',
              }}
              animate={{ boxShadow: ['0 0 0 rgba(201,165,110,0)', '0 0 12px rgba(201,165,110,0.5)', '0 0 0 rgba(201,165,110,0)'] }}
              transition={{ duration: 2.5, repeat: Infinity }}
            >
              ENGINE MODE
            </motion.span>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {NAV_ITEMS.map((item, idx) => {
            const Icon = item.icon;
            const isActive = activeNav === item.id;
            return (
              <motion.button
                key={item.id}
                onClick={() => setActiveNav(item.id)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all ${
                  isActive
                    ? 'nav-active'
                    : 'hover:bg-white/50'
                }`}
                style={{
                  color: isActive ? '#141414' : 'var(--text-secondary)',
                }}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.4, delay: 0.1 + idx * 0.04 }}
                whileHover={{ x: isActive ? 0 : 4 }}
                whileTap={{ scale: 0.98 }}
              >
                <Icon className={`w-4 h-4 ${isActive ? 'text-black' : ''}`} />
                <span>{item.label}</span>
                {isActive && (
                  <motion.div
                    className="ml-auto"
                    initial={{ opacity: 0, scale: 0 }}
                    animate={{ opacity: 1, scale: 1 }}
                  >
                    <ArrowUpRight className="w-3 h-3" />
                  </motion.div>
                )}
              </motion.button>
            );
          })}
        </nav>

        {/* System Status — desktop only, wired to local PC via Tauri */}
        {isDesktop() && (
        <div className="p-4 border-t" style={{ borderColor: 'rgba(60, 50, 40, 0.07)' }}>
          <div className="mb-3">
            <h3 className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: 'var(--text-muted)' }}>
              System Status
            </h3>
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold" style={{ color: 'var(--text-main)' }}>OPTIMAL</span>
              <StatusDot status="pulse-green" />
            </div>
          </div>

          <div className="space-y-2 text-xs">
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2" style={{ color: 'var(--text-secondary)' }}>
                <Cpu className="w-3 h-3" />
                Cores
              </span>
              <span className="font-semibold" style={{ color: 'var(--text-main)' }}>
                {systemStatus.quantumCores.active}/{systemStatus.quantumCores.total}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2" style={{ color: 'var(--text-secondary)' }}>
                <Database className="w-3 h-3" />
                Memory
              </span>
              <span className="font-semibold tabular-nums" style={{ color: 'var(--text-main)' }}>
                {systemStatus.memoryUsage.toFixed(1)}%
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2" style={{ color: 'var(--text-secondary)' }}>
                <Activity className="w-3 h-3" />
                CPU
              </span>
              <span className="font-semibold tabular-nums" style={{ color: 'var(--text-main)' }}>
                {systemStatus.cpuUsage.toFixed(0)}%
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2" style={{ color: 'var(--text-secondary)' }}>
                <Clock className="w-3 h-3" />
                Uptime
              </span>
              <span className="font-semibold" style={{ color: 'var(--text-main)' }}>{systemStatus.uptime}</span>
            </div>
          </div>
        </div>
        )}

      </motion.aside>

      {/* ==========================================================================
          MAIN CONTENT AREA
      ========================================================================== */}
      <main className="flex-1 flex flex-col overflow-hidden relative z-10">
        {/* Top Bar */}
        <motion.header
          className="h-16 flex items-center justify-between px-6 border-b relative"
          style={{
            background: 'rgba(250, 248, 244, 0.85)',
            backdropFilter: 'blur(24px)',
            borderColor: 'rgba(110, 96, 80, 0.08)',
          }}
          initial={{ y: -20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ duration: 0.5, delay: 0.2 }}
        >
          <div>
            <h2 className="text-xl font-bold flex items-center gap-2" style={{ color: 'var(--text-main)' }}>
              <Sparkles className="w-4 h-4" style={{ color: COLORS.gold }} />
              SALAAR
              <span className="font-normal gradient-text-animated" style={{ color: 'var(--text-main)' }}>— QUANTUM ENGINE</span>
            </h2>
            <p className="text-[10px] uppercase tracking-wider font-medium" style={{ color: 'var(--text-muted)' }}>
              AI Command & Control Center
            </p>
          </div>

          <div className="flex items-center gap-5">
            <div className="flex items-center gap-4">
              <div className="flex flex-col items-end">
                <span className="text-[9px] uppercase tracking-wider font-semibold" style={{ color: 'var(--text-muted)' }}>
                  AI MODE
                </span>
                <motion.span
                  className="text-xs font-bold flex items-center gap-1.5"
                  style={{ color: COLORS.gold }}
                  animate={{ opacity: [0.8, 1, 0.8] }}
                  transition={{ duration: 2, repeat: Infinity }}
                >
                  <span className="w-1.5 h-1.5 rounded-full" style={{ background: COLORS.gold }} />
                  QUANTUM MODE
                </motion.span>
              </div>
              <div className="w-px h-8" style={{ background: 'rgba(110, 96, 80, 0.15)' }} />
              <div className="flex flex-col items-end">
                <span className="text-[9px] uppercase tracking-wider font-semibold" style={{ color: 'var(--text-muted)' }}>
                  QUANTUM STATE
                </span>
                <span className="text-xs font-bold flex items-center gap-1.5" style={{ color: COLORS.green }}>
                  <StatusDot status="pulse-green" size={6} />
                  STABLE
                </span>
              </div>
              <div className="w-px h-8" style={{ background: 'rgba(110, 96, 80, 0.15)' }} />
              <div className="flex flex-col items-end">
                <span className="text-[9px] uppercase tracking-wider font-semibold" style={{ color: 'var(--text-muted)' }}>
                  SYSTEM UPTIME
                </span>
                <span className="text-xs font-bold tabular-nums" style={{ color: 'var(--text-main)' }}>
                  {systemStatus.uptime}
                </span>
              </div>
            </div>

            <div className="w-px h-8" style={{ background: 'rgba(110, 96, 80, 0.15)' }} />

            <div className="text-right">
              <motion.p
                key={currentTime.toISOString()}
                className="text-sm font-bold tabular-nums"
                style={{ color: 'var(--text-main)' }}
                initial={{ opacity: 0.7, y: 2 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3 }}
              >
                {formatTime(currentTime)}
              </motion.p>
              <p className="text-[10px] font-medium" style={{ color: 'var(--text-muted)' }}>{formatDate(currentTime)}</p>
            </div>

            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4" style={{ color: 'var(--text-muted)' }} />
              <motion.input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') runSearch(); }}
                placeholder="Search command or ask SALAAR..."
                className="input-quantum pl-10 pr-4 py-2 w-72 text-sm"
                style={{ background: 'rgba(255, 255, 255, 0.6)' }}
                whileFocus={{ width: 320 }}
                transition={{ duration: 0.3 }}
              />
            </div>

            <div className="flex items-center gap-2">
              <motion.button
                className="p-2 rounded-xl relative"
                style={{ background: 'rgba(201, 165, 110, 0.1)' }}
                whileHover={{ scale: 1.05, background: 'rgba(201, 165, 110, 0.2)' }}
                whileTap={{ scale: 0.95 }}
                onClick={async () => {
                  try {
                    const perf = await api.systemPerf();
                    setResponseText(
                      `System: CPU ${perf.cpu?.percent ?? '—'}% · Mem ${perf.memory?.percent ?? '—'}% · Disk ${perf.disk?.percent ?? '—'}% · Uptime ${formatUptime(perf.uptime_seconds ?? 0)}`,
                    );
                  } catch (e: any) {
                    setResponseText(`Could not reach system telemetry: ${e?.message || 'network error'}`);
                  }
                  setShowResponse(true);
                  setTimeout(() => setShowResponse(false), 5000);
                }}
              >
                <Activity className="w-4 h-4" style={{ color: COLORS.gold }} />
              </motion.button>
              <motion.button
                className="p-2 rounded-xl relative"
                style={{ background: 'rgba(201, 165, 110, 0.1)' }}
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={async () => {
                  try {
                    const unread = await api.notificationUnreadCount();
                    setResponseText(
                      unread.unread_count > 0 ? `You have ${unread.unread_count} unread notification${unread.unread_count === 1 ? '' : 's'}.` : 'You are all caught up.',
                    );
                    setUnreadCount(0);
                  } catch (e: any) {
                    setResponseText(`Could not fetch notifications: ${e?.message || 'network error'}`);
                  }
                  setShowResponse(true);
                  setTimeout(() => setShowResponse(false), 5000);
                }}
              >
                <Bell className="w-4 h-4" style={{ color: 'var(--text-secondary)' }} />
                {unreadCount > 0 && (
                  <motion.span
                    className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full"
                    style={{ background: COLORS.coral }}
                    animate={{ scale: [1, 1.5, 1] }}
                    transition={{ duration: 1.5, repeat: Infinity }}
                  />
                )}
              </motion.button>
              <motion.button
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-[10px] font-bold uppercase tracking-wider"
                style={{ background: 'rgba(185, 87, 80, 0.1)', color: COLORS.coral, border: `1px solid ${COLORS.coral}30` }}
                whileHover={{ scale: 1.05, background: 'rgba(185, 87, 80, 0.2)' }}
                whileTap={{ scale: 0.95 }}
                onClick={() => onExitQuantum?.()}
                title="Exit Quantum"
              >
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
                EXIT
              </motion.button>
            </div>
          </div>
        </motion.header>

        {/* Dashboard Content — ThinkingSkull only */}
        <div className="flex-1 flex items-center justify-center relative overflow-hidden">
          <motion.div
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.8, ease: [0.2, 0.8, 0.2, 1] }}
          >
            <ThinkingSkull
              state={
                showResponse || ['thinking', 'planning', 'acting', 'verifying'].includes(coreState)
                  ? 'generating'
                  : commandInput.trim()
                  ? 'typing'
                  : isListening
                  ? 'typing'
                  : 'idle'
              }
              size={220}
            />
          </motion.div>

          {/* Subtle status text below skull */}
          <motion.div
            className="absolute bottom-8 left-1/2 -translate-x-1/2 text-center"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5 }}
          >
            <p className="text-xs font-semibold uppercase tracking-[0.2em]" style={{ color: 'var(--text-muted)' }}>
              {showResponse || ['thinking', 'planning', 'acting', 'verifying'].includes(coreState)
                ? 'Processing'
                : commandInput.trim()
                ? 'Ready'
                : isListening
                ? 'Listening'
                : 'SALAAR Quantum Engine'}
            </p>
          </motion.div>
        </div>

        {/* Non-dashboard nav panels */}
        {activeNav !== 'dashboard' && (
        <div className="flex-1 overflow-y-auto p-6">
          <div className="grid grid-cols-12 gap-5">
            {activeNav === 'intelligence' && (<>
            <AnimatedPanel delay={0.1} dark className="col-span-4 p-5 relative overflow-hidden">
              <motion.div className="absolute inset-0" style={{ background: `radial-gradient(circle at 50% 50%, ${COLORS.gold}20 0%, transparent 70%)` }} animate={{ opacity: [0.4, 0.7, 0.4] }} transition={{ duration: 3, repeat: Infinity }} />
              <div className="flex items-center justify-between mb-3 relative z-10">
                <div>
                  <h3 className="text-sm font-bold" style={{ color: 'var(--dark-primary-text)' }}>SALAAR QUANTUM CORE</h3>
                  <p className="text-[10px] uppercase tracking-wider font-semibold" style={{ color: 'var(--dark-secondary-text)' }}>Quantum Compute Engine</p>
                </div>
                <motion.div className="flex items-center gap-2 px-3 py-1 rounded-full" style={{ background: `${COLORS.green}20` }} animate={{ boxShadow: ['0 0 0 rgba(47,110,89,0)', '0 0 16px rgba(47,110,89,0.4)', '0 0 0 rgba(47,110,89,0)'] }} transition={{ duration: 2.5, repeat: Infinity }}>
                  <StatusDot status="pulse-green" size={6} />
                  <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: COLORS.green }}>ACTIVE</span>
                </motion.div>
              </div>
              <div className="grid grid-cols-2 gap-3 mb-3 relative z-10">
                {[{ label: 'Thinking Depth', value: '8.6', suffix: '/10', accent: COLORS.gold }, { label: 'Context Window', value: '128', suffix: 'K', accent: COLORS.champagne }, { label: 'Learning Rate', value: '0.091', suffix: '', accent: COLORS.paleGold }, { label: 'Model Efficiency', value: '94.7', suffix: '%', accent: COLORS.softGreen }].map((item, i) => (
                  <motion.div key={i} className="p-3 rounded-xl relative overflow-hidden" style={{ background: 'rgba(255, 255, 255, 0.05)' }} whileHover={{ background: 'rgba(255, 255, 255, 0.08)' }}>
                    <p className="text-[9px] uppercase tracking-wider mb-1" style={{ color: 'var(--dark-secondary-text)' }}>{item.label}</p>
                    <p className="text-lg font-bold flex items-baseline gap-1" style={{ color: 'var(--dark-primary-text)' }}>{item.value}<span className="text-xs font-medium" style={{ color: item.accent }}>{item.suffix}</span></p>
                    <motion.div className="absolute bottom-0 left-0 h-[1.5px]" style={{ background: item.accent }} initial={{ width: 0 }} animate={{ width: '100%' }} transition={{ duration: 1.5, delay: 0.5 + i * 0.1 }} />
                  </motion.div>
                ))}
              </div>
              <div className="h-56 relative z-10"><EnhancedQuantumCore state={coreState} /></div>
              <div className="grid grid-cols-4 gap-2 mt-3 relative z-10">
                {[{ label: 'Processing', value: '2.48 PFLOPS' }, { label: 'Response', value: '18 ms' }, { label: 'Active Agents', value: '16' }, { label: 'Tasks Queued', value: '7' }].map((item, i) => (
                  <motion.div key={i} className="text-center p-2.5 rounded-xl relative overflow-hidden" style={{ background: 'rgba(255, 255, 255, 0.04)' }} whileHover={{ background: 'rgba(255, 255, 255, 0.07)' }} initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.5 + i * 0.08 }}>
                    <p className="text-[8px] uppercase tracking-wider mb-1" style={{ color: 'var(--dark-secondary-text)' }}>{item.label}</p>
                    <p className="text-xs font-bold" style={{ color: 'var(--dark-primary-text)' }}>{item.value}</p>
                  </motion.div>
                ))}
              </div>
            </AnimatedPanel>
            <AnimatedPanel delay={0.15} className="col-span-4 p-5">
              <div className="mb-4">
                <h3 className="text-sm font-bold" style={{ color: 'var(--text-main)' }}>PREDICTION ACCURACY</h3>
                <p className="text-[10px] uppercase tracking-wider font-semibold" style={{ color: 'var(--text-muted)' }}>Model Performance</p>
              </div>
              <div className="flex items-center gap-6 mb-5">
                <div className="relative w-32 h-32">
                  <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
                    <circle cx="50" cy="50" r="42" fill="none" stroke="rgba(201, 165, 110, 0.15)" strokeWidth="8" />
                    <motion.circle cx="50" cy="50" r="42" fill="none" stroke={COLORS.gold} strokeWidth="8" strokeDasharray="264" initial={{ strokeDashoffset: 264 }} animate={{ strokeDashoffset: 264 - (264 * 93.8) / 100 }} transition={{ duration: 2, ease: 'easeOut', delay: 0.3 }} strokeLinecap="round" />
                  </svg>
                  <motion.div className="absolute inset-0 flex items-center justify-center" initial={{ scale: 0.8, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ duration: 0.5, delay: 0.8 }}>
                    <div className="text-center">
                      <motion.p className="text-3xl font-bold tabular-nums" style={{ color: 'var(--text-main)' }} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 1, delay: 0.5 }}>93.8%</motion.p>
                      <p className="text-[9px] uppercase tracking-wider font-semibold" style={{ color: 'var(--text-muted)' }}>Accuracy</p>
                    </div>
                  </motion.div>
                </div>
                <div className="flex-1 space-y-2.5">
                  {predictionData.map((item, i) => (
                    <motion.div key={i} className="flex items-center justify-between" initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.4, delay: 0.3 + i * 0.08 }}>
                      <div className="flex items-center gap-2">
                        <motion.span className="w-2 h-2 rounded-full" style={{ background: COLORS.gold }} animate={{ scale: [1, 1.3, 1] }} transition={{ duration: 2, repeat: Infinity, delay: i * 0.2 }} />
                        <span className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>{item.name}</span>
                      </div>
                      <motion.span className="text-sm font-bold tabular-nums" style={{ color: 'var(--text-main)' }} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.5 + i * 0.08 }}>{item.value}%</motion.span>
                    </motion.div>
                  ))}
                </div>
              </div>
              <motion.div className="p-4 rounded-xl relative overflow-hidden" style={{ background: 'var(--quantum-black)' }}>
                <h4 className="text-xs font-bold mb-3" style={{ color: 'var(--dark-primary-text)' }}>TOP PREDICTIONS</h4>
                <div className="space-y-3">
                  {topPredictions.map((pred, i) => (
                    <motion.div key={i} initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.5 + i * 0.1 }}>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-[11px]" style={{ color: 'var(--dark-secondary-text)' }}>{pred.label}</span>
                        <span className="text-xs font-bold tabular-nums" style={{ color: COLORS.gold }}>{pred.value}%</span>
                      </div>
                      <div className="progress-bar h-1.5"><motion.div className="progress-fill h-full" initial={{ width: 0 }} animate={{ width: `${pred.value}%` }} transition={{ duration: 1.2, delay: 0.6 + i * 0.12, ease: 'easeOut' }} /></div>
                    </motion.div>
                  ))}
                </div>
              </motion.div>
            </AnimatedPanel>
            <AnimatedPanel delay={0.2} dark className="col-span-4 p-5">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-sm font-bold" style={{ color: 'var(--dark-primary-text)' }}>KNOWLEDGE GRAPH</h3>
                  <p className="text-[10px] uppercase tracking-wider font-semibold" style={{ color: 'var(--dark-secondary-text)' }}>Connections & Entities</p>
                </div>
                <motion.div animate={{ rotate: 360 }} transition={{ duration: 8, repeat: Infinity, ease: 'linear' }}><Network className="w-4 h-4" style={{ color: COLORS.gold }} /></motion.div>
              </div>
              <div className="h-40 mb-4"><KnowledgeGraph /></div>
              <div className="grid grid-cols-3 gap-3">
                {[{ label: 'Entities', value: '24,531' }, { label: 'Relationships', value: '98,213' }, { label: 'Data Points', value: '3.42 PB' }].map((item, i) => (
                  <motion.div key={i} className="text-center" initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.7 + i * 0.1 }}>
                    <motion.p className="text-lg font-bold tabular-nums" style={{ color: 'var(--dark-primary-text)' }} animate={{ textShadow: ['0 0 0 rgba(201,165,110,0)', '0 0 8px rgba(201,165,110,0.4)', '0 0 0 rgba(201,165,110,0)'] }} transition={{ duration: 3, repeat: Infinity, delay: i * 0.5 }}>{item.value}</motion.p>
                    <p className="text-[9px] uppercase tracking-wider font-semibold" style={{ color: 'var(--dark-secondary-text)' }}>{item.label}</p>
                  </motion.div>
                ))}
              </div>
            </AnimatedPanel>
            </>)}

            {activeNav === 'agents' && (
            <AnimatedPanel delay={0.25} dark className="col-span-12 p-5">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-sm font-bold" style={{ color: 'var(--dark-primary-text)' }}>AGENT NETWORK</h3>
                  <p className="text-[10px] uppercase tracking-wider font-semibold" style={{ color: 'var(--dark-secondary-text)' }}>AI Agents Ecosystem</p>
                </div>
                <Users className="w-4 h-4" style={{ color: 'var(--dark-secondary-text)' }} />
              </div>
              <div className="h-64"><AgentNetwork agents={liveAgents} /></div>
              <div className="flex items-center justify-center gap-2 mt-3">
                <StatusDot status="pulse-green" size={6} />
                <motion.span className="text-xs font-bold uppercase tracking-wider" style={{ color: COLORS.green }} animate={{ opacity: [0.7, 1, 0.7] }} transition={{ duration: 2, repeat: Infinity }}>{liveAgents.length} AGENTS ONLINE</motion.span>
              </div>
            </AnimatedPanel>
            )}

            {activeNav === 'missions' && (
            <AnimatedPanel delay={0.4} dark className="col-span-12 p-5">
              <div className="mb-4">
                <h3 className="text-sm font-bold" style={{ color: 'var(--dark-primary-text)' }}>QUICK ACTIONS</h3>
                <p className="text-[10px] uppercase tracking-wider font-semibold" style={{ color: 'var(--dark-secondary-text)' }}>Execute Commands</p>
              </div>
              <div className="grid grid-cols-6 gap-3">
                {[
                  { icon: Brain, label: 'New Analysis', color: COLORS.gold },
                  { icon: Search, label: 'Deep Research', color: COLORS.champagne },
                  { icon: Settings, label: 'Optimize System', color: COLORS.green },
                  { icon: Database, label: 'Generate Report', color: COLORS.paleGold },
                  { icon: Shield, label: 'Security Scan', color: COLORS.softGreen },
                  { icon: RefreshCw, label: 'Clear Memory', color: COLORS.amber },
                ].map((action, i) => (
                  <motion.button key={i} className="p-4 rounded-xl flex flex-col items-center gap-2 relative overflow-hidden" style={{ background: 'rgba(255, 255, 255, 0.04)' }} initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.6 + i * 0.06, type: 'spring' }} whileHover={{ background: 'rgba(255, 255, 255, 0.08)', scale: 1.03 }} whileTap={{ scale: 0.95 }} onClick={() => handleQuickAction(action.label)}>
                    <motion.div animate={{ y: [0, -2, 0] }} transition={{ duration: 2, repeat: Infinity, delay: i * 0.2 }}><action.icon className="w-5 h-5" style={{ color: action.color }} /></motion.div>
                    <span className="text-[10px] font-semibold" style={{ color: 'var(--dark-secondary-text)' }}>{action.label}</span>
                  </motion.button>
                ))}
              </div>
            </AnimatedPanel>
            )}

            {activeNav === 'security' && (
            <AnimatedPanel delay={0.35} dark className="col-span-12 p-5">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-sm font-bold" style={{ color: 'var(--dark-primary-text)' }}>SECURITY CENTER</h3>
                  <p className="text-[10px] uppercase tracking-wider font-semibold" style={{ color: 'var(--dark-secondary-text)' }}>Threat Monitoring</p>
                </div>
                <motion.div animate={{ rotate: [0, 10, 0, -10, 0] }} transition={{ duration: 4, repeat: Infinity }}><Shield className="w-4 h-4" style={{ color: COLORS.green }} /></motion.div>
              </div>
              <div className="flex items-center gap-8 mb-6">
                <motion.div className="w-32 h-32 flex-shrink-0" initial={{ scale: 0.8, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ delay: 0.5, type: 'spring' }}><SecurityShield /></motion.div>
                <div className="flex-1 grid grid-cols-3 gap-6">
                  <div><p className="text-[9px] uppercase tracking-wider mb-1 font-semibold" style={{ color: 'var(--dark-secondary-text)' }}>Threats Blocked</p><p className="text-3xl font-bold tabular-nums" style={{ color: 'var(--dark-primary-text)' }}>7,842</p></div>
                  <div><p className="text-[9px] uppercase tracking-wider mb-1 font-semibold" style={{ color: 'var(--dark-secondary-text)' }}>Intrusion Attempts</p><p className="text-3xl font-bold" style={{ color: 'var(--dark-primary-text)' }}>{Math.max(alertCount, 1)}</p></div>
                  <div><p className="text-[9px] uppercase tracking-wider mb-1 font-semibold" style={{ color: 'var(--dark-secondary-text)' }}>Risk Level</p><motion.p className="text-3xl font-bold" style={{ color: riskColor }} animate={{ textShadow: [`0 0 0 ${riskColor}00`, `0 0 10px ${riskColor}80`, `0 0 0 ${riskColor}00`] }} transition={{ duration: 2.5, repeat: Infinity }}>{riskLevel}</motion.p></div>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-3">
                {[
                  { label: 'Firewall', value: 'ACTIVE', color: COLORS.green, bg: 'rgba(47, 110, 89, 0.15)' },
                  { label: 'Encryption', value: 'AES-256', color: COLORS.gold, bg: 'rgba(201, 165, 110, 0.15)' },
                  { label: 'Protection', value: '100%', color: COLORS.green, bg: 'rgba(47, 110, 89, 0.15)' },
                ].map((item, i) => (
                  <motion.div key={i} className="p-4 rounded-xl text-center relative overflow-hidden" style={{ background: item.bg }} initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.8 + i * 0.1 }} whileHover={{ scale: 1.03 }}>
                    <p className="text-[9px] uppercase tracking-wider mb-1 font-semibold" style={{ color: item.color }}>{item.label}</p>
                    <p className="text-sm font-bold" style={{ color: item.color }}>{item.value}</p>
                  </motion.div>
                ))}
              </div>
            </AnimatedPanel>
            )}

            {activeNav === 'system' && (<>
            <AnimatedPanel delay={0.3} dark className="col-span-6 p-5">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-sm font-bold" style={{ color: 'var(--dark-primary-text)' }}>RESOURCE MONITOR</h3>
                  <p className="text-[10px] uppercase tracking-wider font-semibold" style={{ color: 'var(--dark-secondary-text)' }}>Real-time Usage</p>
                </div>
                <Server className="w-4 h-4" style={{ color: 'var(--dark-secondary-text)' }} />
              </div>
              <div className="grid grid-cols-4 gap-3 mb-4">
                {resourceData.map((resource, i) => (
                  <motion.div key={i} className="text-center" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.5 + i * 0.1 }}>
                    <div className="relative w-14 h-14 mx-auto mb-2">
                      <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
                        <circle cx="50" cy="50" r="42" fill="none" stroke="rgba(255, 255, 255, 0.1)" strokeWidth="8" />
                        <motion.circle cx="50" cy="50" r="42" fill="none" stroke={resource.fill} strokeWidth="8" strokeDasharray="264" initial={{ strokeDashoffset: 264 }} animate={{ strokeDashoffset: 264 - (264 * resource.value) / 100 }} transition={{ duration: 1.5, delay: 0.6 + i * 0.1, ease: 'easeOut' }} strokeLinecap="round" />
                      </svg>
                      <div className="absolute inset-0 flex items-center justify-center">
                        <motion.span className="text-sm font-bold tabular-nums" style={{ color: 'var(--dark-primary-text)' }} initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ delay: 1.2 + i * 0.1, type: 'spring' }}>{resource.value}%</motion.span>
                      </div>
                    </div>
                    <p className="text-[9px] uppercase tracking-wider font-semibold" style={{ color: 'var(--dark-secondary-text)' }}>{resource.name}</p>
                  </motion.div>
                ))}
              </div>
              <div className="h-20">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={activityData.slice(-12)}>
                    <defs><linearGradient id="activityGradient" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={COLORS.gold} stopOpacity="0.5" /><stop offset="100%" stopColor={COLORS.gold} stopOpacity="0" /></linearGradient></defs>
                    <Area type="monotone" dataKey="requests" stroke={COLORS.gold} strokeWidth="2" fill="url(#activityGradient)" isAnimationActive={true} animationDuration={1500} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </AnimatedPanel>
            <AnimatedPanel delay={0.45} className="col-span-6 p-5">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-sm font-bold" style={{ color: 'var(--text-main)' }}>ACTIVITY TRENDS</h3>
                  <p className="text-[10px] uppercase tracking-wider font-semibold" style={{ color: 'var(--text-muted)' }}>24-Hour Overview</p>
                </div>
                <div className="flex items-center gap-1 p-1 rounded-xl" style={{ background: 'var(--quantum-cream)' }}>
                  {(['Day', 'Week', 'Month'] as const).map((period) => (
                    <motion.button key={period} className="px-3 py-1 rounded-lg text-[10px] font-bold uppercase tracking-wider" style={{ background: activityPeriod === period ? COLORS.gold : 'transparent', color: activityPeriod === period ? '#141414' : 'var(--text-secondary)' }} whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.95 }} onClick={() => setActivityPeriod(period)}>{period}</motion.button>
                  ))}
                </div>
              </div>
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={activityData}>
                    <defs>
                      <linearGradient id="lineGradient1" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stopColor={COLORS.gold} stopOpacity="0.3" /><stop offset="50%" stopColor={COLORS.gold} stopOpacity="1" /><stop offset="100%" stopColor={COLORS.champagne} stopOpacity="0.3" /></linearGradient>
                      <linearGradient id="lineGradient2" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stopColor={COLORS.green} stopOpacity="0.3" /><stop offset="50%" stopColor={COLORS.green} stopOpacity="1" /><stop offset="100%" stopColor={COLORS.softGreen} stopOpacity="0.3" /></linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(110, 96, 80, 0.08)" />
                    <XAxis dataKey="time" tick={{ fontSize: 9, fill: 'var(--text-muted)' }} stroke="transparent" />
                    <YAxis tick={{ fontSize: 9, fill: 'var(--text-muted)' }} stroke="transparent" />
                    <Tooltip contentStyle={{ background: 'var(--quantum-black)', border: `1px solid ${COLORS.gold}40`, borderRadius: '12px', fontSize: '12px', color: 'var(--dark-primary-text)' }} />
                    <Line type="monotone" dataKey="requests" stroke="url(#lineGradient1)" strokeWidth="2.5" dot={false} isAnimationActive={true} animationDuration={1500} />
                    <Line type="monotone" dataKey="latency" stroke="url(#lineGradient2)" strokeWidth="2" dot={false} isAnimationActive={true} animationDuration={1500} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </AnimatedPanel>
            </>)}
          </div>
        </div>
        )}

        {/* ==========================================================================
            COMMAND CONSOLE
        ========================================================================== */}
        <AnimatePresence>
          {showResponse && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.4 }}
              className="overflow-hidden"
            >
              <div className="px-6 py-3 border-b" style={{ background: 'rgba(20, 20, 20, 0.95)', borderColor: 'rgba(201, 165, 110, 0.2)' }}>
                <div className="flex items-center gap-3 max-w-5xl">
                  <Terminal className="w-4 h-4 flex-shrink-0" style={{ color: COLORS.gold }} />
                  <span className="text-[10px] uppercase tracking-wider font-bold" style={{ color: COLORS.gold }}>
                    SALAAR RESPONSE
                  </span>
                  <div className="flex-1">
                    <span className="text-sm" style={{ color: 'var(--dark-primary-text)' }}>
                      <TypingIndicator text={responseText} onComplete={() => {}} />
                    </span>
                  </div>
                  <motion.button
                    onClick={() => setShowResponse(false)}
                    className="text-xs font-semibold px-3 py-1 rounded-lg"
                    style={{ background: 'rgba(255,255,255,0.05)', color: 'var(--dark-secondary-text)' }}
                    whileHover={{ background: 'rgba(255,255,255,0.1)' }}
                  >
                    DISMISS
                  </motion.button>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <motion.footer
          className="h-20 border-t px-6 flex items-center gap-4 relative"
          style={{
            background: 'rgba(250, 248, 244, 0.92)',
            backdropFilter: 'blur(24px)',
            borderColor: 'rgba(110, 96, 80, 0.08)',
          }}
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ duration: 0.5, delay: 0.5 }}
        >
          {/* Thinking Skull — animates equations when typing/generating */}
          <ThinkingSkull
            state={
              showResponse || ['thinking', 'planning', 'acting', 'verifying'].includes(coreState)
                ? 'generating'
                : commandInput.trim()
                ? 'typing'
                : isListening
                ? 'typing'
                : 'idle'
            }
            size={48}
          />

          {/* Greeting */}
          <div className="flex-1">
            <motion.p
              className="text-sm font-semibold"
              style={{ color: 'var(--text-main)' }}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.6 }}
            >
              Good {currentTime.getHours() < 12 ? 'morning' : currentTime.getHours() < 17 ? 'afternoon' : 'evening'}, Admin.
            </motion.p>
            <p className="text-xs flex items-center gap-1.5" style={{ color: 'var(--text-muted)' }}>
              <span className="w-1 h-1 rounded-full" style={{ background: COLORS.gold }} />
              How can I assist you today?
            </p>
          </div>

          {/* Command Input */}
          <div className="flex-1 max-w-2xl relative">
            <motion.input
              type="text"
              value={commandInput}
              onChange={(e) => setCommandInput(e.target.value)}
              placeholder="Ask anything or give a command..."
              className="input-quantum w-full pl-5 pr-36 py-3 text-sm"
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleSendCommand();
              }}
              initial={{ opacity: 0, y: 5 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.6 }}
              whileFocus={{ scale: 1.01 }}
            />
            <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
              <motion.button
                className="p-2 rounded-lg relative"
                style={{ background: isListening ? `${COLORS.green}20` : 'transparent' }}
                onClick={toggleMic}
                whileHover={{ scale: 1.08 }}
                whileTap={{ scale: 0.92 }}
              >
                {isListening ? (
                  <Waveform active={true} barCount={12} height={16} color={COLORS.green} />
                ) : (
                  <Mic className="w-4 h-4" style={{ color: 'var(--text-muted)' }} />
                )}
              </motion.button>
            </div>
          </div>

          {/* Send Button */}
          <motion.button
            className="btn-primary px-6 py-3 flex items-center gap-2"
            onClick={handleSendCommand}
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.95 }}
          >
            <Send className="w-4 h-4" />
            <span className="text-sm font-bold uppercase tracking-wider">SEND COMMAND</span>
          </motion.button>
        </motion.footer>
      </main>
    </div>
  );
};

export default QuantumEngine;
