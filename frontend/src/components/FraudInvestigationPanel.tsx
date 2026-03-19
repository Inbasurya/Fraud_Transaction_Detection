import React, { useState, useEffect, useRef } from "react";
import * as d3 from "d3";

interface Transaction {
  id: string;
  customer_id: string;
  amount: number;
  merchant: string;
  risk_score: number;
  risk_level: string;
  action: string;
  city?: string;
  timestamp?: string;
  rule_names?: string[];
  scenario_description?: string;
  device?: string;
  shap_values?: Record<string, number>;
}

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
  riskTier: string;
}

interface FraudInvestigationPanelProps {
  customer: CustomerProfile | null;
  onClose: () => void;
}

// ─── Mini D3 Fraud Graph Node ────────────────────────────────────────────────
function MiniGraphNode({ customer }: { customer: CustomerProfile }) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current) return;
    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const W = 280, H = 200;

    // Build mini graph from the customer's fraud/suspicious transactions
    const fraudTxns = customer.transactions.filter(
      t => t.risk_level === "fraudulent" || t.risk_level === "suspicious"
    ).slice(0, 8);

    const nodes: any[] = [
      { id: customer.id, type: "customer", risk: "fraud", label: customer.id, r: 18 },
      ...fraudTxns.map((t, i) => ({
        id: t.merchant + i,
        type: "merchant",
        risk: t.risk_level === "fraudulent" ? "fraud" : "risk",
        label: t.merchant.substring(0, 10),
        r: 10 + (t.risk_score / 20),
        txn: t,
      })),
    ];

    const edges = fraudTxns.map((_, i) => ({
      source: customer.id,
      target: nodes[i + 1].id,
    }));

    const sim = d3.forceSimulation(nodes as any)
      .force("link", d3.forceLink(edges).id((d: any) => d.id).distance(65))
      .force("charge", d3.forceManyBody().strength(-120))
      .force("center", d3.forceCenter(W / 2, H / 2))
      .force("collision", d3.forceCollide().radius((d: any) => d.r + 4));

    // Glow filter
    const defs = svg.append("defs");
    const glow = defs.append("filter").attr("id", "mini-glow");
    glow.append("feGaussianBlur").attr("stdDeviation", "3").attr("result", "coloredBlur");
    const merge = glow.append("feMerge");
    merge.append("feMergeNode").attr("in", "coloredBlur");
    merge.append("feMergeNode").attr("in", "SourceGraphic");

    const linkSel = svg.append("g")
      .selectAll("line")
      .data(edges)
      .join("line")
      .attr("stroke", (d: any) => {
        const target = nodes.find(n => n.id === (typeof d.target === "object" ? d.target.id : d.target));
        return target?.risk === "fraud" ? "#EF4444" : "#F59E0B";
      })
      .attr("stroke-width", 1.5)
      .attr("stroke-dasharray", "4,2")
      .attr("opacity", 0.7);

    const tooltip = d3.select("body").append("div")
      .style("position", "absolute").style("background", "#1E293B")
      .style("color", "#F1F5F9").style("padding", "6px 10px")
      .style("border-radius", "6px").style("font-size", "11px")
      .style("pointer-events", "none").style("opacity", 0).style("z-index", "9999");

    const nodeSel = svg.append("g")
      .selectAll("g")
      .data(nodes)
      .join("g")
      .attr("cursor", "pointer")
      .call(d3.drag<SVGGElement, any>()
        .on("start", (event, d) => { if (!event.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
        .on("drag", (event, d) => { d.fx = event.x; d.fy = event.y; })
        .on("end", (event, d) => { if (!event.active) sim.alphaTarget(0); d.fx = null; d.fy = null; })
      );

    nodeSel.each(function(d: any) {
      const el = d3.select(this);
      const color = d.risk === "fraud" ? "#EF4444" : d.risk === "risk" ? "#F59E0B" : "#64748B";
      if (d.type === "customer") {
        el.append("circle").attr("r", d.r).attr("fill", "#EF4444").attr("fill-opacity", 0.9)
          .attr("stroke", "#FCA5A5").attr("stroke-width", 2).attr("filter", "url(#mini-glow)");
        el.append("text").attr("text-anchor", "middle").attr("dy", "0.35em")
          .attr("fill", "white").attr("font-size", 7).attr("font-weight", "bold").text("YOU");
      } else {
        el.append("circle").attr("r", d.r).attr("fill", color).attr("fill-opacity", 0.8)
          .attr("stroke", "white").attr("stroke-width", 1);
      }
      el.append("text").attr("text-anchor", "middle").attr("dy", d.r + 10)
        .attr("fill", "#94A3B8").attr("font-size", 8).text(d.label);
    });

    nodeSel
      .on("mouseover", (event, d: any) => {
        tooltip.transition().duration(150).style("opacity", 1);
        tooltip.html(`<b>${d.label || d.id}</b><br>Type: ${d.type}<br>Risk: ${d.risk?.toUpperCase() || "N/A"}${d.txn ? `<br>Score: ${d.txn.risk_score?.toFixed(1)}` : ""}`)
          .style("left", (event.pageX + 10) + "px").style("top", (event.pageY - 10) + "px");
      })
      .on("mouseout", () => tooltip.transition().duration(200).style("opacity", 0));

    sim.on("tick", () => {
      linkSel
        .attr("x1", (d: any) => d.source.x).attr("y1", (d: any) => d.source.y)
        .attr("x2", (d: any) => d.target.x).attr("y2", (d: any) => d.target.y);
      nodeSel.attr("transform", (d: any) => `translate(${d.x},${d.y})`);
    });

    return () => { sim.stop(); tooltip.remove(); };
  }, [customer]);

  return <svg ref={svgRef} width="100%" height={200} style={{ background: "transparent" }} />;
}

