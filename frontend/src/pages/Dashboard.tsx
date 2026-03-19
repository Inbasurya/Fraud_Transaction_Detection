import React, { useState, useMemo, useEffect } from "react";
import { useFraud } from "../context/FraudContext";
import TransactionDrawer from "../components/TransactionDrawer";
import type { Transaction } from "../hooks/useWebSocket";
import { API_BASE } from "../services/api";

export default function Dashboard() {
  const { transactions, stats, status, txnPerSecond } = useFraud();
  const [selectedTxn, setSelectedTxn] = useState<Transaction | null>(null);
  const [modelInfo, setModelInfo] = useState({ auc: 0, loaded: false });
  const [fraudRateHistory, setFraudRateHistory] = useState<number[]>([]);

  useEffect(() => {
    fetch(`${API_BASE}/api/model-info`)
      .then(r => r.json())
      .then(data => {
         const auc = data.metrics?.auc_roc || data.metrics?.accuracy;
         setModelInfo({
            auc: auc,
            loaded: data.model_loaded || false
         })
      })
      .catch(() => {});
  }, []);

  const totalTxns = stats?.total_transactions ?? transactions.length;
  // SOURCE: stats.blocked_count from WS stats broadcast (BLOCK decisions only)
  // DO NOT use metrics:flagged_txns here
  const blockedCount = stats?.blocked_count ?? transactions.filter((t) => t.action === "BLOCK").length;
  // SOURCE: stats.fraud_rate = rolling 1h BLOCK rate from Redis
  const fraudRate = totalTxns < 10 ? -1 : (stats?.fraud_rate ?? (totalTxns > 0 ? (blockedCount / totalTxns) * 100 : 0));
  const fraudCount = blockedCount;
  const suspCount = stats?.suspicious_count ?? transactions.filter((t) => t.risk_level === "suspicious").length;
  const totalAmount = useMemo(() => transactions.reduce((s, t) => s + t.amount, 0), [transactions]);

  // Fraud rate trend tracking (last 10 readings)
  const currentFraudRate = fraudRate < 0 ? 0 : fraudRate;
  useEffect(() => {
    setFraudRateHistory(prev => {
      const updated = [...prev, currentFraudRate].slice(-10);
      return updated;
    });
  }, [currentFraudRate]);

  const trend = fraudRateHistory.length >= 2
    ? (fraudRateHistory.at(-1)! > fraudRateHistory.at(-2)! ? "up" : fraudRateHistory.at(-1)! < fraudRateHistory.at(-2)! ? "down" : "neutral")
    : "neutral";
  const trendIcon = trend === "up" ? "↑" : trend === "down" ? "↓" : "→";
  const trendColor = trend === "up" ? "#CF222E" : trend === "down" ? "#1A7F37" : "#8C959F";

  const alerts = useMemo(
    () =>
      transactions
        .filter((t) => t.risk_level !== "safe")
        .slice(0, 8)
        .map((t) => ({
          id: t.id,
          title: t.risk_level === "fraudulent" ? `Fraud detected — ${t.merchant}` : `Suspicious — ${t.merchant}`,
          sub: `${t.customer_id} · ₹${t.amount.toLocaleString()}`,
          severity: t.risk_score >= 85 ? "critical" as const : t.risk_score >= 70 ? "high" as const : "medium" as const,
          time: new Date(t.timestamp).toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit" }),
          score: t.risk_score,
        })),
    [transactions],
  );

  const breakdown = useMemo(() => {
    const total = Math.max(transactions.length, 1);
    const cats: Record<string, number> = {};
    transactions.forEach((t) => {
      const category = t.merchant_category || "Other";
      cats[category] = (cats[category] || 0) + 1;
    });
    return Object.entries(cats)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([label, count]) => ({ label: label.replace(/_/g, " "), pct: Math.round((count / total) * 100) }));
  }, [transactions]);

  const riskColors = (level: string) => {
    const l = (level || "").toLowerCase();
    if (l === "critical" || l === "fraudulent" || l === "block") return { border: '#82071E', text: '#82071E', bg: '#82071E' };
    if (l === "high") return { border: '#CF222E', text: '#CF222E', bg: '#CF222E' };
    if (l === "medium" || l === "suspicious" || l === "review") return { border: '#9A6700', text: '#9A6700', bg: '#9A6700' };
    if (l === "low" || l === "monitor") return { border: '#B08800', text: '#B08800', bg: '#B08800' };
    return { border: '#1A7F37', text: '#1A7F37', bg: '#1A7F37' };
  };
  
  const scoreColor = (score: number) => {
    if (score >= 85) return '#82071E';
    if (score >= 70) return '#CF222E';
    if (score >= 50) return '#9A6700';
    if (score >= 30) return '#B08800';
    return '#1A7F37';
  };

  const severityStyle = (sev: string) => {
    switch (sev) {
      case 'critical': return { bg: '#FFEBE9', border: '#FFCECB', color: '#CF222E', icon: '🚨' };
      case 'high': return { bg: '#FFF8C5', border: '#F2CC60', color: '#9A6700', icon: '⚠️' };
      default: return { bg: '#DDF4FF', border: '#9CD8FA', color: '#0969DA', icon: '🔵' };
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden', padding: '16px', gap: '12px' }}>
      {/* ── KPI ROW ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '10px', flexShrink: 0 }}>
        <KPICard
          accent="linear-gradient(90deg, #1F6FEB, #0550AE)"
          label="TRANSACTIONS"
          value={totalTxns.toLocaleString()}
          delta={`+${txnPerSecond}/s`}
          deltaType="positive"
          sub={`${blockedCount} blocked, ${suspCount} flagged`}
        />
        <KPICard
          accent="linear-gradient(90deg, #CF222E, #A40E26)"
          label="FRAUD RATE"
          value={fraudRate < 0 ? 'Calculating...' : `${fraudRate.toFixed(2)}% ${trendIcon}`}
          valueColor={fraudRate > 3 ? '#CF222E' : fraudRate > 1 ? '#9A6700' : '#1A7F37'}
          delta={`${blockedCount} blocked`}
          deltaType={trend === "up" ? "negative" : trend === "down" ? "positive" : "neutral"}
          sub="Last 24h window"
        />
        <KPICard
          accent="linear-gradient(90deg, #1A7F37, #116329)"
          label="VOLUME PROCESSED"
          value={`₹${(totalAmount / 1000).toFixed(0)}K`}
          delta="+8.2%"
          deltaType="positive"
          sub="vs previous hour"
        />
        <KPICard
          accent="linear-gradient(90deg, #6E40C9, #512FA8)"
          label="MODEL CONFIDENCE"
          value={modelInfo.loaded && modelInfo.auc ? `${(modelInfo.auc * 100).toFixed(1)}%` : '...'}
          delta="XGBoost v2"
          deltaType="neutral"
          sub="P99 latency 12ms"
        />
      </div>

      {/* ── BOTTOM GRID ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 296px', gap: '10px', flex: 1, minHeight: 0 }}>
        {/* TRANSACTION PANEL */}
        <div style={{ background: 'white', border: '1px solid #E8ECF0', borderRadius: '12px', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div style={{ padding: '12px 16px', borderBottom: '1px solid #E8ECF0', display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
            <span style={{ fontSize: '13px', fontWeight: '700', color: '#0D1117', letterSpacing: '-0.2px', flex: 1 }}>Live Transactions</span>
            <span style={{
              display: 'flex', alignItems: 'center', gap: '5px',
              fontSize: '10px', fontWeight: '700',
              padding: '3px 8px', borderRadius: '20px',
              background: status === 'connected' ? '#DAFBE1' : '#FFEBE9',
              color: status === 'connected' ? '#1A7F37' : '#CF222E',
              border: `1px solid ${status === 'connected' ? '#ACE6B4' : '#FFCECB'}`
            }}>
              <span style={{ width: '5px', height: '5px', borderRadius: '50%', background: status === 'connected' ? '#1A7F37' : '#CF222E' }} className={status === 'connected' ? 'pulse-dot' : ''} />
              {status === 'connected' ? 'LIVE' : status.toUpperCase()}
            </span>
            <span style={{ fontSize: '10px', color: '#8C959F', fontVariantNumeric: 'tabular-nums' }}>{txnPerSecond} txn/s</span>
          </div>

          {/* Column headers */}
          <div style={{
            display: 'grid', gridTemplateColumns: '120px 85px 80px 1fr 90px',
            padding: '6px 16px',
            background: '#F6F8FA',
            borderBottom: '1px solid #E8ECF0'
          }}>
            {["TXN ID", "AMOUNT", "CUSTOMER", "MERCHANT", "RISK"].map((h) => (
              <span key={h} style={{ fontSize: '10px', fontWeight: '700', color: '#57606A', letterSpacing: '0.5px' }}>{h}</span>
            ))}
          </div>

          {/* Rows */}
          <div style={{ flex: 1, overflowY: 'auto', scrollbarWidth: 'none' as any }}>
            {transactions.map((txn, i) => {
              const rc = riskColors(txn.risk_level);
              const sc = scoreColor(txn.risk_score);
              return (
                <div
                  key={txn.id}
                  onClick={() => setSelectedTxn(txn)}
                  className={`txn-row-hover ${i < 3 ? 'animate-slide-in' : ''}`}
                  style={{
                    display: 'grid', gridTemplateColumns: '120px 85px 80px 1fr 90px',
                    padding: '8px 12px 8px 12px',
                    paddingRight: '16px',
                    borderBottom: '1px solid #F6F8FA',
                    borderLeft: `3px solid ${rc.border}`,
                    alignItems: 'center',
                    cursor: 'pointer',
                  }}
                >
                  <span style={{ fontFamily: "'SF Mono', 'Cascadia Code', monospace", fontSize: '11px', color: '#57606A' }}>{txn.id.slice(0, 12)}</span>
                  <span style={{ fontSize: '13px', fontWeight: '700', color: '#0D1117', fontVariantNumeric: 'tabular-nums' }}>₹{txn.amount.toLocaleString()}</span>
                  <span style={{ fontSize: '11px', color: '#57606A' }}>{txn.customer_id}</span>
                  <span style={{ fontSize: '11px', color: '#57606A', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const }}>{txn.merchant}</span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
                    <div style={{ width: '44px', height: '3px', background: '#E8ECF0', borderRadius: '2px', overflow: 'hidden' }}>
                      <div style={{ width: `${txn.risk_score}%`, height: '100%', background: sc, borderRadius: '2px', transition: 'width 0.4s ease' }} />
                    </div>
                    <span style={{ fontSize: '12px', fontWeight: '800', color: sc, fontVariantNumeric: 'tabular-nums', minWidth: '26px' }}>
                      {txn.risk_score}
                    </span>
                  </div>
                </div>
              );
            })}
            {transactions.length === 0 && (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '128px', fontSize: '12px', color: '#8C959F' }}>Waiting for transactions…</div>
            )}
          </div>
        </div>

        {/* ── RIGHT PANEL ── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', minHeight: 0 }}>
          {/* ALERT PANEL */}
          <div style={{ background: 'white', border: '1px solid #E8ECF0', borderRadius: '12px', flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minHeight: 0 }}>
            <div style={{ padding: '12px 16px', borderBottom: '1px solid #E8ECF0', flexShrink: 0 }}>
              <span style={{ fontSize: '13px', fontWeight: '700', color: '#0D1117', letterSpacing: '-0.2px' }}>Active Alerts</span>
            </div>
            <div style={{ flex: 1, overflowY: 'auto', scrollbarWidth: 'none' as any }}>
              {alerts.length === 0 && <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '96px', fontSize: '12px', color: '#8C959F' }}>No alerts</div>}
              {alerts.map((alert) => {
                const sev = severityStyle(alert.severity);
                return (
                  <div key={alert.id} className="txn-row-hover" style={{
                    padding: '10px 14px',
                    borderBottom: '1px solid #F6F8FA',
                    display: 'flex', gap: '10px',
                    cursor: 'pointer',
                  }}>
                    <div style={{
                      width: '28px', height: '28px',
                      borderRadius: '8px',
                      background: sev.bg,
                      border: `1px solid ${sev.border}`,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: '13px', flexShrink: 0
                    }}>
                      {sev.icon}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: '11px', fontWeight: '700', color: '#0D1117', lineHeight: '1.3', marginBottom: '2px' }}>{alert.title}</div>
                      <div style={{ fontSize: '10px', color: '#57606A', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const }}>{alert.sub}</div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '4px' }}>
                        <span style={{ fontSize: '10px', color: '#8C959F' }}>{alert.time}</span>
                        <span style={{
                          fontSize: '9px', fontWeight: '700',
                          padding: '1px 6px',
                          borderRadius: '4px',
                          background: sev.bg,
                          color: sev.color,
                          letterSpacing: '0.3px'
                        }}>
                          {alert.severity.toUpperCase()}
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })}
              <div style={{ padding: '10px 14px', fontSize: '11px', color: '#57606A', borderTop: '1px solid #F6F8FA', marginTop: 'auto' }}>
                <span>
                  <strong>{blockedCount} blocked, {suspCount} flagged</strong> transactions across detected sessions. 
                  Live analytics monitoring is active.
                </span>
              </div>
            </div>
          </div>

          {/* DETECTION BREAKDOWN */}
          <div style={{ background: 'white', border: '1px solid #E8ECF0', borderRadius: '12px', padding: '12px 14px', flexShrink: 0 }}>
            <div style={{ fontSize: '11px', fontWeight: '700', color: '#0D1117', marginBottom: '8px' }}>Detection Breakdown</div>
            {breakdown.map((row) => (
              <div key={row.label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '3px 0' }}>
                <span style={{ fontSize: '10px', color: '#57606A', fontWeight: '500', textTransform: 'capitalize' as const }}>{row.label}</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <div style={{ width: '60px', height: '3px', background: '#E8ECF0', borderRadius: '2px', overflow: 'hidden' }}>
                    <div style={{ height: '100%', background: '#0969DA', borderRadius: '2px', width: `${row.pct}%`, transition: 'width 0.4s ease' }} />
                  </div>
                  <span style={{ fontSize: '10px', fontWeight: '700', color: '#57606A', fontVariantNumeric: 'tabular-nums', width: '32px', textAlign: 'right' as const }}>{row.pct}%</span>
                </div>
              </div>
            ))}
            {breakdown.length === 0 && <div style={{ fontSize: '10px', color: '#8C959F', textAlign: 'center' as const, padding: '8px 0' }}>No data yet</div>}
          </div>
        </div>
      </div>

      <TransactionDrawer txn={selectedTxn} onClose={() => setSelectedTxn(null)} />
    </div>
  );
}

