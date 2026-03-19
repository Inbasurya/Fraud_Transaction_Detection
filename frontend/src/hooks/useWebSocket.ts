import { useState, useEffect, useRef, useCallback } from 'react'

export interface Transaction {
  type: 'transaction'
  id: string
  customer_id: string
  amount: number
  merchant: string
  merchant_category: string
  city: string
  risk_score: number
  risk_level: 'safe' | 'suspicious' | 'fraudulent'
  action: string
  triggered_rules: string[]
  rule_names: string[]
  timestamp: string
  device: string
  is_new_device: boolean
  shap_top_feature: string
  fraud_scenario?: string | null
  scenario_description?: string
  shap_values?: {
    amount_vs_avg: number
    velocity_1h: number
    geo_risk: number
    device_trust: number
    merchant_risk: number
  }
  explanation?: string
  behavioral_dna?: {
    time_anomaly: number
    amount_anomaly: number
    merchant_anomaly: number
    category_anomaly: number
    geo_anomaly: number
    device_anomaly: number
    dow_anomaly: number
    dna_composite: number
  }
  network_signals?: {
    is_rapid_fanout: boolean
    is_hub_account: boolean
    mule_score: number
    fraud_proximity: number
    network_risk: number
  }
  sim_swap_risk?: number
  alert_channels?: string[]
}

export interface Stats {
  type: 'stats'
  total_transactions: number
  fraud_count: number
  blocked_count: number
  suspicious_count: number
  fraud_rate: number
  avg_risk_score: number
  txn_per_second: number
}

interface WSState {
  transactions: Transaction[]
  stats: Stats | null
  status: 'connecting' | 'connected' | 'disconnected'
  txnPerSecond: number
  setStats: (s: Stats) => void
}

export function useWebSocket(url: string): WSState {
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [status, setStatus] = useState<'connecting'|'connected'|'disconnected'>('connecting')
  const [tps, setTps] = useState(0)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectRef = useRef<ReturnType<typeof setTimeout>>()
  const tpsRef = useRef(0)
  const tpsIntervalRef = useRef<ReturnType<typeof setInterval>>()

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return
    setStatus('connecting')
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setStatus('connected')
      clearTimeout(reconnectRef.current)
    }

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        if (data.type === 'ping') return  // ignore keepalive
        if (data.type === 'transaction') {
          tpsRef.current++
          setTransactions(prev => {
            if (prev.some(t => t.id === data.id)) return prev
            return [data, ...prev].slice(0, 100)
          })
        } else if (data.type === 'stats') {
          setStats(data)
        }
      } catch {}
    }

    ws.onclose = () => {
      setStatus('disconnected')
      reconnectRef.current = setTimeout(connect, 3000)
    }

    ws.onerror = () => {
      ws.close()
    }
  }, [url])

  useEffect(() => {
    connect()
    tpsIntervalRef.current = setInterval(() => {
      setTps(tpsRef.current)
      tpsRef.current = 0
    }, 1000)
    return () => {
      clearTimeout(reconnectRef.current)
      clearInterval(tpsIntervalRef.current)
      wsRef.current?.close()
    }
  }, [connect])

  return { transactions, stats, status, txnPerSecond: tps, setStats }
}
