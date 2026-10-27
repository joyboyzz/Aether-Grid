import {boundBuyerId} from "./lib/auth";
import {parseUTC} from "./lib/api";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  ShoppingCart, MapPin, Clock, TrendingDown, Flame, Gavel, IndianRupee, Package, Zap, CheckCircle2, Shield, Truck as TruckIcon, Thermometer
} from "lucide-react";
import { api, fmtINR, fmtHours } from "./lib/api";
import { getSocket } from "./lib/socket";
import type { Auction, Buyer, Summary } from "./types";

const WHOLESALE: Record<string, number> = {
  "Alphonso Mango": 120, "Tomato": 25, "Dairy (Peda)": 180, "Seafood (Pomfret)": 420,
  "Leafy Greens (Palak)": 32, "Banana (Yelakki)": 45, "Poultry (Chicken)": 190,
};
const BUYER_KIND_LABEL: Record<string,string> = {
  wholesaler:"Wholesale Mandi", juice_processor:"Juice Processor", cold_storage:"Cold Storage",
  supermarket:"Supermarket", restaurant:"Restaurant / Hotel", distributor:"Distributor",
};

export default function BuyerPortal() {
  const [searchParams] = useSearchParams();
  const [buyers, setBuyers] = useState<Buyer[]>([]);
  const [auctions, setAuctions] = useState<Auction[]>([]);
  const [summary, setSummary] = useState<Summary|null>(null);
  const [selectedBuyerId, setSelectedBuyerId] = useState<string>(
    boundBuyerId || searchParams.get("buyer") || localStorage.getItem("ag_buyer_id") || ""
  );
  const [myWins, setMyWins] = useState<any[]>([]);
  const [now, setNow] = useState(Date.now());
  const [toast, setToast] = useState<string>("");

  useEffect(() => { const i = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(i); }, []);

  async function refresh() {
    const [bs, aus, sums, setts] = await Promise.all([api.buyers(), api.auctions(), api.summary(), api.settlements()]);
    setBuyers(bs); setAuctions(aus); setSummary(sums);
    if (selectedBuyerId) setMyWins(setts.filter((s:any) => s.buyer_id === selectedBuyerId));
  }
  useEffect(() => { refresh(); const i = setInterval(refresh, 3000); return () => clearInterval(i); }, [selectedBuyerId]);

  useEffect(() => {
    const s = getSocket();
    const onSettled = (ev: any) => {
      if (ev.buyer_id === selectedBuyerId) {
        setToast(`🎉 Won ${ev.kg_cleared.toFixed(0)}kg ${ev.commodity} at ₹${ev.price_per_kg}/kg — saved ${ev.buyer_savings_pct.toFixed(0)}%!`);
        setTimeout(() => setToast(""), 5000);
      }
      refresh();
    };
    s.on("auction_settled", onSettled);
    return () => { s.off("auction_settled", onSettled); };
  }, [selectedBuyerId]);

  const me = buyers.find(b => b.id === selectedBuyerId) || null;
  const relevant = useMemo(() => {
    if (!me) return auctions.filter(a => a.status === "Open");
    return auctions.filter(a => a.status === "Open" && a.nearby_buyers.some(nb => nb.id === me.id));
  }, [auctions, me]);

  async function placeBid(a: Auction, price: number, kg: number) {
    if (!me) return;
    try {
      await api.bid(a.id, { buyer_id: me.id, price_inr_per_kg: price, kg_requested: kg });
      setToast(`Reserved full lot: ₹${price}/kg × ${kg}kg. Awaiting operator confirmation; no real payment.`);
      await refresh();
    } catch (error) { setToast(`Bid rejected: ${String(error)}`); }

  }

  return (
    <div className="min-h-screen bg-ink-950 text-slate-200">
      {/* Header */}
      <header className="border-b border-ink-700/60 bg-gradient-to-r from-ag-orange/10 to-ag-amber/5">
        <div className="max-w-7xl mx-auto px-6 py-5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-ag-orange to-ag-amber grid place-items-center shadow-glow-orange">
              <ShoppingCart className="w-5 h-5 text-ink-950" strokeWidth={2.5}/>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-bold tracking-tight">AetherGrid — B2B Buyer Portal</h1>
                <span className="chip bg-ag-orange/20 text-ag-orange border border-ag-orange/40 blink"><Zap className="w-3 h-3"/>FLASH LIVE</span>
              </div>
              <p className="text-xs text-slate-400">Geo-fenced distressed cold-chain auctions within service radius · powered by Zero-Trust telemetry</p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="text-right">
              <div className="text-[10px] uppercase tracking-wider text-slate-500">Your identity</div>
              <select value={selectedBuyerId} onChange={e => {
                setSelectedBuyerId(e.target.value);
                localStorage.setItem("ag_buyer_id", e.target.value);
              }} className="bg-ink-800 border border-ink-700 rounded-lg px-3 py-2 text-sm font-semibold focus:outline-none focus:border-ag-orange">
                <option value="">Select your business…</option>
                {buyers.map(b => <option key={b.id} value={b.id}>{b.name} — {BUYER_KIND_LABEL[b.kind]||b.kind}</option>)}
              </select>
            </div>
          </div>
        </div>
      </header>

      {!me && (
        <div className="max-w-3xl mx-auto mt-16 p-8 glass rounded-2xl text-center">
          <ShoppingCart className="w-14 h-14 text-ag-orange mx-auto mb-4 opacity-70"/>
          <h2 className="text-2xl font-bold mb-2">Welcome, B2B Buyer</h2>
          <p className="text-slate-400 mb-6">Select your registered business from the top-right dropdown to see distressed cargo that matches your location and service radius. Auctions close in minutes — bid fast to lock in discounted produce.</p>
        </div>
      )}

      {me && (
        <main className="max-w-7xl mx-auto p-6">
          {/* Identity + Stats */}
          <div className="grid md:grid-cols-4 gap-4 mb-6">
            <div className="glass rounded-xl p-4 col-span-2">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-xl bg-ag-blue/15 grid place-items-center">
                  <MapPin className="w-6 h-6 text-ag-blue"/>
                </div>
                <div>
                  <div className="text-[11px] text-slate-500 uppercase tracking-wider">Logged in as</div>
                  <div className="text-lg font-bold">{me.name}</div>
                  <div className="text-xs text-slate-400">{BUYER_KIND_LABEL[me.kind]} · Capacity {me.capacity_kg.toLocaleString()}kg · Radius {me.service_radius_km.toFixed(0)}km</div>
                </div>
              </div>
            </div>
            <div className="glass rounded-xl p-4 text-center">
              <div className="text-[10px] text-slate-500 uppercase">Relevant Auctions</div>
              <div className="text-3xl font-bold text-ag-orange tabular">{relevant.length}</div>
              <div className="text-[10px] text-slate-500">within your service area</div>
            </div>
            <div className="glass rounded-xl p-4 text-center">
              <div className="text-[10px] text-slate-500 uppercase">My Wins</div>
              <div className="text-3xl font-bold text-ag-green tabular">{myWins.length}</div>
              <div className="text-[10px] text-slate-500">simulated spend ₹{myWins.reduce((s,w)=>s+(w.price_inr_per_kg*w.kg_cleared),0).toLocaleString('en-IN')}</div>
            </div>
          </div>

          <div className="grid lg:grid-cols-3 gap-4">
            {/* Auctions list */}
            <div className="lg:col-span-2 space-y-3">
              <h2 className="font-bold text-lg flex items-center gap-2"><Flame className="w-5 h-5 text-ag-orange"/>Live Distress Auctions {me && <span className="text-xs font-normal text-slate-500">— within {me.service_radius_km.toFixed(0)}km</span>}</h2>
              {relevant.length === 0 && (
                <div className="glass rounded-xl p-10 text-center text-slate-500">
                  <Clock className="w-10 h-10 mx-auto mb-3 opacity-40"/>
                  <div>No distressed cargo in your radius right now. The grid updates every second — this card flashes orange the moment a rescue opportunity appears.</div>
                </div>
              )}
              {relevant.map(a => <AuctionCard key={a.id} a={a} me={me} onBid={placeBid} now={now}/>)}
            </div>

            {/* My wins */}
            <div>
              <h2 className="font-bold text-lg flex items-center gap-2 mb-3"><CheckCircle2 className="w-5 h-5 text-ag-green"/>My Winning Bids</h2>
              <div className="glass rounded-xl p-4 space-y-3 max-h-[70vh] overflow-auto scrollbar-thin">
                {myWins.length === 0 && <div className="text-slate-500 text-sm text-center py-8">No wins yet. Win your first auction to see it here.</div>}
                {myWins.map(w => (
                  <div key={w.id} className="rounded-lg bg-ink-800/60 border border-ag-green/20 p-3">
                    <div className="flex justify-between items-start">
                      <div className="font-bold">{/* commodity from auction via join */}
                        <span className="text-sm">{w.id}</span>
                      </div>
                      <span className="chip bg-ag-green/15 text-ag-green border border-ag-green/30">WON</span>
                    </div>
                    <div className="grid grid-cols-3 gap-2 mt-2 text-xs">
                      <div><div className="text-slate-500">Qty</div><div className="font-bold tabular">{w.kg_cleared.toFixed(0)}kg</div></div>
                      <div><div className="text-slate-500">Price</div><div className="font-bold tabular">₹{w.price_inr_per_kg.toFixed(0)}</div></div>
                      <div><div className="text-slate-500">Saved</div><div className="font-bold tabular text-ag-green">{w.buyer_savings_pct.toFixed(0)}%</div></div>
                    </div>
                    <div className="text-[10px] text-slate-500 mt-2 flex items-center gap-1"><Shield className="w-3 h-3"/> Demo ledger only; delivery not confirmed</div>
                  </div>
                ))}
              </div>

              <div className="glass rounded-xl p-4 mt-4">
                <h3 className="font-bold text-sm flex items-center gap-2 mb-2"><Shield className="w-4 h-4 text-ag-green"/>How it works</h3>
                <ol className="text-xs text-slate-400 space-y-2 list-decimal pl-4">
                  <li>When a reefer fails and AetherGrid's Bio-Timer predicts spoilage before the original destination, a <b>time-boxed demo auction</b> opens to every registered buyer within your service radius.</li>
                  <li>First eligible full-lot bid reserves simulated funds; operator confirmation is required.</li>
                  <li>After manual confirmation, a <b>simulated oracle</b> computes ledger amounts: farmer gets salvage + insurance, logistics pays a prorated penalty, you receive goods at a discount vs. wholesale.</li>
                </ol>
              </div>
            </div>
          </div>
        </main>
      )}

      {toast && (
        <div className="fixed bottom-6 right-6 glass border-ag-green/30 border-2 rounded-xl p-4 shadow-glow z-50 max-w-md flex items-center gap-3">
          <CheckCircle2 className="w-6 h-6 text-ag-green flex-shrink-0"/>
          <div>{toast}</div>
        </div>
      )}
    </div>
  );
}

