import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Shield, CheckCircle2, Clock, Download, FileCheck, Lock, Key } from "lucide-react";
import { api, fmtINR } from "./lib/api";

export default function InsurancePortal() {
  const [claims, setClaims] = useState<any[]>([]);

  useEffect(() => {
    api.get<any[]>("/api/insurance/claims").then(setClaims).catch(()=>{});
    const t = setInterval(() => { api.get<any[]>("/api/insurance/claims").then(setClaims).catch(()=>{}); }, 5000);
    return () => clearInterval(t);
  }, []);

  const downloadCsv = () => { window.open("/api/settlements/export.csv","_blank"); };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 bg-slate-900/70 backdrop-blur sticky top-0 z-20">
        <div className="max-w-[1300px] mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link to="/" className="flex items-center gap-2 text-slate-400 hover:text-white"><ArrowLeft className="w-4 h-4"/> Command Center</Link>
            <span className="text-slate-600">/</span>
            <div className="flex items-center gap-2"><Shield className="w-5 h-5 text-indigo-400"/><h1 className="text-lg font-semibold">Insurance Oracle Portal</h1></div>
          </div>
          <button onClick={downloadCsv} className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm px-3 py-1.5 rounded-lg"><Download className="w-4 h-4"/> Export CSV</button>
        </div>
      </header>

      <main className="max-w-[1300px] mx-auto px-6 py-6 space-y-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="bg-gradient-to-br from-indigo-500/10 to-violet-600/5 border border-indigo-500/30 rounded-xl p-5 lg:col-span-2">
            <h2 className="font-semibold text-lg mb-2 flex items-center gap-2"><FileCheck className="w-5 h-5 text-indigo-400"/>Deterministic simulated settlement, with operator confirmation</h2>
            <p className="text-sm text-slate-300 leading-relaxed mb-3">
              The Smart Split-Settlement Oracle computes farmer payout, insurance shortfall, and abuse-linked logistics penalty deterministically from software-signed simulated telemetry.
              Native .NET records retain a SHA-256 evidence snapshot. This is not hardware-backed non-repudiation, independent sensor verification, or insurer approval.
            </p>
            <div className="flex flex-wrap gap-2 text-xs">
              <span className="px-2 py-1 rounded bg-indigo-500/15 text-indigo-300 border border-indigo-500/30 flex items-center gap-1"><Lock className="w-3 h-3"/>Software HMAC demo</span>
              <span className="px-2 py-1 rounded bg-indigo-500/15 text-indigo-300 border border-indigo-500/30 flex items-center gap-1"><Key className="w-3 h-3"/>Anti-replay seq numbers</span>
              <span className="px-2 py-1 rounded bg-indigo-500/15 text-indigo-300 border border-indigo-500/30">70% target; not guaranteed</span>
              <span className="px-2 py-1 rounded bg-indigo-500/15 text-indigo-300 border border-indigo-500/30">Abuse-linked penalty</span>
            </div>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <div className="text-xs text-slate-400 mb-1">Simulated farmer credits (not paid)</div>
            <div className="text-3xl font-bold text-emerald-400">{fmtINR(claims.reduce((a,c)=>a+c.farmer_total,0))}</div>
            <div className="mt-3 text-xs text-slate-400">Simulated insurance credits</div>
            <div className="text-xl font-semibold text-sky-400">{fmtINR(claims.reduce((a,c)=>a+c.payout,0))}</div>
            <div className="mt-3 text-xs text-slate-400">Simulated carrier penalties</div>
            <div className="text-xl font-semibold text-rose-400">{fmtINR(claims.reduce((a,c)=>a+c.penalty,0))}</div>
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
          <div className="px-5 py-3 border-b border-slate-800 flex items-center justify-between">
            <h3 className="font-semibold text-sm flex items-center gap-2"><FileCheck className="w-4 h-4 text-indigo-400"/>Simulation ledger records</h3>
            <span className="text-xs text-slate-400">{claims.length} records</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-800/50 text-slate-400 text-xs uppercase tracking-wide">
                <tr>
                  <th className="text-left p-3">Claim ID</th>
                  <th className="text-left p-3">Policy</th>
                  <th className="text-left p-3">Carrier</th>
                  <th className="text-left p-3">Commodity</th>
                  <th className="text-right p-3">Kg</th>
                  <th className="text-right p-3">Salvage</th>
                  <th className="text-right p-3">Payout</th>
                  <th className="text-right p-3">Penalty</th>
                  <th className="text-right p-3">Farmer total</th>
                  <th className="text-left p-3">Oracle hash</th>
                  <th className="text-center p-3">Status</th>
                </tr>
              </thead>
              <tbody>
                {claims.length === 0 && (
                  <tr><td colSpan={11} className="p-8 text-center text-slate-500">Awaiting first settlement… records appear only after operator-confirmed settlement.</td></tr>
                )}
                {claims.map(c => (
                  <tr key={c.id} className="border-t border-slate-800 hover:bg-slate-800/30">
                    <td className="p-3 font-mono text-xs">{c.id}</td>
                    <td className="p-3 font-mono text-xs text-slate-400">{c.policy}</td>
                    <td className="p-3">{c.carrier}</td>
                    <td className="p-3">{c.commodity}</td>
                    <td className="p-3 text-right">{c.kg.toFixed(0)}</td>
                    <td className="p-3 text-right text-slate-300">{fmtINR(c.salvage)}</td>
                    <td className="p-3 text-right text-sky-400">{fmtINR(c.payout)}</td>
                    <td className="p-3 text-right text-rose-400">{fmtINR(c.penalty)}</td>
                    <td className="p-3 text-right font-bold text-emerald-400">{fmtINR(c.farmer_total)}</td>
                    <td className="p-3 font-mono text-[10px] text-slate-500">{c.oracle_hash}</td>
                    <td className="p-3 text-center">
                      <span className={`inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full ${c.status==="Paid"?"bg-emerald-500/15 text-emerald-300 border border-emerald-500/30":"bg-amber-500/15 text-amber-300 border border-amber-500/30"}`}>
                        {c.status==="Paid" ? <CheckCircle2 className="w-3 h-3"/> : <Clock className="w-3 h-3"/>}
                        {c.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Info title="Anti-fraud" body="Software MAC checks reject selected replay/spoof packets. Oracle JSON is mutable demo data; there is no independent evidence signature or permanent audit store."/>
          <Info title="Parametric" body="Payout is formula-driven from measured spoilage, not from adjuster discretion: no negotiation, no 6-month claim cycle."/>
          <Info title="Farmer-first" body="70% recovery is a target, not a guarantee. Top-ups are limited to the calculated carrier penalty; no funded stabilisation account exists. Demo platform fee is zero."/>
        </div>
      </main>
    </div>
  );
}

function Info({title,body}:any){
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
      <h4 className="font-semibold text-sm mb-2 text-indigo-300">{title}</h4>
      <p className="text-xs text-slate-400 leading-relaxed">{body}</p>
    </div>
  );
}
