import { useEffect, useState, useMemo } from 'react'
import { useSelector } from 'react-redux'
import {
  AreaChart, Area, ResponsiveContainer, Tooltip, XAxis, YAxis,
  BarChart, Bar, CartesianGrid, PieChart, Pie, Cell, Legend,
} from 'recharts'
import { fetchFraudStats, fetchCases, fetchModelMetrics, fetchPrometheusMetrics } from '../services/api'

const COLORS = ['#53e2a1', '#f6c667', '#ff5f8f', '#6be8ff', '#d4a0ff']

function Sparkline({ data, dataKey, color = '#6be8ff', height = 40 }) {
  if (!data?.length) return <div style={{ height, opacity: 0.3, fontSize: '0.7rem', color: 'var(--muted)' }}>No data</div>
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data}>
        <Area type="monotone" dataKey={dataKey} stroke={color} fill={`${color}22`} strokeWidth={1.5} dot={false} />
      </AreaChart>
    </ResponsiveContainer>
  )
}

function KpiCard({ label, value, unit = '', color = '#6be8ff', sparkData, sparkKey, subtitle, icon }) {
  return (
    <div className="soc-card kpi" style={{ padding: '0.8rem 1rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
        <span style={{ fontSize: '0.72rem', color: 'var(--muted)' }}>{icon} {label}</span>
      </div>
      <h3 style={{ color, margin: '0.3rem 0 0.2rem', fontSize: '1.5rem' }}>
        {value != null ? `${typeof value === 'number' ? value.toLocaleString() : value}${unit}` : '—'}
      </h3>
      {subtitle && <span style={{ fontSize: '0.65rem', color: 'var(--muted)' }}>{subtitle}</span>}
      {sparkData && sparkKey && (
        <div style={{ marginTop: '0.4rem' }}>
          <Sparkline data={sparkData} dataKey={sparkKey} color={color} />
        </div>
      )}
    </div>
  )
}

export default function KPISummary() {
  const stats = useSelector((s) => s.platform.stats)
  const transactions = useSelector((s) => s.platform.transactions)
  const alerts = useSelector((s) => s.platform.alerts)
  const modelMetrics = useSelector((s) => s.platform.modelMetrics)
  const txPerSec = useSelector((s) => s.platform.txPerSec)
  const txPerMin = useSelector((s) => s.platform.txPerMin)

  const [caseStats, setCaseStats] = useState({ open: 0, investigating: 0, resolved: 0 })
  const [liveStats, setLiveStats] = useState(null)
  const [statsHistory, setStatsHistory] = useState([])

  useEffect(() => {
    let active = true
    const poll = async () => {
      try {
        const [st, cases, prom] = await Promise.all([
          fetchFraudStats().catch(() => null),
          fetchCases(null, 500).catch(() => []),
          fetchPrometheusMetrics().catch(() => null),
        ])
        if (!active) return
        setLiveStats({ ...st, prom })
        const cArr = Array.isArray(cases) ? cases : cases?.cases || []
        setCaseStats({
          open: cArr.filter((c) => c.status === 'OPEN').length,
          investigating: cArr.filter((c) => c.status === 'INVESTIGATING').length,
          resolved: cArr.filter((c) => c.status === 'RESOLVED').length,
        })
        setStatsHistory((prev) => {
          const entry = {
            time: new Date().toLocaleTimeString(),
            fraud_rate: st?.fraud_rate || stats.fraud_rate || 0,
            total: st?.total_transactions || stats.total_transactions || 0,
            fraud: st?.fraud || stats.fraud || 0,
          }
          return [...prev.slice(-29), entry]
        })
      } catch { /* noop */ }
    }
    poll()
    const id = setInterval(poll, 15000)
    return () => { active = false; clearInterval(id) }
  }, [stats.fraud_rate, stats.total_transactions, stats.fraud])

  // Computed KPIs
  const totalTx = liveStats?.total_transactions || stats.total_transactions || 0
  const fraudRate = liveStats?.fraud_rate || stats.fraud_rate || 0
  const avgRisk = useMemo(() => {
    if (!transactions.length) return 0
    return transactions.reduce((s, tx) => s + (tx.risk_score || 0), 0) / transactions.length
  }, [transactions])
  const casesPending = caseStats.open + caseStats.investigating
  const best = modelMetrics?.best_model || modelMetrics || {}
  const modelAccuracy = (best.accuracy || 0) * 100
  const fraudPrevented = useMemo(() => {
    return transactions
      .filter((tx) => tx.risk_category === 'FRAUD' || tx.risk_category === 'SUSPICIOUS')
      .reduce((s, tx) => s + (tx.amount || 0), 0)
  }, [transactions])

  // Distribution for pie chart
  const riskDistribution = useMemo(() => {
    const counts = { SAFE: 0, SUSPICIOUS: 0, FRAUD: 0 }
    transactions.forEach((tx) => { counts[tx.risk_category || 'SAFE'] = (counts[tx.risk_category || 'SAFE'] || 0) + 1 })
    return Object.entries(counts).map(([name, value]) => ({ name, value })).filter((d) => d.value > 0)
  }, [transactions])

  // Hourly fraud rate for bar chart
  const hourlyFraud = useMemo(() => {
    const hours = {}
    transactions.forEach((tx) => {
      const h = tx.timestamp ? new Date(tx.timestamp).getHours() : 0
      if (!hours[h]) hours[h] = { hour: `${h}:00`, total: 0, fraud: 0 }
      hours[h].total += 1
      if (tx.risk_category === 'FRAUD') hours[h].fraud += 1
    })
    return Object.values(hours).sort((a, b) => parseInt(a.hour) - parseInt(b.hour))
  }, [transactions])

  return (
    <div className="soc-grid" style={{ gap: '1rem' }}>
      {/* Header */}
      <div className="soc-card">
        <h2 style={{ margin: 0, fontSize: '1.1rem' }}>📊 KPI Summary Dashboard</h2>
        <p style={{ margin: '0.2rem 0 0', color: 'var(--muted)', fontSize: '0.82rem' }}>
          Key performance indicators with live sparklines — auto-refreshes every 15s
        </p>
      </div>

      {/* KPI Cards Row */}
      <div className="soc-grid-kpi" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
        <KpiCard
          label="Total Transactions Today"
          value={totalTx}
          color="#6be8ff"
          icon="📦"
          sparkData={statsHistory}
          sparkKey="total"
          subtitle={`${txPerSec} tx/s · ${txPerMin} tx/min`}
        />
        <KpiCard
          label="Fraud Rate"
          value={Number(fraudRate).toFixed(2)}
          unit="%"
          color={fraudRate > 5 ? '#ff5f8f' : fraudRate > 2 ? '#f6c667' : '#53e2a1'}
          icon="🚨"
          sparkData={statsHistory}
          sparkKey="fraud_rate"
          subtitle={`${stats.fraud || 0} fraud + ${stats.suspicious || 0} suspicious`}
        />
        <KpiCard
          label="Avg Risk Score"
          value={Number(avgRisk).toFixed(4)}
          color={avgRisk > 0.5 ? '#ff5f8f' : avgRisk > 0.3 ? '#f6c667' : '#53e2a1'}
          icon="⚠️"
          subtitle={`Based on ${transactions.length} recent transactions`}
        />
      </div>

      <div className="soc-grid-kpi" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
        <KpiCard
          label="Cases Pending"
          value={casesPending}
          color={casesPending > 10 ? '#ff5f8f' : casesPending > 5 ? '#f6c667' : '#6be8ff'}
          icon="📋"
          subtitle={`${caseStats.open} open · ${caseStats.investigating} investigating · ${caseStats.resolved} resolved`}
        />
        <KpiCard
          label="Model Accuracy"
          value={Number(modelAccuracy).toFixed(1)}
          unit="%"
          color={modelAccuracy > 90 ? '#53e2a1' : modelAccuracy > 70 ? '#f6c667' : '#ff5f8f'}
          icon="🎯"
          subtitle={best.model_name || 'Current production model'}
        />
        <KpiCard
          label="Fraud $ Prevented"
          value={`$${Number(fraudPrevented).toLocaleString(undefined, { maximumFractionDigits: 0 })}`}
          color="#53e2a1"
          icon="🛡️"
          sparkData={statsHistory}
          sparkKey="fraud"
          subtitle="Blocked fraud + suspicious transactions"
        />
      </div>

      {/* Charts Row */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '1rem' }}>
        {/* Fraud Rate Timeline */}
        <div className="soc-card">
          <h2 style={{ fontSize: '0.95rem' }}>Fraud Rate Timeline</h2>
          {statsHistory.length > 1 ? (
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={statsHistory}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                <XAxis dataKey="time" stroke="#4a6080" tick={{ fill: '#89a0c6', fontSize: 9 }} />
                <YAxis stroke="#4a6080" tick={{ fill: '#89a0c6', fontSize: 10 }} />
                <Tooltip contentStyle={{ background: '#0d1529', border: '1px solid rgba(104,133,184,0.35)', borderRadius: 8, color: '#dde9ff' }} />
                <Area type="monotone" dataKey="fraud_rate" stroke="#ff5f8f" fill="rgba(255,95,143,0.15)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          ) : <p style={{ color: 'var(--muted)', textAlign: 'center' }}>Collecting data…</p>}
        </div>

        {/* Risk Distribution */}
        <div className="soc-card">
          <h2 style={{ fontSize: '0.95rem' }}>Risk Distribution</h2>
          {riskDistribution.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={riskDistribution} cx="50%" cy="50%" innerRadius={50} outerRadius={75} dataKey="value" paddingAngle={3}>
                  <Cell fill="#53e2a1" />
                  <Cell fill="#f6c667" />
                  <Cell fill="#ff5f8f" />
                </Pie>
                <Legend wrapperStyle={{ fontSize: '0.72rem', color: '#89a0c6' }} />
                <Tooltip contentStyle={{ background: '#0d1529', border: '1px solid rgba(104,133,184,0.35)', borderRadius: 8, color: '#dde9ff', fontSize: '0.8rem' }} />
              </PieChart>
            </ResponsiveContainer>
          ) : <p style={{ color: 'var(--muted)', textAlign: 'center' }}>No data</p>}
        </div>
      </div>

      {/* Hourly Fraud Distribution */}
      {hourlyFraud.length > 0 && (
        <div className="soc-card">
          <h2 style={{ fontSize: '0.95rem' }}>Hourly Fraud Distribution</h2>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={hourlyFraud}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
              <XAxis dataKey="hour" stroke="#4a6080" tick={{ fill: '#89a0c6', fontSize: 9 }} />
              <YAxis stroke="#4a6080" tick={{ fill: '#89a0c6', fontSize: 10 }} />
              <Tooltip contentStyle={{ background: '#0d1529', border: '1px solid rgba(104,133,184,0.35)', borderRadius: 8, color: '#dde9ff' }} />
              <Bar dataKey="total" fill="rgba(107,232,255,0.3)" name="Total" radius={[4, 4, 0, 0]} />
              <Bar dataKey="fraud" fill="#ff5f8f" name="Fraud" radius={[4, 4, 0, 0]} />
              <Legend wrapperStyle={{ fontSize: '0.72rem', color: '#89a0c6' }} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Alert Summary */}
      <div className="soc-card">
        <h2 style={{ fontSize: '0.95rem' }}>Recent Alerts</h2>
        <div className="soc-table-wrap" style={{ maxHeight: '25vh', overflowY: 'auto' }}>
          <table className="soc-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Alert</th>
                <th>Severity</th>
                <th>Transaction</th>
                <th>Amount</th>
              </tr>
            </thead>
            <tbody>
              {alerts.slice(0, 15).map((a, i) => (
                <tr key={a.alert_id || i}>
                  <td>{a.created_at ? new Date(a.created_at).toLocaleTimeString() : a.received_at ? new Date(a.received_at).toLocaleTimeString() : '—'}</td>
                  <td>#{a.alert_id || i}</td>
                  <td>
                    <span style={{ color: a.severity === 'CRITICAL' ? '#ff5f8f' : a.severity === 'HIGH' ? '#f6c667' : '#6be8ff' }}>
                      {a.severity || a.alert_type || '—'}
                    </span>
                  </td>
                  <td style={{ fontSize: '0.7rem' }}>{(a.transaction_id || '—').slice(0, 12)}</td>
                  <td>${Number(a.amount || 0).toLocaleString()}</td>
                </tr>
              ))}
              {alerts.length === 0 && (
                <tr><td colSpan={5} style={{ textAlign: 'center', color: 'var(--muted)' }}>No recent alerts</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
