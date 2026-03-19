import { useSelector } from 'react-redux'
import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

export default function FraudAlertsPanel() {
  const alerts = useSelector((s) => s.platform.alerts)
  const [filterType, setFilterType] = useState('ALL')

  const filtered = filterType === 'ALL'
    ? alerts
    : alerts.filter((a) =>
        (a.alert_type || a.severity || '').toUpperCase().includes(filterType)
      )

  const fraudCount = alerts.filter((a) => (a.risk_score || 0) >= 0.6).length
  const suspiciousCount = alerts.filter((a) => {
    const s = a.risk_score || 0
    return s >= 0.3 && s < 0.6
  }).length

  return (
    <div className="soc-grid" style={{ gap: '1rem' }}>
      {/* KPI Row */}
      <div className="soc-grid-kpi" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
        <div className="soc-card kpi danger">
          <span>Total Alerts</span>
          <h3>{alerts.length}</h3>
        </div>
        <div className="soc-card kpi" style={{ '--kpi': '#ff5f8f' }}>
          <span>Fraud Alerts</span>
          <h3 style={{ color: '#ff5f8f' }}>{fraudCount}</h3>
        </div>
        <div className="soc-card kpi warn">
          <span>Suspicious Alerts</span>
          <h3>{suspiciousCount}</h3>
        </div>
        <div className="soc-card kpi accent">
          <span>Open Cases</span>
          <h3 style={{ color: 'var(--accent)' }}>
            {alerts.filter((a) => (a.status || 'OPEN') === 'OPEN').length}
          </h3>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="soc-card" style={{ display: 'flex', gap: '0.5rem', padding: '0.6rem 0.9rem', alignItems: 'center' }}>
        <span style={{ color: 'var(--muted)', fontSize: '0.82rem', marginRight: '0.5rem' }}>Filter:</span>
        {['ALL', 'FRAUD', 'SUSPICIOUS'].map((f) => (
          <button
            key={f}
            onClick={() => setFilterType(f)}
            className="soc-btn"
            style={{
              background: filterType === f ? 'rgba(107,232,255,0.2)' : undefined,
              fontSize: '0.75rem',
            }}
          >{f}</button>
        ))}
      </div>

      {/* Alert List */}
      <div className="soc-card" style={{ maxHeight: '68vh', overflowY: 'auto' }}>
        <ul className="alert-list">
          <AnimatePresence initial={false}>
            {filtered.slice(0, 80).map((alert, i) => {
              const score = alert.risk_score || 0
              const isCritical = score >= 0.8
              const isFresh = alert.received_at && (Date.now() - alert.received_at < 10000)

              return (
                <motion.li
                  key={alert.alert_id || alert.id || i}
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  className={`${isFresh ? 'alert-fresh' : ''} ${isCritical ? 'alert-critical' : ''}`}
                  style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr auto', gap: '0.5rem', alignItems: 'center' }}
                >
                  <div>
                    <strong style={{ fontSize: '0.85rem' }}>
                      {alert.alert_id || `ALERT-${alert.id || i}`}
                    </strong>
                    <p style={{ margin: '0.15rem 0 0', fontSize: '0.75rem' }}>
                      TX: {alert.transaction_id || '—'}
                    </p>
                  </div>
                  <div>
                    <span style={{ color: 'var(--muted)', fontSize: '0.72rem' }}>Account</span>
                    <p style={{ margin: 0, fontSize: '0.82rem' }}>{alert.user_id || alert.account_id || '—'}</p>
                  </div>
                  <div>
                    <span style={{ color: 'var(--muted)', fontSize: '0.72rem' }}>Amount</span>
                    <p style={{ margin: 0, fontSize: '0.82rem' }}>
                      ${(alert.amount || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </p>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <span className={`risk-badge ${score >= 0.6 ? 'fraud' : score >= 0.3 ? 'suspicious' : 'safe'}`}>
                      {score.toFixed(3)}
                    </span>
                    <p style={{ margin: '0.2rem 0 0', fontSize: '0.7rem', color: 'var(--muted)' }}>
                      {alert.created_at ? new Date(alert.created_at).toLocaleString() : ''}
                    </p>
                  </div>
                </motion.li>
              )
            })}
          </AnimatePresence>
        </ul>
        {filtered.length === 0 && (
          <p style={{ textAlign: 'center', color: 'var(--muted)', padding: '2rem' }}>
            No alerts matching filter
          </p>
        )}
      </div>
    </div>
  )
}
