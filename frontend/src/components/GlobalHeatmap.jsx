import { motion } from 'framer-motion'
import { useMemo } from 'react'

/* ── Simple city coordinates for plotting dots on a map ── */
const CITY_POS = {
  'New York':  { x: 26, y: 38 },
  'Los Angeles': { x: 14, y: 40 },
  'Chicago':   { x: 22, y: 37 },
  'London':    { x: 47, y: 30 },
  'Berlin':    { x: 51, y: 29 },
  'Paris':     { x: 48, y: 32 },
  'Singapore': { x: 74, y: 58 },
  'Dubai':     { x: 63, y: 43 },
  'Mumbai':    { x: 67, y: 46 },
  'Chennai':   { x: 69, y: 50 },
  'Tokyo':     { x: 83, y: 37 },
  'Sydney':    { x: 86, y: 72 },
  'Toronto':   { x: 23, y: 35 },
  'São Paulo': { x: 33, y: 68 },
  'Moscow':    { x: 57, y: 26 },
  'Lagos':     { x: 48, y: 53 },
  'Seoul':     { x: 80, y: 37 },
  'Bangkok':   { x: 74, y: 50 },
}

const RISK_COLORS = {
  SAFE:       { fill: '#10b981', glow: 'rgba(16,185,129,0.4)' },
  SUSPICIOUS: { fill: '#f59e0b', glow: 'rgba(245,158,11,0.4)' },
  FRAUD:      { fill: '#ef4444', glow: 'rgba(239,68,68,0.5)' },
}

export default function GlobalHeatmap({ transactions }) {
  const hotspots = useMemo(() => {
    const map = {}
    transactions.forEach((tx) => {
      const loc = tx.location || ''
      if (!loc || !CITY_POS[loc]) return
      if (!map[loc]) {
        map[loc] = { city: loc, total: 0, fraud: 0, suspicious: 0, safe: 0 }
      }
      map[loc].total++
      const cat = tx.risk_category || 'SAFE'
      if (cat === 'FRAUD') map[loc].fraud++
      else if (cat === 'SUSPICIOUS') map[loc].suspicious++
      else map[loc].safe++
    })
    return Object.values(map).map((h) => {
      let risk = 'SAFE'
      if (h.fraud > 0) risk = 'FRAUD'
      else if (h.suspicious > 0) risk = 'SUSPICIOUS'
      return { ...h, risk, pos: CITY_POS[h.city] }
    })
  }, [transactions])

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.3 }}
      className="glass p-5 relative overflow-hidden"
    >
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-sm font-semibold">Global Fraud Heatmap</h2>
          <p className="text-[11px] text-soc-muted mt-0.5">Transaction locations — suspicious areas highlighted</p>
        </div>
        <div className="flex items-center gap-3 text-[10px] text-soc-muted">
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-soc-safe" /> Safe</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-soc-warn" /> Suspicious</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-soc-danger" /> Fraud</span>
        </div>
      </div>

      {/* World map SVG background */}
      <div className="relative w-full" style={{ paddingBottom: '50%' }}>
        <svg
          viewBox="0 0 100 80"
          className="absolute inset-0 w-full h-full"
          xmlns="http://www.w3.org/2000/svg"
        >
          {/* Simplified continent outlines */}
          <defs>
            <radialGradient id="dotGlow">
              <stop offset="0%" stopColor="white" stopOpacity="0.3" />
              <stop offset="100%" stopColor="white" stopOpacity="0" />
            </radialGradient>
          </defs>

          {/* Grid lines */}
          {[20, 40, 60, 80].map((x) => (
            <line key={`v${x}`} x1={x} y1={5} x2={x} y2={75} stroke="#1a2744" strokeWidth="0.15" />
          ))}
          {[20, 40, 60].map((y) => (
            <line key={`h${y}`} x1={5} y1={y} x2={95} y2={y} stroke="#1a2744" strokeWidth="0.15" />
          ))}

          {/* Continent shapes (simplified polygons) */}
          {/* North America */}
          <path d="M10,20 L30,18 L32,25 L28,38 L22,42 L15,42 L10,35 Z"
            fill="#111d35" stroke="#1a2744" strokeWidth="0.3" opacity="0.8" />
          {/* South America */}
          <path d="M25,50 L35,48 L37,55 L35,72 L28,75 L22,68 Z"
            fill="#111d35" stroke="#1a2744" strokeWidth="0.3" opacity="0.8" />
          {/* Europe */}
          <path d="M44,22 L56,20 L58,28 L54,35 L46,36 L42,30 Z"
            fill="#111d35" stroke="#1a2744" strokeWidth="0.3" opacity="0.8" />
          {/* Africa */}
          <path d="M44,38 L56,36 L60,45 L57,60 L50,65 L42,58 L40,48 Z"
            fill="#111d35" stroke="#1a2744" strokeWidth="0.3" opacity="0.8" />
          {/* Asia */}
          <path d="M58,18 L85,16 L88,30 L85,42 L75,48 L65,50 L58,42 L56,30 Z"
            fill="#111d35" stroke="#1a2744" strokeWidth="0.3" opacity="0.8" />
          {/* Australia */}
          <path d="M80,62 L92,60 L93,70 L86,75 L78,72 Z"
            fill="#111d35" stroke="#1a2744" strokeWidth="0.3" opacity="0.8" />

          {/* Hotspot dots */}
          {hotspots.map((h, i) => {
            const c = RISK_COLORS[h.risk]
            const r = Math.min(0.8 + h.total * 0.15, 3)
            return (
              <g key={h.city}>
                {/* Glow */}
                <circle
                  cx={h.pos.x} cy={h.pos.y} r={r * 2.5}
                  fill={c.glow} opacity={0.4}
                >
                  <animate attributeName="opacity" values="0.2;0.5;0.2" dur="3s" repeatCount="indefinite" begin={`${i * 0.3}s`} />
                </circle>
                {/* Pulse ring */}
                {h.risk !== 'SAFE' && (
                  <circle cx={h.pos.x} cy={h.pos.y} r={r} fill="none" stroke={c.fill} strokeWidth="0.15" opacity="0.6">
                    <animate attributeName="r" values={`${r};${r*3};${r}`} dur="2.5s" repeatCount="indefinite" />
                    <animate attributeName="opacity" values="0.6;0;0.6" dur="2.5s" repeatCount="indefinite" />
                  </circle>
                )}
                {/* Dot */}
                <circle cx={h.pos.x} cy={h.pos.y} r={r} fill={c.fill} opacity={0.85} />
                {/* Label */}
                <text x={h.pos.x} y={h.pos.y - r - 0.8} textAnchor="middle" fill="#94a3b8" fontSize="1.6" fontFamily="Inter, sans-serif">
                  {h.city}
                </text>
              </g>
            )
          })}

          {hotspots.length === 0 && (
            <text x="50" y="40" textAnchor="middle" fill="#64748b" fontSize="2.5" fontFamily="Inter, sans-serif">
              Waiting for location data…
            </text>
          )}
        </svg>
      </div>

      {/* Stats bar */}
      {hotspots.length > 0 && (
        <div className="mt-3 flex items-center gap-4 text-[10px] text-soc-muted">
          <span>{hotspots.length} active locations</span>
          <span className="text-soc-danger">{hotspots.filter(h => h.risk === 'FRAUD').length} fraud hotspots</span>
          <span className="text-soc-warn">{hotspots.filter(h => h.risk === 'SUSPICIOUS').length} suspicious</span>
        </div>
      )}
    </motion.div>
  )
}
