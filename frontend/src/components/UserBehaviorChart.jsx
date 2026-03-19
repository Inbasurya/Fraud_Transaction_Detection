import { motion } from 'framer-motion'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell,
} from 'recharts'
import { useMemo } from 'react'

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="glass-sm px-3 py-2 text-xs shadow-lg">
      <p className="text-soc-muted mb-1">User {label}</p>
      {payload.map((p) => (
        <p key={p.dataKey} style={{ color: p.color }} className="font-medium">
          {p.name}: ${Number(p.value).toFixed(2)}
        </p>
      ))}
    </div>
  )
}

export default function UserBehaviorChart({ transactions }) {
  const chartData = useMemo(() => {
    const userMap = {}
    transactions.forEach((tx) => {
      const uid = typeof tx.user_id === 'number'
        ? `U${String(tx.user_id).padStart(4, '0')}`
        : tx.user_id
      if (!uid) return
      if (!userMap[uid]) userMap[uid] = { total: 0, count: 0 }
      userMap[uid].total += Number(tx.amount) || 0
      userMap[uid].count += 1
    })
    // Average spend per user, globally
    const globalAvg =
      Object.values(userMap).reduce((s, u) => s + u.total / u.count, 0) /
      (Object.keys(userMap).length || 1)

    return Object.entries(userMap)
      .sort((a, b) => b[1].total / b[1].count - a[1].total / a[1].count)
      .slice(0, 10)
      .map(([uid, u]) => ({
        user: uid,
        spending: Math.round((u.total / u.count) * 100) / 100,
        average: Math.round(globalAvg * 100) / 100,
      }))
  }, [transactions])

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.25 }}
      className="glass p-5"
    >
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-sm font-semibold">User Behavior Analysis</h2>
          <p className="text-[11px] text-soc-muted mt-0.5">Top 10 users — avg spend vs global average</p>
        </div>
        <div className="flex items-center gap-3 text-[10px] text-soc-muted">
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 rounded bg-soc-accent inline-block" /> User Avg
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 rounded bg-soc-muted/40 inline-block" /> Global Avg
          </span>
        </div>
      </div>

      {chartData.length === 0 ? (
        <div className="h-[220px] flex items-center justify-center text-soc-muted text-xs">
          Waiting for transaction data…
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: -10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1a2744" vertical={false} />
            <XAxis
              dataKey="user"
              tick={{ fontSize: 9, fill: '#64748b' }}
              axisLine={false}
              tickLine={false}
              angle={-35}
              textAnchor="end"
              height={40}
            />
            <YAxis tick={{ fontSize: 10, fill: '#64748b' }} axisLine={false} tickLine={false} />
            <Tooltip content={<CustomTooltip />} />
            <Bar dataKey="average" name="Global Avg" fill="#334155" radius={[4, 4, 0, 0]} animationDuration={600} />
            <Bar dataKey="spending" name="User Avg Spend" radius={[4, 4, 0, 0]} animationDuration={600}>
              {chartData.map((d, i) => (
                <Cell key={i} fill={d.spending > d.average * 2 ? '#ef4444' : d.spending > d.average ? '#f59e0b' : '#3b82f6'} fillOpacity={0.8} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </motion.div>
  )
}
