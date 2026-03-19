import React from "react";

export default function Settings() {
  const sid = import.meta.env.VITE_TWILIO_ACCOUNT_SID || "your_sid_here";
  const token = "••••••••••••••••••••••••••••";
  const fromNum = import.meta.env.VITE_TWILIO_FROM_NUMBER || "+1XXXXXXXXXX";
  const toNum = import.meta.env.VITE_ALERT_PHONE_NUMBER || "+91XXXXXXXXXX";

  return (
    <div className="flex flex-col h-full overflow-y-auto p-6 gap-6" style={{ scrollbarWidth: "none" }}>
      <div className="bg-white border border-slate-200 rounded-xl p-6">
        <h2 className="text-[15px] font-bold text-slate-900 mb-1">Twilio Integration</h2>
        <p className="text-[12px] text-slate-400 mb-6">Manage SMS alert settings for critical fraud detection events (Score &ge; 90).</p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <ConfigField label="Account SID" value={sid} />
          <ConfigField label="Auth Token" value={token} isSecret />
          <ConfigField label="From Number" value={fromNum} />
          <ConfigField label="Alert Target Number" value={toNum} />
        </div>
      </div>
    </div>
  );
}

function ConfigField({ label, value, isSecret }: { label: string; value: string; isSecret?: boolean }) {
  return (
    <div className="flex flex-col gap-[6px]">
      <label className="text-[11px] font-bold text-slate-500 uppercase tracking-[0.5px]">{label}</label>
      <input 
        type={isSecret ? "password" : "text"} 
        value={value} 
        disabled 
        className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-[13px] text-slate-700 font-mono focus:outline-none"
      />
    </div>
  );
}
