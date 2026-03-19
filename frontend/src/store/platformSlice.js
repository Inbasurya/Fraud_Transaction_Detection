import { createSlice } from '@reduxjs/toolkit'

const initialState = {
  wsStatus: { stream: 'connecting', alerts: 'connecting' },
  stats: {
    total_transactions: 0,
    fraud: 0,
    suspicious: 0,
    safe: 0,
    fraud_rate: 0,
    open_alerts: 0,
  },
  modelMetrics: null,
  modelHealth: null,
  systemHealth: null,
  transactions: [],
  alerts: [],
  graph: { nodes: [], edges: [] },
  clusters: [],
  heatmap: [],
  accounts: [],
  customers: [],
  notifications: [],
  accountRiskTrend: [],
  selectedTransaction: null,
  selectedAccountId: null,
  txRateTimestamps: [],
  txPerSec: 0,
  txPerMin: 0,
  // ── New state for v3 panels ──
  cases: [],
  auditLogs: [],
  graphData: { nodes: [], links: [] },
  graphClusters: [],
  graphStats: null,
  prometheusMetrics: null,
}

const platformSlice = createSlice({
  name: 'platform',
  initialState,
  reducers: {
    setWsStatus(state, action) {
      state.wsStatus[action.payload.channel] = action.payload.status
    },
    setStats(state, action) {
      state.stats = { ...state.stats, ...action.payload }
    },
    setModelMetrics(state, action) {
      state.modelMetrics = action.payload
    },
    setModelHealth(state, action) {
      state.modelHealth = action.payload
    },
    setSystemHealth(state, action) {
      state.systemHealth = action.payload
    },
    setTransactions(state, action) {
      state.transactions = action.payload ?? []
    },
    setAlerts(state, action) {
      state.alerts = action.payload ?? []
    },
    setGraph(state, action) {
      state.graph = action.payload ?? { nodes: [], edges: [] }
    },
    setClusters(state, action) {
      state.clusters = action.payload ?? []
    },
    setAccounts(state, action) {
      state.accounts = action.payload ?? []
    },
    setHeatmap(state, action) {
      state.heatmap = action.payload ?? []
    },
    setAccountRiskTrend(state, action) {
      state.accountRiskTrend = action.payload ?? []
    },
    setSelectedAccountId(state, action) {
      state.selectedAccountId = action.payload ?? null
    },
    setCustomers(state, action) {
      state.customers = action.payload ?? []
    },
    setNotifications(state, action) {
      state.notifications = action.payload ?? []
    },
    setCases(state, action) {
      state.cases = action.payload ?? []
    },
    updateCase(state, action) {
      const updated = action.payload
      const idx = state.cases.findIndex((c) => c.case_id === updated.case_id)
      if (idx >= 0) state.cases[idx] = { ...state.cases[idx], ...updated }
    },
    setAuditLogs(state, action) {
      state.auditLogs = action.payload ?? []
    },
    setGraphData(state, action) {
      state.graphData = action.payload ?? { nodes: [], links: [] }
    },
    setGraphClusters(state, action) {
      state.graphClusters = action.payload ?? []
    },
    setGraphStats(state, action) {
      state.graphStats = action.payload ?? null
    },
    setPrometheusMetrics(state, action) {
      state.prometheusMetrics = action.payload ?? null
    },
    addTransactionsBatch(state, action) {
      const batch = (action.payload || []).filter((tx) => tx?.transaction_id)
      if (!batch.length) return
      const existing = new Set(state.transactions.map((row) => row.transaction_id))
      const now = Date.now()
      const additions = []
      for (const tx of batch) {
        if (existing.has(tx.transaction_id)) continue
        additions.push(tx)
        existing.add(tx.transaction_id)
        state.txRateTimestamps.push(now)
        state.stats.total_transactions += 1
        if (tx.risk_category === 'FRAUD') state.stats.fraud += 1
        else if (tx.risk_category === 'SUSPICIOUS') state.stats.suspicious += 1
        else state.stats.safe += 1
      }
      if (!additions.length) return
      state.transactions = [...additions.reverse(), ...state.transactions].slice(0, 220)
      if (state.stats.total_transactions > 0) {
        state.stats.fraud_rate =
          (state.stats.fraud / state.stats.total_transactions) * 100
      }
    },
    addAlertsBatch(state, action) {
      const batch = (action.payload || []).filter(Boolean)
      if (!batch.length) return
      const now = Date.now()
      const normalized = batch.map((alert) => ({
        ...alert,
        received_at: now,
      }))
      state.alerts = [...normalized.reverse(), ...state.alerts].slice(0, 120)
      state.stats.open_alerts += normalized.length
    },
    selectTransaction(state, action) {
      state.selectedTransaction = action.payload
    },
    recalcRollingRates(state, action) {
      const now = action.payload || Date.now()
      state.txRateTimestamps = state.txRateTimestamps.filter((t) => now - t <= 60000)
      state.txPerSec = state.txRateTimestamps.filter((t) => now - t <= 1000).length
      state.txPerMin = state.txRateTimestamps.length
    },
  },
})

export const {
  setWsStatus,
  setStats,
  setModelMetrics,
  setModelHealth,
  setSystemHealth,
  setTransactions,
  setAlerts,
  setGraph,
  setClusters,
  setAccounts,
  setHeatmap,
  setAccountRiskTrend,
  setSelectedAccountId,
  setCustomers,
  setNotifications,
  setCases,
  updateCase,
  setAuditLogs,
  setGraphData,
  setGraphClusters,
  setGraphStats,
  setPrometheusMetrics,
  addTransactionsBatch,
  addAlertsBatch,
  selectTransaction,
  recalcRollingRates,
} = platformSlice.actions

export default platformSlice.reducer
