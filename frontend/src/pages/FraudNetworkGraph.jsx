import { useMemo } from 'react'
import { useSelector } from 'react-redux'
import ForceGraph2D from 'react-force-graph-2d'

function riskColor(risk) {
  if (risk >= 0.75) return '#ff5f8f'
  if (risk >= 0.45) return '#f6c667'
  return '#53e2a1'
}

export default function FraudNetworkGraph() {
  const graph = useSelector((s) => s.platform.graph || { nodes: [], edges: [] })
  const clusters = useSelector((s) => s.platform.clusters || [])

  const graphData = useMemo(() => ({
    nodes: (graph.nodes || []).slice(0, 280).map((n) => ({
      id: n.id,
      name: n.label,
      type: n.type || 'unknown',
      risk: Number(n.risk || 0),
      cluster: n.cluster_label ?? -1,
      val: Math.max(2, Math.min(20, Number(n.tx_count || 1))),
    })),
    links: (graph.edges || []).slice(0, 420).map((e) => ({
      source: e.source,
      target: e.target,
      relation: e.relation,
      risk: Number(e.risk || 0),
      weight: Number(e.weight || 1),
    })),
  }), [graph])

  return (
    <section className="soc-grid">
      <article className="soc-card">
        <h2>Fraud Network Graph</h2>
        <p>
          Nodes: {graph?.nodes?.length || 0} | Edges: {graph?.edges?.length || 0} | Communities: {graph?.community_count || 0}
        </p>
        <div className="graph-wrap" style={{ height: 560 }}>
          <ForceGraph2D
            graphData={graphData}
            width={1200}
            height={560}
            backgroundColor="transparent"
            nodeLabel={(n) => `${n.name} | ${n.type} | risk=${n.risk.toFixed(3)} | cluster=${n.cluster}`}
            linkDirectionalParticles={(l) => (l.risk > 0.65 ? 2 : 0)}
            linkDirectionalParticleWidth={1.2}
            nodeCanvasObject={(node, ctx, globalScale) => {
              const label = node.name
              const fontSize = 10 / globalScale
              ctx.beginPath()
              ctx.fillStyle = riskColor(node.risk)
              ctx.globalAlpha = 0.9
              ctx.arc(node.x, node.y, Math.max(2, node.val * 0.4), 0, 2 * Math.PI, false)
              ctx.fill()
              if (node.risk > 0.6) {
                ctx.strokeStyle = '#ff5f8f'
                ctx.lineWidth = 1.4
                ctx.stroke()
              }
              ctx.font = `${fontSize}px 'IBM Plex Mono'`
              ctx.fillStyle = '#dfe9ff'
              ctx.fillText(label, node.x + 5, node.y + 3)
            }}
            linkColor={(l) => (l.risk > 0.65 ? '#ff5f8f' : '#324869')}
            linkWidth={(l) => Math.max(0.6, Math.min(2, l.weight * 0.25))}
          />
        </div>
      </article>

      <article className="soc-card table-card">
        <h2>Suspicious Communities</h2>
        <div className="soc-table-wrap">
          <table className="soc-table">
            <thead>
              <tr>
                <th>Cluster</th>
                <th>Users</th>
                <th>Avg Risk</th>
                <th>Max Risk</th>
                <th>Shared Devices</th>
              </tr>
            </thead>
            <tbody>
              {clusters.slice(0, 20).map((cluster) => (
                <tr key={cluster.cluster_id}>
                  <td>#{cluster.cluster_id}</td>
                  <td>{cluster.users?.join(', ') || '-'}</td>
                  <td>{Number(cluster.avg_risk || 0).toFixed(4)}</td>
                  <td>{Number(cluster.max_risk || 0).toFixed(4)}</td>
                  <td>{cluster.shared_devices?.slice(0, 3).join(', ') || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </article>
    </section>
  )
}
