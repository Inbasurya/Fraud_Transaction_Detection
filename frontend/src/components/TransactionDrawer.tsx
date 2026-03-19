import { useEffect } from 'react'

interface Props {
  txn: any
  onClose: () => void
}

export default function TransactionDrawer({ txn, onClose }: Props) {
  if (!txn) return null

  // Close on ESC
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  const riskColor = txn.risk_level === 'fraudulent' ? '#EF4444' 
    : txn.risk_level === 'suspicious' ? '#F59E0B' : '#10B981'

  const riskBg = txn.risk_level === 'fraudulent' ? '#FEF2F2'
    : txn.risk_level === 'suspicious' ? '#FFFBEB' : '#F0FDF4'

  const actionColor: Record<string, string> = {
    block: '#EF4444',
    flag_and_review: '#F59E0B',
    step_up_auth: '#3B82F6',
    monitor: '#8B5CF6',
    approve: '#10B981'
  }

  const shap = txn.shap_values || {}
  const shapEntries = Object.entries(shap).sort((a: any, b: any) => Math.abs(b[1]) - Math.abs(a[1]))

  const formatFeatureName = (key: string) => {
    const names: Record<string, string> = {
      amount_vs_avg: 'Amount vs 30d average',
      velocity_1h: 'Transaction velocity (1h)',
      geo_risk: 'Geographic risk',
      device_trust: 'Device trust score',
      merchant_risk: 'Merchant risk (MCC)',
      amount_anomaly: 'Amount anomaly score',
      geo_anomaly: 'Geographic anomaly',
      merchant_anomaly: 'Merchant familiarity',
      time_anomaly: 'Time of day pattern',
      device_anomaly: 'Device recognition',
      network_risk_score: 'Network graph risk',
      sim_swap_risk: 'SIM swap signal'
    }
    return names[key] || key.replace(/_/g, ' ')
  }

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed', inset: 0,
          background: 'rgba(0,0,0,0.35)',
          zIndex: 40,
          animation: 'fadeIn 0.2s ease'
        }}
      />

      {/* Drawer */}
      <div style={{
        position: 'fixed', top: 0, right: 0, bottom: 0,
        width: '440px',
        background: 'white',
        zIndex: 50,
        overflowY: 'auto',
        animation: 'slideInRight 0.25s ease',
        boxShadow: '-4px 0 24px rgba(0,0,0,0.15)',
        display: 'flex', flexDirection: 'column'
      }}>

        {/* Header */}
        <div style={{ padding: '16px 20px', borderBottom: '1px solid #F1F5F9', flexShrink: 0 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <div style={{ fontFamily: 'monospace', fontSize: '13px', color: '#64748B', marginBottom: '6px' }}>
                {txn.id}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <span style={{
                  fontSize: '24px', fontWeight: 800, color: riskColor,
                  letterSpacing: '-1px'
                }}>{txn.risk_score}</span>
                <span style={{
                  fontSize: '11px', fontWeight: 700, padding: '3px 10px',
                  background: riskBg, color: riskColor,
                  borderRadius: '20px', letterSpacing: '0.3px'
                }}>{txn.risk_level.toUpperCase()}</span>
              </div>
            </div>
            <button onClick={onClose} style={{
              background: 'none', border: 'none', cursor: 'pointer',
              fontSize: '18px', color: '#94A3B8', padding: '4px'
            }}>✕</button>
          </div>
        </div>

        <div style={{ padding: '0 20px 20px', flex: 1 }}>

          {/* Why flagged — most important */}
          <div style={{
            margin: '16px 0',
            padding: '12px 14px',
            background: txn.risk_level === 'safe' ? '#F0FDF4' : txn.risk_level === 'fraudulent' ? '#FEF2F2' : '#FFFBEB',
            border: `1px solid ${txn.risk_level === 'safe' ? '#BBF7D0' : txn.risk_level === 'fraudulent' ? '#FECACA' : '#FDE68A'}`,
            borderRadius: '10px'
          }}>
            <div style={{ fontSize: '11px', fontWeight: 700, color: riskColor, marginBottom: '4px', letterSpacing: '0.3px' }}>
              {txn.risk_level === 'safe' ? 'WHY APPROVED' : 'WHY FLAGGED'}
            </div>
            <div style={{ fontSize: '13px', color: '#0F172A', fontWeight: 500, lineHeight: 1.5 }}>
              {(() => {
                if (txn.risk_level === 'safe') return 'No anomalies detected — transaction approved'
                if (txn.scenario_description && txn.scenario_description !== 'Normal transaction' && txn.scenario_description !== 'Normal transaction — no anomalies')
                  return txn.scenario_description
                if (txn.rule_names?.length > 0) return `Triggered: ${txn.rule_names.join(', ')}`
                if (txn.shap_top_feature) return `ML detected: ${txn.shap_top_feature.replace(/_/g, ' ')} anomaly`
                return txn.risk_level === 'fraudulent' ? 'Fraud pattern detected by ML model' : 'Suspicious behavior detected'
              })()}
            </div>
            {txn.risk_level !== 'safe' && txn.rule_names?.length > 0 && (
              <div style={{ marginTop: '8px', display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                {txn.rule_names.map((rule: string, i: number) => (
                  <span key={i} style={{
                    fontSize: '10px', fontWeight: 700, padding: '2px 8px',
                    background: '#FEE2E2', color: '#DC2626', borderRadius: '4px'
                  }}>{rule}</span>
                ))}
              </div>
            )}
          </div>

          {/* Action taken */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: '8px',
            marginBottom: '16px', flexWrap: 'wrap',
          }}>
            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: '6px',
              padding: '5px 12px', borderRadius: '20px',
              background: `${actionColor[txn.action] || '#64748B'}15`,
              border: `1px solid ${actionColor[txn.action] || '#64748B'}40`
            }}>
              <span style={{ fontSize: '11px', fontWeight: 700, color: actionColor[txn.action] || '#64748B' }}>
                ACTION: {(txn.action || 'approve').replace(/_/g, ' ').toUpperCase()}
              </span>
            </div>
            {txn.confidence && (
              <span style={{ fontSize: '11px', fontWeight: 600, color: '#64748B' }}>
                Confidence: {(txn.confidence * 100).toFixed(1)}%
              </span>
            )}
          </div>

          {/* Scoring metadata */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginBottom: '16px' }}>
            <div style={{ background: '#F8FAFC', borderRadius: '8px', padding: '8px 10px', border: '1px solid #F1F5F9' }}>
              <div style={{ fontSize: '10px', color: '#94A3B8', fontWeight: 600, marginBottom: '2px' }}>Response time</div>
              <div style={{ fontSize: '12px', color: '#0F172A', fontWeight: 600 }}>{txn.response_time_ms ? `${txn.response_time_ms}ms` : '—'}</div>
            </div>
            <div style={{ background: '#F8FAFC', borderRadius: '8px', padding: '8px 10px', border: '1px solid #F1F5F9' }}>
              <div style={{ fontSize: '10px', color: '#94A3B8', fontWeight: 600, marginBottom: '2px' }}>Model version</div>
              <div style={{ fontSize: '12px', color: '#0F172A', fontWeight: 600 }}>{txn.model_version || txn.model_used || 'XGBoost v2.0'}</div>
            </div>
            {txn.triggered_rule_ids?.length > 0 && (
              <div style={{ background: '#F8FAFC', borderRadius: '8px', padding: '8px 10px', border: '1px solid #F1F5F9', gridColumn: '1 / -1' }}>
                <div style={{ fontSize: '10px', color: '#94A3B8', fontWeight: 600, marginBottom: '4px' }}>Rules triggered</div>
                <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                  {txn.triggered_rule_ids.map((id: string, i: number) => (
                    <span key={i} style={{
                      fontSize: '10px', fontWeight: 700, padding: '2px 6px',
                      background: '#EFF6FF', color: '#1D4ED8', borderRadius: '4px', border: '1px solid #BFDBFE'
                    }}>{id}</span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Transaction details grid */}
          <div style={{ marginBottom: '20px' }}>
            <div style={{ fontSize: '11px', fontWeight: 700, color: '#94A3B8', letterSpacing: '0.5px', marginBottom: '10px' }}>
              TRANSACTION DETAILS
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
              {[
                ['Merchant', txn.merchant],
                ['Amount', `₹${(txn.amount || 0).toLocaleString('en-IN')}`],
                ['Customer', txn.customer_id],
                ['City', txn.city || '—'],
                ['Category', txn.merchant_category?.replace(/_/g, ' ') || '—'],
                ['Device', txn.device + (txn.is_new_device ? ' ⚠ NEW' : '')],
                ['Time', txn.timestamp ? new Date(txn.timestamp).toLocaleTimeString('en-IN') : '—'],
                ['Fraud scenario', txn.fraud_scenario || 'None'],
              ].map(([label, value]) => (
                <div key={label} style={{
                  background: '#F8FAFC', borderRadius: '8px',
                  padding: '8px 10px', border: '1px solid #F1F5F9'
                }}>
                  <div style={{ fontSize: '10px', color: '#94A3B8', fontWeight: 600, marginBottom: '2px' }}>{label}</div>
                  <div style={{
                    fontSize: '12px', color: label === 'Device' && txn.is_new_device ? '#F59E0B' : '#0F172A',
                    fontWeight: 600
                  }}>{value}</div>
                </div>
              ))}
            </div>
          </div>
          
          {/* Payment Details */}
          <div style={{ marginBottom: '20px' }}>
            <div style={{ fontSize: '11px', fontWeight: 700, color: '#94A3B8', letterSpacing: '0.5px', marginBottom: '10px' }}>
              PAYMENT DETAILS
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
              {[
                ['Payment mode', txn.payment_mode || '—'],
                ['Bank', txn.bank || '—'],
                ['Card', txn.card_type ? `${txn.card_type} ****${txn.card_last4 || ''}` : '—'],
                ['IP Address', txn.ip_address ? txn.ip_address.replace(/\.\d+\.\d+$/, '.xx.xx') : '—'],
                ['Terminal', txn.terminal_id || '—'],
                ['Response', txn.response_time_ms ? `${txn.response_time_ms}ms` : '—'],
                ['MCC Code', txn.mcc_code || '—'],
              ].map(([label, value]) => (
                <div key={label} style={{
                  background: '#F8FAFC', borderRadius: '8px',
                  padding: '8px 10px', border: '1px solid #F1F5F9'
                }}>
                  <div style={{ fontSize: '10px', color: '#94A3B8', fontWeight: 600, marginBottom: '2px' }}>{label}</div>
                  <div style={{
                    fontSize: '12px', color: '#0F172A', fontWeight: 600
                  }}>{value}</div>
                </div>
              ))}
            </div>
          </div>

          {/* SHAP explanation */}
          {shapEntries.length > 0 && (
            <div style={{ marginBottom: '20px' }}>
              <div style={{ fontSize: '11px', fontWeight: 700, color: '#94A3B8', letterSpacing: '0.5px', marginBottom: '4px' }}>
                AI MODEL EXPLANATION
              </div>
              <div style={{ fontSize: '11px', color: '#CBD5E1', marginBottom: '12px' }}>
                What features drove this risk score (SHAP values)
              </div>
              {shapEntries.slice(0, 6).map(([feature, val]: any) => {
                const isPositive = val > 0
                const absVal = Math.abs(val)
                const pct = Math.min(absVal * 100, 100)
                return (
                  <div key={feature} style={{ marginBottom: '10px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '3px' }}>
                      <span style={{ fontSize: '11px', color: '#64748B' }}>{formatFeatureName(feature)}</span>
                      <span style={{ fontSize: '11px', fontWeight: 700, color: isPositive ? '#EF4444' : '#10B981' }}>
                        {isPositive ? '+' : ''}{val.toFixed ? val.toFixed(3) : val}
                      </span>
                    </div>
                    <div style={{ height: '5px', background: '#F1F5F9', borderRadius: '3px', overflow: 'hidden' }}>
                      <div style={{
                        height: '100%',
                        width: `${pct}%`,
                        background: isPositive ? '#EF4444' : '#10B981',
                        borderRadius: '3px',
                        transition: 'width 0.4s ease'
                      }} />
                    </div>
                    <div style={{ fontSize: '10px', color: '#CBD5E1', marginTop: '2px' }}>
                      {isPositive ? '↑ Increases fraud probability' : '↓ Reduces fraud probability'}
                    </div>
                  </div>
                )
              })}
            </div>
          )}

          {/* Action buttons for non-safe */}
          {txn.risk_level !== 'safe' && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
              <button style={{
                padding: '10px', borderRadius: '8px', border: 'none', cursor: 'pointer',
                background: '#EF4444', color: 'white', fontSize: '12px', fontWeight: 700
              }} onClick={() => alert(`Customer ${txn.customer_id} blocked`)}>
                Block Customer
              </button>
              <button style={{
                padding: '10px', borderRadius: '8px', border: 'none', cursor: 'pointer',
                background: '#3B82F6', color: 'white', fontSize: '12px', fontWeight: 700
              }} onClick={() => alert('OTP sent to customer')}>
                Send OTP
              </button>
              <button style={{
                padding: '10px', borderRadius: '8px',
                border: '1px solid #E2E8F0', cursor: 'pointer',
                background: 'white', color: '#64748B', fontSize: '12px', fontWeight: 600
              }} onClick={() => alert('Case opened for investigation')}>
                Investigate
              </button>
              <button style={{
                padding: '10px', borderRadius: '8px',
                border: '1px solid #E2E8F0', cursor: 'pointer',
                background: 'white', color: '#64748B', fontSize: '12px', fontWeight: 600
              }} onClick={() => alert('Marked as false positive — logged for retraining')}>
                False Positive
              </button>
            </div>
          )}
        </div>
      </div>

      <style>{`
        @keyframes slideInRight {
          from { transform: translateX(100%); }
          to { transform: translateX(0); }
        }
        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
      `}</style>
    </>
  )
}
