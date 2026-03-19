import { useEffect, useState, useRef, useCallback } from 'react'
import { motion } from 'framer-motion'
import { fetchFraudGraph, fetchFraudClusters, fetchDeviceRings } from '../services/api'

/* ── Simple canvas force-directed graph ── */
function ForceGraph({ graphData }) {
  const canvasRef = useRef(null)
  const simRef = useRef(null)
  const [hovered, setHovered] = useState(null)

  useEffect(() => {
    if (!graphData?.nodes?.length) return
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    const dpr = window.devicePixelRatio || 1
    const rect = canvas.getBoundingClientRect()
    canvas.width = rect.width * dpr
    canvas.height = rect.height * dpr
    ctx.scale(dpr, dpr)
    const W = rect.width
    const H = rect.height

    // Init positions
    const nodes = graphData.nodes.map((n, i) => ({
      ...n,
      x: W / 2 + (Math.random() - 0.5) * W * 0.6,
      y: H / 2 + (Math.random() - 0.5) * H * 0.6,
      vx: 0, vy: 0,
    }))
    const nodeMap = {}
    nodes.forEach((n) => (nodeMap[n.id] = n))

    const edges = graphData.edges
      .map((e) => ({ source: nodeMap[e.source], target: nodeMap[e.target], weight: e.weight || 1 }))
      .filter((e) => e.source && e.target)

    const typeColor = {
      user: '#3b82f6',
      merchant: '#a855f7',
      device: '#06b6d4',
      location: '#f59e0b',
    }

    let running = true
    let frame = 0

    const tick = () => {
      if (!running) return
      frame++
      // Repulsion
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          let dx = nodes[j].x - nodes[i].x
          let dy = nodes[j].y - nodes[i].y
          let d = Math.sqrt(dx * dx + dy * dy) || 1
          let force = 800 / (d * d)
          let fx = (dx / d) * force
          let fy = (dy / d) * force
          nodes[i].vx -= fx
          nodes[i].vy -= fy
          nodes[j].vx += fx
          nodes[j].vy += fy
        }
      }
      // Attraction through edges
      for (const e of edges) {
        let dx = e.target.x - e.source.x
        let dy = e.target.y - e.source.y
        let d = Math.sqrt(dx * dx + dy * dy) || 1
        let force = (d - 80) * 0.005
        let fx = (dx / d) * force
        let fy = (dy / d) * force
        e.source.vx += fx
        e.source.vy += fy
        e.target.vx -= fx
        e.target.vy -= fy
      }
      // Center gravity
      for (const n of nodes) {
        n.vx += (W / 2 - n.x) * 0.001
        n.vy += (H / 2 - n.y) * 0.001
      }
      // Apply velocity + damping
      const damping = Math.max(0.85, 1 - frame * 0.001)
      for (const n of nodes) {
        n.vx *= damping
        n.vy *= damping
        n.x += n.vx
        n.y += n.vy
        n.x = Math.max(20, Math.min(W - 20, n.x))
        n.y = Math.max(20, Math.min(H - 20, n.y))
      }

      // Draw
      ctx.clearRect(0, 0, W, H)

      // Edges
      for (const e of edges) {
        ctx.beginPath()
        ctx.moveTo(e.source.x, e.source.y)
        ctx.lineTo(e.target.x, e.target.y)
        ctx.strokeStyle = 'rgba(100,116,139,0.15)'
        ctx.lineWidth = Math.min(e.weight, 3)
        ctx.stroke()
      }
      // Nodes
      for (const n of nodes) {
        const r = n.type === 'user' ? 6 : 4
        const color = typeColor[n.type] || '#64748b'
        const riskAlpha = n.risk != null ? Math.min(1, n.risk) : 0
        if (riskAlpha > 0.4) {
          ctx.beginPath()
          ctx.arc(n.x, n.y, r + 6, 0, Math.PI * 2)
          ctx.fillStyle = `rgba(239,68,68,${riskAlpha * 0.25})`
          ctx.fill()
        }
        ctx.beginPath()
        ctx.arc(n.x, n.y, r, 0, Math.PI * 2)
        ctx.fillStyle = color
        ctx.fill()
        ctx.strokeStyle = 'rgba(0,0,0,0.3)'
        ctx.lineWidth = 0.5
        ctx.stroke()
      }

      if (frame < 600) requestAnimationFrame(tick)
    }

    simRef.current = { nodes, running: true }
    tick()

    // Hover detection
    const onMouseMove = (e) => {
      const br = canvas.getBoundingClientRect()
      const mx = e.clientX - br.left
      const my = e.clientY - br.top
      let found = null
      for (const n of nodes) {
        const dx = n.x - mx
        const dy = n.y - my
        if (dx * dx + dy * dy < 100) {
          found = n
          break
        }
      }
      setHovered(found)
    }
    canvas.addEventListener('mousemove', onMouseMove)

    return () => {
      running = false
      canvas.removeEventListener('mousemove', onMouseMove)
    }
  }, [graphData])

  return (
    <div className="relative w-full h-full">
      <canvas ref={canvasRef} className="w-full h-full" style={{ display: 'block' }} />
      {hovered && (
        <div
          className="absolute glass-sm px-3 py-2 text-xs pointer-events-none z-10"
          style={{ top: 12, right: 12 }}
        >
          <p className="font-semibold text-soc-accent">{hovered.label || hovered.id}</p>
          <p className="text-soc-muted capitalize">{hovered.type}</p>
          {hovered.risk != null && (
            <p className={hovered.risk > 0.7 ? 'text-soc-danger' : hovered.risk > 0.4 ? 'text-soc-warn' : 'text-soc-safe'}>
              Risk: {hovered.risk.toFixed(4)}
            </p>
          )}
        </div>
      )}
      {/* Legend */}
      <div className="absolute bottom-3 left-3 flex gap-4 glass-sm px-3 py-2 text-[10px]">
        {[
          { color: '#3b82f6', label: 'User' },
          { color: '#a855f7', label: 'Merchant' },
          { color: '#06b6d4', label: 'Device' },
          { color: '#f59e0b', label: 'Location' },
        ].map((l) => (
          <span key={l.label} className="flex items-center gap-1">
            <span className="inline-block w-2 h-2 rounded-full" style={{ background: l.color }} />
            {l.label}
          </span>
        ))}
      </div>
    </div>
  )
}

