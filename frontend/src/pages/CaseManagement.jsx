import { useEffect, useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { fetchCases, updateCase, createCase, fileSAR } from '../services/api'

const COLUMNS = [
  { status: 'OPEN', label: 'Open', color: '#6be8ff', icon: '📂' },
  { status: 'INVESTIGATING', label: 'Investigating', color: '#f6c667', icon: '🔍' },
  { status: 'RESOLVED', label: 'Resolved', color: '#53e2a1', icon: '✅' },
]

const PRIORITY_COLORS = {
  CRITICAL: '#ff5f8f',
  HIGH: '#f6c667',
  MEDIUM: '#6be8ff',
  LOW: '#53e2a1',
}

function timeSince(dateStr) {
  if (!dateStr) return '—'
  const diff = Date.now() - new Date(dateStr).getTime()
  const hours = Math.floor(diff / 3600000)
  if (hours < 1) return `${Math.floor(diff / 60000)}m ago`
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

function CaseCard({ c, onMoveStatus, onViewDetails }) {
  const slaHours = c.priority === 'CRITICAL' ? 2 : c.priority === 'HIGH' ? 4 : c.priority === 'MEDIUM' ? 12 : 24
  const elapsed = c.created_at ? (Date.now() - new Date(c.created_at).getTime()) / 3600000 : 0
  const slaExceeded = c.status !== 'RESOLVED' && elapsed > slaHours

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      className="soc-card"
      style={{
        padding: '0.6rem 0.8rem',
        marginBottom: '0.5rem',
        cursor: 'pointer',
        borderLeft: `3px solid ${PRIORITY_COLORS[c.priority] || '#6be8ff'}`,
        background: slaExceeded ? 'rgba(255,95,143,0.05)' : undefined,
      }}
      onClick={() => onViewDetails(c)}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '0.3rem' }}>
        <span style={{ fontSize: '0.75rem', fontWeight: 600 }}>Case #{c.case_id}</span>
        <span style={{
          fontSize: '0.65rem',
          padding: '1px 6px',
          borderRadius: '4px',
          background: `${PRIORITY_COLORS[c.priority]}22`,
          color: PRIORITY_COLORS[c.priority],
        }}>
          {c.priority}
        </span>
      </div>

      {c.alert_id && (
        <p style={{ fontSize: '0.7rem', color: 'var(--muted)', margin: '0.15rem 0' }}>Alert: #{c.alert_id}</p>
      )}
      {c.assigned_analyst && (
        <p style={{ fontSize: '0.7rem', margin: '0.15rem 0' }}>👤 {c.assigned_analyst}</p>
      )}

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '0.4rem' }}>
        <span style={{ fontSize: '0.65rem', color: slaExceeded ? '#ff5f8f' : 'var(--muted)' }}>
          {slaExceeded ? '⚠️ SLA breached' : `⏱ ${timeSince(c.created_at)}`}
        </span>

        {c.status !== 'RESOLVED' && (
          <div style={{ display: 'flex', gap: '0.3rem' }}>
            {c.status === 'OPEN' && (
              <button
                className="soc-btn"
                style={{ fontSize: '0.6rem', padding: '2px 6px' }}
                onClick={(e) => { e.stopPropagation(); onMoveStatus(c.case_id, 'INVESTIGATING') }}
              >Investigate</button>
            )}
            {c.status === 'INVESTIGATING' && (
              <button
                className="soc-btn"
                style={{ fontSize: '0.6rem', padding: '2px 6px' }}
                onClick={(e) => { e.stopPropagation(); onMoveStatus(c.case_id, 'RESOLVED') }}
              >Resolve</button>
            )}
          </div>
        )}
      </div>
    </motion.div>
  )
}

