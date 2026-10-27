import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  LayoutDashboard, Truck as TruckIcon, Flame, Gavel, Activity, Shield,
  Radio, Satellite, FileText, Map as MapIcon, AlertTriangle,
  TrendingUp, IndianRupee, LeafyGreen, Fish, Milk, Apple, Citrus, Drumstick,
} from "lucide-react";
import { api, fmtINR, fmtHours } from "./lib/api";
import { getSocket } from "./lib/socket";
import type { Batch, Auction, Settlement, Summary, Event, RouteGraph, Telemetry } from "./types";
import MapView from "./components/MapView";
import KPIBar from "./components/KPIBar";
import FleetList from "./components/FleetList";
import AuctionPanel from "./components/AuctionPanel";
import EventFeed from "./components/EventFeed";
import BatchDetail from "./components/BatchDetail";
import SettlementsPanel from "./components/SettlementsPanel";
import StatusBar from "./components/StatusBar";

const COMMODITY_ICON: Record<string, any> = {
  "Alphonso Mango": Apple,
  "Tomato": Citrus,
  "Dairy (Peda)": Milk,
  "Seafood (Pomfret)": Fish,
  "Leafy Greens (Palak)": LeafyGreen,
  "Banana (Yelakki)": Apple,
  "Poultry (Chicken)": Drumstick,
};

type Tab = "dashboard" | "fleet" | "auctions" | "settlements" | "events";

