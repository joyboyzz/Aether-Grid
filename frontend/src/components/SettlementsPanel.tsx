import { CheckCircle2, IndianRupee, TrendingDown, User, Building2, Shield, FileText } from "lucide-react";
import type { Settlement } from "../types";
import { fmtINR } from "../lib/api";
export default function SettlementsPanel({ settlements }: { settlements: Settlement[] }) {
  const totals = settlements.reduce((acc, s) => ({
    count: acc.count + 1,
    kg: acc.kg + s.kg_cleared,
    salvage: acc.salvage + s.salvage_revenue_inr,
    insurance: acc.insurance + s.insurance_payout_inr,
    penalty: acc.penalty + s.logistics_penalty_inr,
    farmer: acc.farmer + s.farmer_total_payout_inr,
    savings: acc.savings + s.buyer_savings_pct,
  }), { count: 0, kg: 0, salvage: 0, insurance: 0, penalty: 0, farmer: 0, savings: 0 });
  return (
    <div className="glass rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-bold flex items-center gap-2"><CheckCircle2 className="w-6 h-6 text-ag-green"/>Simulated Split-Settlements</h2>
        <div className="flex gap-2">
          <span className="chip bg-ag-green/15 text-ag-green border border-ag-green/30">{totals.count} ledger awards</span>
          <span className="chip bg-ag-blue/15 text-ag-blue border border-ag-blue/30">{totals.kg.toFixed(0)} kg</span>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
        <div className="rounded-xl p-4 bg-ink-800/60 border border-ink-700">
          <div className="flex items-center gap-2 text-slate-400 text-xs"><User className="w-4 h-4 text-ag-green"/>Sim Farmer Credits</div>
          <div className="text-2xl font-bold text-ag-green tabular mt-1">{fmtINR(totals.farmer)}</div>
        </div>
        <div className="rounded-xl p-4 bg-ink-800/60 border border-ink-700">
          <div className="flex items-center gap-2 text-slate-400 text-xs"><Shield className="w-4 h-4 text-ag-blue"/>Sim Insurance</div>
          <div className="text-2xl font-bold text-ag-blue tabular mt-1">{fmtINR(totals.insurance)}</div>
        </div>
        <div className="rounded-xl p-4 bg-ink-800/60 border border-ink-700">
          <div className="flex items-center gap-2 text-slate-400 text-xs"><Building2 className="w-4 h-4 text-ag-red"/>Sim Penalties</div>
          <div className="text-2xl font-bold text-ag-red tabular mt-1">{fmtINR(totals.penalty)}</div>
        </div>
        <div className="rounded-xl p-4 bg-ink-800/60 border border-ink-700">
          <div className="flex items-center gap-2 text-slate-400 text-xs"><TrendingDown className="w-4 h-4 text-ag-amber"/>Avg Buyer Savings</div>
          <div className="text-2xl font-bold text-ag-amber tabular mt-1">{totals.count?(totals.savings/totals.count).toFixed(0):0}%</div>
        </div>
      </div>

      <div className="overflow-auto scrollbar-thin rounded-xl border border-ink-700">
        <table className="w-full text-sm">
          <thead className="bg-ink-800/80 text-slate-400 text-xs uppercase tracking-wider">
            <tr>
              <th className="text-left p-3">TXN</th>
              <th className="text-left p-3">Batch</th>
              <th className="text-right p-3">Kg</th>
              <th className="text-right p-3">Price</th>
              <th className="text-right p-3">→ Farmer</th>
              <th className="text-right p-3">Insurance</th>
              <th className="text-right p-3">Penalty</th>
              <th className="text-right p-3">Buyer Saved</th>
              <th className="text-right p-3">Time</th>
            </tr>
          </thead>
          <tbody>
            {settlements.map(s => (
              <tr key={s.id} className="border-t border-ink-700/60 hover:bg-ink-800/40">
                <td className="p-3 font-mono text-xs text-slate-400">AG-{s.id.slice(-6)}</td>
                <td className="p-3 font-mono text-xs">{s.batch_id}</td>
                <td className="p-3 text-right tabular">{s.kg_cleared.toFixed(0)}</td>
                <td className="p-3 text-right tabular">₹{s.price_inr_per_kg.toFixed(0)}</td>
                <td className="p-3 text-right tabular font-bold text-ag-green">{fmtINR(s.farmer_total_payout_inr)}</td>
                <td className="p-3 text-right tabular text-ag-blue">{fmtINR(s.insurance_payout_inr)}</td>
                <td className="p-3 text-right tabular text-ag-red">-{fmtINR(s.logistics_penalty_inr)}</td>
                <td className="p-3 text-right tabular text-ag-amber">{s.buyer_savings_pct.toFixed(0)}%</td>
                <td className="p-3 text-right text-xs text-slate-500">{new Date(s.settled_at).toLocaleTimeString()}</td>
              </tr>
            ))}
            {settlements.length === 0 && (
              <tr><td colSpan={9} className="p-10 text-center text-slate-500"><FileText className="w-8 h-8 mx-auto mb-2 opacity-40"/>No settlements yet. Watch the command center for flash auctions.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
