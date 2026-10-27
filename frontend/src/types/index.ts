export type Health = "fresh" | "aging" | "critical" | "spoiled";
export type BatchStatus = "InTransit" | "DistressedLiquidation" | "Delivered" | "Spoiled" | "Cleared" | "Rerouted";

export interface Batch {
  id: string;
  commodity: string;
  truck_id?: string;
  status: BatchStatus;
  health: Health;
  origin_name: string;
  destination_name: string;
  lat?: number;
  lng?: number;
  rvh_hours?: number;
  ett_hours?: number;
  ett_to_original_dest_hours?: number;
  life_consumed_pct?: number;
  temp_c?: number;
  weight_kg: number;
  contract_value_inr: number;
  farmer_payout_inr: number;
  distance_traveled_km?: number;
  total_km?: number;
  reroute_count: number;
  best_plan?: any;
}

export interface Buyer {
  id: string; name: string; kind: string;
  lat: number; lng: number;
  service_radius_km: number; capacity_kg: number;
  distance_km?: number;
}

export interface Auction {
  id: string; batch_id: string; commodity: string; status: "Open" | "Awarded" | "AwaitingConfirmation" | "Settled" | "Expired";
  opens_at: string; closes_at: string;
  trigger_lat: number; trigger_lng: number;
  trigger_rvh_hours: number; trigger_temp_c: number;
  nearby_buyers: Buyer[];
  winning_buyer_name?: string; winning_price_inr_per_kg?: number;
  kg_cleared?: number; countdown_sec?: number;
  lot_kg?: number; confirmation_deadline?: string; attempt?: number;
}

export interface Settlement {
  id: string; batch_id: string; auction_id: string;
  kg_cleared: number; price_inr_per_kg: number;
  salvage_revenue_inr: number; insurance_payout_inr: number; logistics_penalty_inr: number;
  farmer_total_payout_inr: number; farmer_recovery_pct: number; buyer_savings_pct: number;
  settled_at: string;
}

export interface Event {
  id: number; batch_id: string; ts: string; kind: string; severity: string; description: string;
}

export interface Summary {
  active_trucks: number; active_batches: number; distressed: number;
  spoiled_total: number; rescued_total: number; delivered: number; spoof_rejections: number;
  total_farmer_value_salvaged_inr: number; total_logistics_penalties_inr: number;
  avg_buyer_savings_pct: number; active_auctions: number;
}

export interface RouteNode {
  id: string; name: string; lat: number; lng: number; kind: string; cold?: boolean;
}
export interface RouteEdge { from: string; to: string; km: number; speed: number; type: string; coverage: number; }
export interface DeadZone { lat: number; lng: number; radius_km: number; name: string; }
export interface RouteGraph { nodes: RouteNode[]; edges: RouteEdge[]; dead_zones: DeadZone[]; corridor: string; }

export interface Telemetry {
  batch_id: string; truck_id: string;
  lat: number; lng: number; temp_c: number; humidity_pct: number; ethylene_ppm: number;
  speed_kmh: number; door_open: boolean; in_dead_zone: boolean;
  rvh_hours: number; spoil_eta_hours: number; life_consumed_pct: number;
  decay_rate_mult: number; health: Health; time_to_distress_hours: number;
  status: BatchStatus;
}