/* ── Main page ── */
export default function FraudNetwork() {
  const [graph, setGraph] = useState(null)
  const [clusters, setClusters] = useState([])
  const [deviceRings, setDeviceRings] = useState([])
  const [loading, setLoading] = useState(true)
  const [graphLimit, setGraphLimit] = useState(200)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [g, c, d] = await Promise.all([
        fetchFraudGraph(graphLimit),
        fetchFraudClusters(0.4),
        fetchDeviceRings(),
      ])
      setGraph(g)
      setClusters(c?.clusters || [])
      setDeviceRings(d?.device_rings || [])
    } catch (err) {
      console.error('FraudNetwork load:', err)
    }
    setLoading(false)
  }, [graphLimit])

  useEffect(() => { load() }, [load])

  return (
    <main className="max-w-[1800px] mx-auto px-6 py-6 space-y-6">
      {/* Header */}
      <div className="flex items-end justify-between">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">Fraud Network Graph</h2>
          <p className="text-xs text-soc-muted mt-1">
            Interactive network visualization of transaction relationships & suspicious clusters
          </p>
        </div>
        <div className="flex items-center gap-3">
          <label className="text-[10px] text-soc-muted uppercase tracking-wider">Nodes</label>
          <select
            value={graphLimit}
            onChange={(e) => setGraphLimit(Number(e.target.value))}
            className="glass-sm px-2 py-1 text-xs bg-transparent border-none focus:outline-none cursor-pointer"
          >
            <option value={100}>100</option>
            <option value={200}>200</option>
            <option value={500}>500</option>
          </select>
          <button onClick={load} className="glass-sm px-3 py-1 text-xs hover:bg-soc-border/40 transition">
            Reload
          </button>
        </div>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'Nodes', value: graph?.nodes?.length ?? '—', color: 'from-soc-accent to-blue-600', icon: '🔵' },
          { label: 'Edges', value: graph?.edges?.length ?? '—', color: 'from-purple-500 to-violet-600', icon: '🔗' },
          { label: 'Clusters', value: clusters.length, color: 'from-soc-danger to-red-600', icon: '⚠️' },
          { label: 'Device Rings', value: deviceRings.length, color: 'from-soc-warn to-amber-600', icon: '📱' },
        ].map((c, i) => (
          <motion.div
            key={c.label}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.06 }}
            className="glass p-4 relative overflow-hidden"
          >
            <div className={`absolute top-0 inset-x-0 h-[2px] bg-gradient-to-r ${c.color}`} />
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] text-soc-muted uppercase tracking-wider font-medium">{c.label}</span>
              <span className="text-sm">{c.icon}</span>
            </div>
            <span className="text-2xl font-semibold tabular-nums">{c.value}</span>
          </motion.div>
        ))}
      </div>

      {/* Graph canvas */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="glass overflow-hidden"
        style={{ height: '500px' }}
      >
        <div className="px-5 py-3 border-b border-soc-border/60 flex items-center justify-between">
          <h3 className="text-sm font-semibold tracking-wide">Transaction Relationship Graph</h3>
          {loading && (
            <div className="flex items-center gap-2 text-xs text-soc-muted">
              <div className="w-3 h-3 border-2 border-soc-accent/30 border-t-soc-accent rounded-full animate-spin" />
              Loading…
            </div>
          )}
        </div>
        <div className="w-full" style={{ height: 'calc(100% - 44px)' }}>
          {graph && graph.nodes?.length > 0 ? (
            <ForceGraph graphData={graph} />
          ) : !loading ? (
            <div className="flex items-center justify-center h-full text-soc-muted text-xs">
              No graph data — start the transaction streamer to generate relationships
            </div>
          ) : null}
        </div>
      </motion.div>

      {/* Bottom panels */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Suspicious clusters */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="glass overflow-hidden"
        >
          <div className="px-5 py-4 border-b border-soc-border/60 flex items-center gap-2">
            <span className="text-sm">⚠️</span>
            <h3 className="text-sm font-semibold tracking-wide">Suspicious Clusters</h3>
            <span className="ml-auto text-[10px] text-soc-muted">
              {clusters.length} cluster{clusters.length !== 1 && 's'}
            </span>
          </div>
          <div className="overflow-y-auto max-h-[300px] divide-y divide-soc-border/20">
            {clusters.length === 0 ? (
              <p className="px-5 py-8 text-center text-xs text-soc-muted">
                No suspicious clusters detected
              </p>
            ) : (
              clusters.map((cl, i) => (
                <div key={i} className="px-5 py-3 hover:bg-soc-border/10 transition-colors">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-semibold">
                      Cluster #{i + 1}
                      <span className="ml-2 text-soc-muted font-normal">
                        {cl.size} node{cl.size !== 1 && 's'}
                      </span>
                    </span>
                    <span className={`text-xs font-semibold tabular-nums ${
                      cl.avg_risk >= 0.7 ? 'text-soc-danger' : cl.avg_risk >= 0.4 ? 'text-soc-warn' : 'text-soc-safe'
                    }`}>
                      avg risk {cl.avg_risk?.toFixed(3)}
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {cl.members?.slice(0, 10).map((m) => (
                      <span key={m} className="glass-sm px-1.5 py-0.5 text-[10px] font-mono text-soc-accent">
                        {m}
                      </span>
                    ))}
                    {cl.members?.length > 10 && (
                      <span className="text-[10px] text-soc-muted">+{cl.members.length - 10} more</span>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </motion.div>

        {/* Device rings */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.35 }}
          className="glass overflow-hidden"
        >
          <div className="px-5 py-4 border-b border-soc-border/60 flex items-center gap-2">
            <span className="text-sm">📱</span>
            <h3 className="text-sm font-semibold tracking-wide">Shared Device Rings</h3>
            <span className="ml-auto text-[10px] text-soc-muted">
              {deviceRings.length} ring{deviceRings.length !== 1 && 's'}
            </span>
          </div>
          <div className="overflow-y-auto max-h-[300px] divide-y divide-soc-border/20">
            {deviceRings.length === 0 ? (
              <p className="px-5 py-8 text-center text-xs text-soc-muted">
                No device sharing detected
              </p>
            ) : (
              deviceRings.map((dr, i) => (
                <div key={i} className="px-5 py-3 hover:bg-soc-border/10 transition-colors">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-mono text-cyan-400">{dr.device}</span>
                    <span className="text-[10px] badge-suspicious px-2 py-0.5 rounded-full font-semibold">
                      {dr.user_count} users
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {dr.users?.map((u) => (
                      <span key={u} className="glass-sm px-1.5 py-0.5 text-[10px] font-mono text-soc-accent">
                        U{String(u).padStart(4, '0')}
                      </span>
                    ))}
                  </div>
                </div>
              ))
            )}
          </div>
        </motion.div>
      </div>
    </main>
  )
}
