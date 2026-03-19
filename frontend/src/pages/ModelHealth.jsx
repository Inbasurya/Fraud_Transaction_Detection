import { useMemo } from 'react'
import { useSelector } from 'react-redux'
import { Area, AreaChart, CartesianGrid, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

export default function ModelHealth() {
  const health = useSelector((s) => s.platform.modelHealth)

  const amountDriftData = useMemo(() => {
    const current = health?.feature_distribution?.amount_histogram_current || []
    const baseline = health?.feature_distribution?.amount_histogram_baseline || []
    return current.map((v, i) => ({
      bin: `B${i + 1}`,
      current: Number(v || 0),
      baseline: Number(baseline[i] || 0),
    }))
  }, [health])

  const predictionData = useMemo(() => {
    const p = health?.prediction_distribution || {}
    return [
      { label: 'SAFE', value: Number(p.SAFE || 0) },
      { label: 'SUSPICIOUS', value: Number(p.SUSPICIOUS || 0) },
      { label: 'FRAUD', value: Number(p.FRAUD || 0) },
    ]
  }, [health])

  if (!health) {
    return <section className="soc-card">Model health data is loading.</section>
  }

  return (
    <section className="soc-grid">
      <div className="soc-grid-kpi">
        <article className="soc-card kpi">
          <span>Status</span>
          <h3>{health.status}</h3>
        </article>
        <article className="soc-card kpi warn">
          <span>Amount PSI</span>
          <h3>{Number(health.feature_distribution?.amount_psi || 0).toFixed(4)}</h3>
        </article>
        <article className="soc-card kpi danger">
          <span>Hour PSI</span>
          <h3>{Number(health.feature_distribution?.hour_psi || 0).toFixed(4)}</h3>
        </article>
        <article className="soc-card kpi accent">
          <span>Accuracy Proxy Δ</span>
          <h3>{Number(health.accuracy_changes?.proxy_delta || 0).toFixed(4)}</h3>
        </article>
      </div>

      <article className="soc-card">
        <h2>Feature Distribution Drift (Amount)</h2>
        <ResponsiveContainer width="100%" height={280}>
          <AreaChart data={amountDriftData}>
            <CartesianGrid strokeDasharray="4 4" stroke="#213046" />
            <XAxis dataKey="bin" stroke="#8ca0bf" />
            <YAxis stroke="#8ca0bf" />
            <Tooltip />
            <Area type="monotone" dataKey="baseline" stroke="#6be8ff" fillOpacity={0.08} fill="#6be8ff" />
            <Area type="monotone" dataKey="current" stroke="#ff5f8f" fillOpacity={0.1} fill="#ff5f8f" />
          </AreaChart>
        </ResponsiveContainer>
      </article>

      <article className="soc-card">
        <h2>Prediction Distribution</h2>
        <ResponsiveContainer width="100%" height={280}>
          <PieChart>
            <Pie data={predictionData} dataKey="value" nameKey="label" outerRadius={96} fill="#6be8ff" label />
            <Tooltip />
          </PieChart>
        </ResponsiveContainer>
      </article>

      <article className="soc-card">
        <h2>Drift Alerts</h2>
        {health.alerts?.length ? (
          <ul className="alert-list">
            {health.alerts.map((a) => (
              <li key={a} className="alert-critical">
                <strong>Drift Alert</strong>
                <p>{a}</p>
              </li>
            ))}
          </ul>
        ) : (
          <p>No drift alerts triggered.</p>
        )}
      </article>
    </section>
  )
}
