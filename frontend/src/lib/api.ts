import { request } from "./auth";
const BASE = "";
async function j<T>(r: Response): Promise<T> {
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}
export const api = {
  get: <T = any>(url: string) => request(`${BASE}${url}`).then(j<T>),
  health: () => request(`${BASE}/api/health`).then(j<any>),
  commodities: () => request(`${BASE}/api/commodities`).then(j<any[]>),
  batches: () => request(`${BASE}/api/batches`).then(j<any[]>),
  buyers: (lat?: number, lng?: number, radius = 50) =>
    request(`${BASE}/api/buyers${lat !== undefined ? `?lat=${lat}&lng=${lng}&radius=${radius}` : ""}`).then(j<any[]>),
  auctions: () => request(`${BASE}/api/auctions`).then(j<any[]>),
  settlements: () => request(`${BASE}/api/settlements`).then(j<any[]>),
  events: (batchId?: string) => request(`${BASE}/api/events${batchId ? `?batch_id=${batchId}` : ""}`).then(j<any[]>),
  summary: () => request(`${BASE}/api/summary`).then(j<any>),
  route: () => request(`${BASE}/api/route`).then(j<any>),
  confirm: (auctionId: string, token: string, action: "confirm" | "reject") =>
    request(`${BASE}/api/auctions/${auctionId}/confirm`, {
      method: "POST", headers: {"content-type": "application/json", "X-Operator-Token": token},
      body: JSON.stringify({operator_name: "Demo operator", action, simulated_escrow_acknowledged: true}),
    }).then(j<any>),
  bid: (auctionId: string, payload: { buyer_id: string; price_inr_per_kg: number; kg_requested: number; auto_generated?: boolean }) =>
    request(`${BASE}/api/auctions/${auctionId}/bid`, {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    }).then(j<any>),
};
export function fmtINR(v: number) {
  return "₹" + Math.round(v).toLocaleString("en-IN");
}
export function fmtHours(h: number) {
  if (h == null) return "—";
  if (h >= 24) return (h / 24).toFixed(1) + "d";
  if (h < 1) return Math.round(h * 60) + "m";
  return h.toFixed(1) + "h";
}
export function haversine_km(lat1: number, lng1: number, lat2: number, lng2: number): number {
  const R = 6371;
  const toR = (d: number) => d * Math.PI / 180;
  const p1 = toR(lat1), p2 = toR(lat2);
  const dp = toR(lat2 - lat1), dl = toR(lng2 - lng1);
  const a = Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

export function parseUTC(value: string) { return new Date(/(?:Z|[+-]\d{2}:\d{2})$/.test(value) ? value : value + "Z").getTime(); }
