import React, { useState, useMemo, useEffect } from "react";
import { useFraud } from "../context/FraudContext";
import TransactionDrawer from "../components/TransactionDrawer";
import FraudInvestigationPanel from "../components/FraudInvestigationPanel";
import type { Transaction } from "../hooks/useWebSocket";

const NAMES = [
  "Rahul Sharma", "Priya Patel", "Amit Singh", "Kavya Nair",
  "Rohan Mehta", "Ananya Iyer", "Vikram Reddy", "Sneha Gupta",
  "Arjun Kumar", "Divya Pillai", "Karan Joshi", "Meera Rao",
];

function generateName(cusId: string): string {
  const num = parseInt(cusId.replace("CUS-", "")) || 0;
  return NAMES[num % NAMES.length];
}

type RiskTier = "critical" | "high" | "medium" | "low";

interface CustomerProfile {
  id: string;
  name: string;
  transactions: Transaction[];
  totalAmount: number;
  fraudCount: number;
  suspiciousCount: number;
  cities: Set<string>;
  merchants: Set<string>;
  lastSeen: string;
  riskTier: RiskTier;
  smsSent?: boolean;
}

// ─── SHAP Waterfall Plot Component ───
function ShapWaterfall({ signals }: { signals: Record<string, number> }) {
  if (!signals || Object.keys(signals).length === 0) return null;

  const items = Object.entries(signals).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));
  const maxVal = Math.max(...items.map(i => Math.abs(i[1])), 0.1);

  return (
    <div style={{ marginTop: '10px', padding: '10px', background: '#F6F8FA', borderRadius: '8px', border: '1px solid #E1E4E8' }}>
      <div style={{ fontSize: '9px', fontWeight: 700, color: '#57606A', textTransform: 'uppercase', marginBottom: '8px', letterSpacing: '0.4px' }}>
        SHAP Feature Influence (Waterfall)
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        {items.map(([key, val]) => {
          const percentage = (Math.abs(val) / maxVal) * 100;
          const isPositive = val > 0;
          return (
            <div key={key} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{ width: '80px', fontSize: '10px', color: '#24292F', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {key.replace(/_/g, ' ')}
              </div>
              <div style={{ flex: 1, height: '8px', background: '#E1E4E8', borderRadius: '4px', position: 'relative', overflow: 'hidden' }}>
                <div style={{
                  position: 'absolute',
                  left: '0',
                  height: '100%',
                  width: `${percentage}%`,
                  background: isPositive ? '#CF222E' : '#1A7F37',
                  borderRadius: '4px',
                  transition: 'width 0.5s ease-out'
                }} />
              </div>
              <div style={{ width: '35px', fontSize: '10px', fontWeight: 700, color: isPositive ? '#CF222E' : '#1A7F37', textAlign: 'right' }}>
                {isPositive ? '+' : ''}{val.toFixed(2)}
              </div>
            </div>
          );
        })}
      </div>
      <div style={{ marginTop: '6px', fontSize: '8px', color: '#8C959F', fontStyle: 'italic' }}>
        Red bars indicate increased fraud risk, green indicates reduced risk.
      </div>
    </div>
  );
}

