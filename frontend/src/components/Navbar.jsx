import { NavLink } from 'react-router-dom'
import { motion } from 'framer-motion'

const links = [
  { to: '/', label: 'Dashboard', icon: '📊' },
  { to: '/accounts', label: 'Accounts', icon: '👤' },
  { to: '/fraud-network', label: 'Fraud Network', icon: '🔗' },
]

export default function Navbar({ wsStatus, txPerMin, fraudRate }) {
  const statusColor =
    wsStatus === 'connected' ? 'bg-soc-safe' : wsStatus === 'error' ? 'bg-soc-danger' : 'bg-soc-warn'
  const statusLabel =
    wsStatus === 'connected' ? 'System Online' : wsStatus === 'error' ? 'Connection Error' : 'Reconnecting…'

  return (
    <header className="sticky top-0 z-50 border-b border-soc-border/50 bg-soc-bg/70 backdrop-blur-xl">
      <div className="max-w-[1800px] mx-auto px-6 py-3 flex items-center justify-between">
        {/* Left — logo + nav */}
        <div className="flex items-center gap-6">
          <motion.div
            className="flex items-center gap-2.5"
            initial={{ opacity: 0, x: -16 }}
            animate={{ opacity: 1, x: 0 }}
          >
            <div className="relative">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-soc-accent to-blue-600 flex items-center justify-center text-sm font-bold shadow-glow-blue">
                AI
              </div>
              <span className={`absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full ${statusColor} ring-2 ring-soc-bg`}>
                <span className={`absolute inset-0 rounded-full ${statusColor} animate-ping-slow`} />
              </span>
            </div>
            <div className="hidden sm:block">
              <h1 className="text-sm font-semibold tracking-tight leading-none">
                AI Fraud Monitoring
              </h1>
              <p className="text-[10px] text-soc-muted mt-0.5 tracking-wide uppercase">
                SOC Dashboard
              </p>
            </div>
          </motion.div>

          {/* Nav links */}
          <nav className="flex items-center gap-1">
            {links.map((l) => (
              <NavLink
                key={l.to}
                to={l.to}
                end={l.to === '/'}
                className={({ isActive }) =>
                  `px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200 flex items-center gap-1.5 ${
                    isActive
                      ? 'bg-soc-accent/15 text-soc-accent border border-soc-accent/30'
                      : 'text-soc-muted hover:text-soc-text hover:bg-soc-card/50'
                  }`
                }
              >
                <span className="text-sm">{l.icon}</span>
                <span className="hidden md:inline">{l.label}</span>
              </NavLink>
            ))}
          </nav>
        </div>

        {/* Right — status pills */}
        <motion.div
          className="hidden md:flex items-center gap-3"
          initial={{ opacity: 0, x: 16 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.1 }}
        >
          <div className="glass-sm px-3 py-1.5 flex items-center gap-2 text-xs">
            <span className={`w-1.5 h-1.5 rounded-full ${statusColor}`} />
            <span className="text-soc-muted">{statusLabel}</span>
          </div>
          <div className="glass-sm px-3 py-1.5 text-xs text-soc-muted tabular-nums">
            {txPerMin} tx/min
          </div>
          <div className="glass-sm px-3 py-1.5 text-xs text-soc-muted tabular-nums">
            Fraud Rate: <span className="text-soc-danger font-medium">{fraudRate}%</span>
          </div>
        </motion.div>
      </div>
    </header>
  )
}
