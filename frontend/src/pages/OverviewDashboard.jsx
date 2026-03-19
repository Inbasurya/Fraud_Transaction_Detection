import { useEffect, useMemo, useState } from 'react'
import { useSelector } from 'react-redux'
import { explainTransaction, fetchAccountDetail } from '../services/api'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

function Kpi({ label, value, tone = 'neutral' }) {
  return (
    <article className={`soc-card kpi ${tone}`}>
      <span>{label}</span>
      <h3>{value}</h3>
    </article>
  )
}

function InvestigationModal({ tx, onClose }) {
  const [loading, setLoading] = useState(false)
  const [explain, setExplain] = useState(null)
  const [history, setHistory] = useState([])

  useEffect(() => {
    let active = true
    const load = async () => {
      if (!tx?.transaction_id) return
      setLoading(true)
      try {
        const [exp, detail] = await Promise.all([
          explainTransaction(tx.transaction_id),
          fetchAccountDetail(tx.user_id),
        ])
        if (!active) return
        setExplain(exp)
        setHistory((detail?.recent_transactions || []).slice(0, 8))
      } finally {
        if (active) setLoading(false)
      }
    }
    load()
    return () => {
      active = false
    }
  }, [tx])

  if (!tx) return null
  return (
    <div className="soc-modal-backdrop" onClick={onClose}>
      <div className="soc-modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="panel-head">
          <h2>Fraud Investigation</h2>
          <button className="soc-btn" onClick={onClose}>Close</button>
        </div>
        <p><strong>Transaction:</strong> {tx.transaction_id}</p>
        <p><strong>Account:</strong> U{tx.user_id}</p>
        <p><strong>Amount:</strong> ${Number(tx.amount || 0).toLocaleString()}</p>
        <p><strong>Risk Score:</strong> {Number(tx.risk_score || 0).toFixed(4)}</p>
        <p><strong>Behavior Score:</strong> {Number(tx.behavior_score || tx.behavior_anomaly_score || 0).toFixed(4)}</p>
        <p><strong>Rule Triggers:</strong> {(tx.reasons || []).join(', ') || 'None'}</p>
        {loading ? <p>Loading SHAP explanation...</p> : null}
        {explain?.feature_contributions?.length ? (
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={explain.feature_contributions}>
              <XAxis dataKey="feature" stroke="#8ca0bf" />
              <YAxis stroke="#8ca0bf" />
              <Tooltip />
              <Bar dataKey="impact" fill="#6be8ff" />
            </BarChart>
          </ResponsiveContainer>
        ) : null}
        {history.length ? (
          <>
            <p><strong>Account History</strong></p>
            <ul>
              {history.map((row) => (
                <li key={row.transaction_id}>
                  {row.transaction_id} | ${Number(row.amount || 0).toLocaleString()} | {row.risk_category || 'SAFE'}
                </li>
              ))}
            </ul>
          </>
        ) : null}
      </div>
    </div>
  )
}

export default function OverviewDashboard() {
  const stats = useSelector((s) => s.platform.stats)
  const transactions = useSelector((s) => s.platform.transactions)
  const [investigatingTx, setInvestigatingTx] = useState(null)

  const riskTimeline = useMemo(
    () =>
      transactions
        .slice(0, 50)
        .reverse()
        .map((tx, idx) => ({
          idx,
          risk: Number(tx.risk_score || 0),
        })),
    [transactions],
  )

  const distribution = [
    { label: 'SAFE', value: stats.safe || 0 },
    { label: 'SUSPICIOUS', value: stats.suspicious || 0 },
    { label: 'FRAUD', value: stats.fraud || 0 },
  ]

  return (
    <section className="soc-grid">
      <div className="soc-grid-kpi">
        <Kpi label="Total Transactions" value={stats.total_transactions || 0} />
        <Kpi label="Fraud" value={stats.fraud || 0} tone="danger" />
        <Kpi label="Suspicious" value={stats.suspicious || 0} tone="warn" />
        <Kpi label="Open Alerts" value={stats.open_alerts || 0} tone="accent" />
      </div>

      <article className="soc-card chart-card">
        <h2>Live Risk Timeline</h2>
        <ResponsiveContainer width="100%" height={260}>
          <AreaChart data={riskTimeline}>
            <defs>
              <linearGradient id="riskGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#ff5f8f" stopOpacity={0.65} />
                <stop offset="100%" stopColor="#ff5f8f" stopOpacity={0.05} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="4 4" stroke="#213046" />
            <XAxis dataKey="idx" stroke="#8ca0bf" />
            <YAxis domain={[0, 1]} stroke="#8ca0bf" />
            <Tooltip />
            <Area
              type="monotone"
              dataKey="risk"
              stroke="#ff5f8f"
              fill="url(#riskGrad)"
              isAnimationActive
              animationDuration={1200}
              animationEasing="ease-out"
            />
          </AreaChart>
        </ResponsiveContainer>
      </article>

      <article className="soc-card chart-card">
        <h2>Risk Distribution</h2>
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={distribution}>
            <CartesianGrid strokeDasharray="4 4" stroke="#213046" />
            <XAxis dataKey="label" stroke="#8ca0bf" />
            <YAxis stroke="#8ca0bf" />
            <Tooltip />
            <Bar dataKey="value" fill="#53e2a1" radius={[8, 8, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </article>

      <article className="soc-card table-card">
        <h2>Real-Time Transaction Feed</h2>
        <div className="soc-table-wrap">
          <table className="soc-table">
            <thead>
              <tr>
                <th>TX ID</th>
                <th>User</th>
                <th>Amount</th>
                <th>Risk</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {transactions.slice(0, 15).map((tx) => (
                <tr key={tx.transaction_id} onClick={() => setInvestigatingTx(tx)} style={{ cursor: 'pointer' }}>
                  <td>{tx.transaction_id}</td>
                  <td>U{tx.user_id}</td>
                  <td>${Number(tx.amount || 0).toLocaleString()}</td>
                  <td>{Number(tx.risk_score || 0).toFixed(3)}</td>
                  <td>
                    <span className={`risk-badge ${String(tx.risk_category || 'SAFE').toLowerCase()}`}>
                      {tx.risk_category || 'SAFE'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </article>
      <InvestigationModal tx={investigatingTx} onClose={() => setInvestigatingTx(null)} />
    </section>
  )
}
