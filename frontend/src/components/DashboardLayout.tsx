import React, { useState, useEffect, useMemo, useRef } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useFraud } from "../context/FraudContext";

const sections = [
  {
    label: "MONITORING",
    items: [
      { to: "/", label: "Dashboard", icon: "grid", badge: null as null | { text: string; variant: string } },
      { to: "/alerts", label: "Alerts", icon: "bell", badge: { text: "0", variant: "danger" } },
    ],
  },
  {
    label: "INTELLIGENCE",
    items: [
      { to: "/customers", label: "Customers", icon: "users", badge: null as null | { text: string; variant: string } },
      { to: "/customer-intel", label: "Customer Intel", icon: "shield", badge: { text: "0", variant: "danger" } },
      { to: "/graph", label: "Fraud Network", icon: "network", badge: null as null | { text: string; variant: string } },
    ],
  },
  {
    label: "ANALYSIS",
    items: [
      { to: "/models", label: "ML Models", icon: "cpu", badge: null as null | { text: string; variant: string } },
    ],
  },
  {
    label: "SYSTEM",
    items: [
      { to: "/settings", label: "Settings", icon: "settings", badge: null as null | { text: string; variant: string } },
    ],
  },
];

function Icon({ name, className }: { name: string; className?: string }) {
  const p = {
    width: "14", height: "14", viewBox: "0 0 24 24", fill: "none",
    stroke: "currentColor", strokeWidth: "2",
    strokeLinecap: "round" as const, strokeLinejoin: "round" as const,
    className,
  };
  switch (name) {
    case "grid":
      return <svg {...p}><rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" /><rect x="3" y="14" width="7" height="7" /><rect x="14" y="14" width="7" height="7" /></svg>;
    case "bell":
      return <svg {...p}><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.73 21a2 2 0 0 1-3.46 0" /></svg>;
    case "users":
      return <svg {...p}><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M23 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" /></svg>;
    case "network":
      return <svg {...p}><circle cx="12" cy="5" r="3" /><circle cx="5" cy="19" r="3" /><circle cx="19" cy="19" r="3" /><line x1="12" y1="8" x2="5" y2="16" /><line x1="12" y1="8" x2="19" y2="16" /></svg>;
    case "cpu":
      return <svg {...p}><rect x="4" y="4" width="16" height="16" rx="2" /><rect x="9" y="9" width="6" height="6" /><line x1="9" y1="1" x2="9" y2="4" /><line x1="15" y1="1" x2="15" y2="4" /><line x1="9" y1="20" x2="9" y2="23" /><line x1="15" y1="20" x2="15" y2="23" /><line x1="20" y1="9" x2="23" y2="9" /><line x1="20" y1="14" x2="23" y2="14" /><line x1="1" y1="9" x2="4" y2="9" /><line x1="1" y1="14" x2="4" y2="14" /></svg>;
    case "settings":
      return <svg {...p}><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" /></svg>;
    case "activity":
      return <svg {...p}><polyline points="22 12 18 12 15 21 9 3 6 12 2 12" /></svg>;
    case "folder":
      return <svg {...p}><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" /></svg>;
    case "map":
      return <svg {...p}><polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6" /><line x1="8" y1="2" x2="8" y2="18" /><line x1="16" y1="6" x2="16" y2="22" /></svg>;
    case "doc":
      return <svg {...p}><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" /><polyline points="10 9 9 9 8 9" /></svg>;
    case "shield":
      return <svg {...p}><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /><circle cx="12" cy="12" r="3" /></svg>;
    default:
      return null;
  }
}

const PAGE_TITLES: Record<string, { title: string; sub: string }> = {
  "/": { title: "Dashboard", sub: "Real-time fraud monitoring" },
  "/alerts": { title: "Alerts", sub: "Active fraud alerts" },
  "/live": { title: "Live Monitor", sub: "Real-time stream" },
  "/customers": { title: "Customers", sub: "Customer risk profiles" },
  "/customer-intel": { title: "Customer Intel", sub: "Fraud customer intelligence" },
  "/graph": { title: "Fraud Network", sub: "Network analysis" },
  "/cases": { title: "Case Management", sub: "Investigation tracking" },
  "/models": { title: "ML Models", sub: "Model performance" },
  "/heatmap": { title: "Risk Heatmap", sub: "Geographic risk" },
  "/reports": { title: "Reports", sub: "Analytics & reports" },
  "/settings": { title: "Settings", sub: "System configuration & alerts" },
};

