import { Thermometer, Clock, Navigation, IndianRupee, Leaf, AlertCircle, Droplets, Wind } from "lucide-react";
import type { Batch } from "../types";
import { fmtHours, fmtINR } from "../lib/api";
export default function FleetList({ batches, selected, onSelect }:
  { batches: Batch[]; selected: string | null; onSelect: (id: string) => void }) {
  const sorted = [...batches].sort((a,b) => (b.life_consumed_pct ?? 0) - (a.life_consumed_pct ?? 0));
  return (
    <div className="divide-y divide-ink-700/60">
      {sorted.map(b => {
        const color =
          b.status === "Spoiled" ? "bg-ag-red" :
          b.status === "DistressedLiquidation" ? "bg-ag-orange" :
          b.status === "Cleared" ? "bg-ag-purple" :
          b.status === "Delivered" ? "bg-ink-600" :
          b.health === "fresh" ? "bg-ag-green" :
          b.health === "aging" ? "bg-ag-amber" : "bg-ag-red";
        const active = selected === b.id;
        return (
          <div key={b.id} onClick={() => onSelect(b.id)}
            className={`grid grid-cols-12 gap-3 items-center p-3 cursor-pointer transition ${active?"bg-ink-700/60":"hover:bg-ink-800/50"}`}>
            <div className="col-span-1 flex items-center justify-center"><span className={`w-2.5 h-2.5 rounded-full ${color}`}/></div>
            <div className="col-span-4">
              <div className="font-semibold text-sm flex items-center gap-2">{b.commodity}
                <span className="text-[10px] text-slate-500 font-mono">{b.id}</span>
              </div>
              <div className="text-[11px] text-slate-400 flex items-center gap-2">
                <Navigation className="w-3 h-3"/>{b.truck_id ?? "—"}
                <span className="text-slate-600">·</span>{b.origin_name.split(" ")[0]} → {b.destination_name.split(" ")[0]}
              </div>
            </div>
            <div className="col-span-2 flex items-center gap-1 text-xs tabular">
              <Thermometer className={`w-3 h-3 ${(b.temp_c??0)>15?"text-ag-orange":"text-ag-blue"}`}/>
              <span>{b.temp_c!=null?b.temp_c.toFixed(1)+"°C":"—"}</span>
            </div>
            <div className="col-span-2 text-xs tabular">
              <div className="flex items-center gap-1"><Clock className="w-3 h-3 text-ag-green"/>RVH {b.rvh_hours!=null?fmtHours(b.rvh_hours):"—"}</div>
              <div className="flex items-center gap-1 text-slate-500"><Clock className="w-3 h-3"/>ETT {b.ett_hours!=null?fmtHours(b.ett_hours):"—"}</div>
            </div>
            <div className="col-span-3">
              <div className="flex justify-between text-[10px] text-slate-400"><span>Life used</span><span className="tabular">{(b.life_consumed_pct??0).toFixed(0)}%</span></div>
              <div className="h-2 rounded-full bg-ink-700 overflow-hidden">
                <div className={`h-full ${b.health==="fresh"?"bg-ag-green":b.health==="aging"?"bg-ag-amber":"bg-ag-red"}`} style={{width:`${Math.min(100,b.life_consumed_pct??0)}%`}}/>
              </div>
              <div className="flex justify-between text-[10px] mt-1 text-slate-500">
                <span className="flex items-center gap-0.5"><IndianRupee className="w-3 h-3"/>{fmtINR(b.contract_value_inr)}</span>
                <span className={`chip ${b.status==="DistressedLiquidation"?"bg-ag-orange/15 text-ag-orange":b.status==="Spoiled"?"bg-ag-red/15 text-ag-red":b.status==="Cleared"?"bg-ag-purple/15 text-ag-purple":b.status==="Delivered"?"bg-ink-700 text-slate-300":"bg-ag-green/15 text-ag-green"}`} style={{padding:"1px 8px"}}>{b.status}</span>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
