import { useEffect, useMemo, useState } from 'react'
import {
  fetchLiveTransactions,
  fetchLiveAlerts,
  fetchFraudStats,
} from '../services/api'
import { createWSConnection, WS_URLS } from '../services/websocket'

import StatsCards from '../components/StatsCards'
import TransactionTable from '../components/TransactionTable'
import AlertPanel from '../components/AlertPanel'
import FraudChart from '../components/FraudChart'
import RiskPieChart from '../components/RiskPieChart'
import UserBehaviorChart from '../components/UserBehaviorChart'
import GlobalHeatmap from '../components/GlobalHeatmap'
import FraudExplanation from '../components/FraudExplanation'
import MerchantRiskChart from '../components/MerchantRiskChart'
import VelocityChart from '../components/VelocityChart'
import HighRiskUsers from '../components/HighRiskUsers'

const MAX_TXS   = 200
const MAX_ALERTS = 60

export default function Dashboard() {
  const [transactions, setTransactions] = useState([])
  const [alerts, setAlerts]             = useState([])
  const [stats, setStats]               = useState({
    total_transactions: 0, fraud: 0, suspicious: 0, safe: 0, open_alerts: 0,
  })
  const [wsStatus, setWsStatus]         = useState('connecting')
  const [selectedTx, setSelectedTx]     = useState(null)

  // ── Initial hydration ──────────────────────────────────────
  useEffect(() => {
    fetchLiveTransactions(80).then(d => setTransactions(d || [])).catch(() => {})
    fetchLiveAlerts(40).then(d => setAlerts(d || [])).catch(() => {})
    fetchFraudStats().then(d => setStats(s => ({ ...s, ...d }))).catch(() => {})

    const interval = setInterval(() => {
      fetchFraudStats().then(d => setStats(s => ({ ...s, ...d }))).catch(() => {})
    }, 5000)
    return () => clearInterval(interval)
  }, [])

  // ── WebSocket ──────────────────────────────────────────────
  useEffect(() => {
    const streamWS = createWSConnection(WS_URLS.stream, {
      onMessage(msg) {
        const txData = msg.data || msg.transaction
        if ((msg.type === 'transaction' || msg.type === 'transaction_update') && txData) {
          setTransactions(prev => [txData, ...prev].slice(0, MAX_TXS))
          setStats(prev => ({
            ...prev,
            total_transactions: prev.total_transactions + 1,
            fraud: prev.fraud + (txData.risk_category === 'FRAUD' ? 1 : 0),
            suspicious: prev.suspicious + (txData.risk_category === 'SUSPICIOUS' ? 1 : 0),
            safe: prev.safe + (txData.risk_category === 'SAFE' ? 1 : 0),
          }))
          window.__txCounterGlobal?.()
        }
      },
      onStatus: setWsStatus,
    })

    const alertsWS = createWSConnection(WS_URLS.alerts, {
      onMessage(msg) {
        const alertData = msg.data || msg.alert
        if ((msg.type === 'alert' || msg.type === 'fraud_alert') && alertData) {
          setAlerts(prev => [alertData, ...prev].slice(0, MAX_ALERTS))
          setStats(prev => ({ ...prev, open_alerts: prev.open_alerts + 1 }))
        }
      },
      onStatus() {},
    })

    return () => { streamWS.close(); alertsWS.close() }
  }, [])

  // ── Derived chart data ─────────────────────────────────────
  const riskDistribution = useMemo(() => {
    const b = { SAFE: 0, SUSPICIOUS: 0, FRAUD: 0 }
    transactions.forEach(t => {
      if (t.risk_category && b[t.risk_category] !== undefined) b[t.risk_category]++
    })
    return Object.entries(b).map(([name, value]) => ({ name, value }))
  }, [transactions])

  const timeline = useMemo(() => {
    const map = {}
    transactions.forEach(t => {
      const ts = t.timestamp || t.created_at
      if (!ts) return
      const key = new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      if (!map[key]) map[key] = { time: key, count: 0, fraud: 0 }
      map[key].count++
      if (t.risk_category === 'FRAUD') map[key].fraud++
    })
    return Object.values(map).slice(-30)
  }, [transactions])

  const fraudRate = stats.total_transactions > 0
    ? ((stats.fraud / stats.total_transactions) * 100).toFixed(2)
    : '0.00'

  return (
    <>
      {/* ═══════════ MAIN CONTENT ═══════════ */}
      <main className="max-w-[1800px] mx-auto px-6 py-6 space-y-6">

        {/* Row 1 — Stats cards */}
        <StatsCards stats={stats} />

        {/* Row 2 — Charts: Timeline + Risk Pie */}
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
          <div className="lg:col-span-3">
            <FraudChart data={timeline} />
          </div>
          <div className="lg:col-span-2">
            <RiskPieChart data={riskDistribution} />
          </div>
        </div>

        {/* Row 3 — Live Table + Alert Panel */}
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          <div className="xl:col-span-2">
            <TransactionTable transactions={transactions} onSelect={setSelectedTx} />
          </div>
          <div>
            <AlertPanel alerts={alerts} />
          </div>
        </div>

        {/* Row 4 — Merchant Risk + Velocity */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <MerchantRiskChart />
          <VelocityChart />
        </div>

        {/* Row 5 — User Behavior + Global Heatmap */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <UserBehaviorChart transactions={transactions} />
          <GlobalHeatmap transactions={transactions} />
        </div>

        {/* Row 6 — High Risk Users */}
        <HighRiskUsers />
      </main>

      {/* ═══════════ EXPLAINABILITY MODAL ═══════════ */}
      {selectedTx && (
        <FraudExplanation transaction={selectedTx} onClose={() => setSelectedTx(null)} />
      )}
    </>
  )
}
