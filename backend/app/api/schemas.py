"""
Pydantic DTOs for the AetherGrid public API.
These schemas mirror the production ASP.NET Core contracts.

Author: Praveen Sudireddy
"""
from __future__ import annotations
import datetime as dt
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class HealthOut(BaseModel):
    ok: bool
    service: str
    version: str
    active_trucks: int
    active_batches: int
    author: str = "Praveen Sudireddy"


class CommodityInfo(BaseModel):
    key: str
    shelf_hours_ref: float
    q10: float
    opt_temp_c: float
    max_safe_temp_c: float
    eth_sensitivity: float = 1.0
    wholesale_price_inr_per_kg: float
    unit: str = "crate"
    crate_kg: float


class TelemetryIn(BaseModel):
    signature_version: int = Field(default=1, ge=1, le=2)
    model_config = {"allow_inf_nan": False}
    hsm_serial: str
    batch_id: str
    truck_id: str
    seq: int = Field(ge=0)
    ts: int = Field(gt=0)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    temp_c: float = Field(ge=-80, le=100)
    humidity_pct: float = Field(ge=0, le=100)
    ethylene_ppm: float = Field(ge=0, le=10000)
    speed_kmh: float = 0.0
    reefer_setpoint_c: Optional[float] = None
    door_open: bool = False
    fuel_level_pct: Optional[float] = None
    cellular_rssi: Optional[float] = None
    in_dead_zone: bool = False
    hsm_signature: str


class TelemetryAck(BaseModel):
    ok: bool
    accepted: int
    rejected: int = 0
    failures: List[Dict[str, Any]] = []


class BuyerOut(BaseModel):
    id: str
    name: str
    kind: str
    lat: float
    lng: float
    service_radius_km: float
    capacity_kg: float
    distance_km: Optional[float] = None


class BatchOut(BaseModel):
    id: str
    commodity: str
    truck_id: Optional[str]
    status: str
    health: str
    origin_name: str
    destination_name: str
    lat: Optional[float]
    lng: Optional[float]
    rvh_hours: Optional[float]
    ett_hours: Optional[float]
    ett_to_original_dest_hours: Optional[float]
    life_consumed_pct: Optional[float]
    temp_c: Optional[float]
    weight_kg: float
    contract_value_inr: float
    farmer_payout_inr: float
    distance_traveled_km: Optional[float]
    total_km: Optional[float]
    reroute_count: int
    best_plan: Optional[Dict[str, Any]] = None


class ConfirmationIn(BaseModel):
    operator_name: str = Field(min_length=2, max_length=80)
    action: str = Field(pattern="^(confirm|reject)$")
    simulated_escrow_acknowledged: bool = False


class BidIn(BaseModel):
    model_config = {"allow_inf_nan": False}
    buyer_id: str
    price_inr_per_kg: float = Field(gt=1, le=5000)
    kg_requested: float = Field(gt=10, le=50000)
    auto_generated: bool = False


class AuctionOut(BaseModel):
    id: str
    batch_id: str
    commodity: str
    status: str
    opens_at: dt.datetime
    closes_at: dt.datetime
    trigger_lat: float
    trigger_lng: float
    trigger_rvh_hours: float
    trigger_temp_c: float
    nearby_buyers: List[BuyerOut]
    winning_buyer_name: Optional[str] = None
    winning_price_inr_per_kg: Optional[float] = None
    kg_cleared: Optional[float] = None
    countdown_sec: Optional[int] = None
    confirmation_deadline: Optional[dt.datetime] = None
    lot_kg: Optional[float] = None
    attempt: int = 0


class SettlementOut(BaseModel):
    buyer_id: Optional[str] = None
    id: str
    batch_id: str
    auction_id: str
    kg_cleared: float
    price_inr_per_kg: float
    salvage_revenue_inr: float
    insurance_payout_inr: float
    logistics_penalty_inr: float
    farmer_total_payout_inr: float
    farmer_recovery_pct: float
    buyer_savings_pct: float
    settled_at: dt.datetime


class RouteNodeOut(BaseModel):
    id: str
    name: str
    lat: float
    lng: float
    node_kind: str


class EventOut(BaseModel):
    id: int
    batch_id: str
    ts: dt.datetime
    kind: str
    severity: str
    description: str


class DashboardSummary(BaseModel):
    active_trucks: int
    active_batches: int
    distressed: int
    spoiled_total: int
    rescued_total: int
    delivered: int
    spoof_rejections: int
    total_farmer_value_salvaged_inr: float
    total_logistics_penalties_inr: float
    avg_buyer_savings_pct: float
    active_auctions: int


class SeedTruckBatchIn(BaseModel):
    model_config = {"allow_inf_nan": False}
    truck_id: str
    carrier_id: str
    hsm_serial: str
    commodity: str
    weight_kg: float = Field(gt=10, le=50000)
    contract_value_inr: float = Field(gt=0)
    farmer_payout_inr: float = Field(ge=0)
    origin_name: str
    origin_lat: float
    origin_lng: float
    destination_name: str
    dest_lat: float
    dest_lng: float
