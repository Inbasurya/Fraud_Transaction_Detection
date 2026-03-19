import { createContext, useContext, useMemo, useEffect, ReactNode } from 'react'
import { useWebSocket, Transaction, Stats } from '../hooks/useWebSocket'
import { API_BASE } from '../services/api'

// Dynamic host: works on localhost AND network IPs like 10.185.29.154
const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
const WS_HOST = isLocalhost ? 'localhost:8000' : `${window.location.hostname}:8000`
const WS_URL = `ws://${WS_HOST}/ws/transactions`

export interface AlertItem {
  id: string
  title: string
  customer_id: string
  amount: number
  merchant: string
  risk_score: number
  risk_level: string
  triggered_rules: string[]
  rule_names: string[]
  timestamp: string
  status: 'open' | 'investigating' | 'resolved'
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'
  scenario_description?: string
  fraud_scenario?: string
}

interface FraudContextType {
  transactions: Transaction[]
  stats: Stats | null
  status: 'connecting' | 'connected' | 'disconnected'
  txnPerSecond: number
  alerts: AlertItem[]
}

const FraudContext = createContext<FraudContextType | null>(null)

export function FraudProvider({ children }: { children: ReactNode }) {
  const ws = useWebSocket(WS_URL)

  // On mount, fetch persisted metrics from Redis so page refresh doesn't reset to 0
  useEffect(() => {
    fetch(`${API_BASE}/api/metrics/dashboard`)
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data && data.total_transactions > 0 && !ws.stats) {
          // Seed initial stats from Redis — WS stats will overwrite once connected
          ws.setStats({
            type: 'stats',
            total_transactions: data.total_transactions,
            fraud_count: data.blocked_count,
            blocked_count: data.blocked_count,
            suspicious_count: data.flagged_count,
            fraud_rate: data.fraud_rate,
            avg_risk_score: 0,
            txn_per_second: data.scoring_rate || 0,
          })
        }
      })
      .catch(() => {})
  }, [])

  const alerts = useMemo(() => {
    const seen = new Set<string>()
    return ws.transactions
      .filter(t => {
        if (t.risk_score <= 60) return false
        if (seen.has(t.id)) return false
        seen.add(t.id)
        return true
      })
      .slice(0, 30)
      .map(t => ({
        id: t.id,
        title: getFraudTitle(t),
        customer_id: t.customer_id,
        amount: t.amount,
        merchant: t.merchant,
        risk_score: t.risk_score,
        risk_level: t.risk_level,
        triggered_rules: t.triggered_rules,
        rule_names: t.rule_names,
        timestamp: t.timestamp,
        status: 'open' as const,
        severity: t.risk_score >= 85 ? 'CRITICAL' as const : t.risk_score >= 70 ? 'HIGH' as const : 'MEDIUM' as const,
        scenario_description: (t as any).scenario_description,
        fraud_scenario: (t as any).fraud_scenario,
      }))
  }, [ws.transactions])

  return (
    <FraudContext.Provider value={{ ...ws, alerts }}>
      {children}
    </FraudContext.Provider>
  )
}

function getFraudTitle(t: Transaction): string {
  const rules = t.rule_names || []
  if (rules.includes('High velocity')) return 'Velocity attack detected'
  if (rules.includes('Geographic anomaly')) return 'Geographic impossibility'
  if (rules.includes('New device high value')) return 'New device · high value'
  if (rules.includes('Card testing pattern')) return 'Card testing pattern'
  if (rules.includes('AML structuring')) return 'AML structuring detected'
  if (t.is_new_device) return 'Suspicious new device login'
  return 'Fraud pattern detected'
}

export function useFraud() {
  const ctx = useContext(FraudContext)
  if (!ctx) throw new Error('useFraud must be used inside FraudProvider')
  return ctx
}

export type { Transaction, Stats }