// ─── Transaction Card Component ───
function TransactionCard({ txn, showShap = false }: { txn: any, showShap?: boolean }) {
  const isF = txn.risk_level === 'fraudulent' || txn.risk_level === 'critical'
  const isS = txn.risk_level === 'suspicious' || txn.risk_level === 'high'
  const borderColor = isF ? '#CF222E' : isS ? '#9A6700' : '#1A7F37'
  const bg = isF ? '#FFEBE9' : isS ? '#FFF8C5' : '#DAFBE1'
  const textColor = isF ? '#CF222E' : isS ? '#9A6700' : '#1A7F37'

  // Extract top SHAP signal for importance label
  const topSignal = txn.shap_values 
    ? Object.entries(txn.shap_values as Record<string, number>)
        .sort((a, b) => b[1] - a[1])[0]?.[0]
    : txn.shap_top_feature;

  return (
    <div style={{
      marginBottom: '10px',
      background: 'white',
      border: '1px solid #E8ECF0',
      borderLeft: `4px solid ${borderColor}`,
      borderRadius: '10px',
      padding: '12px 14px'
    }}>
      {/* Row 1: merchant + amount + score */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '6px' }}>
        <div>
          <div style={{ fontSize: '13px', fontWeight: 700, color: '#0D1117' }}>
            {txn.merchant}
          </div>
          <div style={{ fontSize: '12px', fontWeight: 700, color: '#0D1117', marginTop: '1px' }}>
            ₹{txn.amount?.toLocaleString('en-IN')}
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: '20px', fontWeight: 800, color: textColor, fontVariantNumeric: 'tabular-nums' }}>
            {txn.risk_score?.toFixed(1)}
          </div>
          <div style={{
            fontSize: '9px', fontWeight: 700,
            padding: '2px 8px', borderRadius: '4px',
            background: bg, color: textColor
          }}>
            {txn.risk_level?.toUpperCase()}
          </div>
        </div>
      </div>

      {/* Row 2: metadata */}
      <div style={{ fontSize: '10px', color: '#57606A', marginBottom: '8px' }}>
        {txn.merchant_category} · {txn.city} · {txn.timestamp ? new Date(txn.timestamp).toLocaleTimeString('en-IN') : ''}
        {txn.is_new_device && (
          <span style={{ marginLeft: '8px', color: '#9A6700', fontWeight: 700 }}>⚠ NEW DEVICE</span>
        )}
      </div>

      {/* Row 3: WHY FLAGGED / PRIMARY SIGNAL box (Prioritizing amount_to_avg_ratio per specs) */}
      {(isF || isS) && (
        <div style={{
          padding: '10px 12px', marginBottom: '12px',
          background: bg, border: `2px solid ${borderColor}`,
          borderRadius: '8px', fontSize: '12px',
          boxShadow: '0 2px 4px rgba(0,0,0,0.05)'
        }}>
          <div style={{ fontSize: '10px', fontWeight: 800, color: textColor, letterSpacing: '0.6px', marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '14px' }}>🕵️</span> WHY FLAGGED
          </div>
          <div style={{ color: '#1F2328', fontWeight: 600, marginBottom: '4px' }}>
            {topSignal?.replace(/_/g, ' ').toUpperCase() || 'ANOMALY DETECTED'}
          </div>
          <div style={{ color: '#444', fontStyle: 'italic', lineHeight: '1.5' }}>
            "{txn.scenario_description || 'Pattern suggests deviation from normal spending behavior.'}"
          </div>
        </div>
      )}

      {/* SHAP Waterfall Plot - only for investigation view */}
      {showShap && txn.shap_values && (isF || isS) && (
        <ShapWaterfall signals={txn.shap_values} />
      )}

      {/* Row 4: Triggered rules */}
      {txn.rule_names?.length > 0 && (
        <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap', marginTop: '10px', marginBottom: '8px' }}>
          {txn.rule_names.map((r: string, i: number) => (
            <span key={i} style={{
              fontSize: '10px', fontWeight: 700,
              padding: '2px 8px', borderRadius: '4px',
              background: '#FFEBE9', color: '#CF222E',
              border: '1px solid #FFCECB'
            }}>
              {r}
            </span>
          ))}
        </div>
      )}

      {/* Row 5: ML top feature + action */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '8px' }}>
        {txn.model_used && (
          <div style={{ fontSize: '9px', color: '#8C959F', fontStyle: 'italic' }}>
            Engine: {txn.model_used}
          </div>
        )}
        <span style={{
          fontSize: '10px', fontWeight: 700,
          padding: '2px 8px', borderRadius: '4px',
          background: '#DDF4FF', color: '#0969DA',
          marginLeft: 'auto'
        }}>
          {txn.action?.replace(/_/g, ' ').toUpperCase()}
        </span>
      </div>
    </div>
  )
}

