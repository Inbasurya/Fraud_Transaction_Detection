import { useSelector } from 'react-redux'
import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

const riskColor = (cat) => {
  if (cat === 'FRAUD') return '#ff5f8f'
  if (cat === 'SUSPICIOUS') return '#f6c667'
  return '#53e2a1'
}

export default function LiveTransactionMonitor() {
  const transactions = useSelector((s) => s.platform.transactions)
  const txPerSec = useSelector((s) => s.platform.txPerSec)
  const txPerMin = useSelector((s) => s.platform.txPerMin)
  const [filterRisk, setFilterRisk] = useState('ALL')

  const filtered = filterRisk === 'ALL'
    ? transactions
    : transactions.filter((tx) => tx.risk_category === filterRisk)

  return (
    <div className="soc-grid" style={{ gap: '1rem' }}>
      {/* Header Bar */}
      <div className="soc-card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.8rem' }}>
        <div>
          <h2 style={{ margin: 0, fontSize: '1.1rem' }}>Live Transaction Monitor</h2>
          <p style={{ margin: '0.2rem 0 0', color: 'var(--muted)', fontSize: '0.82rem' }}>
            Real-time transaction stream with risk classification
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <span className="soc-pill" style={{ color: 'var(--accent)' }}>⚡ {txPerSec} tx/s</span>
          <span className="soc-pill">{txPerMin} tx/min</span>
          {['ALL', 'SAFE', 'SUSPICIOUS', 'FRAUD'].map((f) => (
            <button
              key={f}
              onClick={() => setFilterRisk(f)}
              className="soc-btn"
              style={{
                background: filterRisk === f ? 'rgba(107,232,255,0.2)' : undefined,
                borderColor: filterRisk === f ? 'rgba(107,232,255,0.6)' : undefined,
                fontSize: '0.75rem',
              }}
            >{f}</button>
          ))}
        </div>
      </div>

      {/* Transaction Stream */}
      <div className="soc-card" style={{ maxHeight: '75vh', overflowY: 'auto' }}>
        <div className="soc-table-wrap">
          <table className="soc-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Transaction ID</th>
                <th>Account</th>
                <th>Amount</th>
                <th>Merchant</th>
                <th>Location</th>
                <th>Device</th>
                <th>Risk Score</th>
                <th>Status</th>
                <th>ML Prob</th>
                <th>Anomaly</th>
                <th>Rules</th>
              </tr>
            </thead>
            <tbody>
              <AnimatePresence initial={false}>
                {filtered.slice(0, 100).map((tx, i) => (
                  <motion.tr
                    key={tx.transaction_id || i}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.3 }}
                    style={{ borderLeft: `3px solid ${riskColor(tx.risk_category)}` }}
                  >
                    <td>{tx.timestamp ? new Date(tx.timestamp).toLocaleTimeString() : '—'}</td>
                    <td style={{ fontSize: '0.7rem' }}>{tx.transaction_id?.slice(0, 12)}</td>
                    <td>{tx.user_id || tx.customer_id}</td>
                    <td style={{ color: (tx.amount || 0) > 5000 ? '#ff5f8f' : '#d5e4ff' }}>
                      ${(tx.amount || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </td>
                    <td>{tx.merchant || '—'}</td>
                    <td>{tx.location || '—'}</td>
                    <td>{tx.device_type || '—'}</td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        <div style={{
                          width: '40px', height: '6px', borderRadius: '3px',
                          background: 'rgba(255,255,255,0.08)',
                          overflow: 'hidden',
                        }}>
                          <div style={{
                            width: `${Math.min((tx.risk_score || 0) * 100, 100)}%`,
                            height: '100%',
                            borderRadius: '3px',
                            background: riskColor(tx.risk_category),
                          }} />
                        </div>
                        <span>{(tx.risk_score || 0).toFixed(3)}</span>
                      </div>
                    </td>
                    <td>
                      <span className={`risk-badge ${(tx.risk_category || 'safe').toLowerCase()}`}>
                        {tx.risk_category || 'SAFE'}
                      </span>
                    </td>
                    <td>{(tx.fraud_probability || tx.ml_probability || 0).toFixed(3)}</td>
                    <td>{(tx.anomaly_score || tx.behavior_score || 0).toFixed(3)}</td>
                    <td>{(tx.rule_score || 0).toFixed(3)}</td>
                  </motion.tr>
                ))}
              </AnimatePresence>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
