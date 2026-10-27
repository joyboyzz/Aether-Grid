import { Wifi, WifiOff, IndianRupee, Shield, AlertTriangle, Truck, CheckCircle2 } from "lucide-react";
import type { Summary } from "../types";
import { fmtINR } from "../lib/api";
export default function StatusBar({ connected, summary }: { connected: boolean; summary: Summary | null }) {
  const stats = [
    { icon: Truck, label: "Active", value: summary?.active_batches ?? "—", color: "text-ag-blue" },
    { icon: AlertTriangle, label: "Distressed", value: summary?.distressed ?? 0, color: "text-ag-orange" },
    { icon: CheckCircle2, label: "Ledger awards", value: summary?.rescued_total ?? 0, color: "text-ag-green" },
    { icon: IndianRupee, label: "Sim credit", value: summary ? fmtINR(summary.total_farmer_value_salvaged_inr) : "—", color: "text-ag-green" },
    { icon: Shield, label: "Spoof Blocks", value: summary?.spoof_rejections ?? 0, color: "text-ag-red" },
  ];
  return (
    <div className="flex items-center gap-5">
      {stats.map((s, i) => {
        const Ic = s.icon;
        return (
          <div key={i} className="flex items-center gap-2 text-sm">
            <Ic className={`w-4 h-4 ${s.color}`}/>
            <span className="text-slate-400 text-xs hidden md:inline">{s.label}</span>
            <span className={`font-bold tabular ${s.color}`}>{s.value}</span>
          </div>
        );
      })}
      <div className="flex items-center gap-2 pl-4 border-l border-ink-700/60">
        {connected ? <><Wifi className="w-4 h-4 text-ag-green"/><span className="text-xs text-ag-green font-medium">Connected</span></>
                 : <><WifiOff className="w-4 h-4 text-ag-red"/><span className="text-xs text-ag-red">Reconnecting…</span></>}
      </div>
    </div>
  );
}
