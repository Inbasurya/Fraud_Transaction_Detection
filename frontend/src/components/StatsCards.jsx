import { motion, useMotionValue, useTransform, animate } from 'framer-motion'
import { useEffect, useRef } from 'react'

/* ── Animated counter ─────────────────────────────── */
function Counter({ value, duration = 1.2 }) {
  const motionVal = useMotionValue(0)
  const rounded = useTransform(motionVal, (v) => Math.round(v).toLocaleString())
  const ref = useRef(null)

  useEffect(() => {
    const ctrl = animate(motionVal, value, { duration, ease: 'easeOut' })
    return ctrl.stop
  }, [value])

  return <motion.span ref={ref}>{rounded}</motion.span>
}

/* ── Single stat card ─────────────────────────────── */
function StatCard({ label, value, icon, color, glowClass, delay = 0 }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.5, delay, ease: [0.16, 1, 0.3, 1] }}
      whileHover={{ y: -4, scale: 1.02 }}
      className={`glass p-5 flex flex-col gap-3 relative overflow-hidden group cursor-default ${glowClass}`}
    >
      {/* Gradient accent line */}
      <div className={`absolute top-0 inset-x-0 h-[2px] bg-gradient-to-r ${color}`} />

      <div className="flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wider text-soc-muted">{label}</span>
        <span className="text-lg opacity-60 group-hover:opacity-100 transition-opacity">{icon}</span>
      </div>

      <span className="text-3xl font-semibold tabular-nums tracking-tight">
        <Counter value={value} />
      </span>
    </motion.div>
  )
}

/* ── Stats row ────────────────────────────────────── */
export default function StatsCards({ stats }) {
  // SOURCE: metrics:blocked_txns (BLOCK decisions only)
  // DO NOT use metrics:flagged_txns here
  const blocked = stats.blocked_count || 0
  const fraudRate = stats.total_transactions > 0
    ? parseFloat(((blocked / stats.total_transactions) * 100).toFixed(2))
    : 0

  const cards = [
    {
      label: 'Total Transactions',
      value: stats.total_transactions,
      icon: '📊',
      color: 'from-soc-accent to-blue-600',
      glowClass: 'glow-blue',
    },
    {
      label: 'Fraud Detected',
      value: stats.fraud,
      icon: '🚨',
      color: 'from-soc-danger to-red-600',
      glowClass: 'glow-red',
    },
    {
      label: 'Suspicious',
      value: stats.suspicious,
      icon: '⚠️',
      color: 'from-soc-warn to-amber-600',
      glowClass: 'glow-amber',
    },
    {
      label: 'Safe',
      value: stats.safe,
      icon: '✅',
      color: 'from-soc-safe to-emerald-600',
      glowClass: 'glow-green',
    },
    {
      label: 'Open Alerts',
      value: stats.open_alerts,
      icon: '🔔',
      color: 'from-purple-500 to-violet-600',
      glowClass: 'glow-blue',
    },
    {
      label: 'Fraud Rate %',
      value: fraudRate,
      icon: '📈',
      color: 'from-rose-500 to-pink-600',
      glowClass: 'glow-red',
    },
  ]

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4">
      {cards.map((c, i) => (
        <StatCard key={c.label} {...c} delay={i * 0.08} />
      ))}
    </div>
  )
}
