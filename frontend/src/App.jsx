import { BrowserRouter, NavLink, Route, Routes } from 'react-router-dom'
import { Component, Suspense, lazy, useEffect, useRef } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import {
  fetchAccounts,
  fetchFraudNetwork,
  fetchFraudClusters,
  fetchFraudStats,
  fetchFraudHeatmap,
  fetchLiveAlerts,
  fetchLiveTransactions,
  fetchModelMetrics,
  fetchModelHealth,
  fetchSystemHealth,
} from './services/api'
import { createWSConnection, WS_URLS } from './services/websocket'
import {
  addAlertsBatch,
  addTransactionsBatch,
  recalcRollingRates,
  setAccounts,
  setAlerts,
  setGraph,
  setClusters,
  setModelMetrics,
  setModelHealth,
  setSystemHealth,
  setHeatmap,
  setStats,
  setTransactions,
  setWsStatus,
} from './store/platformSlice'
import OverviewDashboard from './pages/OverviewDashboard'
import LiveTransactionMonitor from './pages/LiveTransactionMonitor'
import FraudAlertsPanel from './pages/FraudAlertsPanel'
import AccountIntelligencePage from './pages/AccountIntelligencePage'
import ModelIntelligence from './pages/ModelIntelligence'
import ModelPerformancePage from './pages/ModelPerformancePage'
const FraudNetworkGraph = lazy(() => import('./pages/FraudNetworkGraph'))
import AccountRiskMonitor from './pages/AccountRiskMonitor'
import FraudInvestigationPanel from './pages/FraudInvestigationPanel'
import FraudHeatmap from './pages/FraudHeatmap'
import ModelTrainingPanel from './pages/ModelTrainingPanel'
import ModelHealth from './pages/ModelHealth'
import EnhancedTransactionMonitor from './pages/EnhancedTransactionMonitor'
import D3FraudNetwork from './pages/D3FraudNetwork'
import EnhancedModelPerformance from './pages/EnhancedModelPerformance'
import CaseManagement from './pages/CaseManagement'
import KPISummary from './pages/KPISummary'

const NAV_ITEMS = [
  { to: '/', label: '📊 Overview' },
  { to: '/kpi', label: '🎯 KPI Summary' },
  { to: '/live-monitor', label: '⚡ Live Monitor' },
  { to: '/enhanced-monitor', label: '🔎 Enhanced Monitor' },
  { to: '/fraud-alerts', label: '🚨 Fraud Alerts' },
  { to: '/account-intelligence', label: '🧠 Account Intel' },
  { to: '/fraud-network', label: '🕸️ Fraud Network' },
  { to: '/d3-network', label: '🌐 D3 Graph' },
  { to: '/model-performance', label: '📈 Model Perf' },
  { to: '/enhanced-model', label: '🏆 Enhanced Model' },
  { to: '/model-intelligence', label: '🔬 Model Intel' },
  { to: '/case-management', label: '📋 Cases' },
  { to: '/account-risk', label: '⚠️ Risk Monitor' },
  { to: '/investigation', label: '🔍 Investigation' },
  { to: '/model-health', label: '💊 Model Health' },
  { to: '/heatmap', label: '🗺️ Heatmap' },
  { to: '/model-training', label: '🏋️ Training' },
]

function StatusPill({ label, status }) {
  return <span className={`soc-pill soc-pill-${status || 'disconnected'}`}>{label}: {status}</span>
}

function EngineStatus({ label, level }) {
  return <span className={`soc-pill status-${level || 'yellow'}`}>{label}</span>
}

