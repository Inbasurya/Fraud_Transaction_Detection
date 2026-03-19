import { useEffect, useRef, useMemo, useState, useCallback } from 'react'
import * as d3 from 'd3'
import { useFraud } from '../context/FraudContext'

interface GraphNode {
  id: string
  type: 'customer' | 'merchant' | 'device'
  risk: 'safe' | 'suspicious' | 'fraudulent'
  txnCount: number
  totalAmount: number
  x?: number
  y?: number
  fx?: number | null
  fy?: number | null
}

interface GraphEdge {
  source: string | GraphNode
  target: string | GraphNode
  amount: number
  risk: string
  score: number
}

interface SelectedNode {
  id: string
  type: 'customer' | 'merchant' | 'device'
  transactions: any[]
  riskSummary: {
    total: number
    fraud: number
    suspicious: number
    totalAmount: number
    topPattern: string
  }
}

export default function FraudGraph() {
  const svgRef = useRef<SVGSVGElement>(null)
  const { transactions } = useFraud()
  const [selectedNode, setSelectedNode] = useState<SelectedNode | null>(null)

  // ── REF-BASED CLICK HANDLER ──
  const handleNodeClick = useCallback((nodeData: GraphNode) => {
    const nodeTransactions = transactions.filter((t: any) => {
      if (nodeData.type === 'customer') return t.customer_id === nodeData.id
      if (nodeData.type === 'merchant') return `M:${t.merchant}` === nodeData.id
      return false
    }).sort((a: any, b: any) =>
      new Date(b.timestamp || 0).getTime() - new Date(a.timestamp || 0).getTime()
    ).slice(0, 15)

    const fraudTxns = nodeTransactions.filter((t: any) => t.risk_level === 'fraudulent')
    const suspTxns = nodeTransactions.filter((t: any) => t.risk_level === 'suspicious')
    const totalAmt = nodeTransactions.reduce((s: number, t: any) => s + (t.amount || 0), 0)

    const patternCounts: Record<string, number> = {}
    nodeTransactions.forEach((t: any) => {
      const p = t.rule_names?.[0] || t.scenario_description
      if (p && p !== 'Normal transaction' && p !== 'No anomalies detected') {
        patternCounts[p] = (patternCounts[p] || 0) + 1
      }
    })
    const topPattern = Object.entries(patternCounts)
      .sort((a, b) => b[1] - a[1])[0]?.[0] || 'None'

    setSelectedNode({
      id: nodeData.id.replace('M:', ''),
      type: nodeData.type,
      transactions: nodeTransactions,
      riskSummary: {
        total: nodeTransactions.length,
        fraud: fraudTxns.length,
        suspicious: suspTxns.length,
        totalAmount: totalAmt,
        topPattern
      }
    })
  }, [transactions])

  // Store in ref so D3 can access latest version
  const handleNodeClickRef = useRef(handleNodeClick)
  useEffect(() => {
    handleNodeClickRef.current = handleNodeClick
  }, [handleNodeClick])

  const graphData = useMemo(() => {
    const nodeMap = new Map<string, GraphNode>()
    const edges: GraphEdge[] = []
    const edgeSeen = new Set<string>()

    // Only use last 80 transactions for performance
    const recent = transactions.slice(0, 80)

    recent.forEach(t => {
      // Customer node
      if (!nodeMap.has(t.customer_id)) {
        nodeMap.set(t.customer_id, {
          id: t.customer_id,
          type: 'customer',
          risk: t.risk_level as any,
          txnCount: 0,
          totalAmount: 0
        })
      }
      const cNode = nodeMap.get(t.customer_id)!
      cNode.txnCount++
      cNode.totalAmount += t.amount
      // Update risk to worst seen
      const tRisk = t.risk_level as any
      if (tRisk === 'fraudulent') cNode.risk = 'fraudulent'
      else if (tRisk === 'suspicious' && cNode.risk === 'safe') cNode.risk = 'suspicious'

      // Merchant node
      const mId = `M:${t.merchant}`
      if (!nodeMap.has(mId)) {
        nodeMap.set(mId, {
          id: mId,
          type: 'merchant',
          risk: t.risk_level as any,
          txnCount: 0,
          totalAmount: 0
        })
      }
      const mNode = nodeMap.get(mId)!
      mNode.txnCount++
      mNode.totalAmount += t.amount
      const mRisk = t.risk_level as any
      if (mRisk === 'fraudulent') mNode.risk = 'fraudulent'
      else if (mRisk === 'suspicious' && mNode.risk === 'safe') mNode.risk = 'suspicious'

      // Edge (deduplicated by customer+merchant pair)
      const edgeKey = `${t.customer_id}-${mId}`
      if (!edgeSeen.has(edgeKey)) {
        edgeSeen.add(edgeKey)
        edges.push({
          source: t.customer_id,
          target: mId,
          amount: t.amount,
          risk: t.risk_level,
          score: t.risk_score
        })
      }
    })

    return {
      nodes: Array.from(nodeMap.values()),
      edges
    }
  }, [transactions])

  useEffect(() => {
    if (!svgRef.current || graphData.nodes.length === 0) return

    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()

    const width = svgRef.current.clientWidth || 900
    const height = svgRef.current.clientHeight || 600

    // Color scale
    const nodeColor = (node: GraphNode) => {
      if (node.risk === 'fraudulent') return '#EF4444'
      if (node.risk === 'suspicious') return '#F59E0B'
      return '#10B981'
    }

    const edgeColor = (edge: GraphEdge) => {
      if (edge.risk === 'fraudulent') return '#EF4444'
      if (edge.risk === 'suspicious') return '#F59E0B'
      return '#CBD5E1'
    }

    // Zoom container
    const g = svg.append('g')

    svg.call(
      d3.zoom<SVGSVGElement, unknown>()
        .scaleExtent([0.3, 3])
        .on('zoom', (event) => {
          g.attr('transform', event.transform)
        })
    )

    // Force simulation
    const simulation = d3.forceSimulation(graphData.nodes as any)
      .force('link', d3.forceLink(graphData.edges)
        .id((d: any) => d.id)
        .distance(80))
      .force('charge', d3.forceManyBody().strength(-200))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(30))

    // Draw edges
    const link = g.append('g')
      .selectAll('line')
      .data(graphData.edges)
      .join('line')
      .attr('stroke', (d: any) => edgeColor(d))
      .attr('stroke-width', (d: any) => {
        if (d.risk === 'fraudulent') return 2
        if (d.risk === 'suspicious') return 1.5
        return 0.8
      })
      .attr('stroke-dasharray', (d: any) => d.risk === 'fraudulent' ? '4,2' : 'none')
      .attr('opacity', (d: any) => d.risk === 'safe' ? 0.3 : 0.8)

    // Draw nodes
    const node = g.append('g')
      .selectAll('g')
      .data(graphData.nodes)
      .join('g')
      .attr('cursor', 'pointer')
      .call(
        d3.drag<SVGGElement, GraphNode>()
          .on('start', (event, d) => {
            if (!event.active) simulation.alphaTarget(0.3).restart()
            d.fx = d.x; d.fy = d.y
          })
          .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y })
          .on('end', (event, d) => {
            if (!event.active) simulation.alphaTarget(0)
            d.fx = null; d.fy = null
          })
      )

    // Customer = circle, Merchant = rounded rect
    node.each(function(d) {
      const el = d3.select(this)
      if (d.type === 'customer') {
        el.append('circle')
          .attr('r', Math.min(8 + Math.log(d.txnCount + 1) * 3, 20))
          .attr('fill', nodeColor(d))
          .attr('fill-opacity', 0.85)
          .attr('stroke', d.risk === 'fraudulent' ? '#991B1B' : '#fff')
          .attr('stroke-width', d.risk === 'fraudulent' ? 2 : 1)
      } else {
        const size = Math.min(10 + Math.log(d.txnCount + 1) * 2, 18)
        el.append('rect')
          .attr('x', -size).attr('y', -size/2)
          .attr('width', size * 2).attr('height', size)
          .attr('rx', 4)
          .attr('fill', nodeColor(d))
          .attr('fill-opacity', 0.85)
          .attr('stroke', '#fff')
          .attr('stroke-width', 1)
      }
    })

    // Node labels (only for fraud/suspicious nodes to reduce clutter)
    node.filter((d: GraphNode) => d.risk !== 'safe' || d.txnCount > 3)
      .append('text')
      .text((d: GraphNode) => {
        const label = d.type === 'merchant' 
          ? d.id.replace('M:', '').substring(0, 12)
          : d.id
        return label
      })
      .attr('font-size', 9)
      .attr('fill', '#94A3B8')
      .attr('text-anchor', 'middle')
      .attr('dy', (d: GraphNode) => d.type === 'customer' ? 22 : 20)

    // Tooltip
    const tooltip = d3.select('body').append('div')
      .style('position', 'absolute')
      .style('background', '#1E293B')
      .style('color', '#F1F5F9')
      .style('padding', '8px 12px')
      .style('border-radius', '8px')
      .style('font-size', '12px')
      .style('pointer-events', 'none')
      .style('opacity', 0)
      .style('z-index', 9999)

    node
      .on('mouseover', (event, d: GraphNode) => {
        tooltip.transition().duration(150).style('opacity', 1)
        tooltip.html(`
          <div style="font-weight:600;margin-bottom:4px">${d.id.replace('M:','')}</div>
          <div>Type: ${d.type}</div>
          <div>Risk: <span style="color:${nodeColor(d)}">${d.risk.toUpperCase()}</span></div>
          <div>Transactions: ${d.txnCount}</div>
          <div>Volume: ₹${d.totalAmount.toLocaleString('en-IN')}</div>
          <div style="font-size:10px;color:#94A3B8;margin-top:4px">Click to view details →</div>
        `)
        .style('left', (event.pageX + 12) + 'px')
        .style('top', (event.pageY - 10) + 'px')
      })
      .on('mousemove', (event) => {
        tooltip
          .style('left', (event.pageX + 12) + 'px')
          .style('top', (event.pageY - 10) + 'px')
      })
      .on('mouseout', () => {
        tooltip.transition().duration(200).style('opacity', 0)
      })
      .on('click', function(event: any, d: GraphNode) {
        event.stopPropagation()
        tooltip.transition().duration(100).style('opacity', 0)
        // Call via ref — always reads latest transactions without D3 effect re-running
        handleNodeClickRef.current(d)

        // Highlight connected nodes
        const connectedIds = new Set<string>([d.id])
        graphData.edges.forEach((e: any) => {
          const srcId = typeof e.source === 'object' ? e.source.id : e.source
          const tgtId = typeof e.target === 'object' ? e.target.id : e.target
          if (srcId === d.id) connectedIds.add(tgtId)
          if (tgtId === d.id) connectedIds.add(srcId)
        })
        node.attr('opacity', (n: GraphNode) => connectedIds.has(n.id) ? 1 : 0.15)
        link.attr('opacity', (e: any) => {
          const srcId = typeof e.source === 'object' ? e.source.id : e.source
          const tgtId = typeof e.target === 'object' ? e.target.id : e.target
          return (connectedIds.has(srcId) && connectedIds.has(tgtId)) ? 0.9 : 0.05
        })
      })

    // Click empty canvas = close panel + reset
    svg.on('click', () => {
      setSelectedNode(null)
      node.attr('opacity', 1)
      link.attr('opacity', (d: any) => d.risk === 'safe' ? 0.3 : 0.8)
    })

    // Double-click SVG background to reset
    svg.on('dblclick.zoom', null).on('dblclick', () => {
      node.attr('opacity', 1)
      link.attr('opacity', (d: any) => d.risk === 'safe' ? 0.3 : 0.8)
      setSelectedNode(null)
    })

    // Simulation tick
    simulation.on('tick', () => {
      link
        .attr('x1', (d: any) => d.source.x)
        .attr('y1', (d: any) => d.source.y)
        .attr('x2', (d: any) => d.target.x)
        .attr('y2', (d: any) => d.target.y)
      node.attr('transform', (d: any) => `translate(${d.x},${d.y})`)
    })

    return () => {
      simulation.stop()
      tooltip.remove()
    }
  }, [graphData])

  const fraudNodes = graphData.nodes.filter(n => n.risk === 'fraudulent').length
  const suspNodes = graphData.nodes.filter(n => n.risk === 'suspicious').length

  return (
    <div style={{ display:'flex', flexDirection:'column', height:'100%', padding:'16px', gap:'12px' }}>
      {/* Stats bar */}
      <div style={{ display:'flex', gap:'16px', flexShrink:0 }}>
        <div style={{ background:'white', border:'1px solid #E2E8F0', borderRadius:'10px', padding:'10px 16px' }}>
          <div style={{ fontSize:'10px', color:'#94A3B8', fontWeight:700, letterSpacing:'0.5px' }}>TOTAL NODES</div>
          <div style={{ fontSize:'20px', fontWeight:800, color:'#0F172A' }}>{graphData.nodes.length}</div>
        </div>
        <div style={{ background:'white', border:'1px solid #E2E8F0', borderRadius:'10px', padding:'10px 16px' }}>
          <div style={{ fontSize:'10px', color:'#94A3B8', fontWeight:700, letterSpacing:'0.5px' }}>CONNECTIONS</div>
          <div style={{ fontSize:'20px', fontWeight:800, color:'#0F172A' }}>{graphData.edges.length}</div>
        </div>
        <div style={{ background:'white', border:'1px solid #E2E8F0', borderRadius:'10px', padding:'10px 16px' }}>
          <div style={{ fontSize:'10px', color:'#EF4444', fontWeight:700, letterSpacing:'0.5px' }}>FRAUD NODES</div>
          <div style={{ fontSize:'20px', fontWeight:800, color:'#EF4444' }}>{fraudNodes}</div>
        </div>
        <div style={{ background:'white', border:'1px solid #E2E8F0', borderRadius:'10px', padding:'10px 16px' }}>
          <div style={{ fontSize:'10px', color:'#F59E0B', fontWeight:700, letterSpacing:'0.5px' }}>SUSPICIOUS</div>
          <div style={{ fontSize:'20px', fontWeight:800, color:'#F59E0B' }}>{suspNodes}</div>
        </div>
        <div style={{ marginLeft:'auto', fontSize:'11px', color:'#94A3B8', alignSelf:'center' }}>
          Click node to view details · Double-click to reset · Drag to rearrange · Scroll to zoom
        </div>
      </div>

      {/* Graph + Detail Panel */}
      <div style={{ display: 'flex', gap: '12px', flex: 1, minHeight: 0 }}>
        {/* Graph canvas */}
        <div style={{
          flex: 1, background: '#0D1117', borderRadius: '12px',
          border: '1px solid #21262D', overflow: 'hidden', minHeight: '450px'
        }}>
          {graphData.nodes.length === 0 ? (
            <div style={{ display:'flex', alignItems:'center', justifyContent:'center', height:'100%', color:'#475569' }}>
              <div style={{ textAlign:'center' }}>
                <div style={{ fontSize:'14px', marginBottom:'8px' }}>Waiting for transactions...</div>
                <div style={{ fontSize:'12px' }}>Graph builds automatically as transactions stream in</div>
              </div>
            </div>
          ) : (
            <svg ref={svgRef} width="100%" height="100%" style={{ display: 'block', minHeight:'450px' }} />
          )}
        </div>

        {/* Node detail panel — slides in when node clicked */}
        {selectedNode && (
          <div style={{
            width: '340px', flexShrink: 0,
            background: 'white', border: '1px solid #E8ECF0',
            borderRadius: '12px', display: 'flex',
            flexDirection: 'column', overflow: 'hidden',
            animation: 'slideInRight 0.25s ease'
          }}>
            {/* Header */}
            <div style={{ padding: '14px 16px', borderBottom: '1px solid #F6F8FA', display: 'flex', justifyContent: 'space-between', flexShrink: 0 }}>
              <div>
                <div style={{ fontSize: '10px', color: '#57606A', fontWeight: 600, letterSpacing: '0.4px', marginBottom: '3px' }}>
                  {selectedNode.type === 'customer' ? 'CUSTOMER NODE' : 'MERCHANT NODE'}
                </div>
                <div style={{ fontSize: '15px', fontWeight: 800, color: '#0D1117' }}>
                  {selectedNode.id}
                </div>
                {selectedNode.riskSummary.fraud > 0 && (
                  <div style={{ marginTop: '4px', fontSize: '10px', fontWeight: 700, display: 'inline-block', padding: '2px 8px', borderRadius: '20px', background: '#FFEBE9', color: '#CF222E' }}>
                    ● {selectedNode.riskSummary.fraud} fraud · {selectedNode.riskSummary.suspicious} suspicious
                  </div>
                )}
              </div>
              <button onClick={() => setSelectedNode(null)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#57606A', fontSize: '20px' }}>×</button>
            </div>

            {/* Stats row */}
            <div style={{ padding: '10px 16px', borderBottom: '1px solid #F6F8FA', display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '6px', flexShrink: 0 }}>
              {[
                { l: 'Txns', v: selectedNode.riskSummary.total, c: '#0D1117', bg: '#F6F8FA' },
                { l: 'Fraud', v: selectedNode.riskSummary.fraud, c: '#CF222E', bg: '#FFEBE9' },
                { l: 'Susp.', v: selectedNode.riskSummary.suspicious, c: '#9A6700', bg: '#FFF8C5' },
                { l: 'Vol.', v: `₹${(selectedNode.riskSummary.totalAmount/1000).toFixed(0)}K`, c: '#1A7F37', bg: '#DAFBE1' },
              ].map(s => (
                <div key={s.l} style={{ background: s.bg, borderRadius: '6px', padding: '6px 8px', textAlign: 'center' }}>
                  <div style={{ fontSize: '9px', fontWeight: 700, color: s.c, opacity: 0.7 }}>{s.l}</div>
                  <div style={{ fontSize: '16px', fontWeight: 800, color: s.c }}>{s.v}</div>
                </div>
              ))}
            </div>

            {/* Top pattern */}
            {selectedNode.riskSummary.topPattern !== 'None' && (
              <div style={{ margin: '10px 16px 0', padding: '8px 12px', background: '#FFEBE9', border: '1px solid #FFCECB', borderRadius: '8px', flexShrink: 0 }}>
                <span style={{ fontSize: '10px', fontWeight: 700, color: '#CF222E' }}>Top fraud pattern: </span>
                <span style={{ fontSize: '10px', color: '#CF222E' }}>{selectedNode.riskSummary.topPattern}</span>
              </div>
            )}

            {/* Transaction list */}
            <div style={{ padding: '10px 16px 4px', fontSize: '10px', fontWeight: 700, color: '#57606A', letterSpacing: '0.4px', flexShrink: 0 }}>
              TRANSACTIONS — WHY EACH WAS MARKED
            </div>

            <div style={{ flex: 1, overflowY: 'auto', padding: '0 16px 12px' }}>
              {selectedNode.transactions.length === 0 ? (
                <div style={{ fontSize: '12px', color: '#8C959F', textAlign: 'center', padding: '20px' }}>
                  No transactions yet in this session
                </div>
              ) : selectedNode.transactions.map((t: any, i: number) => {
                const isF = t.risk_level === 'fraudulent'
                const isS = t.risk_level === 'suspicious'
                const bc = isF ? '#CF222E' : isS ? '#9A6700' : '#1A7F37'
                const bg2 = isF ? '#FFEBE9' : isS ? '#FFF8C5' : '#DAFBE1'
                return (
                  <div key={i} style={{
                    marginBottom: '8px', background: '#F6F8FA',
                    border: '1px solid #E8ECF0', borderLeft: `3px solid ${bc}`,
                    borderRadius: '8px', padding: '10px 12px'
                  }}>
                    {/* Merchant + amount + score */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '5px' }}>
                      <div>
                        <div style={{ fontSize: '12px', fontWeight: 700, color: '#0D1117' }}>
                          {selectedNode.type === 'customer' ? t.merchant : t.customer_id}
                        </div>
                        <div style={{ fontSize: '13px', fontWeight: 800, color: '#0D1117', fontVariantNumeric: 'tabular-nums' }}>
                          ₹{t.amount?.toLocaleString('en-IN')}
                        </div>
                      </div>
                      <div style={{ textAlign: 'right' }}>
                        <div style={{ fontSize: '18px', fontWeight: 800, color: bc, fontVariantNumeric: 'tabular-nums' }}>{t.risk_score?.toFixed(1)}</div>
                        <div style={{ fontSize: '9px', fontWeight: 700, padding: '1px 6px', borderRadius: '4px', background: bg2, color: bc }}>{t.risk_level?.toUpperCase()}</div>
                      </div>
                    </div>

                    {/* Why flagged */}
                    {t.scenario_description && t.scenario_description !== 'Normal transaction' && t.scenario_description !== 'No anomalies detected' ? (
                      <div style={{ padding: '6px 8px', background: bg2, borderRadius: '5px', marginBottom: '6px', fontSize: '10px', color: bc, fontStyle: 'italic' }}>
                        "{t.scenario_description}"
                      </div>
                    ) : t.risk_level === 'safe' ? (
                      <div style={{ padding: '6px 8px', background: '#DAFBE1', borderRadius: '5px', marginBottom: '6px', fontSize: '10px', color: '#1A7F37', fontStyle: 'italic' }}>
                        No anomalies — approved
                      </div>
                    ) : null}

                    {/* Rules */}
                    {t.rule_names?.length > 0 && (
                      <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', marginBottom: '5px' }}>
                        {t.rule_names.map((r: string, ri: number) => (
                          <span key={ri} style={{ fontSize: '9px', fontWeight: 700, padding: '1px 6px', borderRadius: '4px', background: '#FFEBE9', color: '#CF222E', border: '1px solid #FFCECB' }}>{r}</span>
                        ))}
                      </div>
                    )}

                    {/* City + time + action */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: '10px', color: '#57606A' }}>
                        {t.city} · {t.timestamp ? new Date(t.timestamp).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }) : ''}
                      </span>
                      <span style={{ fontSize: '9px', fontWeight: 700, padding: '2px 7px', borderRadius: '4px', background: '#DDF4FF', color: '#0969DA' }}>
                        {t.action?.replace(/_/g, ' ').toUpperCase()}
                      </span>
                    </div>
                  </div>
                )
              })}
            </div>

            {/* Footer actions */}
            {selectedNode.riskSummary.fraud > 0 && (
              <div style={{ padding: '12px 16px', borderTop: '1px solid #F6F8FA', display: 'flex', gap: '8px', flexShrink: 0 }}>
                <button onClick={() => { alert(`Network flagged: ${selectedNode.id}`); setSelectedNode(null) }}
                  style={{ flex: 1, padding: '9px', background: '#CF222E', color: 'white', border: 'none', borderRadius: '8px', fontSize: '12px', fontWeight: 700, cursor: 'pointer' }}>
                  Flag Network
                </button>
                <button onClick={() => setSelectedNode(null)}
                  style={{ flex: 1, padding: '9px', background: '#F6F8FA', color: '#57606A', border: '1px solid #E8ECF0', borderRadius: '8px', fontSize: '12px', fontWeight: 600, cursor: 'pointer' }}>
                  Dismiss
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
