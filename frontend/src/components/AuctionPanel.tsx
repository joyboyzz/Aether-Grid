import {nativeBackend} from "../lib/auth";
import { useEffect, useState } from "react";
import { Gavel, Flame, MapPin, Clock, Users, Zap } from "lucide-react";
import type { Auction } from "../types";
import { fmtHours, fmtINR, api, parseUTC } from "../lib/api";

const COMMODITY_WHOLESALE: Record<string, number> = {
  "Alphonso Mango": 120, "Tomato": 25, "Dairy (Peda)": 180, "Seafood (Pomfret)": 420,
  "Leafy Greens (Palak)": 32, "Banana (Yelakki)": 45, "Poultry (Chicken)": 190,
};

export default function AuctionPanel({ auctions, onSelect, expanded=false }: {
  auctions: Auction[]; onSelect: (id: string) => void; expanded?: boolean;
}) {
  const [operatorToken, setOperatorToken] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const i = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(i); }, []);

  if (!expanded && auctions.length === 0) {
    return (
      <div className="glass rounded-2xl p-4">
        <h3 className="font-semibold flex items-center gap-2"><Gavel className="w-4 h-4 text-ag-blue"/>Flash Auctions</h3>
        <p className="text-xs text-slate-400 mt-2">No active auctions. When reefers fail, time-boxed demo auctions pop up here to nearby buyers.</p>
      </div>
    );
  }

  return (
    <div className={`glass rounded-2xl p-4 ${expanded?"":"h-[360px] overflow-auto scrollbar-thin"}`}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold flex items-center gap-2">
          {expanded ? <Gavel className="w-5 h-5 text-ag-orange"/> : <Flame className="w-4 h-4 text-ag-orange"/>}
          {expanded ? "Flash Auction Center" : "Active Distress Auctions"}
        </h3>
        <span className="chip bg-ag-orange/20 text-ag-orange border border-ag-orange/40 blink"><Zap className="w-3 h-3"/>LIVE</span>
      </div>
      <div className="mb-3 text-xs text-slate-400" onClick={e=>e.stopPropagation()}>
        {!nativeBackend && <label>Operator token (not saved): <input aria-label="Operator token" type="password" autoComplete="off"
          value={operatorToken} onChange={e=>setOperatorToken(e.target.value)} className="bg-ink-950 border rounded p-2 ml-2"/></label>}
        {nativeBackend && <p>Authenticated browser session · CSRF protected</p>}
        <p className="mt-2">Confirm only after manual review. Escrow, insurance and farmer credits are simulated; this does not confirm delivery.</p>
        {message && <p role="status" className="mt-2 text-ag-amber">{message}</p>}
      </div>
      <div className={`grid ${expanded?"md:grid-cols-2 xl:grid-cols-3":""} gap-3`}>
        {auctions.slice(0, expanded ? 50 : 10).map(a => {
          const rawDeadline = a.status === "AwaitingConfirmation" ? a.confirmation_deadline || a.closes_at : a.closes_at;
          const closesAt = parseUTC(rawDeadline);
          const secs = Math.max(0, Math.round((closesAt - now)/1000));
          const isOpen = a.status === "Open";
          const wholesale = COMMODITY_WHOLESALE[a.commodity] ?? 60;
          return (
            <div key={a.id} onClick={() => onSelect(a.batch_id)}
              className={`rounded-xl border p-3 cursor-pointer transition ${isOpen?"border-ag-orange/40 bg-ag-orange/5 hover:bg-ag-orange/10":a.status==="Settled"?"border-ag-green/30 bg-ag-green/5":"border-ink-700 bg-ink-800/40"}`}>
              <div className="flex justify-between items-start">
                <div>
                  <div className="font-bold text-white flex items-center gap-1.5">
                    <Flame className={`w-4 h-4 ${isOpen?"text-ag-orange":a.status==="Settled"?"text-ag-green":"text-slate-500"}`}/>
                    {a.commodity}
                  </div>
                  <div className="text-[11px] text-slate-400 font-mono">{a.id}</div>
                </div>
                {isOpen ? (
                  <div className="text-right">
                    <div className="text-[10px] text-slate-400 uppercase tracking-wider">Closes in</div>
                    <div className={`text-2xl font-bold font-mono tabular ${secs<60?"text-ag-red":secs<180?"text-ag-amber":"text-ag-green"}`}>
                      {`${Math.floor(secs/60)}:${(secs%60).toString().padStart(2,"0")}`}
                    </div>
                  </div>
                ) : (
                  <span className="chip bg-ag-green/15 text-ag-green border border-ag-green/30">{a.status}</span>
                )}
              </div>
              <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
                <div><div className="text-slate-500 text-[10px]">Temp</div><div className="font-bold text-ag-red tabular">{a.trigger_temp_c.toFixed(1)}°C</div></div>
                <div><div className="text-slate-500 text-[10px]">RVH</div><div className="font-bold tabular text-ag-amber">{fmtHours(a.trigger_rvh_hours)}</div></div>
                <div><div className="text-slate-500 text-[10px]">Wholesale</div><div className="font-bold tabular">{fmtINR(wholesale)}/kg</div></div>
              </div>
              <div className="mt-2 flex items-center gap-2 text-[11px] text-slate-400">
                <Users className="w-3 h-3 text-ag-blue"/>{a.nearby_buyers.length} bidders in range
                <span className="text-slate-600">·</span>
                <MapPin className="w-3 h-3"/>{Math.round(a.trigger_lat*100)/100},{Math.round(a.trigger_lng*100)/100}
              </div>
              {a.status === "AwaitingConfirmation" && <div className="mt-3" onClick={e=>e.stopPropagation()}>
                <p className="text-xs mb-2 text-ag-amber">Awaiting manual review · {secs}s · attempt {a.attempt || 0}</p>
                {(["confirm", "reject"] as const).map(action=><button key={action} disabled={busy || (!nativeBackend && !operatorToken) || secs<=0}
                  className="rounded border px-3 py-2 mr-2 text-xs disabled:opacity-40"
                  onClick={async()=>{setBusy(true); try {
                    const r=await api.confirm(a.id,operatorToken,action);
                    setMessage(`Result: ${r.status}. Simulated ledger only.`);
                  } catch(e) {setMessage(String(e));} finally {setBusy(false);} }}>
                  {action === "confirm" ? "Confirm simulated settlement" : "Reject & release"}</button>)}
              </div>}
              {a.winning_buyer_name && (
                <div className="mt-2 text-[11px] text-ag-green flex items-center gap-1">
                  Reserved / awarded to <b>{a.winning_buyer_name}</b> @ ₹{a.winning_price_inr_per_kg}/kg
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
