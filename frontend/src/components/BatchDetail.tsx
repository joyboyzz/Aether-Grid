import { X, Thermometer, Droplets, Wind, Clock, MapPin, IndianRupee, Package, Shield, Navigation, Gauge, Activity, Radio } from "lucide-react";
import type { Batch, Event } from "../types";
import { fmtHours, fmtINR } from "../lib/api";
export default function BatchDetail({ batch, events, onClose }: { batch: Batch; events: Event[]; onClose: () => void }) {
  const life = batch.life_consumed_pct ?? 0;
  const healthColor = batch.health === "fresh"?"text-ag-green":batch.health==="aging"?"text-ag-amber":"text-ag-red";
  return (
    <div className="col-span-12 xl:col-span-4 glass rounded-2xl p-5 relative">
      <button onClick={onClose} className="absolute top-3 right-3 text-slate-400 hover:text-white"><X className="w-5 h-5"/></button>
      <div className="flex items-start gap-3 mb-3">
        <div className={`w-10 h-10 rounded-xl grid place-items-center ${batch.status==="DistressedLiquidation"?"bg-ag-orange/20":batch.status==="Spoiled"?"bg-ag-red/20":batch.status==="Delivered"?"bg-ag-green/20":"bg-ag-blue/20"}`}>
          <Package className={`w-5 h-5 ${batch.status==="DistressedLiquidation"?"text-ag-orange":batch.status==="Spoiled"?"text-ag-red":batch.status==="Delivered"?"text-ag-green":"text-ag-blue"}`}/>
        </div>
        <div>
          <div className="text-[10px] text-slate-500 font-mono">{batch.id}</div>
          <h3 className="text-lg font-bold">{batch.commodity}</h3>
          <div className="text-xs text-slate-400 flex items-center gap-2"><Navigation className="w-3 h-3"/>{batch.truck_id ?? "—"} · {batch.reroute_count} reroutes</div>
        </div>
      </div>
      <div className="chip mb-3" style={{
        background: batch.status==="DistressedLiquidation"?"rgba(255,122,24,.15)":batch.status==="Spoiled"?"rgba(255,76,92,.15)":batch.status==="Cleared"?"rgba(167,139,250,.15)":batch.status==="Delivered"?"rgba(42,74,58,.5)":"rgba(0,224,164,.12)",
        color: batch.status==="DistressedLiquidation"?"#ff7a18":batch.status==="Spoiled"?"#ff4c5c":batch.status==="Cleared"?"#a78bfa":batch.status==="Delivered"?"#7ef5c8":"#7ef5c8",
        border: `1px solid ${batch.status==="DistressedLiquidation"?"rgba(255,122,24,.3)":batch.status==="Spoiled"?"rgba(255,76,92,.3)":batch.status==="Cleared"?"rgba(167,139,250,.3)":"rgba(0,224,164,.3)"}`,
      }}>{batch.status}</div>

      {/* Bio-timer ring */}
      <div className="flex items-center gap-4 my-4">
        <div className="relative w-24 h-24">
          <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
            <circle cx="50" cy="50" r="42" fill="none" stroke="#15203a" strokeWidth="8"/>
            <circle cx="50" cy="50" r="42" fill="none" stroke={life<40?"#00e0a4":life<70?"#ffc845":"#ff4c5c"} strokeWidth="8" strokeLinecap="round" strokeDasharray={`${2*Math.PI*42*(1-life/100)} ${2*Math.PI*42}`}/>
          </svg>
          <div className="absolute inset-0 grid place-items-center text-center">
            <div>
              <div className={`text-xl font-bold tabular ${healthColor}`}>{life.toFixed(0)}%</div>
              <div className="text-[9px] text-slate-500 uppercase tracking-wider">life used</div>
            </div>
          </div>
        </div>
        <div className="flex-1 grid grid-cols-2 gap-2 text-sm">
          <div className="flex items-center gap-1.5 text-xs"><Clock className="w-3 h-3 text-ag-green"/>RVH: <b className="tabular">{batch.rvh_hours!=null?fmtHours(batch.rvh_hours):"—"}</b></div>
          <div className="flex items-center gap-1.5 text-xs"><Clock className="w-3 h-3 text-ag-blue"/>ETT to dest: <b className="tabular">{batch.ett_hours!=null?fmtHours(batch.ett_hours):"—"}</b></div>
          <div className="flex items-center gap-1.5 text-xs"><Thermometer className="w-3 h-3 text-ag-red"/>Temp: <b className="tabular">{batch.temp_c!=null?batch.temp_c.toFixed(1)+"°C":"—"}</b></div>
          <div className="flex items-center gap-1.5 text-xs"><Gauge className="w-3 h-3 text-ag-amber"/>Health: <b className={healthColor}>{batch.health}</b></div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <div className="p-2 rounded-lg bg-ink-800/60 border border-ink-700">
          <div className="text-[10px] text-slate-500 uppercase flex items-center gap-1"><MapPin className="w-3 h-3"/>Origin</div>
          <div className="text-sm font-medium">{batch.origin_name}</div>
        </div>
        <div className="p-2 rounded-lg bg-ink-800/60 border border-ink-700">
          <div className="text-[10px] text-slate-500 uppercase flex items-center gap-1"><MapPin className="w-3 h-3"/>Destination</div>
          <div className="text-sm font-medium">{batch.destination_name}</div>
        </div>
        <div className="p-2 rounded-lg bg-ink-800/60 border border-ink-700">
          <div className="text-[10px] text-slate-500 uppercase flex items-center gap-1"><Package className="w-3 h-3"/>Weight</div>
          <div className="text-sm font-medium tabular">{batch.weight_kg.toFixed(0)} kg</div>
        </div>
        <div className="p-2 rounded-lg bg-ink-800/60 border border-ink-700">
          <div className="text-[10px] text-slate-500 uppercase flex items-center gap-1"><IndianRupee className="w-3 h-3"/>Contract</div>
          <div className="text-sm font-medium tabular">{fmtINR(batch.contract_value_inr)}</div>
        </div>
      </div>

      <div className="mt-4">
        <div className="flex items-center gap-2 mb-2"><Activity className="w-3 h-3 text-ag-blue"/><span className="text-[11px] uppercase tracking-wider text-slate-400">Recent Events</span></div>
        <div className="space-y-1 max-h-48 overflow-auto scrollbar-thin">
          {events.length === 0 && <div className="text-xs text-slate-500">No events yet.</div>}
          {events.slice(0,10).map(e => (
            <div key={e.id} className="text-[11px] flex items-start gap-2 p-1.5 rounded bg-ink-800/40">
              <Radio className={`w-3 h-3 mt-0.5 ${e.severity==="critical"?"text-ag-red":e.severity==="warn"?"text-ag-amber":"text-ag-green"}`}/>
              <div className="flex-1"><div className="text-slate-300 leading-tight">{e.description}</div>
                <div className="text-slate-600 text-[9px] font-mono">{new Date(e.ts).toLocaleTimeString()}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