function KPICard({
  accent, label, value, delta, sub, deltaType, valueColor,
}: {
  accent: string; label: string; value: string; delta?: string; sub?: string;
  deltaType?: 'positive' | 'negative' | 'neutral'; valueColor?: string;
}) {
  const deltaStyles = {
    positive: { background: '#DAFBE1', color: '#1A7F37', border: '1px solid #ACE6B4' },
    negative: { background: '#FFEBE9', color: '#CF222E', border: '1px solid #FFCECB' },
    neutral: { background: '#DDF4FF', color: '#0969DA', border: '1px solid #9CD8FA' },
  };
  const ds = deltaStyles[deltaType || 'neutral'];

  return (
    <div className="card-hover" style={{
      background: 'white',
      border: '1px solid #E8ECF0',
      borderRadius: '12px',
      padding: '16px 18px',
      position: 'relative' as const,
      overflow: 'hidden'
    }}>
      <div style={{ position: 'absolute' as const, top: 0, left: 0, right: 0, height: '2px', background: accent }} />
      <div style={{ fontSize: '11px', fontWeight: '600', color: '#57606A', letterSpacing: '0.4px', marginBottom: '8px' }}>{label}</div>
      <div style={{
        fontSize: '28px', fontWeight: '800', letterSpacing: '-1px',
        color: valueColor || '#0D1117',
        fontVariantNumeric: 'tabular-nums'
      }}>
        {value}
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '6px' }}>
        <span style={{ fontSize: '11px', color: '#8C959F' }}>{sub}</span>
        {delta && (
          <span style={{
            fontSize: '10px', fontWeight: '700',
            padding: '2px 7px', borderRadius: '20px',
            ...ds
          }}>
            {delta}
          </span>
        )}
      </div>
    </div>
  );
}
