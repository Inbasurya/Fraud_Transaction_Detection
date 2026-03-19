import { useEffect, useState } from 'react'
import { fetchCustomers, fetchCustomer, fetchCustomerDevices, fetchCustomerNotifications } from '../services/api'
import { motion } from 'framer-motion'

const riskBadge = (level) => {
  const l = (level || 'LOW').toUpperCase()
  const cls = l === 'HIGH' ? 'fraud' : l === 'MEDIUM' ? 'suspicious' : 'safe'
  return <span className={`risk-badge ${cls}`}>{l}</span>
}

export default function AccountIntelligencePage() {
  const [customers, setCustomers] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [detail, setDetail] = useState(null)
  const [devices, setDevices] = useState([])
  const [notifications, setNotifications] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchCustomers(100)
      .then(setCustomers)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!selectedId) return
    Promise.all([
      fetchCustomer(selectedId).catch(() => null),
      fetchCustomerDevices(selectedId).catch(() => []),
      fetchCustomerNotifications(selectedId).catch(() => []),
    ]).then(([c, d, n]) => {
      setDetail(c)
      setDevices(d || [])
      setNotifications(n || [])
    })
  }, [selectedId])

  return (
    <div className="soc-grid" style={{ gap: '1rem' }}>
      <div className="soc-card">
        <h2 style={{ margin: '0 0 0.3rem' }}>Account Intelligence</h2>
        <p style={{ color: 'var(--muted)', fontSize: '0.82rem', margin: 0 }}>
          Customer risk profiles, device history, and notification log
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: selectedId ? '1fr 1.3fr' : '1fr', gap: '1rem' }}>
        {/* Customer List */}
        <div className="soc-card" style={{ maxHeight: '72vh', overflowY: 'auto' }}>
          <h2>Customers</h2>
          {loading ? (
            <p style={{ color: 'var(--muted)' }}>Loading customers...</p>
          ) : customers.length === 0 ? (
            <p style={{ color: 'var(--muted)' }}>No customers registered yet. Use POST /customers/register to add.</p>
          ) : (
            <div className="soc-table-wrap">
              <table className="soc-table">
                <thead>
                  <tr>
                    <th>Customer ID</th>
                    <th>Name</th>
                    <th>Avg Tx</th>
                    <th>Total Tx</th>
                    <th>Risk</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {customers.map((c) => (
                    <tr
                      key={c.customer_id}
                      onClick={() => setSelectedId(c.customer_id)}
                      style={{ cursor: 'pointer', background: selectedId === c.customer_id ? 'rgba(107,232,255,0.08)' : undefined }}
                    >
                      <td>{c.customer_id}</td>
                      <td>{c.name}</td>
                      <td>${(c.avg_transaction_amount || 0).toFixed(2)}</td>
                      <td>{c.total_transactions}</td>
                      <td>{riskBadge(c.risk_level)}</td>
                      <td>
                        <button className="soc-btn" style={{ fontSize: '0.7rem' }}>View</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Detail Panel */}
        {selectedId && detail && (
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            className="soc-grid"
            style={{ gap: '1rem' }}
          >
            {/* Profile Card */}
            <div className="soc-card">
              <h2>Customer Profile</h2>
              <div className="metric-grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
                <div className="metric-tile">
                  <span>Name</span>
                  <strong>{detail.name}</strong>
                </div>
                <div className="metric-tile">
                  <span>Email</span>
                  <strong style={{ fontSize: '0.82rem', wordBreak: 'break-all' }}>{detail.email}</strong>
                </div>
                <div className="metric-tile">
                  <span>Phone</span>
                  <strong>{detail.phone || '—'}</strong>
                </div>
                <div className="metric-tile">
                  <span>Home Location</span>
                  <strong>{detail.home_location || '—'}</strong>
                </div>
                <div className="metric-tile">
                  <span>Avg Transaction</span>
                  <strong>${(detail.avg_transaction_amount || 0).toFixed(2)}</strong>
                </div>
                <div className="metric-tile">
                  <span>Risk Level</span>
                  <strong>{riskBadge(detail.risk_level)}</strong>
                </div>
              </div>
            </div>

            {/* Devices */}
            <div className="soc-card">
              <h2>Known Devices ({devices.length})</h2>
              {devices.length === 0 ? (
                <p style={{ color: 'var(--muted)', fontSize: '0.82rem' }}>No devices registered</p>
              ) : (
                <div className="soc-table-wrap">
                  <table className="soc-table">
                    <thead>
                      <tr>
                        <th>Device ID</th>
                        <th>Type</th>
                        <th>Browser</th>
                        <th>OS</th>
                        <th>IP</th>
                        <th>First Seen</th>
                        <th>Last Used</th>
                      </tr>
                    </thead>
                    <tbody>
                      {devices.map((d) => (
                        <tr key={d.device_id}>
                          <td>{d.device_id}</td>
                          <td>{d.device_type || '—'}</td>
                          <td>{d.browser || '—'}</td>
                          <td>{d.operating_system || '—'}</td>
                          <td>{d.ip_address || '—'}</td>
                          <td>{d.first_seen ? new Date(d.first_seen).toLocaleDateString() : '—'}</td>
                          <td>{d.last_used ? new Date(d.last_used).toLocaleDateString() : '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Notifications */}
            <div className="soc-card">
              <h2>Notifications ({notifications.length})</h2>
              {notifications.length === 0 ? (
                <p style={{ color: 'var(--muted)', fontSize: '0.82rem' }}>No notifications sent</p>
              ) : (
                <ul className="alert-list">
                  {notifications.slice(0, 20).map((n) => (
                    <li key={n.id}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <strong style={{ fontSize: '0.82rem' }}>
                          {n.notification_type === 'SMS' ? '📱' : '📧'} {n.notification_type}
                        </strong>
                        <span className={`risk-badge ${n.status === 'SENT' ? 'safe' : 'fraud'}`}>
                          {n.status}
                        </span>
                      </div>
                      <p style={{ fontSize: '0.78rem', margin: '0.3rem 0 0' }}>{n.message?.slice(0, 120)}</p>
                      <p style={{ fontSize: '0.7rem', color: 'var(--muted)', margin: '0.15rem 0 0' }}>
                        {n.created_at ? new Date(n.created_at).toLocaleString() : ''}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </motion.div>
        )}
      </div>
    </div>
  )
}
