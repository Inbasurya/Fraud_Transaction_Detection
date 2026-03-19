import { useSelector } from 'react-redux'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  AreaChart, Area, PieChart, Pie, Cell, Legend,
} from 'recharts'

const COLORS = ['#53e2a1', '#f6c667', '#ff5f8f', '#6be8ff']

export default function ModelPerformancePage() {
  const metrics = useSelector((s) => s.platform.modelMetrics)

  if (!metrics) {
    return (
      <div className="soc-card" style={{ textAlign: 'center', padding: '3rem' }}>
        <h2>Model Performance</h2>
        <p style={{ color: 'var(--muted)' }}>
          No model metrics available yet. Train a model first via Model Training panel.
        </p>
      </div>
    )
  }

  const best = metrics.best_model || metrics
  const cm = best.confusion_matrix || metrics.confusion_matrix || [[0, 0], [0, 0]]
  const rocData = (best.roc_curve || metrics.roc_curve || []).map((p, i) => ({
    fpr: p[0] || p.fpr || 0,
    tpr: p[1] || p.tpr || 0,
    index: i,
  }))

  const featureImportance = (best.feature_importance || metrics.feature_importance || [])
    .slice(0, 12)
    .map((f) => ({
      name: typeof f === 'string' ? f : f.feature || f.name || `F${f.index || 0}`,
      importance: typeof f === 'number' ? f : f.importance || f.value || 0,
    }))
    .sort((a, b) => b.importance - a.importance)

  const tp = cm[1]?.[1] || 0
  const tn = cm[0]?.[0] || 0
  const fp = cm[0]?.[1] || 0
  const fn = cm[1]?.[0] || 0

  const accuracy = best.accuracy || metrics.accuracy || 0
  const precision = best.precision || metrics.precision || 0
  const recall = best.recall || metrics.recall || 0
  const f1 = best.f1_score || best.f1 || metrics.f1_score || 0
  const auc = best.roc_auc || metrics.roc_auc || 0

  const pieData = [
    { name: 'True Positive', value: tp },
    { name: 'True Negative', value: tn },
    { name: 'False Positive', value: fp },
    { name: 'False Negative', value: fn },
  ].filter((d) => d.value > 0)

  return (
    <div className="soc-grid" style={{ gap: '1rem' }}>
      {/* Header */}
      <div className="soc-card">
        <h2 style={{ margin: 0, fontSize: '1.1rem' }}>Model Performance Dashboard</h2>
        <p style={{ margin: '0.2rem 0 0', color: 'var(--muted)', fontSize: '0.82rem' }}>
          Comprehensive model evaluation metrics — accuracy, precision, recall, F1, ROC AUC
        </p>
      </div>

      {/* Core Metrics */}
      <div className="soc-grid-kpi" style={{ gridTemplateColumns: 'repeat(5, 1fr)' }}>
        {[
          { label: 'Accuracy', value: accuracy, color: '#6be8ff' },
          { label: 'Precision', value: precision, color: '#53e2a1' },
          { label: 'Recall', value: recall, color: '#f6c667' },
          { label: 'F1 Score', value: f1, color: '#d4a0ff' },
          { label: 'ROC AUC', value: auc, color: '#ff5f8f' },
        ].map((m) => (
          <div key={m.label} className="soc-card kpi">
            <span>{m.label}</span>
            <h3 style={{ color: m.color }}>
              {typeof m.value === 'number' ? (m.value * (m.value < 1 ? 100 : 1)).toFixed(2) + '%' : '—'}
            </h3>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
        {/* ROC Curve */}
        <div className="soc-card">
          <h2>ROC Curve</h2>
          {rocData.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <AreaChart data={rocData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                <XAxis dataKey="fpr" label={{ value: 'FPR', position: 'bottom', fill: '#89a0c6', fontSize: 11 }} stroke="#4a6080" tick={{ fill: '#89a0c6', fontSize: 10 }} />
                <YAxis label={{ value: 'TPR', angle: -90, position: 'left', fill: '#89a0c6', fontSize: 11 }} stroke="#4a6080" tick={{ fill: '#89a0c6', fontSize: 10 }} />
                <Tooltip contentStyle={{ background: '#0d1529', border: '1px solid rgba(104,133,184,0.35)', borderRadius: 8, color: '#dde9ff' }} />
                <Area type="monotone" dataKey="tpr" stroke="#6be8ff" fill="rgba(107,232,255,0.15)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <p style={{ color: 'var(--muted)', textAlign: 'center' }}>No ROC data available</p>
          )}
        </div>

        {/* Confusion Matrix */}
        <div className="soc-card">
          <h2>Confusion Matrix</h2>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.6rem', maxWidth: '320px', margin: '1rem auto' }}>
            <div className="cm-cell" style={{ background: 'rgba(83,226,161,0.12)', borderColor: 'rgba(83,226,161,0.3)', color: '#53e2a1' }}>
              <div style={{ fontSize: '0.7rem', color: 'var(--muted)' }}>TN</div>
              <div style={{ fontSize: '1.4rem' }}>{tn}</div>
            </div>
            <div className="cm-cell" style={{ background: 'rgba(255,95,143,0.12)', borderColor: 'rgba(255,95,143,0.3)', color: '#ff5f8f' }}>
              <div style={{ fontSize: '0.7rem', color: 'var(--muted)' }}>FP</div>
              <div style={{ fontSize: '1.4rem' }}>{fp}</div>
            </div>
            <div className="cm-cell" style={{ background: 'rgba(246,198,103,0.12)', borderColor: 'rgba(246,198,103,0.3)', color: '#f6c667' }}>
              <div style={{ fontSize: '0.7rem', color: 'var(--muted)' }}>FN</div>
              <div style={{ fontSize: '1.4rem' }}>{fn}</div>
            </div>
            <div className="cm-cell" style={{ background: 'rgba(107,232,255,0.12)', borderColor: 'rgba(107,232,255,0.3)', color: '#6be8ff' }}>
              <div style={{ fontSize: '0.7rem', color: 'var(--muted)' }}>TP</div>
              <div style={{ fontSize: '1.4rem' }}>{tp}</div>
            </div>
          </div>
          <div style={{ display: 'flex', justifyContent: 'center', marginTop: '0.5rem' }}>
            <ResponsiveContainer width="100%" height={180}>
              <PieChart>
                <Pie data={pieData} cx="50%" cy="50%" innerRadius={45} outerRadius={70} dataKey="value" paddingAngle={3}>
                  {pieData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Legend wrapperStyle={{ fontSize: '0.72rem', color: '#89a0c6' }} />
                <Tooltip contentStyle={{ background: '#0d1529', border: '1px solid rgba(104,133,184,0.35)', borderRadius: 8, color: '#dde9ff', fontSize: '0.8rem' }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Feature Importance */}
      {featureImportance.length > 0 && (
        <div className="soc-card">
          <h2>Feature Importance</h2>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={featureImportance} layout="vertical" margin={{ left: 120 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
              <XAxis type="number" stroke="#4a6080" tick={{ fill: '#89a0c6', fontSize: 10 }} />
              <YAxis type="category" dataKey="name" stroke="#4a6080" tick={{ fill: '#89a0c6', fontSize: 10 }} width={115} />
              <Tooltip contentStyle={{ background: '#0d1529', border: '1px solid rgba(104,133,184,0.35)', borderRadius: 8, color: '#dde9ff' }} />
              <Bar dataKey="importance" fill="#6be8ff" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}