function AuctionCard({ a, me, onBid, now }: { a: Auction; me: Buyer; onBid: (a:Auction,price:number,kg:number)=>void; now:number }) {
  const closesAt = parseUTC(a.closes_at);
  const secs = Math.max(0, Math.round((closesAt - now)/1000));
  const wholesale = WHOLESALE[a.commodity] ?? 60;
  const recommended = Math.round(wholesale * 0.62);
  const [price, setPrice] = useState(recommended);
  const kg = a.lot_kg ?? 0;
  const myDist = a.nearby_buyers.find(n => n.id === me.id)?.distance_km ?? 0;
  const etaMin = Math.round((myDist / 30 + 0.25) * 60);
  const savingsPct = Math.max(0, Math.round((wholesale - price) / wholesale * 100));
  const urgent = secs < 90;

  return (
    <div className={`rounded-2xl border p-5 transition ${urgent?"border-ag-red/40 bg-ag-red/5 blink":"border-ag-orange/40 bg-ag-orange/5"}`}>
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="flex items-center gap-2">
            <Package className="w-5 h-5 text-ag-orange"/>
            <h3 className="text-lg font-bold">{a.commodity}</h3>
            <span className="chip bg-ag-orange/20 text-ag-orange border border-ag-orange/30"><Gavel className="w-3 h-3"/>FLASH</span>
          </div>
          <div className="text-xs text-slate-400 mt-1 flex items-center gap-3 flex-wrap">
            <span className="flex items-center gap-1"><MapPin className="w-3 h-3"/>{myDist.toFixed(1)}km away</span>
            <span className="flex items-center gap-1"><TruckIcon className="w-3 h-3"/>~{etaMin}min ETA to pickup</span>
            <span className="flex items-center gap-1"><Thermometer/>{a.trigger_temp_c.toFixed(1)}°C reefer failure</span>
          </div>
        </div>
        <div className="text-right">
          <div className="text-[10px] text-slate-400 uppercase tracking-wider">Closes in</div>
          <div className={`text-3xl font-bold font-mono tabular ${urgent?"text-ag-red":secs<180?"text-ag-amber":"text-ag-green"}`}>
            {`${Math.floor(secs/60)}:${(secs%60).toString().padStart(2,"0")}`}
          </div>
          <div className="text-[10px] text-slate-500">{a.nearby_buyers.length} bidders in range</div>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-2 mb-4">
        <Stat k="RVH" v={fmtHours(a.trigger_rvh_hours)} color="text-ag-red" label="remaining life"/>
        <Stat k="Wholesale" v={`₹${wholesale}`} color="text-slate-400" label="/kg regular"/>
        <Stat k="R-Bidders" v={a.nearby_buyers.length} color="text-ag-blue" label="in radius"/>
        <Stat k="Cargo temp" v={`${a.trigger_temp_c.toFixed(0)}°C`} color="text-ag-red" label="rising"/>
      </div>

      <div className="grid md:grid-cols-[1fr_1fr_auto] gap-3 items-end">
        <div>
          <label className="text-[11px] text-slate-400 uppercase tracking-wider">Your bid (₹/kg)</label>
          <div className="flex items-center gap-2 mt-1">
            <input type="number" value={price} onChange={e=>setPrice(Number(e.target.value))}
              className="w-full bg-ink-900 border border-ink-700 rounded-lg px-3 py-2 text-lg font-bold tabular focus:outline-none focus:border-ag-orange"/>
            <div className={`text-xs whitespace-nowrap ${savingsPct>=25?"text-ag-green":savingsPct>=10?"text-ag-amber":"text-ag-red"}`}>
              {savingsPct}% off
            </div>
          </div>
        </div>
        <div>
          <label className="text-[11px] text-slate-400 uppercase tracking-wider">Full lot only (kg)</label>
          <input type="number" value={kg} readOnly aria-label="Full lot kg"
            className="w-full bg-ink-900 border border-ink-700 rounded-lg px-3 py-2 text-lg font-bold tabular focus:outline-none focus:border-ag-orange mt-1"/>
        </div>
        <button disabled={secs<=0 || kg<=0 || kg>me.capacity_kg} onClick={()=>onBid(a,price,kg)}
          className={`px-6 py-3 font-bold rounded-lg transition ${urgent?"bg-ag-red hover:bg-red-500":"bg-ag-orange hover:bg-orange-500"} text-ink-950 whitespace-nowrap flex items-center gap-2`}>
          <Zap className="w-4 h-4"/>RESERVE FULL LOT
        </button>
      </div>
      <div className="text-[11px] text-slate-500 mt-2 flex items-center justify-between">
        <span>Your total: <b className="text-slate-200 tabular">{fmtINR(price*kg)}</b></span>
        <span className="flex items-center gap-1"><IndianRupee className="w-3 h-3 text-ag-green"/> Simulated escrow · Operator review required</span>
      </div>
    </div>
  );
}
function Stat({k,v,color,label}:{k:string;v:any;color:string;label:string}){
  return <div className="rounded-lg bg-ink-900/60 border border-ink-700 p-2">
    <div className="text-[10px] text-slate-500 uppercase tracking-wider">{k}</div>
    <div className={`text-lg font-bold tabular ${color}`}>{v}</div>
    <div className="text-[9px] text-slate-600">{label}</div>
  </div>;
}