export default function CustomerManagement() {
  const { transactions } = useFraud();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [tierFilter, setTierFilter] = useState<RiskTier | "all">("all");
  const [smsModal, setSmsModal] = useState<CustomerProfile | null>(null);
  const [smsSentIds, setSmsSentIds] = useState<Set<string>>(new Set());
  const [drawerTxn, setDrawerTxn] = useState<Transaction | null>(null);
  const [showInvestigation, setShowInvestigation] = useState(false);
  const [historyExpanded, setHistoryExpanded] = useState(true);

  const customerProfiles = useMemo(() => {
    const map = new Map<string, CustomerProfile>();
    transactions.forEach(t => {
      if (!map.has(t.customer_id)) {
        map.set(t.customer_id, {
          id: t.customer_id,
          name: generateName(t.customer_id),
          transactions: [],
          totalAmount: 0,
          fraudCount: 0,
          suspiciousCount: 0,
          cities: new Set(),
          merchants: new Set(),
          lastSeen: t.timestamp,
          riskTier: "low",
        });
      }
      const p = map.get(t.customer_id)!;
      p.transactions.push(t);
      p.totalAmount += t.amount;
      if (t.risk_level === "fraudulent") p.fraudCount++;
      if (t.risk_level === "suspicious") p.suspiciousCount++;
      p.cities.add(t.city || "Unknown");
      p.merchants.add(t.merchant);
      if (t.timestamp > p.lastSeen) p.lastSeen = t.timestamp;
      const fraudRate = p.fraudCount / p.transactions.length;
      // Relaxed risk tiers: any fraud is critical, any suspicious is high
      p.riskTier = p.fraudCount > 0 ? "critical" : p.suspiciousCount > 0 ? "high" : "low";
    });
    return Array.from(map.values()).sort((a, b) => b.fraudCount - a.fraudCount || b.suspiciousCount - a.suspiciousCount);
  }, [transactions]);

  const filteredCustomers = useMemo(() => {
    // Fix 6: Relaxed Customer Intelligence filtering
    // Show ANY customer with fraud, suspicious, or high risk tier
    let list = customerProfiles.filter(
      c => c.fraudCount > 0 || c.suspiciousCount > 0 || c.riskTier === "critical" || c.riskTier === "high"
    );
    if (search) {
      const s = search.toLowerCase();
      list = list.filter(c => c.id.toLowerCase().includes(s) || c.name.toLowerCase().includes(s));
    }
    return list;
  }, [customerProfiles, search]);

  const fraudCustomers = filteredCustomers;


  const selected = selectedId ? customerProfiles.find(c => c.id === selectedId) ?? null : null;

  // Auto-select first customer when data first loads
  useEffect(() => {
    if (customerProfiles.length > 0 && !selectedId) {
      setSelectedId(customerProfiles[0].id)
    }
  }, [customerProfiles, selectedId])

  const tierColors: Record<RiskTier, { bg: string; text: string; dot: string }> = {
    critical: { bg: "bg-red-50", text: "text-red-600", dot: "bg-red-500" },
    high: { bg: "bg-orange-50", text: "text-orange-600", dot: "bg-orange-500" },
    medium: { bg: "bg-amber-50", text: "text-amber-600", dot: "bg-amber-500" },
    low: { bg: "bg-emerald-50", text: "text-emerald-600", dot: "bg-emerald-500" },
  };

  const tiers: (RiskTier | "all")[] = ["all", "critical", "high", "medium", "low"];

  function sendSms(c: CustomerProfile) {
    setSmsModal(null);
    setSmsSentIds(s => new Set(s).add(c.id));
    showToast(`SMS alert sent to ${c.id}`);
  }

  // Compute risk score for sidebar
  const riskScore = selected
    ? Math.round(
        selected.transactions.reduce((s, t) => s + (t.risk_score || 0), 0) /
        Math.max(selected.transactions.length, 1)
      )
    : 0;

  const riskScoreColor = riskScore >= 70 ? '#CF222E' : riskScore >= 40 ? '#9A6700' : '#1A7F37';
  const riskScoreLabel = riskScore >= 70 ? 'High' : riskScore >= 40 ? 'Medium' : 'Low';

  return (
    <div className="flex h-full overflow-hidden p-4 gap-3">
      {/* LEFT PANEL — Customer List */}
      <div className="w-[40%] flex flex-col bg-white border border-slate-200 rounded-xl overflow-hidden flex-shrink-0">
        {/* Search */}
        <div className="p-3 border-b border-slate-100">
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search by ID or name..."
            className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-[6px] text-[12px] text-slate-700 placeholder-slate-400 outline-none focus:border-blue-300"
          />
        </div>

        {/* Banner */}
        <div style={{
          padding: '10px 16px', marginBottom: '12px',
          background: '#FFEBE9', border: '1px solid #FFCECB',
          borderRadius: '8px', fontSize: '11px', color: '#CF222E',
          display: 'flex', alignItems: 'center', gap: '8px',
          margin: '12px'
        }}>
          <span style={{ fontSize: '14px' }}>⚠</span>
          <span>
            <strong>{fraudCustomers.length} customers</strong> with fraud or suspicious transactions 
            in current session. Click any customer to see the full fraud investigation.
          </span>
        </div>


        {/* Customer rows */}
        <div className="flex-1 overflow-y-auto" style={{ scrollbarWidth: "none" }}>
          {filteredCustomers.length === 0 && (
            <div className="text-[12px] text-slate-400 text-center py-8">No customers yet</div>
          )}
            {filteredCustomers.map(c => {
            const tc = tierColors[c.riskTier];
            const initials = c.name.split(" ").map(n => n[0]).join("");
            return (
              <div
                key={c.id}
                onClick={() => {
                  setSelectedId(c.id);
                  if (c.fraudCount > 0 || c.suspiciousCount > 0) setShowInvestigation(true);
                }}
                className={`px-3 py-[10px] border-b border-slate-50 flex items-center gap-3 cursor-pointer transition-colors hover:bg-slate-50 ${selectedId === c.id ? "bg-blue-50" : ""}`}
              >
                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-[10px] font-bold ${tc.bg} ${tc.text} flex-shrink-0`}>
                  {initials}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-[12px] font-semibold text-slate-900 truncate">{c.name}</span>
                    <span className={`text-[9px] font-bold px-[5px] py-[1px] rounded-md uppercase ${tc.bg} ${tc.text}`}>{c.riskTier}</span>
                    {smsSentIds.has(c.id) && <span className="text-[8px] font-bold px-[4px] py-[1px] rounded bg-emerald-100 text-emerald-600">SMS Sent</span>}
                  </div>
                  <div className="text-[10px] text-slate-400">
                    {c.id} · {c.transactions.length} txns · {c.fraudCount > 0 ? <span className="text-red-500 font-semibold">{c.fraudCount} fraud</span> : "clean"}
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  <span className="text-[9px] text-slate-300 flex-shrink-0">{getTimeAgo(c.lastSeen)}</span>
                  {(c.fraudCount > 0 || c.suspiciousCount > 0) && (
                    <span
                      title="Open Investigation Panel"
                      style={{
                        width: 18, height: 18, borderRadius: "50%",
                        background: showInvestigation && selectedId === c.id ? "#EF4444" : "#FFEBE9",
                        display: "flex", alignItems: "center", justifyContent: "center",
                        fontSize: 9, cursor: "pointer", flexShrink: 0, color: "#EF4444",
                        border: "1px solid #FECACA",
                      }}
                      onClick={e => { e.stopPropagation(); setSelectedId(c.id); setShowInvestigation(true); }}
                    >🔍</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* RIGHT PANEL — Profile with TransactionCards */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden transition-all duration-200">
        {!selected ? (
          <div className="flex-1 bg-white border border-slate-200 rounded-xl flex items-center justify-center">
            <div className="text-center">
              <div className="text-[40px] mb-2">👤</div>
              <div className="text-[13px] text-slate-400">Select a customer to view profile</div>
            </div>
          </div>
        ) : (
          <div className="flex-1 bg-white border border-slate-200 rounded-xl overflow-y-auto p-5 space-y-4" style={{ scrollbarWidth: "none" }}>
            {/* SECTION A — Header */}
            <div className="flex items-center gap-4">
              <div className={`w-14 h-14 rounded-full flex items-center justify-center text-[18px] font-bold ${tierColors[selected.riskTier].bg} ${tierColors[selected.riskTier].text}`}>
                {selected.name.split(" ").map(n => n[0]).join("")}
              </div>
              <div>
                <div className="text-[16px] font-bold text-slate-900">Customer Intelligence</div>
                <div className="text-[12px] text-slate-400">Fraud-affected customers only — click to see why each transaction was flagged</div>
              </div>
              <span className={`text-[10px] font-bold px-2 py-[3px] rounded-md uppercase ${tierColors[selected.riskTier].bg} ${tierColors[selected.riskTier].text}`}>
                {selected.riskTier}
              </span>

              {/* Risk Score */}
              <div style={{ marginLeft: 'auto', textAlign: 'right' }}>
                <div style={{ fontSize: '10px', color: '#57606A', fontWeight: 600 }}>Risk Score</div>
                <div style={{ fontSize: '22px', fontWeight: 800, color: riskScoreColor, fontVariantNumeric: 'tabular-nums' }}>
                  {riskScore}<span style={{ fontSize: '12px', fontWeight: 600, color: '#8C959F' }}>/100</span>
                </div>
                <div style={{ fontSize: '9px', fontWeight: 700, color: riskScoreColor }}>{riskScoreLabel}</div>
              </div>
            </div>

            {/* SECTION B — KPI row */}
            <div className="grid grid-cols-4 gap-2">
              <MiniKPI label="Total Txns" value={selected.transactions.length.toString()} />
              <MiniKPI label="Total Volume" value={`₹${(selected.totalAmount / 1000).toFixed(1)}K`} />
              <MiniKPI label="Fraud Count" value={selected.fraudCount.toString()} red={selected.fraudCount > 0} />
              <MiniKPI label="Suspicious" value={selected.suspiciousCount.toString()} />
            </div>

            {/* City & Merchant tags */}
            <div className="space-y-2">
              <div>
                <span className="text-[10px] font-bold text-slate-400 tracking-[0.3px] uppercase mr-2">Active in:</span>
                {Array.from(selected.cities).map(c => (
                  <span key={c} className="text-[10px] bg-slate-100 text-slate-600 px-2 py-[2px] rounded-md mr-1">{c}</span>
                ))}
              </div>
              <div>
                <span className="text-[10px] font-bold text-slate-400 tracking-[0.3px] uppercase mr-2">Shops at:</span>
                {Array.from(selected.merchants).slice(0, 6).map(m => (
                  <span key={m} className="text-[10px] bg-blue-50 text-blue-600 px-2 py-[2px] rounded-md mr-1">{m}</span>
                ))}
              </div>
            </div>

            {/* SECTION C — Last active */}
            <div className="text-[10px] text-slate-400">
              Last active {getTimeAgo(selected.lastSeen)} · Account age: {Math.round(selected.transactions.length * 1.5)} days
            </div>

            {/* SECTION D — Transaction History with TransactionCards */}
            <div>
              <button
                onClick={() => setHistoryExpanded(e => !e)}
                style={{
                  width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '8px 0', border: 'none', background: 'none', cursor: 'pointer'
                }}
              >
                <span className="text-[11px] font-bold text-slate-400 tracking-[0.5px] uppercase">
                  Transaction History ({selected.transactions.length})
                </span>
                <span style={{ fontSize: '14px', color: '#94A3B8', transition: 'transform 0.2s', transform: historyExpanded ? 'rotate(180deg)' : 'rotate(0deg)' }}>▼</span>
              </button>
              {historyExpanded && (
                <div>
                  {selected.transactions.map((t, i) => (
                    <TransactionCard key={i} txn={t} showShap={true} />
                  ))}
                </div>
              )}

            </div>

            {/* SECTION E — Action panel (only if fraudCount > 0) */}
            {(selected.riskTier === "critical" || selected.riskTier === "high") && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-3">
                <div className="text-[12px] font-semibold text-red-700 mb-2">
                  ⚠️ This customer has {selected.fraudCount} fraud transaction{selected.fraudCount !== 1 ? "s" : ""}
                </div>
                <div className="flex gap-2 flex-wrap">
                  <button
                    onClick={() => showToast("Customer blocked")}
                    className="text-[10px] font-semibold px-3 py-[5px] rounded-md bg-red-500 text-white hover:bg-red-600 transition-colors"
                  >
                    Block Customer
                  </button>
                  <button
                    onClick={() => showToast("OTP verification sent")}
                    className="text-[10px] font-semibold px-3 py-[5px] rounded-md bg-blue-500 text-white hover:bg-blue-600 transition-colors"
                  >
                    Send OTP Verification
                  </button>
                  <button
                    onClick={() => showToast("Flagged for review")}
                    className="text-[10px] font-semibold px-3 py-[5px] rounded-md bg-amber-500 text-white hover:bg-amber-600 transition-colors"
                  >
                    Flag for Review
                  </button>
                  <button
                    onClick={() => setSmsModal(selected)}
                    className="text-[10px] font-semibold px-3 py-[5px] rounded-md bg-emerald-500 text-white hover:bg-emerald-600 transition-colors"
                  >
                    Send SMS Alert
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* INVESTIGATION PANEL — right drawer */}
      {showInvestigation && selected && (
        <FraudInvestigationPanel
          customer={selected as any}
          onClose={() => setShowInvestigation(false)}
        />
      )}

      {smsModal && (
        <>
          <div className="fixed inset-0 bg-black/40 z-40" onClick={() => setSmsModal(null)} />
          <div className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-50 w-[380px] bg-white rounded-xl shadow-2xl border border-slate-200 overflow-hidden">
            <div className="px-4 py-3 border-b border-slate-100 flex items-center gap-2">
              <span className="text-lg">📱</span>
              <span className="text-[13px] font-bold text-slate-900">SMS Alert Preview</span>
            </div>
            <div className="p-4">
              <div className="text-[11px] text-slate-400 mb-2">To: {smsModal.id} (registered mobile)</div>
              <div className="bg-slate-50 rounded-lg p-3 text-[12px] text-slate-700 leading-relaxed border border-slate-200">
                "Dear {smsModal.name}, suspicious activity detected on your account.
                Transaction of ₹{smsModal.transactions[0]?.amount.toLocaleString()} at {smsModal.transactions[0]?.merchant} has been flagged.
                If not you, reply BLOCK to +91-1800-XXX-XXXX. - FraudGuard Security Team"
              </div>
              <div className="flex gap-2 mt-3 justify-end">
                <button onClick={() => setSmsModal(null)} className="text-[11px] font-semibold px-3 py-[5px] rounded-md bg-slate-100 text-slate-600 hover:bg-slate-200">
                  Cancel
                </button>
                <button onClick={() => sendSms(smsModal)} className="text-[11px] font-semibold px-3 py-[5px] rounded-md bg-emerald-500 text-white hover:bg-emerald-600">
                  Send SMS
                </button>
              </div>
            </div>
          </div>
        </>
      )}

      <TransactionDrawer txn={drawerTxn} onClose={() => setDrawerTxn(null)} />
    </div>
  );
}

function MiniKPI({ label, value, red }: { label: string; value: string; red?: boolean }) {
  return (
    <div className="bg-slate-50 rounded-lg p-2">
      <div className="text-[9px] text-slate-400 uppercase tracking-[0.3px]">{label}</div>
      <div className={`text-[16px] font-extrabold tabular-nums ${red ? "text-red-600" : "text-slate-900"}`}>{value}</div>
    </div>
  );
}

function getTimeAgo(ts: string): string {
  const diff = Date.now() - new Date(ts).getTime();
  const sec = Math.floor(diff / 1000);
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  return `${Math.floor(min / 60)}h ago`;
}

function showToast(msg: string) {
  const el = document.createElement("div");
  el.className = "fixed bottom-4 right-4 z-[100] bg-slate-900 text-white text-[12px] px-4 py-2 rounded-lg shadow-lg animate-slide-in";
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => { el.style.opacity = "0"; el.style.transition = "opacity 300ms"; setTimeout(() => el.remove(), 300); }, 2500);
}
