import { useMemo } from 'react'
import { useSelector } from 'react-redux'
import { Bar, BarChart, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

function MetricTile({ label, value }) {
  return (
    <div className="metric-tile">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

export default function ModelIntelligence() {
  const metrics = useSelector((s) => s.platform.modelMetrics)
  const kaggle = metrics?.kaggle_model
  const models = kaggle?.models || {}
  const best = kaggle?.best_model
  const bestMetrics = models?.[best]
  const training = metrics?.training_statistics || {}
  const featureImportance = kaggle?.feature_importance || []

  const rocData = useMemo(() => {
    const curve = bestMetrics?.roc_curve
    if (!curve?.fpr || !curve?.tpr) return []
    return curve.fpr.map((fpr, i) => ({ fpr, tpr: curve.tpr[i] || 0 }))
  }, [bestMetrics])

  if (!metrics) {
    return <section className="soc-card">Model metrics are loading or unavailable.</section>
  }

  return (
    <section className="soc-grid">
      <article className="soc-card">
        <h2>Model Summary</h2>
        <p>Selected best model: <strong>{best}</strong></p>
        <div className="metric-grid">
          <MetricTile label="Rows" value={kaggle?.dataset?.rows || 0} />
          <MetricTile label="Fraud Ratio" value={kaggle?.dataset?.fraud_ratio || 0} />
          <MetricTile label="Best ROC-AUC" value={bestMetrics?.roc_auc || 0} />
          <MetricTile label="Behavior Source" value={metrics?.behavior_model?.dataset?.training_source || '-'} />
          <MetricTile label="Behavior Rows" value={training?.behavioral_dataset?.rows || 0} />
          <MetricTile label="Features" value={training?.behavioral_dataset?.features_used?.length || 0} />
        </div>
      </article>

      <article className="soc-card table-card">
        <h2>Kaggle Model Metrics</h2>
        <div className="soc-table-wrap">
          <table className="soc-table">
            <thead>
              <tr>
                <th>Model</th>
                <th>Accuracy</th>
                <th>Precision</th>
                <th>Recall</th>
                <th>F1</th>
                <th>ROC-AUC</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(models).map(([name, m]) => (
                <tr key={name}>
                  <td>{name}</td>
                  <td>{m.accuracy}</td>
                  <td>{m.precision}</td>
                  <td>{m.recall}</td>
                  <td>{m.f1_score}</td>
                  <td>{m.roc_auc}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </article>

      <article className="soc-card">
        <h2>ROC Curve ({best})</h2>
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={rocData}>
            <XAxis dataKey="fpr" stroke="#8ca0bf" />
            <YAxis dataKey="tpr" stroke="#8ca0bf" />
            <Tooltip />
            <Line type="monotone" dataKey="tpr" stroke="#6be8ff" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </article>

      <article className="soc-card">
        <h2>Confusion Matrix ({best})</h2>
        <div className="cm-grid">
          {(bestMetrics?.confusion_matrix || [[0, 0], [0, 0]]).flat().map((val, idx) => (
            <div className="cm-cell" key={idx}>{val}</div>
          ))}
        </div>
      </article>

      <article className="soc-card">
        <h2>Feature Importance ({best})</h2>
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={featureImportance}>
            <XAxis dataKey="feature" stroke="#8ca0bf" />
            <YAxis stroke="#8ca0bf" />
            <Tooltip />
            <Bar dataKey="importance" fill="#53e2a1" radius={[8, 8, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </article>
    </section>
  )
}
