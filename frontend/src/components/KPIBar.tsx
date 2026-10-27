import { Truck, AlertTriangle, CheckCircle2, XCircle, IndianRupee, Gavel, TrendingUp, Timer } from "lucide-react";
import type { Summary } from "../types";
import { fmtINR } from "../lib/api";
export default function KPIBar({ summary }: { summary: Summary | null }) {
  if (!summary) return null;
  const cards = [
    { icon: Truck, label: "Active Trucks", value: summary.active_trucks, color: "text-ag-blue", sub: "on corridor" },
    { icon: AlertTriangle, label: "Distressed", value: summary.distressed, color: "text-ag-orange", sub: "auction live" },
    { icon: Gavel, label: "Open Auctions", value: summary.active_auctions, color: "text-ag-amber", sub: "flash bidding" },
    { icon: CheckCircle2, label: "Ledger Awards", value: summary.rescued_total, color: "text-ag-green", sub: "simulated; not delivered" },
    { icon: XCircle, label: "Model-spoiled", value: summary.spoiled_total, color: "text-ag-red", sub: "no rescue in time" },
    { icon: IndianRupee, label: "Sim Farmer Credit", value: fmtINR(summary.total_farmer_value_salvaged_inr), color: "text-ag-green", sub: `penalties ${fmtINR(summary.total_logistics_penalties_inr)}` },
    { icon: TrendingUp, label: "Avg Buyer Savings", value: `${summary.avg_buyer_savings_pct.toFixed(0)}%`, color: "text-ag-purple", sub: "below wholesale" },
    { icon: Timer, label: "Rescue Time", value: "N/A", color: "text-ag-blue", sub: "not measured" },
  ];
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-8 gap-3 px-4 pt-4">
      {cards.map((c, i) => {
        const Ic = c.icon;
        return (
          <div key={i} className="glass rounded-xl p-3 relative overflow-hidden">
            <div className={`absolute -top-4 -right-4 w-16 h-16 rounded-full blur-2xl opacity-25 ${c.color.replace("text-","bg-")}`}/>
            <div className="flex items-center gap-2 text-slate-400 text-[11px] uppercase tracking-wider"><Ic className={`w-3.5 h-3.5 ${c.color}`}/>{c.label}</div>
            <div className={`text-2xl font-bold mt-1 tabular ${c.color}`}>{c.value}</div>
            <div className="text-[11px] text-slate-500 mt-0.5">{c.sub}</div>
          </div>
        );
      })}
    </div>
  );
}
