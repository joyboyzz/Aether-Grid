import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Truck, AlertTriangle, CheckCircle2, XCircle, IndianRupee, Award } from "lucide-react";
import { api, fmtINR } from "./lib/api";

export default function CarrierPortal() {
  const [carriers, setCarriers] = useState<any[]>([]);

  useEffect(() => {
    api.get<any[]>("/api/carrier/sla").then(setCarriers).catch(()=>{});
    const t = setInterval(() => { api.get<any[]>("/api/carrier/sla").then(setCarriers).catch(()=>{}); }, 5000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 bg-slate-900/70 backdrop-blur sticky top-0 z-20">
        <div className="max-w-[1200px] mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link to="/" className="flex items-center gap-2 text-slate-400 hover:text-white"><ArrowLeft className="w-4 h-4"/> Command Center</Link>
            <span className="text-slate-600">/</span>
            <div className="flex items-center gap-2"><Truck className="w-5 h-5 text-orange-400"/><h1 className="text-lg font-semibold">Carrier SLA Dashboard</h1></div>
          </div>
          <div className="text-xs text-slate-400">AetherGrid · Logistics Providers</div>
        </div>
      </header>

      <main className="max-w-[1200px] mx-auto px-6 py-6 space-y-6">
        <div className="bg-gradient-to-br from-orange-500/10 to-amber-600/5 border border-orange-500/30 rounded-xl p-5">
          <h2 className="font-semibold text-lg mb-2 flex items-center gap-2"><Award className="w-5 h-5 text-orange-400"/>Behaviour-linked penalties, not flat fees</h2>
          <p className="text-sm text-slate-300 leading-relaxed">
            Penalties are prorated to documented abuse: life-consumed percentage, hours outside safe temperature band, number of door-open events, and whether a spoofed telemetry packet was rejected.
            This software cannot establish physical sensor tampering. Displayed penalties and SLA inputs are simulated or operator-asserted; no money is collected.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {carriers.map(c => {
            const grade = c.sla_score >= 90 ? {label:"A · Excellent", color:"emerald"}
                       : c.sla_score >= 75 ? {label:"B · Good", color:"sky"}
                       : c.sla_score >= 60 ? {label:"C · Watch", color:"amber"}
                       : {label:"D · Critical", color:"rose"};
            return (
              <div key={c.carrier_id} className="bg-slate-900 border border-slate-800 rounded-xl p-5">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <div className="text-xs text-slate-400">Carrier</div>
                    <div className="font-semibold text-base">{c.carrier}</div>
                  </div>
                  <span className={`text-xs px-2 py-1 rounded-full bg-${grade.color}-500/20 text-${grade.color}-300 border border-${grade.color}-500/30`}>{grade.label}</span>
                </div>

                <div className="text-3xl font-bold mb-1">{c.sla_score}<span className="text-sm text-slate-500 font-normal">/100</span></div>
                <div className="h-2 bg-slate-800 rounded-full overflow-hidden mb-4">
                  <div className={`h-full bg-${grade.color}-500`} style={{width:`${Math.max(0,Math.min(100,c.sla_score))}%`}}/>
                </div>

                <div className="grid grid-cols-2 gap-3 text-sm">
                  <Stat label="Trucks" value={c.trucks} icon={<Truck className="w-3 h-3"/>}/>
                  <Stat label="Active" value={c.batches_active} icon={<CheckCircle2 className="w-3 h-3 text-sky-400"/>}/>
                  <Stat label="Distressed" value={c.distressed} icon={<AlertTriangle className="w-3 h-3 text-amber-400"/>} color="text-amber-300"/>
                  <Stat label="Rescued" value={c.rescued} icon={<CheckCircle2 className="w-3 h-3 text-emerald-400"/>} color="text-emerald-300"/>
                  <Stat label="Spoiled" value={c.spoiled} icon={<XCircle className="w-3 h-3 text-rose-400"/>} color="text-rose-300"/>
                  <Stat label="Penalties" value={fmtINR(c.penalties_inr)} icon={<IndianRupee className="w-3 h-3 text-rose-400"/>} color="text-rose-300"/>
                </div>

                <div className="mt-4 pt-3 border-t border-slate-800 flex items-center justify-between text-xs">
                  <span className="text-slate-400">Farmer value recovered via rescue</span>
                  <span className="text-emerald-400 font-semibold">{fmtINR(c.farmer_recovered_inr)}</span>
                </div>
              </div>
            );
          })}
        </div>
      </main>
    </div>
  );
}

function Stat({label,value,icon,color="text-slate-200"}:any){
  return (
    <div className="bg-slate-950 rounded-lg p-2 border border-slate-800">
      <div className="flex items-center gap-1 text-slate-500 text-[10px] uppercase tracking-wide">{icon}{label}</div>
      <div className={`font-bold text-base ${color}`}>{value}</div>
    </div>
  );
}
