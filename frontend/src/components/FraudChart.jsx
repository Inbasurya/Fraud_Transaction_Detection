import { motion } from 'framer-motion'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from 'recharts'

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="glass-sm px-3 py-2 text-xs shadow-lg">
      <p className="text-soc-muted mb-1">{label}</p>
      {payload.map((p) => (
        <p key={p.dataKey} style={{ color: p.color }} className="font-medium">
          {p.name}: {p.value}
        </p>
      ))}
    </div>
  )
}

export default function FraudChart({ data }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.15 }}
      className="glass p-5"
    >
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-sm font-semibold">Fraud Probability Over Time</h2>
          <p className="text-[11px] text-soc-muted mt-0.5">Live updating — last 30 data points</p>
        </div>
        <div className="flex items-center gap-3 text-[10px] text-soc-muted">
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-0.5 rounded bg-soc-accent inline-block" /> Transactions
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-0.5 rounded bg-soc-danger inline-block" /> Fraud
          </span>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={260}>
        <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
          <defs>
            <linearGradient id="gTx" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="gFr" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#ef4444" stopOpacity={0.4} />
              <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#1a2744" vertical={false} />
          <XAxis dataKey="time" tick={{ fontSize: 10, fill: '#64748b' }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fontSize: 10, fill: '#64748b' }} axisLine={false} tickLine={false} />
          <Tooltip content={<CustomTooltip />} />
          <Area
            type="monotone" dataKey="count" name="Transactions"
            stroke="#3b82f6" strokeWidth={2} fill="url(#gTx)"
            animationDuration={600}
          />
          <Area
            type="monotone" dataKey="fraud" name="Fraud"
            stroke="#ef4444" strokeWidth={2} fill="url(#gFr)"
            animationDuration={600}
          />
        </AreaChart>
      </ResponsiveContainer>
    </motion.div>
  )
}
