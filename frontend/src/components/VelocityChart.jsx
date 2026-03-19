import { motion } from 'framer-motion'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import { useEffect, useState } from 'react'
import { fetchVelocity } from '../services/api'

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="glass-sm px-3 py-2 text-xs shadow-lg">
      <p className="text-soc-muted mb-1">Hour: {label}:00</p>
      <p className="text-soc-accent font-medium">Transactions: {payload[0]?.value}</p>
    </div>
  )
}

export default function VelocityChart() {
  const [data, setData] = useState([])

  useEffect(() => {
    const load = () => fetchVelocity().then(setData).catch(() => {})
    load()
    const id = setInterval(load, 15000)
    return () => clearInterval(id)
  }, [])

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.3 }}
      className="glass p-5"
    >
      <div className="mb-4">
        <h2 className="text-sm font-semibold">Transaction Velocity</h2>
        <p className="text-[11px] text-soc-muted mt-0.5">Transactions per hour distribution</p>
      </div>

      {data.length === 0 ? (
        <div className="flex items-center justify-center h-[220px] text-soc-muted text-xs">
          Collecting velocity data…
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={220}>
          <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
            <defs>
              <linearGradient id="gVelocity" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#1a2744" vertical={false} />
            <XAxis dataKey="hour" tick={{ fontSize: 10, fill: '#64748b' }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 10, fill: '#64748b' }} axisLine={false} tickLine={false} />
            <Tooltip content={<CustomTooltip />} />
            <Area
              type="monotone" dataKey="count" name="Transactions"
              stroke="#8b5cf6" strokeWidth={2} fill="url(#gVelocity)"
              animationDuration={600}
            />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </motion.div>
  )
}
