import { motion } from 'framer-motion'
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts'

const COLORS = {
  SAFE:       '#10b981',
  SUSPICIOUS: '#f59e0b',
  FRAUD:      '#ef4444',
}

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null
  const d = payload[0]
  return (
    <div className="glass-sm px-3 py-2 text-xs shadow-lg">
      <p style={{ color: COLORS[d.name] || '#e2e8f0' }} className="font-medium">
        {d.name}: {d.value}
      </p>
    </div>
  )
}

export default function RiskPieChart({ data }) {
  const total = data.reduce((s, d) => s + d.value, 0) || 1

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.2 }}
      className="glass p-5"
    >
      <h2 className="text-sm font-semibold mb-1">Risk Distribution</h2>
      <p className="text-[11px] text-soc-muted mb-4">Based on monitored transactions</p>

      <div className="flex items-center">
        <ResponsiveContainer width="55%" height={220}>
          <PieChart>
            <Pie
              data={data}
              cx="50%" cy="50%"
              innerRadius={60} outerRadius={90}
              paddingAngle={3}
              dataKey="value"
              animationBegin={200}
              animationDuration={800}
              stroke="none"
            >
              {data.map((entry) => (
                <Cell key={entry.name} fill={COLORS[entry.name] || '#475569'} />
              ))}
            </Pie>
            <Tooltip content={<CustomTooltip />} />
          </PieChart>
        </ResponsiveContainer>

        <div className="flex-1 space-y-3 pl-2">
          {data.map((d) => {
            const pct = ((d.value / total) * 100).toFixed(1)
            return (
              <div key={d.name} className="flex items-center gap-3">
                <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: COLORS[d.name] }} />
                <div className="flex-1">
                  <div className="flex justify-between text-xs">
                    <span className="font-medium">{d.name}</span>
                    <span className="tabular-nums text-soc-muted">{d.value}</span>
                  </div>
                  <div className="h-1 rounded-full bg-soc-border/60 mt-1 overflow-hidden">
                    <motion.div
                      className="h-full rounded-full"
                      style={{ backgroundColor: COLORS[d.name] }}
                      initial={{ width: 0 }}
                      animate={{ width: `${pct}%` }}
                      transition={{ duration: 0.8, ease: 'easeOut' }}
                    />
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </motion.div>
  )
}
