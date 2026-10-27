import { AlertTriangle, CheckCircle2, XCircle, Flame, Shield, Truck, Info, Radio } from "lucide-react";
import type { Event } from "../types";
const KIND_META: Record<string, { icon: any; color: string; label: string }> = {
  reefer_failure:       { icon: AlertTriangle, color: "text-ag-amber", label: "Reefer Failure" },
  reefer_restored:      { icon: CheckCircle2, color: "text-ag-green", label: "Reefer Restored" },
  distressed:           { icon: Flame, color: "text-ag-orange", label: "Distressed" },
  auction_opened:       { icon: Flame, color: "text-ag-orange", label: "Flash Auction" },
  bid_received:         { icon: Radio, color: "text-ag-blue", label: "Bid Received" },
  settled:              { icon: CheckCircle2, color: "text-ag-green", label: "Settled" },
  delivered:            { icon: Truck, color: "text-ag-green", label: "Delivered" },
  spoiled:              { icon: XCircle, color: "text-ag-red", label: "Spoiled" },
  spoof_rejected:       { icon: Shield, color: "text-ag-red", label: "Zero-Trust Block" },
  rerouted:             { icon: Truck, color: "text-ag-blue", label: "Rerouted" },
  no_rescue:            { icon: AlertTriangle, color: "text-ag-red", label: "No Rescue" },
};
export default function EventFeed({ events, compact=false, expanded=false }:
  { events: Event[]; compact?: boolean; expanded?: boolean }) {
  const list = expanded ? events : events.slice(0, compact?12:50);
  return (
    <div className={`glass rounded-2xl ${compact?"p-4":"p-5"}`}>
      <h3 className="font-semibold flex items-center gap-2 mb-3"><Info className="w-4 h-4 text-ag-blue"/>Live Event Feed</h3>
      <div className={`space-y-2 ${expanded?"max-h-[600px]":compact?"max-h-[360px]":""} overflow-auto scrollbar-thin`}>
        {list.length === 0 && <p className="text-slate-500 text-sm text-center py-6">Awaiting events…</p>}
        {list.map(ev => {
          const meta = KIND_META[ev.kind] ?? { icon: Info, color: "text-slate-400", label: ev.kind };
          const Ic = meta.icon;
          const sevColor = ev.severity === "critical" ? "border-l-ag-red" : ev.severity === "warn" ? "border-l-ag-amber" : ev.severity === "ok" ? "border-l-ag-green" : "border-l-ink-600";
          return (
            <div key={`${ev.id}-${ev.ts}`} className={`p-2.5 rounded-lg bg-ink-800/50 border-l-4 ${sevColor}`}>
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-start gap-2">
                  <Ic className={`w-4 h-4 mt-0.5 ${meta.color}`}/>
                  <div>
                    <div className={`text-[11px] font-bold uppercase tracking-wider ${meta.color}`}>{meta.label}</div>
                    <div className="text-xs text-slate-300 leading-snug">{ev.description}</div>
                  </div>
                </div>
                <div className="text-[10px] text-slate-500 font-mono tabular whitespace-nowrap">{new Date(ev.ts).toLocaleTimeString()}</div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
