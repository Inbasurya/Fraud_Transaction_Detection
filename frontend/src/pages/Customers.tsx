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

// ─── Transaction Card Component ───
function TransactionCard({ txn }: { txn: any }) {
  const isF = txn.risk_level === 'fraudulent'
  const isS = txn.risk_level === 'suspicious'
  const borderColor = isF ? '#CF222E' : isS ? '#9A6700' : '#1A7F37'
  const bg = isF ? '#FFEBE9' : isS ? '#FFF8C5' : '#DAFBE1'
  const textColor = isF ? '#CF222E' : isS ? '#9A6700' : '#1A7F37'

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

      {/* Row 3: WHY FLAGGED box */}
      {(txn.scenario_description && txn.scenario_description !== 'Normal transaction') ? (
        <div style={{
          padding: '8px 10px', marginBottom: '8px',
          background: bg, border: `1px solid ${borderColor}30`,
          borderRadius: '6px', fontSize: '11px'
        }}>
          <div style={{ fontSize: '9px', fontWeight: 700, color: textColor, letterSpacing: '0.4px', marginBottom: '3px' }}>
            WHY FLAGGED
          </div>
          <div style={{ color: textColor, fontStyle: 'italic', lineHeight: '1.4' }}>
            "{txn.scenario_description}"
          </div>
        </div>
      ) : txn.risk_level === 'safe' ? (
        <div style={{ padding: '6px 10px', marginBottom: '8px', background: '#DAFBE1', borderRadius: '6px', fontSize: '11px', color: '#1A7F37', fontStyle: 'italic' }}>
          No anomalies detected — approved normally
        </div>
      ) : null}

      {/* Row 4: Triggered rules */}
      {txn.rule_names?.length > 0 && (
        <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap', marginBottom: '8px' }}>
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
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        {txn.shap_top_feature && txn.risk_level !== 'safe' && (
          <div style={{ fontSize: '10px', color: '#57606A' }}>
            ML signal: <strong>{txn.shap_top_feature?.replace(/_/g, ' ')}</strong>
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

// ─── Behavioral DNA Visualization ───
function BehavioralDNAVisualization({ dna, cid }: { dna: any, cid: string }) {
  if (!dna) return <div className="text-[10px] text-slate-400 italic mb-4">No DNA profile captured yet for {cid}</div>;

  return (
    <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 space-y-3 mb-4">
      <div className="flex justify-between items-center">
        <span className="text-[9px] font-bold text-slate-500 uppercase tracking-wider">Behavioral DNA Profile</span>
        <span className="text-[8px] px-2 py-0.5 bg-blue-100 text-blue-600 rounded font-bold">EMA SMOOTHED</span>
      </div>
      
      {/* Spend Rhythm (Hours) */}
      <div>
        <div className="text-[8px] text-slate-400 mb-1">ACTIVITY RHYTHM (24H)</div>
        <div className="flex items-end gap-[1px] h-10 border-b border-slate-200">
          {(dna.hour_pattern || Array(24).fill(0.1)).map((val: number, i: number) => (
            <div 
              key={i} 
              title={`Hour ${i}: ${(val*100).toFixed(1)}%`}
              style={{ 
                height: `${Math.max(val * 100, 5)}%`, 
                flex: 1, 
                backgroundColor: i >= 0 && i <= 5 ? '#F87171' : '#60A5FA',
                opacity: val > 0.2 ? 1 : 0.4
              }} 
            />
          ))}
        </div>
        <div className="flex justify-between text-[7px] text-slate-400 mt-1">
          <span>00:00</span>
          <span>12:00</span>
          <span>23:59</span>
        </div>
      </div>

      {/* Affinity Chips */}
      <div className="flex flex-wrap gap-2">
        <div className="flex-1 min-w-[100px]">
          <div className="text-[8px] text-slate-400 mb-1 uppercase">Top Categories</div>
          <div className="flex flex-wrap gap-1">
            {Object.entries(dna.category_affinity || {}).sort((a: any, b: any) => b[1] - a[1]).slice(0, 3).map(([cat, val]: any) => (
              <span key={cat} className="text-[8px] bg-white border border-slate-200 px-1.5 py-0.5 rounded text-slate-600">
                {cat} ({(val*100).toFixed(0)}%)
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function Customers() {
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
      p.riskTier = fraudRate > 0.3 ? "critical" : fraudRate > 0.1 ? "high" : p.suspiciousCount > 2 ? "medium" : "low";
    });
    return Array.from(map.values()).sort((a, b) => b.fraudCount - a.fraudCount);
  }, [transactions]);

  const filteredCustomers = useMemo(() => {
    let list = customerProfiles;
    if (tierFilter !== "all") list = list.filter(c => c.riskTier === tierFilter);
    if (search) {
      const s = search.toLowerCase();
      list = list.filter(c => c.id.toLowerCase().includes(s) || c.name.toLowerCase().includes(s));
    }
    return list;
  }, [customerProfiles, tierFilter, search]);

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

  const riskScoreColor = riskScore >= 85 ? '#82071E' : riskScore >= 70 ? '#CF222E' : riskScore >= 50 ? '#9A6700' : riskScore >= 30 ? '#B08800' : '#1A7F37';
  const riskScoreLabel = riskScore >= 85 ? 'Critical' : riskScore >= 70 ? 'High' : riskScore >= 50 ? 'Suspicious' : riskScore >= 30 ? 'Monitor' : 'Low';

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

        {/* Tier tabs */}
        <div className="flex gap-1 px-3 py-2 border-b border-slate-100">
          {tiers.map(tier => (
            <button
              key={tier}
              onClick={() => setTierFilter(tier)}
              className={`text-[10px] font-semibold px-2 py-[4px] rounded-md capitalize transition-colors ${
                tierFilter === tier ? "bg-blue-500 text-white" : "bg-slate-50 text-slate-500 hover:bg-slate-100"
              }`}
            >
              {tier}
            </button>
          ))}
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
                <div className="text-[16px] font-bold text-slate-900">{selected.name}</div>
                <div className="text-[12px] text-slate-400">{selected.id}</div>
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

            {/* SECTION D — Transaction History & DNA */}
            <div className="space-y-4">
              {/* Behavioral DNA Section */}
              <BehavioralDNAVisualization cid={selected.id} dna={(selected as any).dna_profile} />

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
                    {selected.transactions.slice(0, 10).map(t => (
                      <div key={t.id} onClick={() => setDrawerTxn(t)} style={{ cursor: 'pointer' }}>
                        <TransactionCard txn={t} />
                      </div>
                    ))}
                  </div>
                )}
              </div>
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