function CaseDetailModal({ c, onClose, onUpdate }) {
  const [notes, setNotes] = useState(c.notes || '')
  const [resolution, setResolution] = useState(c.resolution || '')
  const [analyst, setAnalyst] = useState(c.assigned_analyst || '')
  const [saving, setSaving] = useState(false)
  const [sarMsg, setSarMsg] = useState(null)

  const handleSave = async () => {
    setSaving(true)
    try {
      await updateCase(c.case_id, {
        notes,
        resolution: resolution || undefined,
        assigned_analyst: analyst || undefined,
      })
      onUpdate()
    } catch { /* noop */ }
    setSaving(false)
  }

  const handleSAR = async () => {
    try {
      await fileSAR(c.case_id, { notes: `SAR filed for case #${c.case_id}` })
      setSarMsg('SAR filed successfully')
      onUpdate()
    } catch {
      setSarMsg('SAR filing failed')
    }
  }

  return (
    <div className="soc-modal-backdrop" onClick={onClose}>
      <div className="soc-modal-card" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '500px' }}>
        <div className="panel-head">
          <h2 style={{ fontSize: '1rem' }}>Case #{c.case_id}</h2>
          <button className="soc-btn" onClick={onClose}>Close</button>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', fontSize: '0.8rem', margin: '0.8rem 0' }}>
          <p><strong>Status:</strong> {c.status}</p>
          <p><strong>Priority:</strong> <span style={{ color: PRIORITY_COLORS[c.priority] }}>{c.priority}</span></p>
          <p><strong>Alert ID:</strong> {c.alert_id || '—'}</p>
          <p><strong>Created:</strong> {timeSince(c.created_at)}</p>
          <p><strong>SAR Required:</strong> {c.sar_required ? 'Yes' : 'No'}</p>
          <p><strong>SAR Filed:</strong> {c.sar_filed_at ? new Date(c.sar_filed_at).toLocaleDateString() : 'No'}</p>
        </div>

        <div style={{ marginBottom: '0.5rem' }}>
          <label style={{ fontSize: '0.75rem', color: 'var(--muted)' }}>Assigned Analyst</label>
          <input
            value={analyst}
            onChange={(e) => setAnalyst(e.target.value)}
            className="soc-input"
            style={{ width: '100%', marginTop: '0.2rem' }}
            placeholder="analyst@company.com"
          />
        </div>

        <div style={{ marginBottom: '0.5rem' }}>
          <label style={{ fontSize: '0.75rem', color: 'var(--muted)' }}>Resolution</label>
          <select
            value={resolution}
            onChange={(e) => setResolution(e.target.value)}
            className="soc-input"
            style={{ width: '100%', marginTop: '0.2rem' }}
          >
            <option value="">— Select —</option>
            <option value="confirmed_fraud">Confirmed Fraud</option>
            <option value="false_positive">False Positive</option>
            <option value="inconclusive">Inconclusive</option>
          </select>
        </div>

        <div style={{ marginBottom: '0.8rem' }}>
          <label style={{ fontSize: '0.75rem', color: 'var(--muted)' }}>Notes</label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            className="soc-input"
            style={{ width: '100%', marginTop: '0.2rem', minHeight: '80px', resize: 'vertical' }}
            placeholder="Investigation notes..."
          />
        </div>

        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className="soc-btn" onClick={handleSave} disabled={saving}>
            {saving ? 'Saving…' : '💾 Save'}
          </button>
          {c.sar_required && !c.sar_filed_at && (
            <button className="soc-btn" onClick={handleSAR} style={{ borderColor: 'rgba(255,95,143,0.5)' }}>
              📄 File SAR
            </button>
          )}
          {sarMsg && <span className="soc-pill" style={{ fontSize: '0.7rem' }}>{sarMsg}</span>}
        </div>
      </div>
    </div>
  )
}

