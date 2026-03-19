import { motion, AnimatePresence } from 'framer-motion'
import { useState } from 'react'

const STATUS_STYLE = {
  FRAUD:      'badge-fraud',
  SUSPICIOUS: 'badge-suspicious',
  SAFE:       'badge-safe',
}

const ROW_BG = {
  FRAUD:      'bg-soc-danger/[0.04]',
  SUSPICIOUS: 'bg-soc-warn/[0.03]',
  SAFE:       '',
}

function RiskBar({ score }) {
  const pct = Math.min(Math.round((score || 0) * 100), 100)
  const color =
    pct >= 70 ? 'bg-soc-danger' : pct >= 40 ? 'bg-soc-warn' : 'bg-soc-safe'
  return (
    <div className="flex items-center gap-2 min-w-[100px]">
      <div className="flex-1 h-1.5 rounded-full bg-soc-border/60 overflow-hidden">
        <motion.div
          className={`h-full rounded-full ${color}`}
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.6, ease: 'easeOut' }}
        />
      </div>
      <span className="text-[11px] tabular-nums font-mono text-soc-muted w-9 text-right">
        {(score || 0).toFixed(2)}
      </span>
    </div>
  )
}

export default function TransactionTable({ transactions, onSelect }) {
  const [hoveredId, setHoveredId] = useState(null)

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.2 }}
      className="glass overflow-hidden"
    >
      <div className="px-5 py-4 border-b border-soc-border/60 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-soc-safe animate-pulse" />
          <h2 className="text-sm font-semibold tracking-wide">Live Transaction Stream</h2>
        </div>
        <span className="text-xs text-soc-muted tabular-nums">
          {transactions.length} transactions
        </span>
      </div>

      <div className="overflow-x-auto overflow-y-auto max-h-[460px]">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-soc-muted uppercase tracking-wider border-b border-soc-border/40">
              <th className="text-left px-4 py-3 font-medium">Transaction ID</th>
              <th className="text-left px-4 py-3 font-medium">User</th>
              <th className="text-right px-4 py-3 font-medium">Amount</th>
              <th className="text-left px-4 py-3 font-medium">Location</th>
              <th className="text-left px-4 py-3 font-medium">Device</th>
              <th className="text-left px-4 py-3 font-medium">Risk Score</th>
              <th className="text-center px-4 py-3 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            <AnimatePresence initial={false}>
              {transactions.map((tx, i) => {
                const cat = tx.risk_category || 'SAFE'
                return (
                  <motion.tr
                    key={tx.transaction_id || i}
                    layout
                    initial={{ opacity: 0, x: -12 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, height: 0 }}
                    transition={{ duration: 0.3, ease: 'easeOut' }}
                    className={`border-b border-soc-border/20 cursor-pointer transition-colors
                      ${ROW_BG[cat]}
                      ${hoveredId === tx.transaction_id ? 'bg-soc-accent/[0.06]' : 'hover:bg-soc-border/20'}`}
                    onClick={() => onSelect?.(tx)}
                    onMouseEnter={() => setHoveredId(tx.transaction_id)}
                    onMouseLeave={() => setHoveredId(null)}
                  >
                    <td className="px-4 py-3 font-mono text-soc-accent">
                      {tx.transaction_id}
                    </td>
                    <td className="px-4 py-3 text-soc-muted">
                      {typeof tx.user_id === 'number' ? `U${String(tx.user_id).padStart(4, '0')}` : tx.user_id}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums font-medium">
                      ${Number(tx.amount).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </td>
                    <td className="px-4 py-3 text-soc-muted">{tx.location || '—'}</td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center gap-1 text-soc-muted">
                        {tx.device_type === 'mobile' && '📱'}
                        {tx.device_type === 'web' && '💻'}
                        {tx.device_type === 'tablet' && '📱'}
                        {tx.device_type === 'atm' && '🏧'}
                        {tx.device_type}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <RiskBar score={tx.risk_score} />
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className={`inline-block px-2.5 py-1 rounded-full text-[10px] font-semibold uppercase tracking-wide ${STATUS_STYLE[cat]}`}>
                        {cat}
                      </span>
                    </td>
                  </motion.tr>
                )
              })}
            </AnimatePresence>
          </tbody>
        </table>
      </div>
    </motion.div>
  )
}
