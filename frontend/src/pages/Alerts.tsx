import React, { useState, useMemo } from "react";
import { useFraud, AlertItem } from "../context/FraudContext";

type FilterTab = "all" | "CRITICAL" | "HIGH" | "MEDIUM" | "resolved";

export default function Alerts() {
  const { alerts, transactions } = useFraud();
  const [activeTab, setActiveTab] = useState<FilterTab>("all");
  const [localStatuses, setLocalStatuses] = useState<Record<string, string>>({});

  const enrichedAlerts = useMemo(() =>
    alerts.map(a => ({
      ...a,
      status: (localStatuses[a.id] || a.status) as AlertItem["status"],
    })),
    [alerts, localStatuses]
  );

  const filtered = useMemo(() => {
    if (activeTab === "all") return enrichedAlerts.filter(a => a.status !== "resolved");
    if (activeTab === "resolved") return enrichedAlerts.filter(a => a.status === "resolved");
    return enrichedAlerts.filter(a => a.severity === activeTab && a.status !== "resolved");
  }, [enrichedAlerts, activeTab]);

  const counts = useMemo(() => ({
    all: enrichedAlerts.filter(a => a.status !== "resolved").length,
    CRITICAL: enrichedAlerts.filter(a => a.severity === "CRITICAL" && a.status !== "resolved").length,
    HIGH: enrichedAlerts.filter(a => a.severity === "HIGH" && a.status !== "resolved").length,
    MEDIUM: enrichedAlerts.filter(a => a.severity === "MEDIUM" && a.status !== "resolved").length,
    resolved: enrichedAlerts.filter(a => a.status === "resolved").length,
  }), [enrichedAlerts]);

  function acknowledge(id: string) {
    setLocalStatuses(s => ({ ...s, [id]: "investigating" }));
  }
  function investigate(id: string) {
    showToast("Investigation opened");
    setLocalStatuses(s => ({ ...s, [id]: "investigating" }));
  }
  function block(id: string) {
    showToast("Customer blocked");
    setLocalStatuses(s => ({ ...s, [id]: "resolved" }));
  }

  const tabs: { key: FilterTab; label: string }[] = [
    { key: "all", label: "All" },
    { key: "CRITICAL", label: "Critical" },
    { key: "HIGH", label: "High" },
    { key: "MEDIUM", label: "Medium" },
    { key: "resolved", label: "Resolved" },
  ];

  return (
    <div className="flex flex-col h-full overflow-hidden p-4 gap-3">
      {/* Stats row */}
      <div className="grid grid-cols-4 gap-[10px] flex-shrink-0">
        <StatBox label="Total Alerts" value={counts.all} color="text-slate-900" />
        <StatBox label="Critical" value={counts.CRITICAL} color="text-red-600" />
        <StatBox label="Avg Response" value="2.4 min" color="text-blue-600" />
        <StatBox label="Resolved Today" value={counts.resolved} color="text-emerald-600" />
      </div>

      {/* Filter tabs */}
      <div className="flex gap-[6px] flex-shrink-0">
        {tabs.map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`text-[11px] font-semibold px-3 py-[6px] rounded-lg transition-colors flex items-center gap-[6px] ${
              activeTab === tab.key
                ? "bg-blue-500 text-white"
                : "bg-white border border-slate-200 text-slate-600 hover:bg-slate-50"
            }`}
          >
            {tab.label}
            <span className={`text-[10px] px-[5px] py-[1px] rounded-full ${
              activeTab === tab.key ? "bg-blue-400 text-white" : "bg-slate-100 text-slate-500"
            }`}>
              {counts[tab.key]}
            </span>
          </button>
        ))}
      </div>

      {/* Alert cards */}
      <div className="flex-1 overflow-y-auto space-y-[8px]" style={{ scrollbarWidth: "none" }}>
        {filtered.length === 0 && (
          <div className="flex flex-col items-center justify-center h-40">
            <div className="w-10 h-10 rounded-full bg-emerald-50 flex items-center justify-center mb-2">
              <span className="text-emerald-500 text-lg">✓</span>
            </div>
            <div className="text-[13px] font-semibold text-slate-400">
              {activeTab === "resolved" ? "No resolved alerts yet" : "Monitoring for threats..."}
            </div>
            <div className="text-[11px] text-slate-300 mt-1">
              {transactions.length} transactions analyzed
            </div>
          </div>
        )}

        {filtered.map(alert => {
          const isAcked = alert.status === "investigating";
          const timeAgo = getTimeAgo(alert.timestamp);
          const sevIcon = alert.severity === "CRITICAL" ? "\uD83D\uDEA8" : alert.severity === "HIGH" ? "\u26A0\uFE0F" : "\uD83D\uDCCB";
          const sevBg = alert.severity === "CRITICAL" ? "bg-red-50 border-red-100" :
            alert.severity === "HIGH" ? "bg-orange-50 border-orange-100" : "bg-amber-50 border-amber-100";
          const sevText = alert.severity === "CRITICAL" ? "bg-red-100 text-red-700" :
            alert.severity === "HIGH" ? "bg-orange-100 text-orange-700" : "bg-amber-100 text-amber-700";

          return (
            <div
              key={alert.id}
              className={`bg-white border border-slate-200 rounded-xl p-4 flex gap-3 transition-opacity ${isAcked ? "opacity-50" : ""}`}
            >
              {/* Severity icon */}
              <div className={`w-[30px] h-[30px] rounded-lg flex items-center justify-center text-[13px] flex-shrink-0 border ${sevBg}`}>
                {sevIcon}
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-[3px]">
                  <span className="text-[12px] font-bold text-slate-900">{alert.title}</span>
                  <span className={`text-[9px] font-bold px-[5px] py-[1px] rounded-md ${sevText}`}>
                    {alert.severity}
                  </span>
                  <span className="text-[10px] text-slate-400 ml-auto flex-shrink-0">{timeAgo}</span>
                </div>
                <div className="text-[11px] text-slate-500 mb-1">
                  {alert.customer_id} · {alert.merchant} · ₹{alert.amount.toLocaleString()}
                </div>
                {alert.rule_names.length > 0 && (
                  <div className="flex flex-wrap gap-1 mb-1">
                    {alert.rule_names.map((r, i) => (
                      <span key={i} className="text-[9px] font-semibold px-[5px] py-[1px] rounded bg-slate-100 text-slate-600">
                        {r}
                      </span>
                    ))}
                  </div>
                )}
                {alert.risk_level === "fraudulent" && alert.scenario_description && (
                  <div className="text-[10px] text-slate-400 italic">{alert.scenario_description}</div>
                )}
              </div>

              {/* Actions */}
              <div className="flex flex-col gap-1 flex-shrink-0">
                <button
                  onClick={() => acknowledge(alert.id)}
                  className="text-[10px] font-semibold px-2 py-[4px] rounded-md bg-slate-100 text-slate-600 hover:bg-slate-200 transition-colors"
                >
                  Acknowledge
                </button>
                <button
                  onClick={() => investigate(alert.id)}
                  className="text-[10px] font-semibold px-2 py-[4px] rounded-md bg-blue-50 text-blue-600 hover:bg-blue-100 transition-colors"
                >
                  Investigate
                </button>
                {alert.severity === "CRITICAL" && (
                  <button
                    onClick={() => block(alert.id)}
                    className="text-[10px] font-semibold px-2 py-[4px] rounded-md bg-red-50 text-red-600 hover:bg-red-100 transition-colors"
                  >
                    Block
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function StatBox({ label, value, color }: { label: string; value: string | number; color: string }) {
  return (
    <div className="bg-white border border-slate-200 rounded-xl p-3">
      <div className="text-[10px] font-bold text-slate-400 tracking-[0.5px] uppercase mb-1">{label}</div>
      <div className={`text-[20px] font-extrabold tabular-nums ${color}`}>{value}</div>
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