export default function CaseManagement() {
  const [cases, setCases] = useState([])
  const [loading, setLoading] = useState(true)
  const [detailCase, setDetailCase] = useState(null)
  const [showCreate, setShowCreate] = useState(false)
  const [newAlertId, setNewAlertId] = useState('')
  const [newPriority, setNewPriority] = useState('MEDIUM')

  const loadCases = useCallback(async () => {
    try {
      const data = await fetchCases(null, 200)
      setCases(Array.isArray(data) ? data : data?.cases || [])
    } catch { /* noop */ }
    setLoading(false)
  }, [])

  useEffect(() => {
    loadCases()
    const id = setInterval(loadCases, 20000)
    return () => clearInterval(id)
  }, [loadCases])

  const handleMoveStatus = async (caseId, newStatus) => {
    try {
      await updateCase(caseId, { status: newStatus })
      loadCases()
    } catch { /* noop */ }
  }

  const handleCreateCase = async () => {
    try {
      await createCase({
        alert_id: newAlertId ? Number(newAlertId) : undefined,
        priority: newPriority,
      })
      setShowCreate(false)
      setNewAlertId('')
      loadCases()
    } catch { /* noop */ }
  }

  const grouped = COLUMNS.map((col) => ({
    ...col,
    items: cases.filter((c) => c.status === col.status),
  }))

  const totalOpen = grouped.find((g) => g.status === 'OPEN')?.items.length || 0
  const totalInvestigating = grouped.find((g) => g.status === 'INVESTIGATING')?.items.length || 0
  const criticalCount = cases.filter((c) => c.priority === 'CRITICAL' && c.status !== 'RESOLVED').length

  return (
    <div className="soc-grid" style={{ gap: '1rem' }}>
      {/* Header */}
      <div className="soc-card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
        <div>
          <h2 style={{ margin: 0, fontSize: '1.1rem' }}>📋 Case Management</h2>
          <p style={{ margin: '0.2rem 0 0', color: 'var(--muted)', fontSize: '0.82rem' }}>
            Kanban board — move cases through investigation lifecycle
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <span className="soc-pill">Open: {totalOpen}</span>
          <span className="soc-pill" style={{ color: '#f6c667' }}>Investigating: {totalInvestigating}</span>
          {criticalCount > 0 && <span className="soc-pill" style={{ color: '#ff5f8f' }}>🚨 Critical: {criticalCount}</span>}
          <button className="soc-btn" onClick={() => setShowCreate(!showCreate)} style={{ fontSize: '0.75rem' }}>
            + New Case
          </button>
        </div>
      </div>

      {/* Create Case Inline */}
      {showCreate && (
        <div className="soc-card" style={{ display: 'flex', gap: '0.8rem', alignItems: 'end', flexWrap: 'wrap' }}>
          <div>
            <label style={{ fontSize: '0.72rem', color: 'var(--muted)' }}>Alert ID (optional)</label>
            <input
              value={newAlertId}
              onChange={(e) => setNewAlertId(e.target.value)}
              className="soc-input"
              style={{ marginTop: '0.2rem', width: '120px' }}
              placeholder="e.g., 42"
            />
          </div>
          <div>
            <label style={{ fontSize: '0.72rem', color: 'var(--muted)' }}>Priority</label>
            <select value={newPriority} onChange={(e) => setNewPriority(e.target.value)} className="soc-input" style={{ marginTop: '0.2rem' }}>
              <option value="LOW">Low</option>
              <option value="MEDIUM">Medium</option>
              <option value="HIGH">High</option>
              <option value="CRITICAL">Critical</option>
            </select>
          </div>
          <button className="soc-btn" onClick={handleCreateCase}>Create</button>
        </div>
      )}

      {/* Kanban Board */}
      {loading ? (
        <div className="soc-card" style={{ textAlign: 'center', padding: '3rem', color: 'var(--muted)' }}>
          Loading cases…
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem', minHeight: '55vh' }}>
          {grouped.map((col) => (
            <div key={col.status}>
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: '0.6rem',
                padding: '0 0.2rem',
              }}>
                <span style={{ fontSize: '0.85rem', fontWeight: 600, color: col.color }}>
                  {col.icon} {col.label}
                </span>
                <span className="soc-pill" style={{ fontSize: '0.7rem' }}>{col.items.length}</span>
              </div>

              <div style={{
                minHeight: '40vh',
                background: 'rgba(255,255,255,0.01)',
                borderRadius: '8px',
                padding: '0.4rem',
                border: '1px dashed rgba(255,255,255,0.06)',
              }}>
                <AnimatePresence>
                  {col.items
                    .sort((a, b) => {
                      const pri = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 }
                      return (pri[a.priority] ?? 2) - (pri[b.priority] ?? 2)
                    })
                    .map((c) => (
                      <CaseCard
                        key={c.case_id}
                        c={c}
                        onMoveStatus={handleMoveStatus}
                        onViewDetails={setDetailCase}
                      />
                    ))}
                </AnimatePresence>
                {col.items.length === 0 && (
                  <p style={{ textAlign: 'center', color: 'var(--muted)', fontSize: '0.75rem', padding: '2rem 0' }}>
                    No cases
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Detail Modal */}
      {detailCase && (
        <CaseDetailModal
          c={detailCase}
          onClose={() => setDetailCase(null)}
          onUpdate={() => { setDetailCase(null); loadCases() }}
        />
      )}
    </div>
  )
}
