import React from "react";
import type { Transaction } from "../types";

const riskColors: Record<string, string> = {
  critical: "bg-red-500",
  high: "bg-orange-500",
  medium: "bg-yellow-500",
  low: "bg-green-500",
};

interface Props {
  transactions: Transaction[];
  onSelect?: (txn: Transaction) => void;
}

export default function TransactionFeed({ transactions, onSelect }: Props) {
  if (transactions.length === 0) {
    return (
      <div className="bg-gray-800 rounded-lg p-6 text-center text-gray-500">
        Waiting for transactions…
      </div>
    );
  }

  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-700 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-300">Live Transaction Feed</h3>
        <span className="text-xs text-gray-500">{transactions.length} transactions</span>
      </div>
      <div className="max-h-[500px] overflow-y-auto">
        {transactions.map((txn) => (
          <div
            key={txn.id}
            className="px-4 py-2 border-b border-gray-700/50 hover:bg-gray-700/30 cursor-pointer flex items-center gap-3 text-sm"
            onClick={() => onSelect?.(txn)}
          >
            <span
              className={`w-2 h-2 rounded-full flex-shrink-0 ${riskColors[txn.risk_level] || "bg-gray-500"}`}
            />
            <span className="text-gray-400 w-20 flex-shrink-0">{txn.customer_id}</span>
            <span className="text-white font-mono w-28 flex-shrink-0 text-right">
              ₹{txn.amount.toLocaleString(undefined, { maximumFractionDigits: 2 })}
            </span>
            <span className="text-gray-500 flex-1 truncate">{txn.merchant_category}</span>
            <span className="text-gray-400 w-16 text-right">
              {(txn.risk_score * 100).toFixed(0)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
