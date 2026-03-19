import { useEffect, useState, useCallback, useRef } from 'react'
import { fetchFullGraph, fetchGraphClusters, fetchGraphStats, fetchGraphNeighborhood } from '../services/api'

const NODE_COLORS = {
  customer: '#6be8ff',
  merchant: '#53e2a1',
  device: '#d4a0ff',
  ip: '#f6c667',
}

const riskGradient = (score) => {
  if (score >= 0.7) return '#ff5f8f'
  if (score >= 0.4) return '#f6c667'
  return '#53e2a1'
}

function GraphCanvas({ graphData, onNodeClick }) {
  const canvasRef = useRef(null)
  const simRef = useRef(null)
  const nodesRef = useRef([])
  const linksRef = useRef([])
  const transformRef = useRef({ x: 0, y: 0, k: 1 })
  const dragRef = useRef(null)
  const hoveredRef = useRef(null)

  useEffect(() => {
    if (!graphData?.nodes?.length) return

    const nodes = graphData.nodes.map((n) => ({
      ...n,
      x: (Math.random() - 0.5) * 600,
      y: (Math.random() - 0.5) * 600,
      vx: 0,
      vy: 0,
    }))
    const nodeMap = new Map(nodes.map((n) => [n.id, n]))
    const links = (graphData.links || graphData.edges || [])
      .map((l) => ({
        source: nodeMap.get(l.source) || nodeMap.get(l.from),
        target: nodeMap.get(l.target) || nodeMap.get(l.to),
        type: l.type || 'default',
      }))
      .filter((l) => l.source && l.target)

    nodesRef.current = nodes
    linksRef.current = links

    // Simple force simulation
    const alpha = { value: 1 }
    const tick = () => {
      if (alpha.value < 0.001) return
      alpha.value *= 0.99

      // Repulsion
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = nodes[j].x - nodes[i].x
          const dy = nodes[j].y - nodes[i].y
          const dist = Math.sqrt(dx * dx + dy * dy) || 1
          const force = (80 * alpha.value) / dist
          nodes[i].x -= (dx / dist) * force
          nodes[i].y -= (dy / dist) * force
          nodes[j].x += (dx / dist) * force
          nodes[j].y += (dy / dist) * force
        }
      }

      // Attraction along links
      for (const l of links) {
        const dx = l.target.x - l.source.x
        const dy = l.target.y - l.source.y
        const dist = Math.sqrt(dx * dx + dy * dy) || 1
        const force = (dist - 80) * 0.01 * alpha.value
        l.source.x += (dx / dist) * force
        l.source.y += (dy / dist) * force
        l.target.x -= (dx / dist) * force
        l.target.y -= (dy / dist) * force
      }

      // Center gravity
      for (const n of nodes) {
        n.x *= 0.998
        n.y *= 0.998
      }
    }

    const intervalId = setInterval(tick, 16)
    simRef.current = intervalId
    return () => clearInterval(intervalId)
  }, [graphData])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')

    const draw = () => {
      const { width, height } = canvas.getBoundingClientRect()
      canvas.width = width * 2
      canvas.height = height * 2
      ctx.setTransform(2, 0, 0, 2, 0, 0)

      const t = transformRef.current
      ctx.clearRect(0, 0, width, height)
      ctx.save()
      ctx.translate(width / 2 + t.x, height / 2 + t.y)
      ctx.scale(t.k, t.k)

      // Draw links
      for (const l of linksRef.current) {
        ctx.beginPath()
        ctx.moveTo(l.source.x, l.source.y)
        ctx.lineTo(l.target.x, l.target.y)
        ctx.strokeStyle = 'rgba(107,232,255,0.15)'
        ctx.lineWidth = 0.5
        ctx.stroke()
      }

      // Draw nodes
      for (const n of nodesRef.current) {
        const r = n.type === 'customer' ? 6 : 4
        const color = n.risk_score != null ? riskGradient(n.risk_score) : (NODE_COLORS[n.type] || '#6be8ff')
        ctx.beginPath()
        ctx.arc(n.x, n.y, r, 0, Math.PI * 2)
        ctx.fillStyle = color
        ctx.fill()

        if (hoveredRef.current === n.id) {
          ctx.strokeStyle = '#fff'
          ctx.lineWidth = 2
          ctx.stroke()
          ctx.fillStyle = '#fff'
          ctx.font = '10px sans-serif'
          ctx.fillText(n.label || n.id, n.x + r + 4, n.y + 4)
        }
      }

      ctx.restore()
      requestAnimationFrame(draw)
    }

    const frameId = requestAnimationFrame(draw)
    return () => cancelAnimationFrame(frameId)
  }, [])

  // Pan & zoom handlers
  const handleWheel = (e) => {
    e.preventDefault()
    const t = transformRef.current
    const factor = e.deltaY > 0 ? 0.9 : 1.1
    t.k = Math.max(0.1, Math.min(5, t.k * factor))
  }

  const handleMouseDown = (e) => {
    dragRef.current = { startX: e.clientX, startY: e.clientY, tx: transformRef.current.x, ty: transformRef.current.y }
  }

  const handleMouseMove = (e) => {
    if (dragRef.current) {
      transformRef.current.x = dragRef.current.tx + (e.clientX - dragRef.current.startX)
      transformRef.current.y = dragRef.current.ty + (e.clientY - dragRef.current.startY)
    }

    // Hover detection
    const canvas = canvasRef.current
    if (!canvas) return
    const rect = canvas.getBoundingClientRect()
    const t = transformRef.current
    const mx = (e.clientX - rect.left - rect.width / 2 - t.x) / t.k
    const my = (e.clientY - rect.top - rect.height / 2 - t.y) / t.k

    let found = null
    for (const n of nodesRef.current) {
      const dx = n.x - mx
      const dy = n.y - my
      if (dx * dx + dy * dy < 64) {
        found = n.id
        break
      }
    }
    hoveredRef.current = found
    canvas.style.cursor = found ? 'pointer' : 'grab'
  }

  const handleMouseUp = () => {
    dragRef.current = null
  }

  const handleClick = (e) => {
    if (!hoveredRef.current) return
    const node = nodesRef.current.find((n) => n.id === hoveredRef.current)
    if (node && onNodeClick) onNodeClick(node)
  }

  return (
    <canvas
      ref={canvasRef}
      style={{ width: '100%', height: '100%', cursor: 'grab' }}
      onWheel={handleWheel}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
      onClick={handleClick}
    />
  )
}