export default function App() {
  const [batches, setBatches] = useState<Batch[]>([]);
  const [auctions, setAuctions] = useState<Auction[]>([]);
  const [settlements, setSettlements] = useState<Settlement[]>([]);
  const [events, setEvents] = useState<Event[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [route, setRoute] = useState<RouteGraph | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("dashboard");
  const [connected, setConnected] = useState(false);
  const telemetryRef = useRef<Map<string, Telemetry>>(new Map());

  // Initial load
  useEffect(() => {
    (async () => {
      const [b, a, s, e, su, r] = await Promise.all([
        api.batches(), api.auctions(), api.settlements(), api.events(), api.summary(), api.route()
      ]);
      setBatches(b); setAuctions(a); setSettlements(s); setEvents(e); setSummary(su); setRoute(r);
    })();
    const tick = setInterval(async () => {
      try {
        const [b, a, s, e, su] = await Promise.all([api.batches(), api.auctions(), api.settlements(), api.events(undefined), api.summary()]);
        setBatches(b); setAuctions(a); setSettlements(s); setEvents(e); setSummary(su);
      } catch {}
    }, 4000);
    return () => clearInterval(tick);
  }, []);

  // Socket.IO live events
  useEffect(() => {
    const s = getSocket();
    s.on("connect", () => setConnected(true));
    s.on("disconnect", () => setConnected(false));
    s.on("telemetry", (t: Telemetry) => { telemetryRef.current.set(t.batch_id, t); });
    s.on("distressed", (ev: any) => {
      setEvents((xs) => [{ id: Date.now(), batch_id: ev.batch_id, ts: new Date().toISOString(), kind: "auction_opened", severity: "critical", description: `Flash auction opened: ${ev.commodity} (RVH ${ev.rvh_hours.toFixed(1)}h vs ETT ${ev.ett_hours.toFixed(1)}h, ${ev.nearby_buyers.length} bidders)` }, ...xs].slice(0, 200));
      api.auctions().then(setAuctions);
      api.summary().then(setSummary);
    });
    s.on("auction_settled", (ev: any) => {
      setEvents((xs) => [{ id: Date.now() + 1, batch_id: ev.batch_id, ts: new Date().toISOString(), kind: "settled", severity: "ok", description: `Demo ledger awarded ${ev.kg_cleared.toFixed(0)}kg ${ev.commodity} → ${ev.buyer_name} (farmer ${fmtINR(ev.farmer_payout_rs)}, buyer saved ${ev.buyer_savings_pct.toFixed(0)}%)` }, ...xs].slice(0, 200));
      api.auctions().then(setAuctions);
      api.settlements().then(setSettlements);
      api.summary().then(setSummary);
      api.batches().then(setBatches);
    });
    s.on("spoiled", (ev: any) => {
      setEvents((xs) => [{ id: Date.now() + 2, batch_id: ev.batch_id, ts: new Date().toISOString(), kind: "spoiled", severity: "critical", description: `${ev.commodity} spoiled in transit near (${ev.lat.toFixed(2)},${ev.lng.toFixed(2)}) — no rescue reached in time` }, ...xs].slice(0, 200));
      api.batches().then(setBatches);
      api.summary().then(setSummary);
    });
    s.on("delivered", (ev: any) => {
      setEvents((xs) => [{ id: Date.now() + 3, batch_id: ev.batch_id, ts: new Date().toISOString(), kind: "delivered", severity: "ok", description: `${ev.commodity} delivered to ${ev.destination} with ${ev.life_consumed_pct.toFixed(0)}% life consumed` }, ...xs].slice(0, 200));
      api.batches().then(setBatches);
      api.summary().then(setSummary);
    });
    return () => { s.off("telemetry"); s.off("distressed"); s.off("auction_settled"); s.off("spoiled"); s.off("delivered"); s.off("connect"); s.off("disconnect"); };
  }, []);

  // Merge live telemetry into batch state for smooth UI updates
  const liveBatches = useMemo(() => batches.map(b => {
    const t = telemetryRef.current.get(b.id);
    if (!t) return b;
    return { ...b, lat: t.lat, lng: t.lng, temp_c: t.temp_c, rvh_hours: t.rvh_hours, life_consumed_pct: t.life_consumed_pct, health: t.health, status: ["Cleared", "Delivered", "Spoiled", "RescueDeliveryReported"].includes(b.status) ? b.status : t.status, ett_hours: Math.max(0, b.ett_hours ?? t.spoil_eta_hours) };
  }), [batches]);

  const selectedBatch = liveBatches.find(b => b.id === selected) || null;
  const openAuctions = auctions.filter(a => ["Open", "AwaitingConfirmation"].includes(a.status));

  const tabs: { id: Tab; label: string; icon: any; badge?: number }[] = [
    { id: "dashboard", label: "Command Center", icon: LayoutDashboard },
    { id: "fleet", label: "Fleet", icon: TruckIcon, badge: summary?.active_batches },
    { id: "auctions", label: "Flash Auctions", icon: Gavel, badge: summary?.active_auctions },
    { id: "settlements", label: "Settlements", icon: IndianRupee },
    { id: "events", label: "Event Log", icon: Activity },
  ];

  return (
    <div className="min-h-screen flex flex-col bg-ink-950 text-slate-200">
      {/* Top bar */}
      <header className="border-b border-ink-700/60 bg-ink-900/80 backdrop-blur-lg sticky top-0 z-30">
        <div className="flex items-center justify-between px-6 py-3">
          <div className="flex items-center gap-3">
            <div className="relative w-10 h-10 rounded-xl bg-gradient-to-br from-ag-green to-ag-blue grid place-items-center shadow-glow">
              <Satellite className="w-5 h-5 text-ink-950" strokeWidth={2.5}/>
              <span className="absolute inset-0 rounded-xl ring-2 ring-ag-green/40 pulse-ring" style={{r:0}}/>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-lg font-bold tracking-tight">AetherGrid</h1>
                <span className="chip bg-ag-green/15 text-ag-green border border-ag-green/30">LIVE</span>
                <span className="chip bg-ink-700/60 text-slate-300 border border-ink-600">v1.0 · NH-44 Corridor</span>
              </div>
              <p className="text-xs text-slate-400">Zero-Trust Micro-Cold-Chain Mesh · Dynamic Liquidation Engine · Author: Praveen Sudireddy</p>
            </div>
          </div>
          <StatusBar connected={connected} summary={summary} />
        </div>
        <nav className="flex gap-1 px-6 pb-1">
          {tabs.map(t => {
            const Icon = t.icon;
            const active = tab === t.id;
            return (
              <button key={t.id} onClick={() => setTab(t.id)}
                className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium rounded-t-lg border-b-2 transition ${
                  active ? "border-ag-green text-white bg-ink-800/60" : "border-transparent text-slate-400 hover:text-slate-200 hover:bg-ink-800/30"
                }`}>
                <Icon className="w-4 h-4"/>{t.label}
                {t.badge != null && t.badge > 0 && (
                  <span className="ml-1 inline-flex items-center justify-center text-[10px] font-bold min-w-[18px] h-[18px] px-1.5 rounded-full bg-ag-orange/20 text-ag-orange border border-ag-orange/40">{t.badge}</span>
                )}
              </button>
            );
          })}
        </nav>
      </header>

      <KPIBar summary={summary} />

      {tab === "dashboard" && (
        <main className="flex-1 grid grid-cols-12 gap-4 p-4">
          <section className="col-span-12 xl:col-span-8 glass rounded-2xl p-3 overflow-hidden flex flex-col min-h-[640px]">
            <div className="flex items-center justify-between px-2 py-1 mb-2">
              <div className="flex items-center gap-2">
                <MapIcon className="w-4 h-4 text-ag-blue"/>
                <h2 className="font-semibold">Thermal Geospatial Command — Delhi → Bengaluru (NH-44)</h2>
              </div>
              <div className="flex gap-2 text-xs">
                <span className="chip bg-ag-green/15 text-ag-green border border-ag-green/20"><span className="status-dot bg-ag-green"/>Fresh</span>
                <span className="chip bg-ag-amber/15 text-ag-amber border border-ag-amber/20"><span className="status-dot bg-ag-amber"/>Aging</span>
                <span className="chip bg-ag-red/15 text-ag-red border border-ag-red/20"><span className="status-dot bg-ag-red"/>Critical</span>
                <span className="chip bg-ag-orange/15 text-ag-orange border border-ag-orange/30 blink"><Flame className="w-3 h-3"/>Distress Auction</span>
              </div>
            </div>
            <div className="flex-1 rounded-xl overflow-hidden border border-ink-700/60 relative bg-grid">
              {route && <MapView route={route} batches={liveBatches} auctions={openAuctions} selected={selected} onSelect={setSelected}/>}
            </div>
          </section>
          <section className="col-span-12 xl:col-span-4 flex flex-col gap-4">
            <div className="glass rounded-2xl p-4">
              <div className="flex items-center justify-between mb-2">
                <h3 className="font-semibold flex items-center gap-2"><Shield className="w-4 h-4 text-ag-green"/>Zero-Trust Telemetry</h3>
                <span className="chip bg-ag-green/15 text-ag-green border border-ag-green/30"><Radio className="w-3 h-3"/>Software HMAC</span>
              </div>
              <p className="text-xs text-slate-400 leading-relaxed">Selected telemetry fields carry a software HMAC with sequence and timestamp checks. This does not verify physical truth; mTLS and hardware signing are not implemented.</p>
              <div className="mt-3 grid grid-cols-3 gap-2 text-center">
                <div className="rounded-lg bg-ink-800/60 border border-ink-700 p-2">
                  <div className="text-[10px] text-slate-400 uppercase tracking-wider">Attested</div>
                  <div className="text-ag-green font-bold text-lg tabular">{summary?.active_batches ?? "—"}</div>
                </div>
                <div className="rounded-lg bg-ink-800/60 border border-ink-700 p-2">
                  <div className="text-[10px] text-slate-400 uppercase tracking-wider">Dead-Zone Mesh</div>
                  <div className="text-ag-blue font-bold text-lg tabular">4</div>
                </div>
                <div className="rounded-lg bg-ink-800/60 border border-ink-700 p-2">
                  <div className="text-[10px] text-slate-400 uppercase tracking-wider">Spoof Rejected</div>
                  <div className="text-ag-red font-bold text-lg tabular">{summary?.spoof_rejections ?? 0}</div>
                </div>
              </div>
            </div>
            <AuctionPanel auctions={openAuctions} onSelect={setSelected}/>
            <EventFeed events={events.slice(0,12)} compact/>
          </section>
          {selectedBatch && <BatchDetail batch={selectedBatch} events={events.filter(e => e.batch_id === selectedBatch.id)} onClose={() => setSelected(null)}/>}
        </main>
      )}

      {tab === "fleet" && (
        <main className="flex-1 grid grid-cols-12 gap-4 p-4">
          <section className="col-span-12 xl:col-span-8 glass rounded-2xl p-4 min-h-[640px] flex flex-col">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-semibold flex items-center gap-2"><TruckIcon className="w-4 h-4 text-ag-blue"/>Live Fleet</h2>
              <span className="text-xs text-slate-400">{liveBatches.length} batches tracked</span>
            </div>
            <div className="flex-1 overflow-auto scrollbar-thin"><FleetList batches={liveBatches} selected={selected} onSelect={setSelected}/></div>
          </section>
          <section className="col-span-12 xl:col-span-4">{selectedBatch ? <BatchDetail batch={selectedBatch} events={events.filter(e => e.batch_id === selectedBatch.id)} onClose={() => setSelected(null)}/> : <EventFeed events={events}/>}</section>
        </main>
      )}

      {tab === "auctions" && (
        <main className="flex-1 p-4 grid grid-cols-12 gap-4">
          <section className="col-span-12 glass rounded-2xl p-4"><AuctionPanel auctions={auctions} onSelect={setSelected} expanded/></section>
        </main>
      )}

      {tab === "settlements" && (
        <main className="flex-1 p-4"><SettlementsPanel settlements={settlements}/></main>
      )}

      {tab === "events" && (
        <main className="flex-1 p-4"><EventFeed events={events} expanded/></main>
      )}

      <footer className="border-t border-ink-700/60 px-6 py-3 text-xs text-slate-500">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-4">
            <a href="/analytics" className="text-cyan-400 hover:text-cyan-300 font-semibold">📊 Analytics</a>
            <a href="/buyer" target="_blank" className="text-ag-orange hover:text-ag-amber font-semibold">🛒 B2B Buyer Portal →</a>
            <a href="/carrier" className="text-orange-400 hover:text-orange-300 font-semibold">🚛 Carrier SLA</a>
            <a href="/insurance" className="text-indigo-400 hover:text-indigo-300 font-semibold">🛡 Insurance Oracle</a>
            <span className="text-slate-600">|</span>
            <span>AetherGrid · Cold-chain intervention engine · © 2026 Praveen Sudireddy</span>
          </div>
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1"><Shield className="w-3 h-3 text-ag-green"/> Software HMAC demo</span>
            <span className="flex items-center gap-1"><Radio className="w-3 h-3 text-ag-blue"/> Mesh Sync</span>
            <span className="flex items-center gap-1"><TrendingUp className="w-3 h-3 text-ag-orange"/> Insurance Oracle</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
