import { motion } from 'framer-motion'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell } from 'recharts'
import { useEffect, useState } from 'react'
import { fetchTopMerchants } from '../services/api'

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="glass-sm px-3 py-2 text-xs shadow-lg">
      <p className="font-medium text-soc-text mb-1">{d.merchant}</p>
      <p className="text-soc-danger">Fraud count: {d.fraud_count}</p>
      <p className="text-soc-warn">Avg risk: {d.avg_risk?.toFixed(4)}</p>
    </div>
  )
}

export default function MerchantRiskChart() {
  const [data, setData] = useState([])

  useEffect(() => {
    const load = () => fetchTopMerchants(8).then(setData).catch(() => {})
    load()
    const id = setInterval(load, 15000)
    return () => clearInterval(id)
  }, [])

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.25 }}
      className="glass p-5"
    >
      <div className="mb-4">
        <h2 className="text-sm font-semibold">Top Risky Merchants</h2>
        <p className="text-[11px] text-soc-muted mt-0.5">Merchants with highest fraud incidents</p>
      </div>

      {data.length === 0 ? (
        <div className="flex items-center justify-center h-[220px] text-soc-muted text-xs">
          Collecting merchant data…
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1a2744" vertical={false} />
            <XAxis
              dataKey="merchant"
              tick={{ fontSize: 9, fill: '#64748b' }}
              axisLine={false}
              tickLine={false}
              interval={0}
              angle={-25}
              textAnchor="end"
              height={50}
            />
            <YAxis tick={{ fontSize: 10, fill: '#64748b' }} axisLine={false} tickLine={false} />
            <Tooltip content={<CustomTooltip />} />
            <Bar dataKey="fraud_count" name="Fraud Count" radius={[4, 4, 0, 0]} animationDuration={600}>
              {data.map((entry, i) => (
                <Cell key={i} fill={entry.avg_risk > 0.6 ? '#ef4444' : entry.avg_risk > 0.4 ? '#f59e0b' : '#3b82f6'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </motion.div>
  )
}