export default function DashboardLayout() {
  const location = useLocation();
  const [clock, setClock] = useState("");
  const page = PAGE_TITLES[location.pathname] || PAGE_TITLES["/"];
  const { transactions, stats, status } = useFraud();
  
  const criticalCount = transactions.filter((t: any) => t.risk_level === "fraudulent").length;
  const alertCount = transactions.filter((t: any) => t.risk_score >= 70).length;

  // Fraud customer count for Customer Intel badge
  const fraudCustomerCount = useMemo(() => {
    const seen = new Set<string>();
    transactions.forEach((t: any) => {
      if (t.risk_level === 'fraudulent') seen.add(t.customer_id);
    });
    return seen.size;
  }, [transactions]);

  const [toastTxn, setToastTxn] = useState<any>(null);
  const shownToasts = useRef(new Set<string>());

  // Fix 5: Toast Deduplication & Auto-dismiss logic
  useEffect(() => {
    if (transactions.length === 0) return;
    
    const latest = transactions[0];
    const isCritical = latest.risk_score >= 85 || latest.action === "BLOCK";
    const alreadyShown = shownToasts.current.has(latest.id);

    if (isCritical && !alreadyShown) {
      shownToasts.current.add(latest.id);
      
      // Rotate set to save memory
      if (shownToasts.current.size > 40) {
        const first = shownToasts.current.values().next().value;
        if (first) shownToasts.current.delete(first);
      }

      setToastTxn(latest);
    }

    // Always ensure a timeout exists to clear whatever is currently showing
    const timer = setTimeout(() => {
      setToastTxn(null);
    }, 5000);

    return () => clearTimeout(timer);
  }, [transactions.length > 0 ? transactions[0].id : null]);

  const dynamicSections = sections.map(section => {
    if (section.label === "MONITORING") {
      return {
        ...section,
        items: section.items.map(item => {
          if (item.label === "Alerts") {
             return { ...item, badge: { text: alertCount.toString(), variant: "danger"} }
          }
          return item;
        })
      }
    }
    if (section.label === "INTELLIGENCE") {
      return {
        ...section,
        items: section.items.map(item => {
          if (item.label === "Customer Intel") {
            return { ...item, badge: { text: fraudCustomerCount.toString(), variant: "danger" } }
          }
          return item;
        })
      }
    }
    return section;
  });

  useEffect(() => {
    const tick = () =>
      setClock(new Date().toLocaleTimeString("en-IN", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" }));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: '#F7F8FA' }}>
      {/* ── SIDEBAR ── */}
      <nav style={{
        width: '224px',
        background: '#0D1117',
        display: 'flex',
        flexDirection: 'column',
        flexShrink: 0,
        borderRight: '1px solid rgba(255,255,255,0.06)',
        overflow: 'hidden'
      }}>
        {/* Logo */}
        <div style={{ padding: '16px 16px 12px', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
            <div style={{
              width: '32px', height: '32px',
              background: 'linear-gradient(135deg, #1F6FEB 0%, #0969DA 100%)',
              borderRadius: '8px',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              flexShrink: 0
            }}>
              <Icon name="shield" className="text-white" />
            </div>
            <div>
              <div style={{ fontSize: '14px', fontWeight: '700', color: '#E6EDF3', letterSpacing: '-0.3px' }}>
                FraudGuard
              </div>
              <div style={{ fontSize: '10px', color: '#1F6FEB', fontWeight: '600', letterSpacing: '0.5px' }}>
                ENTERPRISE · v3.2
              </div>
            </div>
          </div>
          
          {/* System status card */}
          <div style={{
            background: status === 'connected' 
              ? 'rgba(26, 127, 55, 0.12)'
              : 'rgba(207, 34, 46, 0.12)',
            border: `1px solid ${status === 'connected' ? 'rgba(26,127,55,0.25)' : 'rgba(207,34,46,0.25)'}`,
            borderRadius: '8px',
            padding: '8px 10px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
              {status === 'connected' ? (
                <span className="w-[6px] h-[6px] rounded-full bg-emerald-400 pulse-dot" />
              ) : (
                <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#CF222E' }} />
              )}
              <span style={{
                fontSize: '11px', fontWeight: '600',
                color: status === 'connected' ? '#3FB950' : '#F85149'
              }}>
                {status === 'connected' ? 'Live stream' : 'Disconnected'}
              </span>
            </div>
            <span style={{ fontSize: '10px', color: '#484F58', fontVariantNumeric: 'tabular-nums' }}>
              {stats?.txn_per_second?.toFixed(1) || '0'}/s
            </span>
          </div>
        </div>

        {/* Nav */}
        <div className="flex-1 overflow-y-auto py-2" style={{ scrollbarWidth: "none" }}>
          {dynamicSections.map((section) => (
            <div key={section.label}>
              <div style={{
                fontSize: '10px', fontWeight: '700',
                color: '#30363D',
                letterSpacing: '0.8px',
                padding: '8px 16px 4px'
              }}>
                {section.label}
              </div>
              {section.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === "/"}
                  className={({ isActive }) =>
                    `mx-2 px-3 py-[7px] rounded-[6px] flex items-center gap-[9px] cursor-pointer transition-colors ${
                      isActive
                        ? "bg-[rgba(31,111,235,0.12)] border border-[rgba(31,111,235,0.2)]"
                        : "border border-transparent hover:bg-white/[0.05]"
                    }`
                  }
                >
                  {({ isActive }) => (
                    <>
                      <div style={{
                        width: '26px', height: '26px',
                        borderRadius: '5px',
                        background: isActive ? 'rgba(31,111,235,0.2)' : 'rgba(255,255,255,0.05)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        flexShrink: 0
                      }}>
                        <Icon name={item.icon} className={isActive ? "text-[#79C0FF]" : "text-[#484F58]"} />
                      </div>
                      <span style={{
                        fontSize: '12px',
                        fontWeight: isActive ? '600' : '400',
                        color: isActive ? '#79C0FF' : '#8B949E',
                        flex: 1
                      }}>
                        {item.label}
                      </span>
                      {item.badge && parseInt(item.badge.text) > 0 && (
                        <span style={{
                          fontSize: '10px', fontWeight: '700',
                          padding: '1px 6px',
                          background: criticalCount > 0 ? '#3D0E0C' : '#271700',
                          color: criticalCount > 0 ? '#FF7B72' : '#E3B341',
                          borderRadius: '10px',
                          border: criticalCount > 0 ? '1px solid #5C1614' : '1px solid #3D2200'
                        }}>
                          {parseInt(item.badge.text) > 99 ? '99+' : item.badge.text}
                        </span>
                      )}
                    </>
                  )}
                </NavLink>
              ))}
            </div>
          ))}
        </div>

        {/* Bottom status */}
        <div style={{ padding: '12px 16px', borderTop: '1px solid rgba(255,255,255,0.06)' }}>
          <div style={{ fontSize: '10px', color: '#484F58', lineHeight: '1.6' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '2px' }}>
              <span>Transactions today</span>
              <span style={{ color: '#8B949E', fontVariantNumeric: 'tabular-nums' }}>
                {stats?.total_transactions?.toLocaleString('en-IN') || '0'}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '2px' }}>
              <span>Fraud detected</span>
              <span style={{ color: '#FF7B72', fontVariantNumeric: 'tabular-nums' }}>
                {/* SOURCE: metrics:blocked_txns (BLOCK decisions only) */}
                {/* DO NOT use metrics:flagged_txns here */}
                {stats?.blocked_count || '0'}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Model</span>
              <span style={{ color: '#3FB950' }}>XGBoost v2 ●</span>
            </div>
          </div>
        </div>
      </nav>

      {/* ── MAIN AREA ── */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* TOPBAR */}
        <header style={{
          height: '52px',
          background: 'white',
          borderBottom: '1px solid #E8ECF0',
          display: 'flex',
          alignItems: 'center',
          padding: '0 20px',
          gap: '10px',
          flexShrink: 0
        }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: '14px', fontWeight: '700', color: '#0D1117', letterSpacing: '-0.3px' }}>{page.title}</div>
            <div style={{ fontSize: '11px', color: '#8C959F' }}>{page.sub}</div>
          </div>
          
          {criticalCount > 0 && (
            <span style={{
              display: 'flex', alignItems: 'center', gap: '5px',
              fontSize: '11px', fontWeight: '600',
              padding: '4px 10px', borderRadius: '20px',
              background: '#FFEBE9', color: '#CF222E',
              border: '1px solid #FFCECB'
            }}>
              <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#CF222E', flexShrink: 0 }} />
              {criticalCount} critical
            </span>
          )}
          
          <span style={{
            display: 'flex', alignItems: 'center', gap: '5px',
            fontSize: '11px', fontWeight: '600',
            padding: '4px 10px', borderRadius: '20px',
            background: status === 'connected' ? '#DAFBE1' : '#FFEBE9',
            color: status === 'connected' ? '#1A7F37' : '#CF222E',
            border: `1px solid ${status === 'connected' ? '#ACE6B4' : '#FFCECB'}`
          }}>
            {status === 'connected' && <span className="w-[6px] h-[6px] rounded-full bg-emerald-400 pulse-dot" />}
            {status === 'connected' ? 'Streaming' : 'Disconnected'}
          </span>
          
          <span style={{
            fontSize: '11px', fontWeight: '600',
            padding: '4px 10px', borderRadius: '20px',
            background: '#DDF4FF', color: '#0969DA',
            border: '1px solid #9CD8FA'
          }}>
            Model Active
          </span>
          
          {alertCount > 0 && (
            <span style={{
              fontSize: '11px', fontWeight: '600',
              padding: '4px 10px', borderRadius: '20px',
              background: '#FFF8C5', color: '#9A6700',
              border: '1px solid #F2CC60'
            }}>
              {alertCount} Pending
            </span>
          )}
          
          <span style={{
            fontSize: '12px', color: '#57606A',
            fontVariantNumeric: 'tabular-nums',
            minWidth: '68px', textAlign: 'right' as const,
            fontWeight: '500'
          }}>
            {clock}
          </span>
        </header>

        {/* CONTENT */}
        <main className="flex-1 overflow-hidden relative" style={{ background: '#F7F8FA' }}>
          <Outlet />

          {/* RED TOAST NOTIFICATION */}
          {toastTxn && (
            <div className="absolute bottom-6 right-6 animate-toast" style={{
              background: 'linear-gradient(135deg, #CF222E 0%, #A40E26 100%)',
              color: 'white',
              padding: '16px 20px',
              borderRadius: '14px',
              boxShadow: '0 8px 32px rgba(207,34,46,0.35)',
              zIndex: 50,
              maxWidth: '380px',
              border: '1px solid rgba(255,255,255,0.12)',
              backdropFilter: 'blur(8px)'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', gap: '12px' }}>
                <span style={{ fontWeight: '800', fontSize: '13px', letterSpacing: '0.3px' }}>
                  ⛔ CRITICAL FRAUD ALERT <span style={{ opacity: 0.7, fontWeight: '600' }}>({toastTxn.risk_score} SCORE)</span>
                </span>
                <button style={{ color: 'rgba(255,255,255,0.5)', cursor: 'pointer', background: 'none', border: 'none', fontSize: '14px' }} onClick={() => setToastTxn(null)}>✕</button>
              </div>
              <p style={{ fontSize: '12px', fontWeight: '500', lineHeight: '1.5', marginTop: '6px', color: 'rgba(255,255,255,0.9)' }}>
                Transaction <span style={{ fontFamily: 'monospace', background: 'rgba(0,0,0,0.2)', padding: '1px 5px', borderRadius: '4px' }}>{toastTxn.id.slice(0, 12)}</span> by {toastTxn.customer_id} at <strong>{toastTxn.merchant}</strong> — ₹{toastTxn.amount.toLocaleString()}
              </p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
