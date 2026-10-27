import { useMemo } from "react";
import type { Batch, Auction, RouteGraph } from "../types";

interface Props {
  route: RouteGraph;
  batches: Batch[];
  auctions: Auction[];
  selected: string | null;
  onSelect: (id: string) => void;
}

const BBOX = { minLat: 12.5, maxLat: 29.3, minLng: 76.9, maxLng: 79.9 };
const VW = 1000, VH = 900;
function project(lat: number, lng: number) {
  const x = ((lng - BBOX.minLng) / (BBOX.maxLng - BBOX.minLng)) * VW;
  const y = VH - ((lat - BBOX.minLat) / (BBOX.maxLat - BBOX.minLat)) * VH;
  return [x, y] as const;
}
const kmPerDegLat = 111;

export default function MapView({ route, batches, auctions, selected, onSelect }: Props) {
  const nodeById = useMemo(() => Object.fromEntries(route.nodes.map(n => [n.id, n])), [route]);
  const corridorPath = useMemo(() => {
    const pts: string[] = [];
    for (const e of route.edges) {
      const a = nodeById[e.from], b = nodeById[e.to];
      if (!a || !b) continue;
      if (!pts.length) { const [x,y]=project(a.lat,a.lng); pts.push(`M ${x.toFixed(1)} ${y.toFixed(1)}`); }
      const [x,y]=project(b.lat,b.lng); pts.push(`L ${x.toFixed(1)} ${y.toFixed(1)}`);
    }
    return pts.join(" ");
  }, [route, nodeById]);

  const auctionBatchIds = new Set(auctions.map(a => a.batch_id));

  return (
    <svg viewBox={`0 0 ${VW} ${VH}`} className="w-full h-full" preserveAspectRatio="xMidYMid meet">
      <defs>
        <linearGradient id="corridor" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#3fa9ff" stopOpacity=".5"/>
          <stop offset="1" stopColor="#00e0a4" stopOpacity=".5"/>
        </linearGradient>
        <filter id="glowOrange" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
        <filter id="glowRed" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
        <filter id="glowGreen" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
      </defs>

      {/* BG grid labels */}
      <g opacity="0.4">
        {["29°N Delhi","25°N Jhansi","21°N Nagpur","17°N Hyderabad","13°N Bengaluru"].map((lbl,i)=>{
          const lat = [29,25,21,17,13][i]; const [,y]=project(lat,77);
          return <g key={i}><line x1={0} x2={VW} y1={y} y2={y} stroke="#1d2a44" strokeDasharray="3 6"/>
            <text x={10} y={y-6} fill="#6c7e9e" fontSize="11">{lbl}</text></g>;
        })}
      </g>

      {/* Dead zones */}
      {route.dead_zones.map((dz, i) => {
        const [x,y] = project(dz.lat, dz.lng);
        const r = (dz.radius_km / kmPerDegLat) / (BBOX.maxLat - BBOX.minLat) * VH;
        return <g key={i}>
          <circle cx={x} cy={y} r={r} fill="#ff4c5c" fillOpacity="0.08" stroke="#ff4c5c" strokeOpacity="0.3" strokeDasharray="4 4"/>
          <text x={x} y={y+r-6} textAnchor="middle" fill="#ff8a94" fontSize="10">⚠ {dz.name}</text>
        </g>;
      })}

      {/* Corridor */}
      <path d={corridorPath} fill="none" stroke="#3fa9ff22" strokeWidth={26} strokeLinecap="round"/>
      <path d={corridorPath} fill="none" stroke="url(#corridor)" strokeWidth={10} strokeLinecap="round" strokeOpacity={0.8}/>
      <path d={corridorPath} fill="none" stroke="#3fa9ff" strokeWidth={1.5} strokeDasharray="6 6" strokeOpacity={0.5}/>

      {/* Cities */}
      {route.nodes.map(n => {
        const [x,y]=project(n.lat,n.lng);
        const isMajor = n.kind === "city" || n.kind === "origin" || n.kind === "destination";
        return <g key={n.id}>
          <circle cx={x} cy={y} r={isMajor?4:2.5} fill={n.cold?"#a78bfa":"#6c7e9e"}/>
          {isMajor && <text x={x+7} y={y+3} fill="#c6d2e6" fontSize="11" fontWeight={n.kind==="destination"||n.kind==="origin"?700:500}>{n.name}</text>}
          {n.cold && <circle cx={x} cy={y} r={7} fill="none" stroke="#a78bfa" strokeOpacity={0.6} strokeDasharray="2 2"/>}
        </g>;
      })}

      {/* Auction radius pulses */}
      {auctions.map(a => {
        const [x,y]=project(a.trigger_lat, a.trigger_lng);
        const r = (45 / kmPerDegLat) / (BBOX.maxLat - BBOX.minLat) * VH;
        return <g key={a.id}>
          <circle cx={x} cy={y} r={r} fill="#ff7a18" fillOpacity="0.08" stroke="#ff7a18" strokeOpacity="0.4"/>
        </g>;
      })}

      {/* Trucks */}
      {batches.map(b => {
        if (b.lat == null || b.lng == null) return null;
        const [x,y] = project(b.lat, b.lng);
        const status = b.status;
        const isDistressed = status === "DistressedLiquidation" || auctionBatchIds.has(b.id);
        const isSpoiled = status === "Spoiled";
        const isDelivered = status === "Delivered";
        const isCleared = status === "Cleared";
        const color =
          isSpoiled ? "#ff4c5c" :
          isDistressed ? "#ff7a18" :
          isDelivered || isCleared ? "#2a4a3a" :
          b.health === "fresh" ? "#00e0a4" :
          b.health === "aging" ? "#ffc845" :
          "#ff4c5c";
        const filter =
          isDistressed ? "url(#glowOrange)" :
          isSpoiled ? "url(#glowRed)" :
          isDelivered ? "" :
          b.health === "critical" ? "url(#glowRed)" : "";
        const isSelected = selected === b.id;
        return (
          <g key={b.id} className="cursor-pointer" onClick={() => onSelect(b.id)} style={{cursor:"pointer"}}>
            {(isDistressed || isSpoiled) && (
              <circle cx={x} cy={y} r={6} fill="none" stroke={color} strokeWidth={2} className="pulse-ring"/>
            )}
            {isSelected && <circle cx={x} cy={y} r={14} fill="none" stroke="#fff" strokeWidth={1.5} strokeDasharray="3 2"/>}
            <circle cx={x} cy={y} r={isDistressed?6:5} fill={color} stroke="#0008" strokeWidth={1.2} filter={filter}/>
            {/* RVH ring */}
            {b.rvh_hours != null && b.life_consumed_pct != null && status !== "Delivered" && (
              <circle cx={x} cy={y} r={9} fill="none" stroke={color} strokeOpacity={0.85} strokeWidth={2}
                strokeDasharray={`${((1 - b.life_consumed_pct/100))*56.5} 56.5`}
                transform={`rotate(-90 ${x} ${y})`}/>
            )}
          </g>
        );
      })}

      {/* Legend built into top-right */}
    </svg>
  );
}
