import { useSelector } from 'react-redux'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from 'recharts'

export default function FraudHeatmap() {
  const heatmap = useSelector((s) => s.platform.heatmap || [])

  return (
    <section className="soc-grid">
      <article className="soc-card">
        <h2>Fraud Heatmap</h2>
        <p>Fraud hotspots and suspicious areas by location intelligence.</p>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={heatmap.slice(0, 15)}>
            <CartesianGrid strokeDasharray="4 4" stroke="#213046" />
            <XAxis dataKey="location" stroke="#8ca0bf" hide />
            <YAxis stroke="#8ca0bf" />
            <Tooltip />
            <Bar dataKey="hotspot_score" fill="#ff5f8f" radius={[8, 8, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </article>

      <article className="soc-card">
        <h2>Hotspot Markers</h2>
        <ResponsiveContainer width="100%" height={280}>
          <ScatterChart>
            <CartesianGrid strokeDasharray="4 4" stroke="#213046" />
            <XAxis dataKey="transactions" name="Transactions" stroke="#8ca0bf" />
            <YAxis dataKey="avg_risk" name="Risk" stroke="#8ca0bf" />
            <ZAxis dataKey="hotspot_score" range={[40, 320]} />
            <Tooltip cursor={{ strokeDasharray: '3 3' }} />
            <Scatter data={heatmap.slice(0, 30)} fill="#ff5f8f" />
          </ScatterChart>
        </ResponsiveContainer>
      </article>

      <article className="soc-card table-card">
        <h2>Hotspot Table</h2>
        <div className="soc-table-wrap">
          <table className="soc-table">
            <thead>
              <tr>
                <th>Location</th>
                <th>Transactions</th>
                <th>Fraud</th>
                <th>Suspicious</th>
                <th>Avg Risk</th>
                <th>Hotspot Score</th>
              </tr>
            </thead>
            <tbody>
              {heatmap.slice(0, 30).map((row) => (
                <tr key={row.location}>
                  <td>{row.location}</td>
                  <td>{row.transactions}</td>
                  <td>{row.fraud_count}</td>
                  <td>{row.suspicious_count}</td>
                  <td>{Number(row.avg_risk || 0).toFixed(4)}</td>
                  <td>{Number(row.hotspot_score || 0).toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </article>
    </section>
  )
}