export default function D3FraudNetwork() {
  const [graphData, setGraphData] = useState({ nodes: [], links: [] })
  const [clusters, setClusters] = useState([])
  const [stats, setStats] = useState(null)
  const [selectedNode, setSelectedNode] = useState(null)
  const [neighborhood, setNeighborhood] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    const load = async () => {
      try {
        const [g, c, s] = await Promise.all([
          fetchFullGraph(1000),
          fetchGraphClusters().catch(() => []),
          fetchGraphStats().catch(() => null),
        ])
        if (!active) return
        setGraphData(g || { nodes: [], links: [] })
        setClusters(c || [])
        setStats(s)
      } catch { /* noop */ }
      setLoading(false)
    }
    load()
    return () => { active = false }
  }, [])

  const handleNodeClick = useCallback(async (node) => {
    setSelectedNode(node)
    if (node.type === 'customer') {
      try {
        const nb = await fetchGraphNeighborhood(node.id)
        setNeighborhood(nb)
      } catch { /* noop */ }
    }
  }, [])

  return (
    <div className="soc-grid" style={{ gap: '1rem' }}>
      {/* Header + Stats */}
      <div className="soc-card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.8rem' }}>
        <div>
          <h2 style={{ margin: 0, fontSize: '1.1rem' }}>🕸️ Fraud Network Graph</h2>
          <p style={{ margin: '0.2rem 0 0', color: 'var(--muted)', fontSize: '0.82rem' }}>
            Force-directed graph — click nodes to explore neighborhoods
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          {stats && (
            <>
              <span className="soc-pill">Nodes: {stats.total_nodes || graphData.nodes.length}</span>
              <span className="soc-pill">Edges: {stats.total_edges || (graphData.links || []).length}</span>
              <span className="soc-pill">Communities: {stats.communities || clusters.length}</span>
              {stats.avg_risk != null && <span className="soc-pill" style={{ color: riskGradient(stats.avg_risk) }}>Avg Risk: {stats.avg_risk.toFixed(3)}</span>}
            </>
          )}
        </div>
      </div>

      {/* Legend */}
      <div className="soc-card" style={{ display: 'flex', gap: '1.2rem', padding: '0.6rem 1rem', fontSize: '0.78rem' }}>
        {Object.entries(NODE_COLORS).map(([type, color]) => (
          <span key={type} style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
            <span style={{ width: 10, height: 10, borderRadius: '50%', background: color, display: 'inline-block' }} />
            {type}
          </span>
        ))}
        <span style={{ marginLeft: 'auto', color: 'var(--muted)' }}>Scroll to zoom · Drag to pan</span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: selectedNode ? '2fr 1fr' : '1fr', gap: '1rem' }}>
        {/* Graph Canvas */}
        <div className="soc-card" style={{ height: '65vh', padding: '0.4rem' }}>
          {loading ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--muted)' }}>
              Loading graph data…
            </div>
          ) : graphData.nodes.length === 0 ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--muted)' }}>
              No graph data available. Process transactions to build the fraud network.
            </div>
          ) : (
            <GraphCanvas graphData={graphData} onNodeClick={handleNodeClick} />
          )}
        </div>

        {/* Node Inspector */}
        {selectedNode && (
          <div className="soc-card" style={{ maxHeight: '65vh', overflowY: 'auto' }}>
            <h2 style={{ fontSize: '0.95rem', marginBottom: '0.6rem' }}>Node Inspector</h2>
            <p><strong>ID:</strong> {selectedNode.id}</p>
            <p><strong>Type:</strong> {selectedNode.type}</p>
            {selectedNode.risk_score != null && (
              <p>
                <strong>Risk:</strong>{' '}
                <span style={{ color: riskGradient(selectedNode.risk_score) }}>
                  {selectedNode.risk_score.toFixed(4)}
                </span>
              </p>
            )}
            {selectedNode.label && <p><strong>Label:</strong> {selectedNode.label}</p>}

            {neighborhood && (
              <>
                <h3 style={{ fontSize: '0.85rem', marginTop: '1rem' }}>Neighborhood</h3>
                <p style={{ fontSize: '0.78rem', color: 'var(--muted)' }}>
                  {neighborhood.nodes?.length || 0} nodes, {neighborhood.links?.length || 0} edges
                </p>
                {(neighborhood.nodes || []).slice(0, 20).map((n) => (
                  <div key={n.id} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', padding: '0.2rem 0', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                    <span style={{ color: NODE_COLORS[n.type] || '#6be8ff' }}>{n.type}: {n.id}</span>
                    {n.risk_score != null && <span style={{ color: riskGradient(n.risk_score) }}>{n.risk_score.toFixed(3)}</span>}
                  </div>
                ))}
              </>
            )}
          </div>
        )}
      </div>

      {/* Clusters Table */}
      {clusters.length > 0 && (
        <div className="soc-card">
          <h2 style={{ fontSize: '0.95rem' }}>Fraud Clusters</h2>
          <div className="soc-table-wrap" style={{ maxHeight: '30vh', overflowY: 'auto' }}>
            <table className="soc-table">
              <thead>
                <tr>
                  <th>Cluster</th>
                  <th>Members</th>
                  <th>Avg Risk</th>
                  <th>Flagged Nodes</th>
                </tr>
              </thead>
              <tbody>
                {clusters.map((c, i) => (
                  <tr key={c.cluster_id || i}>
                    <td>#{c.cluster_id ?? i}</td>
                    <td>{c.size || c.members?.length || 0}</td>
                    <td style={{ color: riskGradient(c.avg_risk || 0) }}>{(c.avg_risk || 0).toFixed(3)}</td>
                    <td>{c.flagged || c.fraud_count || 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
