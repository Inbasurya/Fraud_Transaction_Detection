import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { fetchAccounts, fetchAccountDetail, fetchPatterns } from '../services/api'

const riskBadge = (level) => {
  const map = {
    CRITICAL: 'badge-fraud',
    HIGH: 'badge-suspicious',
    LOW: 'badge-safe',
  }
  return map[level] || 'badge-safe'
}

function AccountModal({ userId, onClose }) {
  const [detail, setDetail] = useState(null)

  useEffect(() => {
    fetchAccountDetail(userId).then(setDetail).catch(() => {})
  }, [userId])

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
      onClick={onClose}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.92, y: 24 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.92, y: 24 }}
        transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
        className="glass p-6 w-full max-w-2xl max-h-[80vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between mb-5">
          <div>
            <h2 className="text-base font-semibold">
              Account U{String(userId).padStart(4, '0')}
            </h2>
            <p className="text-xs text-soc-muted">Transaction History & Profile</p>
          </div>
          <button onClick={onClose} className="text-soc-muted hover:text-soc-text transition text-lg">
            ✕
          </button>
        </div>

        {!detail ? (
          <div className="flex items-center justify-center py-12 text-soc-muted text-xs">
            <div className="w-5 h-5 border-2 border-soc-accent/30 border-t-soc-accent rounded-full animate-spin mr-2" />
            Loading…
          </div>
        ) : (
          <>
            {/* Profile summary */}
            {detail.profile && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
                <div className="glass-sm p-3 text-center">
                  <p className="text-[10px] text-soc-muted uppercase tracking-wider mb-1">Avg Amount</p>
                  <p className="text-sm font-semibold tabular-nums">
                    ${detail.profile.avg_transaction_amount?.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </p>
                </div>
                <div className="glass-sm p-3 text-center">
                  <p className="text-[10px] text-soc-muted uppercase tracking-wider mb-1">Total Tx</p>
                  <p className="text-sm font-semibold tabular-nums">{detail.profile.total_transactions}</p>
                </div>
                <div className="glass-sm p-3 text-center">
                  <p className="text-[10px] text-soc-muted uppercase tracking-wider mb-1">Last Location</p>
                  <p className="text-xs font-medium">{detail.profile.last_location || '—'}</p>
                </div>
                <div className="glass-sm p-3 text-center">
                  <p className="text-[10px] text-soc-muted uppercase tracking-wider mb-1">Last Device</p>
                  <p className="text-xs font-medium">{detail.profile.last_device || '—'}</p>
                </div>
              </div>
            )}

            {/* Recent transactions */}
            <h3 className="text-xs font-medium text-soc-muted uppercase tracking-wider mb-3">
              Recent Transactions ({detail.recent_transactions?.length || 0})
            </h3>
            <div className="overflow-y-auto max-h-[300px]">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-soc-muted uppercase tracking-wider border-b border-soc-border/40">
                    <th className="text-left px-3 py-2 font-medium">TX ID</th>
                    <th className="text-right px-3 py-2 font-medium">Amount</th>
                    <th className="text-left px-3 py-2 font-medium">Merchant</th>
                    <th className="text-left px-3 py-2 font-medium">Location</th>
                    <th className="text-right px-3 py-2 font-medium">Risk</th>
                  </tr>
                </thead>
                <tbody>
                  {detail.recent_transactions?.map((tx, i) => {
                    const catColor =
                      tx.risk_category === 'FRAUD' ? 'text-soc-danger' :
                      tx.risk_category === 'SUSPICIOUS' ? 'text-soc-warn' : 'text-soc-safe'
                    return (
                      <tr key={i} className="border-b border-soc-border/20 hover:bg-soc-border/20">
                        <td className="px-3 py-2 font-mono text-soc-accent">{tx.transaction_id?.slice(-8)}</td>
                        <td className="px-3 py-2 text-right tabular-nums">${tx.amount?.toLocaleString()}</td>
                        <td className="px-3 py-2">{tx.merchant || '—'}</td>
                        <td className="px-3 py-2">{tx.location || '—'}</td>
                        <td className={`px-3 py-2 text-right font-semibold ${catColor}`}>
                          {tx.risk_score?.toFixed(3) || '—'}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}
      </motion.div>
    </motion.div>
  )
}

export default function Accounts() {
  const [accounts, setAccounts] = useState([])
  const [patterns, setPatterns] = useState(null)
  const [selectedUser, setSelectedUser] = useState(null)

  useEffect(() => {
    fetchAccounts(50).then(setAccounts).catch(() => {})
    fetchPatterns().then(setPatterns).catch(() => {})
  }, [])

  return (
    <>
      <main className="max-w-[1800px] mx-auto px-6 py-6 space-y-6">
        {/* Page header */}
        <div>
          <h2 className="text-lg font-semibold tracking-tight">Account Risk Monitor</h2>
          <p className="text-xs text-soc-muted mt-1">
            All accounts ranked by risk level — click any row for details
          </p>
        </div>

        {/* Pattern summary cards */}
        {patterns && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            {[
              { label: 'Total Patterns', value: patterns.total_patterns, icon: '🔍', color: 'from-soc-accent to-blue-600' },
              { label: 'Rapid Tx', value: patterns.rapid_transactions, icon: '⚡', color: 'from-soc-warn to-amber-600' },
              { label: 'Location Hop', value: patterns.location_hopping, icon: '🌍', color: 'from-purple-500 to-violet-600' },
              { label: 'Device Switch', value: patterns.device_switching, icon: '📱', color: 'from-rose-500 to-pink-600' },
              { label: 'Amount Spike', value: patterns.amount_spikes, icon: '📈', color: 'from-soc-danger to-red-600' },
            ].map((c, i) => (
              <motion.div
                key={c.label}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.06 }}
                className="glass p-4 relative overflow-hidden"
              >
                <div className={`absolute top-0 inset-x-0 h-[2px] bg-gradient-to-r ${c.color}`} />
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[10px] text-soc-muted uppercase tracking-wider font-medium">{c.label}</span>
                  <span className="text-sm">{c.icon}</span>
                </div>
                <span className="text-2xl font-semibold tabular-nums">{c.value}</span>
              </motion.div>
            ))}
          </div>
        )}

        {/* Accounts table */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="glass overflow-hidden"
        >
          <div className="px-5 py-4 border-b border-soc-border/60">
            <h3 className="text-sm font-semibold tracking-wide">All Accounts — Risk Ranking</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-soc-muted uppercase tracking-wider border-b border-soc-border/40">
                  <th className="text-left px-4 py-3 font-medium">Account</th>
                  <th className="text-right px-4 py-3 font-medium">Transactions</th>
                  <th className="text-right px-4 py-3 font-medium">Total Amount</th>
                  <th className="text-center px-4 py-3 font-medium">Risk Level</th>
                  <th className="text-right px-4 py-3 font-medium">Avg Risk</th>
                  <th className="text-right px-4 py-3 font-medium">Max Risk</th>
                  <th className="text-right px-4 py-3 font-medium">Fraud</th>
                  <th className="text-right px-4 py-3 font-medium">Suspicious</th>
                  <th className="text-left px-4 py-3 font-medium">Last Activity</th>
                </tr>
              </thead>
              <tbody>
                {accounts.map((a, i) => (
                  <motion.tr
                    key={a.user_id}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.02 }}
                    className="border-b border-soc-border/20 hover:bg-soc-border/20 transition-colors cursor-pointer"
                    onClick={() => setSelectedUser(a.user_id)}
                  >
                    <td className="px-4 py-3 font-mono text-soc-accent font-medium">
                      U{String(a.user_id).padStart(4, '0')}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">{a.tx_count}</td>
                    <td className="px-4 py-3 text-right tabular-nums font-medium">
                      ${a.total_amount?.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${riskBadge(a.risk_level)}`}>
                        {a.risk_level}
                      </span>
                    </td>
                    <td className={`px-4 py-3 text-right tabular-nums font-semibold ${
                      a.avg_risk >= 0.7 ? 'text-soc-danger' : a.avg_risk >= 0.4 ? 'text-soc-warn' : 'text-soc-safe'
                    }`}>
                      {a.avg_risk?.toFixed(4)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-soc-muted">{a.max_risk?.toFixed(4)}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-soc-danger">{a.fraud_count}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-soc-warn">{a.suspicious_count}</td>
                    <td className="px-4 py-3 text-soc-muted">
                      {a.last_activity ? new Date(a.last_activity).toLocaleString([], {
                        month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
                      }) : '—'}
                    </td>
                  </motion.tr>
                ))}
                {accounts.length === 0 && (
                  <tr>
                    <td colSpan={9} className="px-4 py-12 text-center text-soc-muted">
                      No account data yet — start the transaction streamer
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </motion.div>

        {/* Pattern details */}
        {patterns?.patterns?.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="glass overflow-hidden"
          >
            <div className="px-5 py-4 border-b border-soc-border/60 flex items-center gap-2">
              <span className="text-sm">⚠️</span>
              <h3 className="text-sm font-semibold tracking-wide">Detected Fraud Patterns</h3>
              <span className="ml-auto text-xs text-soc-muted">{patterns.patterns.length} patterns</span>
            </div>
            <div className="overflow-y-auto max-h-[300px] divide-y divide-soc-border/20">
              {patterns.patterns.slice(0, 20).map((p, i) => (
                <div key={i} className="px-5 py-3 flex items-center gap-4 hover:bg-soc-border/10 transition-colors">
                  <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                    p.severity === 'CRITICAL' ? 'badge-fraud' :
                    p.severity === 'HIGH' ? 'badge-suspicious' : 'badge-safe'
                  }`}>
                    {p.severity}
                  </span>
                  <span className="text-xs font-mono text-soc-accent">
                    U{String(p.user_id).padStart(4, '0')}
                  </span>
                  <span className="text-xs text-soc-muted capitalize">
                    {p.pattern?.replace(/_/g, ' ')}
                  </span>
                  {p.amount && (
                    <span className="text-xs tabular-nums ml-auto">
                      ${p.amount?.toLocaleString()} ({p.spike_ratio}× avg)
                    </span>
                  )}
                  {p.tx_count && (
                    <span className="text-xs tabular-nums ml-auto">{p.tx_count} tx</span>
                  )}
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </main>

      {/* Account detail modal */}
      <AnimatePresence>
        {selectedUser && <AccountModal userId={selectedUser} onClose={() => setSelectedUser(null)} />}
      </AnimatePresence>
    </>
  )
}
