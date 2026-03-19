import { useEffect, useState } from 'react'
import { useSelector } from 'react-redux'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  AreaChart, Area, PieChart, Pie, Cell, Legend, LineChart, Line,
} from 'recharts'
import { fetchModelMetrics, fetchModelHealth, fetchPrometheusMetrics } from '../services/api'

const COLORS = ['#53e2a1', '#f6c667', '#ff5f8f', '#6be8ff', '#d4a0ff']

function MetricCard({ label, value, unit = '', color = '#6be8ff', subtitle }) {
  return (
    <div className="soc-card kpi">
      <span style={{ fontSize: '0.72rem', color: 'var(--muted)' }}>{label}</span>
      <h3 style={{ color, margin: '0.2rem 0 0' }}>
        {value != null ? `${Number(value).toFixed(2)}${unit}` : '—'}
      </h3>
      {subtitle && <span style={{ fontSize: '0.65rem', color: 'var(--muted)' }}>{subtitle}</span>}
    </div>
  )
}

export default function EnhancedModelPerformance() {
  const modelMetrics = useSelector((s) => s.platform.modelMetrics)
  const modelHealth = useSelector((s) => s.platform.modelHealth)
  const [liveMetrics, setLiveMetrics] = useState(null)
  const [metricsHistory, setMetricsHistory] = useState([])
  const [refreshCount, setRefreshCount] = useState(0)

  useEffect(() => {
    let active = true
    const poll = async () => {
      try {
        const [metrics, health, prom] = await Promise.all([
          fetchModelMetrics().catch(() => null),
          fetchModelHealth().catch(() => null),
          fetchPrometheusMetrics().catch(() => null),
        ])
        if (!active) return
        setLiveMetrics({ metrics, health, prom })
        setMetricsHistory((prev) => {
          const entry = {
            time: new Date().toLocaleTimeString(),
            accuracy: metrics?.best_model?.accuracy || metrics?.accuracy || 0,
            precision: metrics?.best_model?.precision || metrics?.precision || 0,
            recall: metrics?.best_model?.recall || metrics?.recall || 0,
            f1: metrics?.best_model?.f1_score || metrics?.f1_score || 0,
          }
          return [...prev.slice(-29), entry]
        })
        setRefreshCount((c) => c + 1)
      } catch { /* noop */ }
    }
    poll()
    const id = setInterval(poll, 15000)
    return () => { active = false; clearInterval(id) }
  }, [])

  const best = modelMetrics?.best_model || modelMetrics || {}
  const cm = best.confusion_matrix || [[0, 0], [0, 0]]
  const tp = cm[1]?.[1] || 0, tn = cm[0]?.[0] || 0, fp = cm[0]?.[1] || 0, fn = cm[1]?.[0] || 0

  const rocData = (best.roc_curve || []).map((p, i) => ({
    fpr: p[0] ?? p.fpr ?? 0,
    tpr: p[1] ?? p.tpr ?? 0,
    index: i,
  }))

  const featureImportance = (best.feature_importance || [])
    .slice(0, 12)
    .map((f) => ({
      name: typeof f === 'string' ? f : f.feature || f.name || 'F?',
      importance: typeof f === 'number' ? f : f.importance || f.value || 0,
    }))
    .sort((a, b) => b.importance - a.importance)

  const pieData = [
    { name: 'True Positive', value: tp },
    { name: 'True Negative', value: tn },
    { name: 'False Positive', value: fp },
    { name: 'False Negative', value: fn },
  ].filter((d) => d.value > 0)

  const health = liveMetrics?.health || modelHealth || {}
  const prom = liveMetrics?.prom || {}

  // Champion vs Challenger mock — real data comes from model registry endpoint
  const champion = {
    name: health.model_name || best.model_name || 'Champion',
    accuracy: best.accuracy || 0,
    precision: best.precision || 0,
    recall: best.recall || 0,
    f1: best.f1_score || best.f1 || 0,
    auc: best.roc_auc || 0,
  }
  const challenger = modelMetrics?.challenger || null

  const comparisonData = challenger ? [
    { metric: 'Accuracy', champion: champion.accuracy * 100, challenger: challenger.accuracy * 100 },
    { metric: 'Precision', champion: champion.precision * 100, challenger: challenger.precision * 100 },
    { metric: 'Recall', champion: champion.recall * 100, challenger: challenger.recall * 100 },
    { metric: 'F1', champion: champion.f1 * 100, challenger: challenger.f1 * 100 },
    { metric: 'AUC', champion: champion.auc * 100, challenger: challenger.auc * 100 },
  ] : null

  return (
    <div className="soc-grid" style={{ gap: '1rem' }}>
      {/* Header */}
      <div className="soc-card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap' }}>
        <div>
          <h2 style={{ margin: 0, fontSize: '1.1rem' }}>📈 Enhanced Model Performance</h2>
          <p style={{ margin: '0.2rem 0 0', color: 'var(--muted)', fontSize: '0.82rem' }}>
            Live model metrics with champion vs challenger tracking — auto-refreshes every 15s
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <span className="soc-pill">Refreshes: {refreshCount}</span>
          {health.drift_detected != null && (
            <span className="soc-pill" style={{ color: health.drift_detected ? '#ff5f8f' : '#53e2a1' }}>
              Drift: {health.drift_detected ? 'DETECTED' : 'None'}
            </span>
          )}
          {health.model_status && (
            <span className={`soc-pill status-${health.model_status}`}>Model: {health.model_status}</span>
          )}
        </div>
      </div>

      {/* KPI Row */}
      <div className="soc-grid-kpi" style={{ gridTemplateColumns: 'repeat(6, 1fr)' }}>
        <MetricCard label="Accuracy" value={(champion.accuracy || 0) * 100} unit="%" color="#6be8ff" />
        <MetricCard label="Precision" value={(champion.precision || 0) * 100} unit="%" color="#53e2a1" />
        <MetricCard label="Recall" value={(champion.recall || 0) * 100} unit="%" color="#f6c667" />
        <MetricCard label="F1 Score" value={(champion.f1 || 0) * 100} unit="%" color="#d4a0ff" />
        <MetricCard label="ROC AUC" value={(champion.auc || 0) * 100} unit="%" color="#ff5f8f" />
        <MetricCard
          label="Pred Latency"
          value={prom?.model_prediction_latency_avg_ms || health?.avg_latency_ms}
          unit="ms"
          color="#6be8ff"
          subtitle="avg per prediction"
        />
      </div>

      {/* Live Metrics Timeline */}
      {metricsHistory.length > 1 && (
        <div className="soc-card">
          <h2 style={{ fontSize: '0.95rem' }}>Live Metrics Timeline</h2>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={metricsHistory}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
              <XAxis dataKey="time" stroke="#4a6080" tick={{ fill: '#89a0c6', fontSize: 9 }} />
              <YAxis stroke="#4a6080" tick={{ fill: '#89a0c6', fontSize: 10 }} domain={[0, 1]} />
              <Tooltip contentStyle={{ background: '#0d1529', border: '1px solid rgba(104,133,184,0.35)', borderRadius: 8, color: '#dde9ff' }} />
              <Line type="monotone" dataKey="accuracy" stroke="#6be8ff" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="precision" stroke="#53e2a1" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="recall" stroke="#f6c667" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="f1" stroke="#d4a0ff" strokeWidth={2} dot={false} />
              <Legend wrapperStyle={{ fontSize: '0.72rem', color: '#89a0c6' }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Champion vs Challenger */}
      {comparisonData && (
        <div className="soc-card">
          <h2 style={{ fontSize: '0.95rem' }}>Champion vs Challenger</h2>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={comparisonData}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
              <XAxis dataKey="metric" stroke="#4a6080" tick={{ fill: '#89a0c6', fontSize: 10 }} />
              <YAxis stroke="#4a6080" tick={{ fill: '#89a0c6', fontSize: 10 }} domain={[0, 100]} />
              <Tooltip contentStyle={{ background: '#0d1529', border: '1px solid rgba(104,133,184,0.35)', borderRadius: 8, color: '#dde9ff' }} />
              <Bar dataKey="champion" fill="#6be8ff" name="Champion" radius={[4, 4, 0, 0]} />
              <Bar dataKey="challenger" fill="#d4a0ff" name="Challenger" radius={[4, 4, 0, 0]} />
              <Legend wrapperStyle={{ fontSize: '0.72rem', color: '#89a0c6' }} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
        {/* ROC Curve */}
        <div className="soc-card">
          <h2 style={{ fontSize: '0.95rem' }}>ROC Curve</h2>
          {rocData.length > 0 ? (
            <ResponsiveContainer width="100%" height={260}>
              <AreaChart data={rocData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                <XAxis dataKey="fpr" stroke="#4a6080" tick={{ fill: '#89a0c6', fontSize: 10 }} label={{ value: 'FPR', position: 'bottom', fill: '#89a0c6', fontSize: 11 }} />
                <YAxis stroke="#4a6080" tick={{ fill: '#89a0c6', fontSize: 10 }} label={{ value: 'TPR', angle: -90, position: 'left', fill: '#89a0c6', fontSize: 11 }} />
                <Tooltip contentStyle={{ background: '#0d1529', border: '1px solid rgba(104,133,184,0.35)', borderRadius: 8, color: '#dde9ff' }} />
                <Area type="monotone" dataKey="tpr" stroke="#6be8ff" fill="rgba(107,232,255,0.15)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          ) : <p style={{ color: 'var(--muted)', textAlign: 'center' }}>No ROC data</p>}
        </div>

        {/* Confusion Matrix */}
        <div className="soc-card">
          <h2 style={{ fontSize: '0.95rem' }}>Confusion Matrix</h2>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.6rem', maxWidth: '280px', margin: '1rem auto' }}>
            {[
              { label: 'TN', value: tn, bg: 'rgba(83,226,161,0.12)', border: 'rgba(83,226,161,0.3)', color: '#53e2a1' },
              { label: 'FP', value: fp, bg: 'rgba(255,95,143,0.12)', border: 'rgba(255,95,143,0.3)', color: '#ff5f8f' },
              { label: 'FN', value: fn, bg: 'rgba(246,198,103,0.12)', border: 'rgba(246,198,103,0.3)', color: '#f6c667' },
              { label: 'TP', value: tp, bg: 'rgba(107,232,255,0.12)', border: 'rgba(107,232,255,0.3)', color: '#6be8ff' },
            ].map((c) => (
              <div key={c.label} className="cm-cell" style={{ background: c.bg, borderColor: c.border, color: c.color }}>
                <div style={{ fontSize: '0.7rem', color: 'var(--muted)' }}>{c.label}</div>
                <div style={{ fontSize: '1.4rem' }}>{c.value}</div>
              </div>
            ))}
          </div>
          {pieData.length > 0 && (
            <ResponsiveContainer width="100%" height={160}>
              <PieChart>
                <Pie data={pieData} cx="50%" cy="50%" innerRadius={40} outerRadius={60} dataKey="value" paddingAngle={3}>
                  {pieData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Legend wrapperStyle={{ fontSize: '0.7rem', color: '#89a0c6' }} />
                <Tooltip contentStyle={{ background: '#0d1529', border: '1px solid rgba(104,133,184,0.35)', borderRadius: 8, color: '#dde9ff', fontSize: '0.8rem' }} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Feature Importance */}
      {featureImportance.length > 0 && (
        <div className="soc-card">
          <h2 style={{ fontSize: '0.95rem' }}>Feature Importance</h2>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={featureImportance} layout="vertical" margin={{ left: 120 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
              <XAxis type="number" stroke="#4a6080" tick={{ fill: '#89a0c6', fontSize: 10 }} />
              <YAxis type="category" dataKey="name" stroke="#4a6080" tick={{ fill: '#89a0c6', fontSize: 10 }} width={115} />
              <Tooltip contentStyle={{ background: '#0d1529', border: '1px solid rgba(104,133,184,0.35)', borderRadius: 8, color: '#dde9ff' }} />
              <Bar dataKey="importance" fill="#6be8ff" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* System Metrics from Prometheus */}
      {prom && Object.keys(prom).length > 0 && (
        <div className="soc-card">
          <h2 style={{ fontSize: '0.95rem' }}>System Metrics</h2>
          <div className="soc-grid-kpi" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
            {prom.fraud_decisions_total != null && (
              <MetricCard label="Total Decisions" value={prom.fraud_decisions_total} color="#6be8ff" />
            )}
            {prom.http_requests_total != null && (
              <MetricCard label="HTTP Requests" value={prom.http_requests_total} color="#53e2a1" />
            )}
            {prom.fraud_detection_latency_avg_ms != null && (
              <MetricCard label="Detection Latency" value={prom.fraud_detection_latency_avg_ms} unit="ms" color="#f6c667" />
            )}
            {prom.active_websocket_connections != null && (
              <MetricCard label="WS Connections" value={prom.active_websocket_connections} color="#d4a0ff" />
            )}
          </div>
        </div>
      )}
    </div>
  )
}
