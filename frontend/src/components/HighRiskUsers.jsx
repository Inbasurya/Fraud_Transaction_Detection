import { motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { fetchHighRiskUsers } from '../services/api'

export default function HighRiskUsers() {
  const [users, setUsers] = useState([])

  useEffect(() => {
    const load = () => fetchHighRiskUsers(8).then(setUsers).catch(() => {})
    load()
    const id = setInterval(load, 15000)
    return () => clearInterval(id)
  }, [])

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.35 }}
      className="glass overflow-hidden"
    >
      <div className="px-5 py-4 border-b border-soc-border/60 flex items-center gap-2">
        <span className="text-sm">👤</span>
        <h2 className="text-sm font-semibold tracking-wide">High Risk Accounts</h2>
        <span className="ml-auto text-xs text-soc-muted tabular-nums">{users.length} users</span>
      </div>

      <div className="overflow-y-auto max-h-[320px]">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-soc-muted uppercase tracking-wider border-b border-soc-border/40">
              <th className="text-left px-4 py-2.5 font-medium">User ID</th>
              <th className="text-right px-4 py-2.5 font-medium">Transactions</th>
              <th className="text-right px-4 py-2.5 font-medium">Total Amount</th>
              <th className="text-right px-4 py-2.5 font-medium">Avg Risk</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u, i) => {
              const riskColor = u.avg_risk >= 0.7 ? 'text-soc-danger' : u.avg_risk >= 0.4 ? 'text-soc-warn' : 'text-soc-safe'
              return (
                <motion.tr
                  key={u.user_id}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.04 }}
                  className="border-b border-soc-border/20 hover:bg-soc-border/20 transition-colors"
                >
                  <td className="px-4 py-2.5 font-mono text-soc-accent">
                    U{String(u.user_id).padStart(4, '0')}
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums text-soc-muted">
                    {u.tx_count}
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums font-medium">
                    ${u.total_amount?.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </td>
                  <td className={`px-4 py-2.5 text-right tabular-nums font-semibold ${riskColor}`}>
                    {u.avg_risk?.toFixed(4)}
                  </td>
                </motion.tr>
              )
            })}
            {users.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-soc-muted">
                  Collecting user risk data…
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </motion.div>
  )
}
