import React from "react";
import type { Alert } from "../types";

const severityColors: Record<string, string> = {
  critical: "text-red-400 bg-red-900/30",
  high: "text-orange-400 bg-orange-900/30",
  medium: "text-yellow-400 bg-yellow-900/30",
  low: "text-green-400 bg-green-900/30",
};

const statusColors: Record<string, string> = {
  new: "text-blue-400",
  investigating: "text-yellow-400",
  resolved: "text-green-400",
  false_positive: "text-gray-400",
};

interface Props {
  alerts: Alert[];
  onUpdateStatus?: (id: string, status: string) => void;
}

export default function AlertPanel({ alerts, onUpdateStatus }: Props) {
  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700">
      <div className="px-4 py-3 border-b border-gray-700">
        <h3 className="text-sm font-semibold text-gray-300">Alerts</h3>
      </div>
      {alerts.length === 0 ? (
        <div className="p-6 text-center text-gray-500 text-sm">No alerts</div>
      ) : (
        <div className="max-h-[400px] overflow-y-auto divide-y divide-gray-700/50">
          {alerts.map((alert) => (
            <div key={alert.id} className="px-4 py-3 hover:bg-gray-700/20">
              <div className="flex items-center justify-between mb-1">
                <span
                  className={`text-xs px-2 py-0.5 rounded ${severityColors[alert.severity] || ""}`}
                >
                  {alert.severity.toUpperCase()}
                </span>
                <span className={`text-xs ${statusColors[alert.status] || "text-gray-400"}`}>
                  {alert.status}
                </span>
              </div>
              <p className="text-sm text-gray-300">
                Customer: {alert.customer_id} — Score: {(alert.risk_score * 100).toFixed(0)}%
              </p>
              <p className="text-xs text-gray-500 mt-1">
                {new Date(alert.created_at).toLocaleString()}
              </p>
              {onUpdateStatus && alert.status === "new" && (
                <div className="mt-2 flex gap-2">
                  <button
                    className="text-xs px-2 py-1 bg-yellow-600/30 text-yellow-400 rounded hover:bg-yellow-600/50"
                    onClick={() => onUpdateStatus(alert.id, "investigating")}
                  >
                    Investigate
                  </button>
                  <button
                    className="text-xs px-2 py-1 bg-green-600/30 text-green-400 rounded hover:bg-green-600/50"
                    onClick={() => onUpdateStatus(alert.id, "resolved")}
                  >
                    Resolve
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
