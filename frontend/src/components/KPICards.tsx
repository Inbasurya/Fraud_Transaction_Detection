import React from "react";
import type { DashboardStats } from "../types";

interface Props {
  stats: DashboardStats | null;
}

const cards = [
  { key: "total_transactions", label: "Total Transactions", fmt: (v: number) => v.toLocaleString() },
  { key: "transactions_24h", label: "Last 24h", fmt: (v: number) => v.toLocaleString() },
  { key: "fraud_detected", label: "Fraud Detected", fmt: (v: number) => v.toLocaleString(), color: "text-red-400" },
  { key: "fraud_rate", label: "Fraud Rate", fmt: (v: number) => `${v.toFixed(2)}%` },
  { key: "avg_risk_score", label: "Avg Risk Score", fmt: (v: number) => v.toFixed(4) },
  { key: "total_amount_processed", label: "Amount Processed", fmt: (v: number) => `₹${(v / 100000).toFixed(1)}L` },
  { key: "active_alerts", label: "Active Alerts", fmt: (v: number) => v.toLocaleString(), color: "text-yellow-400" },
  { key: "avg_processing_latency_ms", label: "Avg Latency", fmt: (v: number) => `${v.toFixed(1)}ms` },
] as const;

export default function KPICards({ stats }: Props) {
  if (!stats) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {cards.map((c) => (
          <div key={c.key} className="bg-gray-800 rounded-lg p-4 animate-pulse h-24" />
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {cards.map((c) => (
        <div key={c.key} className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <p className="text-gray-400 text-xs uppercase tracking-wider">{c.label}</p>
          <p className={`text-2xl font-bold mt-1 ${"color" in c ? c.color : "text-white"}`}>
            {c.fmt((stats as Record<string, number>)[c.key] ?? 0)}
          </p>
        </div>
      ))}
    </div>
  );
}
