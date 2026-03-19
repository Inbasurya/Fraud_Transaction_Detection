import { useState } from 'react'
import { retrainModels, uploadModelDataset } from '../services/api'

export default function ModelTrainingPanel() {
  const [modelType, setModelType] = useState('all')
  const [file, setFile] = useState(null)
  const [status, setStatus] = useState('')
  const [response, setResponse] = useState(null)

  const handleRetrain = async () => {
    setStatus('Retraining models...')
    try {
      const res = await retrainModels(modelType)
      setResponse(res)
      setStatus('Retraining completed.')
    } catch (error) {
      setStatus(error?.response?.data?.detail || 'Retraining failed.')
    }
  }

  const handleUpload = async () => {
    if (!file) return
    setStatus('Uploading dataset...')
    try {
      const res = await uploadModelDataset(file, modelType === 'behavior' ? 'behavior' : 'supervised')
      setResponse(res)
      setStatus('Dataset uploaded and model retrained.')
    } catch (error) {
      setStatus(error?.response?.data?.detail || 'Dataset upload failed.')
    }
  }

  return (
    <section className="soc-grid">
      <article className="soc-card">
        <h2>Model Training Panel</h2>
        <p>Admin controls for retraining and dataset updates.</p>
        <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap', marginBottom: '0.8rem' }}>
          <select className="soc-input" value={modelType} onChange={(e) => setModelType(e.target.value)}>
            <option value="all">All Models</option>
            <option value="supervised">Supervised</option>
            <option value="behavior">Behavior</option>
          </select>
          <button className="soc-btn" onClick={handleRetrain}>Retrain</button>
        </div>
        <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap' }}>
          <input type="file" className="soc-input" onChange={(e) => setFile(e.target.files?.[0] || null)} />
          <button className="soc-btn" onClick={handleUpload}>Upload Dataset</button>
        </div>
        {status ? <p style={{ marginTop: '0.8rem' }}>{status}</p> : null}
      </article>

      <article className="soc-card">
        <h2>Training Response</h2>
        <pre style={{ margin: 0, whiteSpace: 'pre-wrap', fontSize: '0.74rem' }}>
          {response ? JSON.stringify(response, null, 2) : 'No training operation executed yet.'}
        </pre>
      </article>
    </section>
  )
}
