import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, BarChart, Bar, PieChart, Pie, Cell, AreaChart, Area,
} from "recharts";
import { ArrowLeft, Activity, TrendingUp, TrendingDown, LeafyGreen, Apple, Fish, Milk, Drumstick, Citrus } from "lucide-react";
import { api, fmtINR, fmtHours } from "./lib/api";
import KPIBar from "./components/KPIBar";

const COMMODITY_COLORS: Record<string, string> = {
  "Alphonso Mango": "#f59e0b",
  "Tomato": "#ef4444",
  "Dairy (Peda)": "#60a5fa",
  "Seafood (Pomfret)": "#06b6d4",
  "Leafy Greens (Palak)": "#10b981",
  "Banana (Yelakki)": "#eab308",
  "Poultry (Chicken)": "#f97316",
};
const PIE_COLORS = ["#00a279","#f59e0b","#ef4444","#64748b","#0ea5e9"];

export default function Analytics() {
  const [settlements, setSettlements] = useState<any[]>([]);
  const [batches, setBatches] = useState<any[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [selectedBatch, setSelectedBatch] = useState<string | null>(null);
  const [telemetry, setTelemetry] = useState<any[]>([]);

  useEffect(() => {
    api.settlements().then(setSettlements);
    api.batches().then(setBatches);
    api.summary().then(setSummary);
    const t = setInterval(() => { api.summary().then(setSummary); api.batches().then(setBatches); api.settlements().then(setSettlements); }, 5000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (!selectedBatch) { setTelemetry([]); return; }
    api.get<any[]>(`/api/batches/${selectedBatch}/telemetry`).then(setTelemetry).catch(() => setTelemetry([]));
    const t = setInterval(() => { api.get<any[]>(`/api/batches/${selectedBatch}/telemetry`).then(setTelemetry).catch(() => {}); }, 4000);
    return () => clearInterval(t);
  }, [selectedBatch]);

  const statusDist = useMemo(() => {
    const m: Record<string, number> = {};
    for (const b of batches) { m[b.status] = (m[b.status]||0) + 1; }
    return Object.entries(m).map(([name, value]) => ({ name, value }));
  }, [batches]);

  const commodityDist = useMemo(() => {
    const m: Record<string, number> = {};
    for (const b of batches) { m[b.commodity_key] = (m[b.commodity_key]||0) + 1; }
    return Object.entries(m).map(([commodity, count]) => ({ commodity, count }));
  }, [batches]);

  const settlementTimeline = useMemo(() => {
    return [...settlements].sort((a,b) => (a.settled_at > b.settled_at ? 1 : -1)).map((s,i) => ({
      idx: i+1,
      salvage: Math.round(s.salvage_revenue_inr),
      insurance: Math.round(s.insurance_payout_inr),
      penalty: Math.round(s.logistics_penalty_inr),
      farmer: Math.round(s.farmer_total_payout_inr),
      buyer_savings: s.buyer_savings_pct,
      farmer_recovery: s.farmer_recovery_pct,
    }));
  }, [settlements]);

  const telemetrySeries = useMemo(() => {
    return telemetry.map((s, i) => ({
      t: i,
      temp: s.temp,
      humidity: s.h,
      door: s.door ? 1 : 0,
    }));
  }, [telemetry]);

  const distressedBatches = useMemo(() => batches.filter(b => b.status === "DistressedLiquidation").slice(0,8), [batches]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 bg-slate-900/70 backdrop-blur sticky top-0 z-20">
        <div className="max-w-[1400px] mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link to="/" className="flex items-center gap-2 text-slate-400 hover:text-white"><ArrowLeft className="w-4 h-4"/> Command Center</Link>
            <span className="text-slate-600">/</span>
            <div className="flex items-center gap-2"><Activity className="w-5 h-5 text-emerald-400"/><h1 className="text-lg font-semibold">Telemetry &amp; Analytics</h1></div>
          </div>
          <div className="text-xs text-slate-400">AetherGrid · Praveen Sudireddy</div>
        </div>
      </header>

      <main className="max-w-[1400px] mx-auto px-6 py-6 space-y-6">
        {summary && <KPIBar summary={summary}/>}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <div className="flex items-center gap-2 mb-3"><TrendingUp className="w-4 h-4 text-emerald-400"/><h3 className="font-semibold text-sm">Batch Status Distribution</h3></div>
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie data={statusDist} dataKey="value" nameKey="name" outerRadius={85} label={({name,value})=>`${name}: ${value}`}>
                  {statusDist.map((_,i)=>(<Cell key={i} fill={PIE_COLORS[i%PIE_COLORS.length]}/>))}
                </Pie>
                <Tooltip contentStyle={{background:"#0f172a",border:"1px solid #334155"}}/>
              </PieChart>
            </ResponsiveContainer>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <div className="flex items-center gap-2 mb-3"><Apple className="w-4 h-4 text-amber-400"/><h3 className="font-semibold text-sm">Cargo by Commodity</h3></div>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={commodityDist}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b"/>
                <XAxis dataKey="commodity" tick={{fill:"#94a3b8",fontSize:10}} angle={-15} height={50} textAnchor="end"/>
                <YAxis tick={{fill:"#94a3b8",fontSize:11}}/>
                <Tooltip contentStyle={{background:"#0f172a",border:"1px solid #334155"}}/>
                <Bar dataKey="count" radius={[6,6,0,0]}>
                  {commodityDist.map((d,i)=>(<Cell key={i} fill={COMMODITY_COLORS[d.commodity] || "#0ea5e9"}/>))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2"><TrendingUp className="w-4 h-4 text-emerald-400"/><h3 className="font-semibold text-sm">Settlement Economics (progressive settlements)</h3></div>
          </div>
          {settlementTimeline.length === 0 ? (
            <div className="text-slate-500 text-sm py-10 text-center">Awaiting first rescue settlement…</div>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <AreaChart data={settlementTimeline}>
                <defs>
                  <linearGradient id="gfarmer" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#10b981" stopOpacity={0.7}/><stop offset="100%" stopColor="#10b981" stopOpacity={0}/></linearGradient>
                  <linearGradient id="gpen" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#ef4444" stopOpacity={0.5}/><stop offset="100%" stopColor="#ef4444" stopOpacity={0}/></linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b"/>
                <XAxis dataKey="idx" tick={{fill:"#94a3b8",fontSize:11}} label={{value:"Settlement #",position:"insideBottom",offset:-5,fill:"#64748b",fontSize:10}}/>
                <YAxis tick={{fill:"#94a3b8",fontSize:11}}/>
                <Tooltip contentStyle={{background:"#0f172a",border:"1px solid #334155"}}/>
                <Legend wrapperStyle={{fontSize:11}}/>
                <Area type="monotone" dataKey="farmer" stroke="#10b981" fill="url(#gfarmer)" name="Farmer payout ₹"/>
                <Area type="monotone" dataKey="penalty" stroke="#ef4444" fill="url(#gpen)" name="Logistics penalty ₹"/>
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <div className="flex items-center gap-3 mb-3">
            <Activity className="w-4 h-4 text-cyan-400"/><h3 className="font-semibold text-sm">Per-Batch Telemetry Trace</h3>
            <select value={selectedBatch||""} onChange={e=>setSelectedBatch(e.target.value||null)} className="bg-slate-800 border border-slate-700 rounded px-3 py-1 text-xs">
              <option value="">— pick a distressed batch to inspect —</option>
              {distressedBatches.map(b => (<option key={b.id} value={b.id}>{b.id} · {b.commodity_key} · RVH {b.rvh_hours.toFixed?.(1)}h</option>))}
              {batches.slice(0,20).filter(b=>!distressedBatches.includes(b)).map(b => (<option key={b.id} value={b.id}>{b.id} · {b.commodity_key}</option>))}
            </select>
          </div>
          {telemetrySeries.length === 0 ? (
            <div className="text-slate-500 text-sm py-10 text-center">Select a batch above to see its temperature/humidity timeline.</div>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={telemetrySeries}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b"/>
                <XAxis dataKey="t" tick={{fill:"#94a3b8",fontSize:11}} label={{value:"Sample",position:"insideBottom",offset:-5,fill:"#64748b",fontSize:10}}/>
                <YAxis yAxisId="t" tick={{fill:"#f87171",fontSize:11}}/>
                <YAxis yAxisId="h" orientation="right" tick={{fill:"#60a5fa",fontSize:11}}/>
                <Tooltip contentStyle={{background:"#0f172a",border:"1px solid #334155"}}/>
                <Legend wrapperStyle={{fontSize:11}}/>
                <Line yAxisId="t" type="monotone" dataKey="temp" stroke="#f87171" strokeWidth={2} dot={false} name="Cargo temp °C"/>
                <Line yAxisId="h" type="monotone" dataKey="humidity" stroke="#60a5fa" strokeWidth={2} dot={false} name="Humidity %"/>
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <MetricCard icon={<TrendingUp className="w-4 h-4 text-emerald-400"/>} label="Total farmer value salvaged" value={fmtINR(summary?.total_farmer_value_salvaged_inr||0)} />
          <MetricCard icon={<TrendingDown className="w-4 h-4 text-rose-400"/>} label="Logistics penalties levied" value={fmtINR(summary?.total_logistics_penalties_inr||0)} />
          <MetricCard icon={<LeafyGreen className="w-4 h-4 text-teal-400"/>} label="Avg buyer savings" value={`${(summary?.avg_buyer_savings_pct||0).toFixed?.(1)||0}%`} />
        </div>
      </main>
    </div>
  );
}

function MetricCard({icon,label,value}:any){
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
      <div className="flex items-center gap-2 text-slate-400 text-xs mb-2">{icon}{label}</div>
      <div className="text-2xl font-bold">{value}</div>
    </div>
  );
}
