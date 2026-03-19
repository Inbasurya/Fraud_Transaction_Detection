import { useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { explainTransaction, fetchAccountDetail } from '../services/api'
import { selectTransaction } from '../store/platformSlice'

export default function FraudInvestigationPanel() {
  const dispatch = useDispatch()
  const alerts = useSelector((s) => s.platform.alerts)
  const transactions = useSelector((s) => s.platform.transactions)
  const selected = useSelector((s) => s.platform.selectedTransaction)
  const [explain, setExplain] = useState(null)
  const [accountHistory, setAccountHistory] = useState([])
  const [loading, setLoading] = useState(false)

  const inspect = async (tx) => {
    dispatch(selectTransaction(tx))
    setLoading(true)
    try {
      const res = await explainTransaction(tx.transaction_id)
      setExplain(res)
      const detail = await fetchAccountDetail(tx.user_id)
      setAccountHistory((detail?.recent_transactions || []).slice(0, 10))
    } catch {
      setExplain(null)
      setAccountHistory([])
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="soc-grid investigation-layout">
      <article className="soc-card table-card">
        <h2>Fraud Investigation Queue</h2>
        <div className="soc-table-wrap">
          <table className="soc-table">
            <thead>
              <tr>
                <th>Transaction</th>
                <th>Risk</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {transactions
                .filter((tx) => ['FRAUD', 'SUSPICIOUS'].includes(tx.risk_category))
                .slice(0, 20)
                .map((tx) => (
                  <tr key={tx.transaction_id}>
                    <td>{tx.transaction_id}</td>
                    <td>{Number(tx.risk_score || 0).toFixed(4)}</td>
                    <td>{tx.risk_category}</td>
                    <td>
                      <button className="soc-btn" onClick={() => inspect(tx)}>Investigate</button>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </article>

      <article className="soc-card">
        <h2>Alert Feed</h2>
        <ul className="alert-list">
          {alerts.slice(0, 8).map((alert, idx) => (
            <li
              key={`${alert.alert_id || idx}`}
              className={`${
                (alert.severity || '').toUpperCase() === 'HIGH' ? 'alert-critical' : ''
              } ${Date.now() - Number(alert.received_at || 0) < 7000 ? 'alert-fresh' : ''}`}
            >
              <strong>{alert.alert_id || `ALERT-${idx + 1}`} | {alert.severity || 'MEDIUM'}</strong>
              <p>Account: U{alert.account_id || alert.user_id || 'N/A'}</p>
              <p>Amount: ${Number(alert.amount || 0).toLocaleString()}</p>
              <p>Reason: {alert.message || 'High-risk transaction detected'}</p>
              <p>Time: {alert.timestamp || alert.created_at || '-'}</p>
            </li>
          ))}
        </ul>
      </article>

      <article className="soc-card">
        <h2>Case Intelligence</h2>
        {!selected && <p>Select a suspicious transaction to view SHAP-style reasoning.</p>}
        {selected && (
          <div className="case-box">
            <p><strong>TX:</strong> {selected.transaction_id}</p>
            <p><strong>User:</strong> U{selected.user_id}</p>
            <p><strong>Risk:</strong> {selected.risk_category} ({Number(selected.risk_score || 0).toFixed(4)})</p>
            <p><strong>Behavior Score:</strong> {Number(selected.behavior_score || selected.behavior_anomaly_score || 0).toFixed(4)}</p>
            <p><strong>Rule Triggers:</strong> {(selected.reasons || []).join(', ') || 'None'}</p>
            {loading ? <p>Loading explanation...</p> : null}
            {explain?.reasons?.length ? (
              <ul>
                {explain.reasons.map((reason) => <li key={reason}>{reason}</li>)}
              </ul>
            ) : (
              !loading && <p>Explanation unavailable for this transaction.</p>
            )}
            {explain?.feature_contributions?.length ? (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={explain.feature_contributions}>
                  <XAxis dataKey="feature" stroke="#8ca0bf" />
                  <YAxis stroke="#8ca0bf" />
                  <Tooltip />
                  <Bar dataKey="impact" fill="#6be8ff" />
                </BarChart>
              </ResponsiveContainer>
            ) : null}
            {accountHistory.length ? (
              <div>
                <p><strong>Account History</strong></p>
                <ul>
                  {accountHistory.map((row) => (
                    <li key={row.transaction_id}>
                      {row.transaction_id} | ${Number(row.amount || 0).toLocaleString()} | {row.risk_category || 'SAFE'}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        )}
      </article>
    </section>
  )
}
