import { useSelector } from 'react-redux'
import { useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { explainTransaction, fetchAuditLog, requestStepUp } from '../services/api'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
} from 'recharts'

const riskColor = (cat) => {
  if (cat === 'FRAUD') return '#ff5f8f'
  if (cat === 'SUSPICIOUS') return '#f6c667'
  return '#53e2a1'
}

function ExpandedRow({ tx }) {
  const [tab, setTab] = useState('shap')
  const [explain, setExplain] = useState(null)
  const [audit, setAudit] = useState(null)
  const [loading, setLoading] = useState(false)
  const [stepUpMsg, setStepUpMsg] = useState(null)

  const loadTab = useCallback(async (t) => {
    setTab(t)
    if (t === 'shap' && !explain) {
      setLoading(true)
      try {
        const data = await explainTransaction(tx.transaction_id)
        setExplain(data)
      } catch { /* noop */ }
      setLoading(false)
    } else if (t === 'audit' && !audit) {
      setLoading(true)
      try {
        const data = await fetchAuditLog(tx.transaction_id)
        setAudit(data)
      } catch { /* noop */ }
      setLoading(false)
    }
  }, [tx, explain, audit])

  const handleStepUp = async () => {
    try {
      const res = await requestStepUp(tx.transaction_id, {
        customer_id: tx.user_id || tx.customer_id,
        channel: 'email',
      })
      setStepUpMsg(res?.message || 'OTP sent')
    } catch {
      setStepUpMsg('Step-up failed')
    }
  }

  const shapData = (explain?.feature_contributions || [])
    .slice(0, 10)
    .map((f) => ({
      feature: f.feature || f.name,
      impact: f.impact || f.value || 0,
    }))
    .sort((a, b) => Math.abs(b.impact) - Math.abs(a.impact))

  const behaviorSignals = [
    { name: 'Velocity', value: tx.velocity_flag || 0 },
    { name: 'Amount Spike', value: tx.amount_spike || 0 },
    { name: 'Geo Anomaly', value: tx.geo_anomaly || 0 },
    { name: 'Device Risk', value: tx.device_risk || 0 },
    { name: 'Time Anomaly', value: tx.time_anomaly || 0 },
    { name: 'Behavior Score', value: tx.behavior_score || tx.behavior_anomaly_score || 0 },
  ]

  return (
    <motion.tr
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: 'auto' }}
      exit={{ opacity: 0, height: 0 }}
    >
      <td colSpan={12} style={{ padding: '0.8rem 1rem' }}>
        <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.6rem' }}>
          {['shap', 'behavior', 'audit'].map((t) => (
            <button
              key={t}
              className="soc-btn"
              onClick={() => loadTab(t)}
              style={{
                fontSize: '0.72rem',
                background: tab === t ? 'rgba(107,232,255,0.2)' : undefined,
                borderColor: tab === t ? 'rgba(107,232,255,0.6)' : undefined,
              }}
            >
              {t === 'shap' ? '📊 SHAP' : t === 'behavior' ? '🧠 Behavior' : '📋 Audit'}
            </button>
          ))}
          {(tx.risk_category === 'SUSPICIOUS' || tx.risk_category === 'FRAUD') && (
            <button className="soc-btn" onClick={handleStepUp} style={{ fontSize: '0.72rem', marginLeft: 'auto' }}>
              🔐 Step-Up Auth
            </button>
          )}
          {stepUpMsg && <span className="soc-pill" style={{ fontSize: '0.7rem' }}>{stepUpMsg}</span>}
        </div>

        {loading && <p style={{ color: 'var(--muted)', fontSize: '0.8rem' }}>Loading…</p>}

        {tab === 'shap' && shapData.length > 0 && (
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={shapData} layout="vertical" margin={{ left: 100 }}>
              <XAxis type="number" stroke="#4a6080" tick={{ fill: '#89a0c6', fontSize: 10 }} />
              <YAxis type="category" dataKey="feature" stroke="#4a6080" tick={{ fill: '#89a0c6', fontSize: 9 }} width={95} />
              <Tooltip contentStyle={{ background: '#0d1529', border: '1px solid rgba(104,133,184,0.35)', borderRadius: 8, color: '#dde9ff' }} />
              <Bar dataKey="impact" fill="#6be8ff" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}

        {tab === 'behavior' && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.5rem' }}>
            {behaviorSignals.map((s) => (
              <div key={s.name} className="soc-card" style={{ padding: '0.5rem 0.7rem' }}>
                <span style={{ fontSize: '0.7rem', color: 'var(--muted)' }}>{s.name}</span>
                <h3 style={{
                  fontSize: '1rem',
                  margin: '0.2rem 0 0',
                  color: s.value > 0.5 ? '#ff5f8f' : s.value > 0.2 ? '#f6c667' : '#53e2a1',
                }}>
                  {Number(s.value).toFixed(3)}
                </h3>
              </div>
            ))}
          </div>
        )}

        {tab === 'audit' && audit && (
          <div style={{ fontSize: '0.8rem' }}>
            <p><strong>Risk Score:</strong> {audit.risk_score?.toFixed(4)}</p>
            <p><strong>Model Version:</strong> {audit.model_version || '—'}</p>
            <p><strong>Action:</strong> {audit.action_taken || '—'}</p>
            <p><strong>Rules Triggered:</strong> {JSON.stringify(audit.rules_triggered || [])}</p>
            {audit.explanation_text && <p><strong>Explanation:</strong> {audit.explanation_text}</p>}
          </div>
        )}
      </td>
    </motion.tr>
  )
}

export default function EnhancedTransactionMonitor() {
  const transactions = useSelector((s) => s.platform.transactions)
  const txPerSec = useSelector((s) => s.platform.txPerSec)
  const txPerMin = useSelector((s) => s.platform.txPerMin)
  const [filterRisk, setFilterRisk] = useState('ALL')
  const [expandedId, setExpandedId] = useState(null)

  const filtered = filterRisk === 'ALL'
    ? transactions
    : transactions.filter((tx) => tx.risk_category === filterRisk)

  return (
    <div className="soc-grid" style={{ gap: '1rem' }}>
      <div className="soc-card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.8rem' }}>
        <div>
          <h2 style={{ margin: 0, fontSize: '1.1rem' }}>Enhanced Transaction Monitor</h2>
          <p style={{ margin: '0.2rem 0 0', color: 'var(--muted)', fontSize: '0.82rem' }}>
            Click any row to inspect SHAP explanation, behavioral signals, and audit trail
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

      <div className="soc-card" style={{ maxHeight: '78vh', overflowY: 'auto' }}>
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
                  <AnimatePresence key={tx.transaction_id || i}>
                    <motion.tr
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0 }}
                      transition={{ duration: 0.3 }}
                      style={{
                        borderLeft: `3px solid ${riskColor(tx.risk_category)}`,
                        cursor: 'pointer',
                        background: expandedId === tx.transaction_id ? 'rgba(107,232,255,0.05)' : undefined,
                      }}
                      onClick={() => setExpandedId(expandedId === tx.transaction_id ? null : tx.transaction_id)}
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
                          <div style={{ width: '40px', height: '6px', borderRadius: '3px', background: 'rgba(255,255,255,0.08)', overflow: 'hidden' }}>
                            <div style={{ width: `${Math.min((tx.risk_score || 0) * 100, 100)}%`, height: '100%', borderRadius: '3px', background: riskColor(tx.risk_category) }} />
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
                    {expandedId === tx.transaction_id && <ExpandedRow tx={tx} />}
                  </AnimatePresence>
                ))}
              </AnimatePresence>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
