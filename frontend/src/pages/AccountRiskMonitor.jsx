import { useMemo, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { fetchAccountRiskTrend } from '../services/api'
import { setAccountRiskTrend, setSelectedAccountId } from '../store/platformSlice'

function Sparkline({ avgRisk, maxRisk }) {
  const values = [
    Number(avgRisk || 0) * 0.65,
    Number(avgRisk || 0) * 0.78,
    Number(avgRisk || 0) * 0.92,
    Number(maxRisk || avgRisk || 0),
  ]
  const points = values.map((v, i) => `${i * 16},${24 - v * 20}`).join(' ')
  return (
    <svg width="56" height="24" viewBox="0 0 56 24" aria-hidden>
      <polyline fill="none" stroke="#6be8ff" strokeWidth="2" points={points} />
    </svg>
  )
}

export default function AccountRiskMonitor() {
  const dispatch = useDispatch()
  const accounts = useSelector((s) => s.platform.accounts)
  const selectedAccountId = useSelector((s) => s.platform.selectedAccountId)
  const trend = useSelector((s) => s.platform.accountRiskTrend)
  const [query, setQuery] = useState('')

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return accounts
    return accounts.filter((a) => String(a.user_id).includes(q) || String(a.risk_level || '').toLowerCase().includes(q))
  }, [accounts, query])

  const loadTrend = async (userId) => {
    dispatch(setSelectedAccountId(userId))
    try {
      const data = await fetchAccountRiskTrend(userId, 30)
      dispatch(setAccountRiskTrend(data?.points || []))
    } catch {
      dispatch(setAccountRiskTrend([]))
    }
  }

  return (
    <section className="soc-grid">
      <article className="soc-card table-card">
        <div className="panel-head">
          <h2>Account Risk Monitor</h2>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="soc-input"
            placeholder="Filter by user or risk level"
          />
        </div>

        <div className="soc-table-wrap">
          <table className="soc-table">
            <thead>
              <tr>
                <th>Account</th>
                <th>Risk Score</th>
                <th>Transactions</th>
                <th>Average Amount</th>
                <th>Fraud Ratio</th>
                <th>Fraud</th>
                <th>Suspicious</th>
                <th>Behavior</th>
                <th>Devices</th>
                <th>Locations</th>
                <th>Device Change</th>
                <th>Location Change</th>
                <th>Risk Trend</th>
              </tr>
            </thead>
            <tbody>
              {filtered.slice(0, 120).map((a) => (
                <tr
                  key={a.user_id}
                  onClick={() => loadTrend(a.user_id)}
                  style={{ cursor: 'pointer', background: selectedAccountId === a.user_id ? 'rgba(107, 232, 255, 0.08)' : 'transparent' }}
                >
                  <td>U{a.user_id}</td>
                  <td>{Number(a.avg_risk || 0).toFixed(4)}</td>
                  <td>{a.tx_count}</td>
                  <td>${Number(a.avg_amount || 0).toLocaleString()}</td>
                  <td>{(Number(a.fraud_ratio || 0) * 100).toFixed(2)}%</td>
                  <td>{a.fraud_count}</td>
                  <td>{a.suspicious_count}</td>
                  <td>{a.risk_level}</td>
                  <td>{a.distinct_devices || 0}</td>
                  <td>{a.distinct_locations || 0}</td>
                  <td>{Number(a.device_change_score || 0).toFixed(3)}</td>
                  <td>{Number(a.location_change_score || 0).toFixed(3)}</td>
                  <td><Sparkline avgRisk={a.avg_risk} maxRisk={a.max_risk} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </article>

      <article className="soc-card">
        <h2>Account Risk Trend {selectedAccountId ? `(U${selectedAccountId})` : ''}</h2>
        {!selectedAccountId ? (
          <p>Select an account row to inspect risk trend.</p>
        ) : (
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={trend}>
              <XAxis dataKey="timestamp" hide />
              <YAxis domain={[0, 1]} stroke="#8ca0bf" />
              <Tooltip />
              <Line type="monotone" dataKey="risk_score" stroke="#6be8ff" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </article>
    </section>
  )
}
