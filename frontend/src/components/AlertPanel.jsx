import { motion, AnimatePresence } from 'framer-motion'

function timeAgo(ts) {
  if (!ts) return ''
  const diff = (Date.now() - new Date(ts).getTime()) / 1000
  if (diff < 60) return `${Math.round(diff)}s ago`
  if (diff < 3600) return `${Math.round(diff / 60)}m ago`
  return `${Math.round(diff / 3600)}h ago`
}

export default function AlertPanel({ alerts }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.3 }}
      className="glass overflow-hidden h-full flex flex-col"
    >
      <div className="px-5 py-4 border-b border-soc-border/60 flex items-center gap-2">
        <span className="relative flex h-2.5 w-2.5">
          <span className="animate-ping-slow absolute inline-flex h-full w-full rounded-full bg-soc-danger opacity-75" />
          <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-soc-danger" />
        </span>
        <h2 className="text-sm font-semibold tracking-wide">Fraud Alerts</h2>
        <span className="ml-auto text-xs text-soc-muted tabular-nums">{alerts.length}</span>
      </div>

      <div className="overflow-y-auto flex-1 max-h-[460px] p-3 space-y-2">
        <AnimatePresence initial={false}>
          {alerts.map((a, i) => {
            const isFraud = a.alert_type === 'FRAUD'
            return (
              <motion.div
                key={a.id || a.transaction_id + '-' + i}
                initial={{ opacity: 0, x: 24, scale: 0.95 }}
                animate={{ opacity: 1, x: 0, scale: 1 }}
                exit={{ opacity: 0, x: -24 }}
                transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
                className={`rounded-xl p-3.5 border transition-colors cursor-default
                  ${isFraud
                    ? 'bg-soc-danger/[0.06] border-soc-danger/20 hover:border-soc-danger/40'
                    : 'bg-soc-warn/[0.06] border-soc-warn/20 hover:border-soc-warn/40'
                  }`}
              >
                <div className="flex items-start justify-between gap-2 mb-2">
                  <span className={`text-xs font-semibold uppercase tracking-wider ${isFraud ? 'text-soc-danger' : 'text-soc-warn'}`}>
                    {isFraud ? '🚨 Fraud Detected' : '⚠ Suspicious Activity'}
                  </span>
                  <span className="text-[10px] text-soc-muted whitespace-nowrap">{timeAgo(a.created_at)}</span>
                </div>

                <p className="text-xs text-soc-text/80 mb-2 line-clamp-2">{a.message}</p>

                <div className="flex items-center justify-between text-[11px] text-soc-muted">
                  <span className="font-mono">TX: {a.transaction_id}</span>
                  <span className="tabular-nums font-medium">
                    Risk: <span className={isFraud ? 'text-soc-danger' : 'text-soc-warn'}>
                      {(a.risk_score || 0).toFixed(2)}
                    </span>
                  </span>
                </div>

                {a.amount != null && (
                  <div className="mt-1.5 text-[11px] text-soc-muted flex gap-3">
                    <span>User: {typeof a.user_id === 'number' ? `U${String(a.user_id).padStart(4, '0')}` : a.user_id || '—'}</span>
                    <span>${Number(a.amount).toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                  </div>
                )}
              </motion.div>
            )
          })}
        </AnimatePresence>

        {alerts.length === 0 && (
          <div className="flex flex-col items-center justify-center py-12 text-soc-muted text-xs">
            <span className="text-2xl mb-2">🛡️</span>
            No active alerts
          </div>
        )}
      </div>
    </motion.div>
  )
}