// ─── Rule Trigger Explanation ─────────────────────────────────────────────────
function RuleTriggerCard({ txn }: { txn: Transaction }) {
  const rules = txn.rule_names?.length
    ? txn.rule_names
    : txn.scenario_description
    ? [txn.scenario_description]
    : ["No specific rules triggered"];

  const shap = txn.shap_values || {};
  const shapEntries = Object.entries(shap)
    .sort(([, a], [, b]) => Number(b) - Number(a))
    .slice(0, 4);

  const confidence = txn.risk_score ? Math.min(99, Math.round(txn.risk_score + 4)) : 72;

  const decisionLabel = txn.risk_level === "fraudulent"
    ? { text: "BLOCKED", color: "#EF4444", bg: "rgba(239,68,68,0.15)" }
    : txn.risk_level === "suspicious"
    ? { text: "RISK", color: "#F59E0B", bg: "rgba(245,158,11,0.15)" }
    : { text: "NORMAL", color: "#10B981", bg: "rgba(16,185,129,0.15)" };

  return (
    <div style={{ background: "#1E293B", borderRadius: 10, padding: "14px", marginBottom: 10, border: "1px solid #334155" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
        <div>
          <div style={{ fontSize: 11, color: "#94A3B8", marginBottom: 2 }}>{txn.id}</div>
          <div style={{ fontSize: 13, fontWeight: 700, color: "#F1F5F9" }}>
            {txn.merchant} · ₹{txn.amount?.toLocaleString("en-IN")}
          </div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: 22, fontWeight: 800, color: decisionLabel.color, letterSpacing: "-0.5px", fontVariantNumeric: "tabular-nums" }}>
            {txn.risk_score?.toFixed(1)}
          </div>
          <div style={{ fontSize: 9, fontWeight: 700, padding: "2px 8px", borderRadius: 20, background: decisionLabel.bg, color: decisionLabel.color, border: `1px solid ${decisionLabel.color}40` }}>
            {decisionLabel.text}
          </div>
        </div>
      </div>

      {/* Triggered Rules */}
      <div style={{ marginBottom: 10 }}>
        <div style={{ fontSize: 9, fontWeight: 700, color: "#64748B", letterSpacing: "0.5px", marginBottom: 6 }}>TRIGGERED RULES</div>
        {rules.map((r, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 5 }}>
            <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#EF4444", flexShrink: 0 }} />
            <div style={{ fontSize: 11, color: "#F1F5F9", flex: 1 }}>{r}</div>
          </div>
        ))}
      </div>

      {/* SHAP feature breakdown */}
      {shapEntries.length > 0 && (
        <div style={{ marginBottom: 10 }}>
          <div style={{ fontSize: 9, fontWeight: 700, color: "#64748B", letterSpacing: "0.5px", marginBottom: 6 }}>TOP CONTRIBUTING FEATURES</div>
          {shapEntries.map(([key, val]) => {
            const pct = Math.min(100, Math.round(Number(val) * 100));
            const label = key.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
            return (
              <div key={key} style={{ marginBottom: 6 }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 2 }}>
                  <span style={{ fontSize: 10, color: "#94A3B8" }}>{label}</span>
                  <span style={{ fontSize: 10, fontWeight: 700, color: "#F59E0B" }}>{pct}%</span>
                </div>
                <div style={{ height: 4, background: "#334155", borderRadius: 4, overflow: "hidden" }}>
                  <div style={{ height: "100%", width: `${pct}%`, background: "linear-gradient(90deg,#F59E0B,#EF4444)", borderRadius: 4, transition: "width 0.6s ease" }} />
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Confidence meter */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 10px", background: "#0F172A", borderRadius: 8, border: "1px solid #1E293B" }}>
        <div style={{ fontSize: 10, color: "#64748B", flexShrink: 0 }}>Model Confidence</div>
        <div style={{ flex: 1, height: 6, background: "#334155", borderRadius: 4, overflow: "hidden" }}>
          <div style={{ height: "100%", width: `${confidence}%`, background: `linear-gradient(90deg,${confidence > 80 ? "#EF4444" : confidence > 60 ? "#F59E0B" : "#10B981"},${confidence > 80 ? "#DC2626" : confidence > 60 ? "#D97706" : "#059669"})`, borderRadius: 4 }} />
        </div>
        <div style={{ fontSize: 14, fontWeight: 800, color: confidence > 80 ? "#EF4444" : confidence > 60 ? "#F59E0B" : "#10B981", minWidth: 38, textAlign: "right" }}>{confidence}%</div>
      </div>
    </div>
  );
}

// ─── Feedback Form ────────────────────────────────────────────────────────────
function FeedbackForm({ txn, onClose }: { txn: Transaction; onClose: () => void }) {
  const [label, setLabel] = useState<"correct" | "wrong" | "">("");
  const [reason, setReason] = useState("");
  const [submitted, setSubmitted] = useState(false);

  if (submitted) {
    return (
      <div style={{ padding: "16px", background: "rgba(16,185,129,0.1)", border: "1px solid rgba(16,185,129,0.3)", borderRadius: 10, textAlign: "center" }}>
        <div style={{ fontSize: 20, marginBottom: 6 }}>✅</div>
        <div style={{ fontSize: 12, fontWeight: 700, color: "#10B981" }}>Feedback submitted!</div>
        <div style={{ fontSize: 10, color: "#64748B", marginTop: 4 }}>Your feedback will improve model accuracy in the next retrain cycle.</div>
        <button onClick={onClose} style={{ marginTop: 10, padding: "6px 16px", background: "#334155", color: "#94A3B8", border: "none", borderRadius: 6, fontSize: 11, cursor: "pointer" }}>Close</button>
      </div>
    );
  }

  return (
    <div style={{ background: "#1E293B", borderRadius: 10, padding: "14px", border: "1px solid #334155" }}>
      <div style={{ fontSize: 12, fontWeight: 700, color: "#F1F5F9", marginBottom: 10 }}>📋 Flag Transaction: {txn.id}</div>

      <div style={{ fontSize: 10, color: "#64748B", marginBottom: 6 }}>Was this detection correct?</div>
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        {[{ v: "correct" as const, label: "✓ Correct — Real Fraud", color: "#10B981" }, { v: "wrong" as const, label: "✗ Wrong — False Positive", color: "#EF4444" }].map(opt => (
          <button key={opt.v} onClick={() => setLabel(opt.v)} style={{
            flex: 1, padding: "8px", borderRadius: 8, border: `1.5px solid ${label === opt.v ? opt.color : "#334155"}`,
            background: label === opt.v ? `${opt.color}20` : "transparent", color: label === opt.v ? opt.color : "#64748B",
            fontSize: 10, fontWeight: 700, cursor: "pointer", transition: "all 0.15s"
          }}>{opt.label}</button>
        ))}
      </div>

      <div style={{ fontSize: 10, color: "#64748B", marginBottom: 4 }}>Reason (optional)</div>
      <textarea value={reason} onChange={e => setReason(e.target.value)} rows={3} placeholder="e.g. This is a regular grocery purchase by the customer..." style={{
        width: "100%", background: "#0F172A", border: "1px solid #334155", borderRadius: 8,
        color: "#F1F5F9", fontSize: 11, padding: "8px", resize: "none", boxSizing: "border-box",
        outline: "none", fontFamily: "inherit"
      }} />

      <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
        <button onClick={onClose} style={{ flex: 1, padding: "8px", background: "#334155", color: "#94A3B8", border: "none", borderRadius: 8, fontSize: 11, cursor: "pointer" }}>Cancel</button>
        <button onClick={() => label && setSubmitted(true)} style={{
          flex: 2, padding: "8px", background: label ? "#3B82F6" : "#334155",
          color: label ? "white" : "#64748B", border: "none", borderRadius: 8, fontSize: 11, fontWeight: 700,
          cursor: label ? "pointer" : "not-allowed", transition: "all 0.15s"
        }}>Submit Feedback</button>
      </div>
    </div>
  );
}

// ─── Main Panel ───────────────────────────────────────────────────────────────
export default function FraudInvestigationPanel({ customer, onClose }: FraudInvestigationPanelProps) {
  const [retrainingQueued, setRetrainingQueued] = useState(false);
  const [feedbackTxn, setFeedbackTxn] = useState<Transaction | null>(null);
  const [activeSection, setActiveSection] = useState<"details" | "graph" | "transactions">("details");

  if (!customer) return null;

  const fraudTxns = customer.transactions.filter(t => t.risk_level === "fraudulent" || t.risk_level === "suspicious");
  const lastTxn = fraudTxns[0];
  const riskScore = lastTxn?.risk_score ?? 0;

  const riskColor = customer.riskTier === "critical" ? "#EF4444"
    : customer.riskTier === "high" ? "#F59E0B"
    : customer.riskTier === "medium" ? "#3B82F6" : "#10B981";

  const email = `${customer.name.toLowerCase().replace(" ", ".")}@gmail.com`;
  const phone = `+91 9${Math.floor(100000000 + parseInt(customer.id.slice(-4)) * 1000).toString().slice(0, 9)}`;

  const tabs = [
    { id: "details" as const, label: "👤 Details" },
    { id: "graph" as const, label: "🕸 Graph" },
    { id: "transactions" as const, label: `⚠ ${fraudTxns.length} Alerts` },
  ];

  return (
    <div style={{
      width: 360, flexShrink: 0, height: "100%",
      background: "#0F172A", borderLeft: "1px solid #1E293B",
      display: "flex", flexDirection: "column", overflow: "hidden",
      animation: "slideInRight 0.2s ease",
    }}>
      {/* Header */}
      <div style={{ padding: "14px 16px 0", borderBottom: "1px solid #1E293B", flexShrink: 0 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
          <div>
            <div style={{ fontSize: 9, fontWeight: 700, color: "#475569", letterSpacing: "0.8px", marginBottom: 3 }}>FRAUD INVESTIGATION PANEL</div>
            <div style={{ fontSize: 16, fontWeight: 800, color: "#F1F5F9", letterSpacing: "-0.3px" }}>{customer.name}</div>
            <div style={{ fontSize: 11, color: "#64748B", marginTop: 2 }}>{customer.id}</div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{
              padding: "3px 10px", borderRadius: 20, fontSize: 9, fontWeight: 700,
              background: `${riskColor}20`, color: riskColor, border: `1px solid ${riskColor}40`
            }}>{customer.riskTier.toUpperCase()}</div>
            <button onClick={onClose} style={{ background: "none", border: "none", color: "#475569", fontSize: 20, cursor: "pointer", padding: "2px 4px", lineHeight: 1 }}>×</button>
          </div>
        </div>

        {/* Tabs */}
        <div style={{ display: "flex", gap: 0 }}>
          {tabs.map(tab => (
            <button key={tab.id} onClick={() => setActiveSection(tab.id)} style={{
              flex: 1, padding: "7px 4px", background: "none", border: "none",
              borderBottom: activeSection === tab.id ? `2px solid ${riskColor}` : "2px solid transparent",
              color: activeSection === tab.id ? riskColor : "#475569",
              fontSize: 10, fontWeight: 700, cursor: "pointer", transition: "all 0.15s"
            }}>{tab.label}</button>
          ))}
        </div>
      </div>

      {/* Content (scrollable) */}
      <div style={{ flex: 1, overflowY: "auto", padding: "14px 16px 16px", scrollbarWidth: "none" }}>

        {/* ── TAB: Customer Details ── */}
        {activeSection === "details" && (
          <div>
            {/* KPI grid */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 14 }}>
              {[
                { label: "Total Txns", value: customer.transactions.length, color: "#F1F5F9" },
                { label: "Total Volume", value: `₹${(customer.totalAmount / 1000).toFixed(1)}K`, color: "#F1F5F9" },
                { label: "Fraud Count", value: customer.fraudCount, color: "#EF4444" },
                { label: "Risk Score", value: riskScore.toFixed(1), color: riskScore > 80 ? "#EF4444" : riskScore > 50 ? "#F59E0B" : "#10B981" },
              ].map(k => (
                <div key={k.label} style={{ background: "#1E293B", borderRadius: 10, padding: "10px 12px", border: "1px solid #334155" }}>
                  <div style={{ fontSize: 9, fontWeight: 700, color: "#475569", letterSpacing: "0.4px", marginBottom: 3 }}>{k.label}</div>
                  <div style={{ fontSize: 20, fontWeight: 800, color: k.color, letterSpacing: "-0.5px", fontVariantNumeric: "tabular-nums" }}>{k.value}</div>
                </div>
              ))}
            </div>

            {/* Contact / profile info */}
            <div style={{ background: "#1E293B", borderRadius: 10, padding: "12px 14px", marginBottom: 14, border: "1px solid #334155" }}>
              <div style={{ fontSize: 9, fontWeight: 700, color: "#475569", letterSpacing: "0.5px", marginBottom: 10 }}>PROFILE</div>
              {[
                { icon: "📧", label: "Email", value: email },
                { icon: "📱", label: "Phone", value: phone },
                { icon: "🕐", label: "Last Active", value: (() => { const diff = Date.now() - new Date(customer.lastSeen).getTime(); const m = Math.floor(diff / 60000); return m < 60 ? `${m}m ago` : `${Math.floor(m / 60)}h ago`; })() },
                { icon: "📍", label: "Cities", value: Array.from(customer.cities).slice(0, 3).join(", ") },
              ].map(row => (
                <div key={row.label} style={{ display: "flex", alignItems: "flex-start", gap: 10, marginBottom: 8 }}>
                  <span style={{ fontSize: 13, flexShrink: 0 }}>{row.icon}</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 9, color: "#475569", fontWeight: 600 }}>{row.label}</div>
                    <div style={{ fontSize: 11, color: "#94A3B8", wordBreak: "break-all" }}>{row.value}</div>
                  </div>
                </div>
              ))}
            </div>

            {/* Action buttons */}
            {fraudTxns.length > 0 && (
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <button
                  onClick={() => setFeedbackTxn(feedbackTxn ? null : (lastTxn ?? null))}
                  style={{ padding: "10px", background: feedbackTxn ? "#334155" : "linear-gradient(135deg,#3B82F6,#6366F1)", color: "white", border: "none", borderRadius: 10, fontSize: 12, fontWeight: 700, cursor: "pointer", transition: "all 0.15s" }}
                >
                  {feedbackTxn ? "× Close Feedback Form" : "📋 Mark as False Positive / Feedback"}
                </button>

                {feedbackTxn && (
                  <FeedbackForm txn={feedbackTxn} onClose={() => setFeedbackTxn(null)} />
                )}

                <button
                  onClick={() => setRetrainingQueued(true)}
                  style={{ padding: "10px", background: retrainingQueued ? "rgba(16,185,129,0.15)" : "linear-gradient(135deg,#10B981,#059669)", color: retrainingQueued ? "#10B981" : "white", border: retrainingQueued ? "1px solid rgba(16,185,129,0.4)" : "none", borderRadius: 10, fontSize: 12, fontWeight: 700, cursor: retrainingQueued ? "default" : "pointer", transition: "all 0.15s" }}
                >
                  {retrainingQueued ? "✓ Case Added — Model Accuracy Will Improve After Next Retrain" : "🔁 Request Retraining with this Case"}
                </button>
              </div>
            )}
          </div>
        )}

        {/* ── TAB: Fraud Graph ── */}
        {activeSection === "graph" && (
          <div>
            <div style={{ fontSize: 10, color: "#64748B", marginBottom: 10, lineHeight: 1.5 }}>
              Interactive fraud network for <b style={{ color: "#94A3B8" }}>{customer.name}</b>. Central node = this customer. Connected nodes = merchants/accounts linked by fraud patterns. <span style={{ color: "#EF4444" }}>Red = fraud</span>, <span style={{ color: "#F59E0B" }}>orange = risk</span>.
            </div>

            {/* Legend */}
            <div style={{ display: "flex", gap: 12, marginBottom: 12 }}>
              {[["#EF4444", "Fraud"], ["#F59E0B", "Risk"], ["#64748B", "Normal"]].map(([c, l]) => (
                <div key={l} style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 10, color: "#94A3B8" }}>
                  <div style={{ width: 8, height: 8, borderRadius: "50%", background: c as string }} />
                  {l}
                </div>
              ))}
            </div>

            <div style={{ background: "#1E293B", borderRadius: 12, border: "1px solid #334155", overflow: "hidden" }}>
              {fraudTxns.length > 0 ? (
                <MiniGraphNode customer={customer} />
              ) : (
                <div style={{ height: 200, display: "flex", alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 8 }}>
                  <div style={{ fontSize: 24, opacity: 0.4 }}>🕸</div>
                  <div style={{ fontSize: 12, color: "#475569" }}>No fraud connections for this customer</div>
                </div>
              )}
            </div>

            <div style={{ marginTop: 10, fontSize: 10, color: "#475569", textAlign: "center" }}>
              Drag nodes to explore · Hover for details
            </div>

            {/* Connected stats */}
            {fraudTxns.length > 0 && (
              <div style={{ marginTop: 12, padding: "10px 12px", background: "#1E293B", borderRadius: 10, border: "1px solid #334155" }}>
                <div style={{ fontSize: 9, fontWeight: 700, color: "#475569", letterSpacing: "0.5px", marginBottom: 8 }}>NETWORK SUMMARY</div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8 }}>
                  {[
                    { label: "Connections", value: fraudTxns.length },
                    { label: "Fraud Links", value: customer.fraudCount },
                    { label: "Risk Links", value: customer.suspiciousCount },
                  ].map(s => (
                    <div key={s.label} style={{ textAlign: "center" }}>
                      <div style={{ fontSize: 18, fontWeight: 800, color: "#F1F5F9" }}>{s.value}</div>
                      <div style={{ fontSize: 9, color: "#475569" }}>{s.label}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── TAB: Transaction Alerts ── */}
        {activeSection === "transactions" && (
          <div>
            {fraudTxns.length === 0 ? (
              <div style={{ textAlign: "center", padding: "40px 0", color: "#475569", fontSize: 12 }}>
                <div style={{ fontSize: 28, marginBottom: 8 }}>✅</div>
                No flagged transactions for this customer
              </div>
            ) : (
              <>
                <div style={{ fontSize: 10, color: "#64748B", marginBottom: 12 }}>
                  Showing {fraudTxns.length} flagged transaction{fraudTxns.length !== 1 ? "s" : ""} with scoring explanation
                </div>
                {fraudTxns.slice(0, 6).map(txn => (
                  <div key={txn.id}>
                    <RuleTriggerCard txn={txn} />
                    <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
                      <button onClick={() => { setFeedbackTxn(txn); setActiveSection("details"); }} style={{
                        flex: 1, padding: "7px", background: "transparent", border: "1px solid #334155",
                        color: "#94A3B8", borderRadius: 8, fontSize: 10, fontWeight: 600, cursor: "pointer"
                      }}>📋 False Positive?</button>
                      <button onClick={() => { setRetrainingQueued(true); setActiveSection("details"); }} style={{
                        flex: 1, padding: "7px", background: "transparent", border: "1px solid #334155",
                        color: "#94A3B8", borderRadius: 8, fontSize: 10, fontWeight: 600, cursor: "pointer"
                      }}>🔁 Retrain with Case</button>
                    </div>
                  </div>
                ))}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