function Shell() {
  const dispatch = useDispatch()
  const wsStatus = useSelector((s) => s.platform.wsStatus)
  const txPerSec = useSelector((s) => s.platform.txPerSec)
  const txPerMin = useSelector((s) => s.platform.txPerMin)
  const stats = useSelector((s) => s.platform.stats)
  const systemHealth = useSelector((s) => s.platform.systemHealth)
  const txBufferRef = useRef([])
  const alertBufferRef = useRef([])

  useEffect(() => {
    let mounted = true

    const hydrate = async () => {
      try {
        const [txs, alerts, statsRes, graph, clusters, accounts, metrics, modelHealth, system, heatmap] = await Promise.all([
          fetchLiveTransactions(80),
          fetchLiveAlerts(40),
          fetchFraudStats(),
          fetchFraudNetwork(900),
          fetchFraudClusters(0.5),
          fetchAccounts(80),
          fetchModelMetrics(),
          fetchModelHealth(),
          fetchSystemHealth(),
          fetchFraudHeatmap(),
        ])

        if (!mounted) return
        dispatch(setTransactions(txs || []))
        dispatch(setAlerts(alerts || []))
        dispatch(setStats(statsRes || {}))
        dispatch(setGraph(graph || { nodes: [], edges: [] }))
        dispatch(setClusters(clusters || []))
        dispatch(setAccounts(accounts || []))
        dispatch(setModelMetrics(metrics || null))
        dispatch(setModelHealth(modelHealth || null))
        dispatch(setSystemHealth(system || null))
        dispatch(setHeatmap(heatmap || []))
      } catch {
        // keep shell running even when data endpoints are unavailable
      }
    }

    hydrate()
    const refreshId = setInterval(hydrate, 20000)
    return () => {
      mounted = false
      clearInterval(refreshId)
    }
  }, [dispatch])

  useEffect(() => {
    const rateTicker = setInterval(() => dispatch(recalcRollingRates(Date.now())), 1000)
    const flushTicker = setInterval(() => {
      if (txBufferRef.current.length) {
        dispatch(addTransactionsBatch(txBufferRef.current.splice(0, txBufferRef.current.length)))
      }
      if (alertBufferRef.current.length) {
        dispatch(addAlertsBatch(alertBufferRef.current.splice(0, alertBufferRef.current.length)))
      }
    }, 1500)
    return () => {
      clearInterval(rateTicker)
      clearInterval(flushTicker)
    }
  }, [dispatch])

  useEffect(() => {
    const stream = createWSConnection(WS_URLS.stream, {
      onStatus: (status) => dispatch(setWsStatus({ channel: 'stream', status })),
      onMessage: (msg) => {
        const payload = msg?.transaction || msg?.data || msg
        if (payload?.transaction_id) {
          txBufferRef.current.push(payload)
        }
      },
    })

    const alerts = createWSConnection(WS_URLS.alerts, {
      onStatus: (status) => dispatch(setWsStatus({ channel: 'alerts', status })),
      onMessage: (msg) => {
        const payload = msg?.alert || msg?.data || msg
        if (payload) alertBufferRef.current.push(payload)
      },
    })

    return () => {
      stream.close()
      alerts.close()
    }
  }, [dispatch])

  return (
    <div className="soc-app min-h-screen">
      <header className="soc-header">
        <div>
          <h1>Fraud Intelligence SOC</h1>
          <p>Hybrid AI monitoring with real-time transaction intelligence</p>
        </div>
        <div className="soc-metrics-strip">
          <StatusPill label="Stream" status={wsStatus.stream} />
          <StatusPill label="Alerts" status={wsStatus.alerts} />
          <span className="soc-pill">Tx/Sec: {txPerSec}</span>
          <span className="soc-pill">Tx/Min: {txPerMin}</span>
          <span className="soc-pill">Fraud Rate: {(stats.fraud_rate || 0).toFixed(2)}%</span>
          <EngineStatus label={`Model ${systemHealth?.model_status || 'yellow'}`} level={systemHealth?.model_status} />
          <EngineStatus label={`Stream ${systemHealth?.streaming_status || 'yellow'}`} level={systemHealth?.streaming_status} />
          <EngineStatus label={`Engine ${systemHealth?.fraud_engine_status || 'yellow'}`} level={systemHealth?.fraud_engine_status} />
          <EngineStatus label={`DB ${systemHealth?.database_status || 'yellow'}`} level={systemHealth?.database_status} />
        </div>
      </header>

      <nav className="soc-nav">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) => `soc-nav-link ${isActive ? 'active' : ''}`}
          >
            {item.label}
          </NavLink>
        ))}
      </nav>

      <main className="soc-main">
        <Routes>
          <Route path="/" element={<OverviewDashboard />} />
          <Route path="/kpi" element={<KPISummary />} />
          <Route path="/live-monitor" element={<LiveTransactionMonitor />} />
          <Route path="/enhanced-monitor" element={<EnhancedTransactionMonitor />} />
          <Route path="/fraud-alerts" element={<FraudAlertsPanel />} />
          <Route path="/account-intelligence" element={<AccountIntelligencePage />} />
          <Route path="/fraud-network" element={<Suspense fallback={<div className="soc-card">Loading graph…</div>}><FraudNetworkGraph /></Suspense>} />
          <Route path="/d3-network" element={<D3FraudNetwork />} />
          <Route path="/model-performance" element={<ModelPerformancePage />} />
          <Route path="/enhanced-model" element={<EnhancedModelPerformance />} />
          <Route path="/model-intelligence" element={<ModelIntelligence />} />
          <Route path="/case-management" element={<CaseManagement />} />
          <Route path="/account-risk" element={<AccountRiskMonitor />} />
          <Route path="/investigation" element={<FraudInvestigationPanel />} />
          <Route path="/model-health" element={<ModelHealth />} />
          <Route path="/heatmap" element={<FraudHeatmap />} />
          <Route path="/model-training" element={<ModelTrainingPanel />} />
        </Routes>
      </main>
    </div>
  )
}

class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="soc-app min-h-screen">
          <div className="soc-error-boundary">
            <h2>Something went wrong</h2>
            <p>{this.state.error?.message || 'An unexpected error occurred.'}</p>
            <button
              className="soc-btn"
              style={{ marginTop: '1rem' }}
              onClick={() => { this.setState({ hasError: false, error: null }); window.location.reload() }}
            >
              Reload Dashboard
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <Shell />
      </BrowserRouter>
    </ErrorBoundary>
  )
}
