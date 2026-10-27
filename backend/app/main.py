"""
AetherGrid Backend — Main Application
=====================================
FastAPI service that:
  * Ingests software HMAC-signed demo telemetry over WebSocket & REST (not mTLS)
  * Runs Bio-Timer integration per batch
  * Runs Dynamic Router for thermal-shortest-path decisions
  * Triggers flash auctions when RVH / ETT triggers fire
  * Executes Insurance Oracle settlement
  * Publishes all events over Socket.IO
  * Serves the production React frontend (dist) at /

Production porting note: this entire file maps 1:1 to ASP.NET Core
Controllers + MediatR handlers. The SQLAlchemy models translate to
EF Core entities with [Column(TypeName="geography")] for SQL Server.

Author: Praveen Sudireddy
"""
from __future__ import annotations
import datetime as dt
import asyncio
import secrets
import logging
import json
import random
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import socketio
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session as OrmSession
from sqlalchemy import func

from .core.config import settings, COMMODITY_PROFILES
from .services.buyer_eligibility import rejection_reasons, demo_commodities
from .core.database import BuyerAuthorization, AuctionControl, TelemetryCheckpoint, ReceiverCursor, TelemetryBaseline
from .core.access import AccessBoundary, validate_deployment
from .services.auction_lifecycle import lock_writer, control_for, fail_and_retry, expire_due
from .core.database import (
    init_db, SessionLocal, engine, CargoBatch, TelemetrySample, Truck,
    RegisteredBuyer, FlashAuction, AuctionBid, Settlement, RouteNode,
    RouteEdge, Farmer, LogisticsCarrier, CargoEvent, InsurancePolicy,
)
from .core.security import register_hsm, verify_packet, verify_packet_v2
from .core.event_bus import init_bus, get_bus
from .algorithms.bio_timer import BioTimer
from .algorithms.router import DynamicRouter, haversine_km
from .services.insurance_oracle import compute_settlement, new_txn_reference
from .simulation.seed_data import ROUTE_NODES, ROUTE_EDGES, BUYERS, CARRIERS, FARMERS_SAMPLE
from .api import schemas


# ===== App + Socket.IO setup =====
sio = socketio.AsyncServer(cors_allowed_origins=settings.CORS_ORIGINS, async_mode="asgi")
app = FastAPI(
    title="AetherGrid Zero-Trust Cold-Chain Mesh",
    version="1.0.0",
    description="Dynamic Liquidation Engine for perishable supply chains. "
                "Author: Praveen Sudireddy.",
    docs_url="/docs",
)
app.add_middleware(
    CORSMiddleware, allow_origins=settings.CORS_ORIGINS, allow_credentials=False,
    allow_methods=["*"], allow_headers=["*"],
)
asgi_app = AccessBoundary(socketio.ASGIApp(sio, other_asgi_app=app))

app.add_middleware(AccessBoundary)  # also guard direct app entry, not only Socket.IO wrapper

bus = init_bus(sio)


# ===== In-memory state =====
bio_timers: Dict[str, BioTimer] = {}
router: Optional[DynamicRouter] = None
spoof_rejections: int = 0
lifecycle_task = None


# ===== DB dependency =====
def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()


# ===== Seeding =====
def seed_database(db: OrmSession):
    init_db()
    # Seed farmers
    if db.query(Farmer).count() == 0:
        for f in FARMERS_SAMPLE:
            db.add(Farmer(**f))
    # Seed carriers
    if db.query(LogisticsCarrier).count() == 0:
        for c in CARRIERS:
            db.add(LogisticsCarrier(
                id=c["id"], name=c["name"], iata_gstn=c["iata_gstn"],
                hsm_serial_prefix=c["hsm_prefix"], sla_compliance_pct=c["sla"],
            ))
    # Seed route nodes
    if db.query(RouteNode).count() == 0:
        for n in ROUTE_NODES:
            db.add(RouteNode(
                id=n["id"], corridor="NH44", name=n["name"],
                lat=n["lat"], lng=n["lng"], node_kind=n["kind"],
                has_cold_storage=n.get("cold", False),
                population_2023=n.get("pop"),
            ))
    if db.query(RouteEdge).count() == 0:
        for e in ROUTE_EDGES:
            db.add(RouteEdge(**e))
    # Seed buyers
    if db.query(RegisteredBuyer).count() == 0:
        for b in BUYERS:
            db.add(RegisteredBuyer(**b))
    db.flush()
    # Explicit DEMO balances: no bank/UPI or real insurance integration.
    for buyer in db.query(RegisteredBuyer).all():
        if db.get(BuyerAuthorization, buyer.id) is None:
            db.add(BuyerAuthorization(buyer_id=buyer.id,
                accepted_commodities=demo_commodities(buyer.kind, COMMODITY_PROFILES),
                simulated_escrow_inr=2_000_000.0, pre_authorized=True, mode="simulated"))
    # Register HSM secrets for seeded carriers (prefix-wide)
    for c in CARRIERS:
        for i in range(0, 3000):
            register_hsm(f"{c['hsm_prefix']}-HSM-{i:05d}")
    db.commit()


# ===== Start-up =====
@app.on_event("startup")
def on_start():
    validate_deployment()
    init_db()
    with SessionLocal() as db:
        if settings.ENV != "production": seed_database(db)
        # Derived software key provisioning; production requires rotated root secret.
        for truck in db.query(Truck).all(): register_hsm(truck.hsm_serial)
    global router
    nodes: Dict[str, dict] = {}
    edges: List[dict] = []
    with SessionLocal() as db:
        for n in db.query(RouteNode).filter(RouteNode.corridor == "NH44").all():
            nodes[n.id] = {"id": n.id, "name": n.name, "lat": n.lat, "lng": n.lng}
        for e in db.query(RouteEdge).filter(RouteEdge.corridor == "NH44").all():
            edges.append({
                "from_node": e.from_node, "to_node": e.to_node,
                "distance_km": e.distance_km, "base_speed_kmh": e.base_speed_kmh,
                "road_type": e.road_type, "cellular_coverage_pct": e.cellular_coverage_pct,
                "accident_risk": e.accident_risk,
            })
    router = DynamicRouter(nodes, edges)
    print(f"[aethergrid] Router loaded with {len(nodes)} nodes, {len(edges)} edges (NH-44 Delhi→Bengaluru)")
    print("[aethergrid] Author: Praveen Sudireddy")


async def lifecycle_worker():
    while True:
        try:
            def sweep():
                with SessionLocal() as db: return expire_due(db)
            changed = await asyncio.to_thread(sweep)
            if changed: await get_bus().emit("auction_lifecycle", {"changes": changed})
        except asyncio.CancelledError:
            raise
        except Exception:
            logging.exception("Auction lifecycle sweep failed; retrying next second")
        await asyncio.sleep(1)


@app.on_event("startup")
async def start_lifecycle_worker():
    global lifecycle_task
    lifecycle_task = asyncio.create_task(lifecycle_worker())


@app.on_event("shutdown")
async def stop_lifecycle_worker():
    if lifecycle_task:
        lifecycle_task.cancel()
        try: await lifecycle_task
        except asyncio.CancelledError: pass


# ===== Routes =====
@app.get("/api/health", response_model=schemas.HealthOut)
def health(db: OrmSession = Depends(get_db)):
    return schemas.HealthOut(
        ok=True, service="AetherGrid", version=settings.APP_VERSION,
        active_trucks=db.query(Truck).filter(Truck.last_heartbeat != None).count(),
        active_batches=db.query(CargoBatch).filter(CargoBatch.status.in_(["InTransit","DistressedLiquidation","Rerouted"])).count(),
    )


@app.get("/api/commodities", response_model=List[schemas.CommodityInfo])
def list_commodities():
    out = []
    for k, p in COMMODITY_PROFILES.items():
        out.append(schemas.CommodityInfo(key=k, **p))
    return out


@app.get("/api/buyers", response_model=List[schemas.BuyerOut])
def list_buyers(lat: Optional[float] = None, lng: Optional[float] = None,
                kind: Optional[str] = None, radius: float = settings.DISTRESSED_RADIUS_KM,
                db: OrmSession = Depends(get_db)):
    q = db.query(RegisteredBuyer)
    if kind: q = q.filter(RegisteredBuyer.kind == kind)
    result=[]
    for b in q.all():
        d = haversine_km(lat, lng, b.lat, b.lng) if (lat is not None and lng is not None) else None
        if d is not None and d > radius: continue
        result.append(schemas.BuyerOut(
            id=b.id, name=b.name, kind=b.kind, lat=b.lat, lng=b.lng,
            service_radius_km=b.service_radius_km, capacity_kg=b.capacity_kg,
            distance_km=None if d is None else round(d,2),
        ))
    result.sort(key=lambda x: x.distance_km or 9999)
    return result


@app.get("/api/batches", response_model=List[schemas.BatchOut])
def list_batches(db: OrmSession = Depends(get_db)):
    out=[]
    for b in db.query(CargoBatch).order_by(CargoBatch.created_at.desc()).all():
        total_km = haversine_km(b.origin_lat, b.origin_lng, b.dest_lat, b.dest_lng)
        traveled = haversine_km(b.origin_lat, b.origin_lng, b.current_lat or b.origin_lat, b.current_lng or b.origin_lng)
        out.append(schemas.BatchOut(
            id=b.id, commodity=b.commodity, truck_id=b.truck_id, status=b.status,
            health=b.health or "fresh",
            origin_name=b.origin_name, destination_name=b.destination_name,
            lat=b.current_lat, lng=b.current_lng,
            rvh_hours=b.rvh_hours, ett_hours=b.ett_hours,
            ett_to_original_dest_hours=b.ett_to_original_dest_hours,
            life_consumed_pct=b.life_consumed_pct, temp_c=b.current_temp_c,
            weight_kg=b.weight_kg, contract_value_inr=b.contract_value_inr,
            farmer_payout_inr=b.farmer_payout_inr,
            distance_traveled_km=round(traveled,2), total_km=round(total_km,2),
            reroute_count=b.reroute_count,
        ))
    return out


@app.get("/api/batches/{batch_id}")
def get_batch(batch_id: str, db: OrmSession = Depends(get_db)):
    b = db.query(CargoBatch).filter(CargoBatch.id == batch_id).first()
    if not b: raise HTTPException(404)
    t = db.query(Truck).filter(Truck.id == b.truck_id).first()
    carrier = db.query(LogisticsCarrier).filter(LogisticsCarrier.id == b.carrier_id).first() if b else None
    samples = db.query(TelemetrySample).filter(TelemetrySample.batch_id == batch_id).order_by(TelemetrySample.ts.desc()).limit(80).all()
    prof = COMMODITY_PROFILES.get(b.commodity, {})
    # compute kg and wholesale from seed
    kg = getattr(b, "weight_kg", 0) or 0
    return {
        "id": b.id, "truck_id": b.truck_id, "truck_reg": t.id if t else None,
        "carrier": carrier.name if carrier else None, "driver": t.driver_name if t else None,
        "commodity_key": b.commodity,
        "commodity_label": b.commodity,
        "origin": b.origin_name, "destination": b.destination_name,
        "kg": kg,
        "wholesale_price_inr_per_kg": prof.get("wholesale_price_inr_per_kg", 0),
        "status": b.status, "rvh": getattr(b, "rvh_hours", 0) or 0,
        "life_consumed_pct": getattr(b, "life_consumed_pct", 0) or 0,
        "temp_c": b.temp_c if hasattr(b, "temp_c") else (t.temp_c if t else None),
        "humidity": getattr(b, "humidity_pct", None),
        "lat": b.lat if hasattr(b,"lat") else (t.lat if t else None),
        "lng": b.lng if hasattr(b,"lng") else (t.lng if t else None),
        "door_open_count": 0,
        "profile": prof,
        "samples": [{"ts": s.ts.isoformat() if s.ts else None,"temp":s.temp_c,"h":s.humidity_pct,"lat":s.lat,"lng":s.lng,"rvh":0,"life":0,"door":s.door_open} for s in reversed(samples)],
    }


@app.get("/api/batches/{batch_id}/telemetry")
def get_batch_telemetry(batch_id: str, limit: int = 200, db: OrmSession = Depends(get_db)):
    samples = db.query(TelemetrySample).filter(TelemetrySample.batch_id == batch_id).order_by(TelemetrySample.ts.asc()).limit(limit).all()
    return [{"ts": s.ts.isoformat() if s.ts else None, "temp": s.temp_c, "h": s.humidity_pct, "lat": s.lat, "lng": s.lng, "rvh": 0, "life": 0, "door": s.door_open} for s in samples]


@app.get("/api/carrier/sla")
def carrier_sla(db: OrmSession = Depends(get_db)):
    rows = []
    carriers = db.query(LogisticsCarrier).all()
    for c in carriers:
        trucks = db.query(Truck).filter(Truck.carrier_id == c.id).all()
        tids = [t.id for t in trucks]
        batches = db.query(CargoBatch).filter(CargoBatch.carrier_id == c.id).all()
        bids = [b.id for b in batches]
        settled = db.query(Settlement).filter(Settlement.batch_id.in_(bids)).all() if bids else []
        spoiled = sum(1 for b in batches if b.status == "Spoiled")
        distressed = sum(1 for b in batches if b.status == "DistressedLiquidation")
        rescued = sum(1 for b in batches if b.status == "Cleared")
        rows.append({
            "carrier": c.name,
            "carrier_id": c.id,
            "trucks": len(trucks),
            "batches_active": sum(1 for b in batches if b.status in ("InTransit","DistressedLiquidation","Rerouted")),
            "distressed": distressed,
            "spoiled": spoiled,
            "rescued": rescued,
            "penalties_inr": round(sum(s.logistics_penalty_inr for s in settled),2),
            "farmer_recovered_inr": round(sum(s.farmer_total_payout_inr for s in settled),2),
            "sla_score": round(max(0.0, 100.0 - 10.0*spoiled - 3.0*distressed), 1),
        })
    return rows


@app.get("/api/insurance/claims")
def insurance_claims(db: OrmSession = Depends(get_db)):
    out = []
    for s in db.query(Settlement).order_by(Settlement.settled_at.desc()).limit(100).all():
        b = db.query(CargoBatch).filter(CargoBatch.id == s.batch_id).first()
        c = db.query(LogisticsCarrier).filter(LogisticsCarrier.id == b.carrier_id).first() if b else None
        out.append({
            "id": s.id, "batch_id": s.batch_id,
            "carrier": c.name if c else "Unknown",
            "commodity": b.commodity if b else "?",
            "kg": s.kg_cleared,
            "salvage": s.salvage_revenue_inr,
            "payout": s.insurance_payout_inr,
            "penalty": s.logistics_penalty_inr,
            "farmer_total": s.farmer_total_payout_inr,
            "settled_at": s.settled_at,
            "policy": f"AG-INS-{abs(hash(s.id))%100000:05d}",
            "oracle_hash": f"0x{abs(hash(s.id+s.batch_id)):010x}",
            "status": "Paid" if s.farmer_total_payout_inr > 0 else "Pending",
        })
    return out


@app.get("/api/settlements/export.csv")
def settlements_csv(db: OrmSession = Depends(get_db)):
    out = ["settlement_id,batch_id,commodity,truck,kg_cleared,price_inr_per_kg,salvage_revenue_inr,insurance_payout_inr,logistics_penalty_inr,farmer_total_payout_inr,farmer_recovery_pct,buyer_savings_pct,settled_at"]
    for s in db.query(Settlement).order_by(Settlement.settled_at.asc()).all():
        b = db.query(CargoBatch).filter(CargoBatch.id == s.batch_id).first()
        t = db.query(Truck).filter(Truck.id == b.truck_id).first() if b else None
        out.append(f"{s.id},{s.batch_id},{b.commodity if b else ''},{t.id if t else ''},{s.kg_cleared:.1f},{s.price_inr_per_kg:.2f},{s.salvage_revenue_inr:.2f},{s.insurance_payout_inr:.2f},{s.logistics_penalty_inr:.2f},{s.farmer_total_payout_inr:.2f},{s.farmer_recovery_pct:.1f},{s.buyer_savings_pct:.1f},{s.settled_at}")
    return PlainTextResponse("\n".join(out), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=settlements.csv"})


@app.get("/api/auctions", response_model=List[schemas.AuctionOut])
def list_auctions(db: OrmSession = Depends(get_db)):
    out=[]
    for a in db.query(FlashAuction).order_by(FlashAuction.opened_at.desc()).limit(100).all():
        batch = db.query(CargoBatch).get(a.batch_id)
        nearby = []
        # compute nearby buyers at trigger time
        for b in db.query(RegisteredBuyer).all():
            d = haversine_km(a.trigger_lat, a.trigger_lng, b.lat, b.lng)
            if d <= settings.DISTRESSED_RADIUS_KM:
                nearby.append(schemas.BuyerOut(
                    id=b.id,name=b.name,kind=b.kind,lat=b.lat,lng=b.lng,
                    service_radius_km=b.service_radius_km,capacity_kg=b.capacity_kg,
                    distance_km=round(d,2),
                ))
        nearby.sort(key=lambda x: x.distance_km or 9999)
        win_bid = db.query(AuctionBid).get(a.winning_bid_id) if a.winning_bid_id else None
        win_buyer = db.query(RegisteredBuyer).get(win_bid.buyer_id) if win_bid else None
        cd = max(0, int((a.closes_at - dt.datetime.utcnow()).total_seconds())) if a.status=="Open" else None
        out.append(schemas.AuctionOut(
            id=a.id, batch_id=a.batch_id, commodity=batch.commodity if batch else "?",
            lot_kg=batch.weight_kg if batch else None,
            confirmation_deadline=(db.get(AuctionControl,a.id).confirmation_deadline if db.get(AuctionControl,a.id) else None),
            attempt=(db.get(AuctionControl,a.id).attempt if db.get(AuctionControl,a.id) else 0),
            status=a.status, opens_at=a.opened_at, closes_at=a.closes_at,
            trigger_lat=a.trigger_lat, trigger_lng=a.trigger_lng,
            trigger_rvh_hours=a.trigger_rvh_hours or 0, trigger_temp_c=a.trigger_temp_c or 0,
            nearby_buyers=nearby[:10],
            winning_buyer_name=win_buyer.name if win_buyer else None,
            winning_price_inr_per_kg=win_bid.price_inr_per_kg if win_bid else None,
            kg_cleared=None if not win_bid else None,  # set by settlement
            countdown_sec=cd,
        ))
    return out


@app.get("/api/settlements", response_model=List[schemas.SettlementOut])
def list_settlements(db: OrmSession = Depends(get_db)):
    out=[]
    for s in db.query(Settlement).order_by(Settlement.settled_at.desc()).limit(50).all():
        out.append(schemas.SettlementOut(
            id=s.id,batch_id=s.batch_id,auction_id=s.auction_id,buyer_id=s.buyer_id,
            kg_cleared=s.kg_cleared,price_inr_per_kg=s.price_inr_per_kg,
            salvage_revenue_inr=s.salvage_revenue_inr,
            insurance_payout_inr=s.insurance_payout_inr,
            logistics_penalty_inr=s.logistics_penalty_inr,
            farmer_total_payout_inr=s.farmer_total_payout_inr,
            farmer_recovery_pct=s.farmer_recovery_pct,
            buyer_savings_pct=s.buyer_savings_pct,
            settled_at=s.settled_at,
        ))
    return out


@app.get("/api/events", response_model=List[schemas.EventOut])
def list_events(batch_id: Optional[str] = None, limit: int = 100, db: OrmSession = Depends(get_db)):
    q = db.query(CargoEvent).order_by(CargoEvent.ts.desc())
    if batch_id: q = q.filter(CargoEvent.batch_id == batch_id)
    return q.limit(limit).all()


@app.get("/api/summary", response_model=schemas.DashboardSummary)
def dashboard_summary(db: OrmSession = Depends(get_db)):
    active = db.query(CargoBatch).filter(CargoBatch.status.in_(["InTransit","DistressedLiquidation","Rerouted"])).count()
    distressed = db.query(CargoBatch).filter(CargoBatch.status == "DistressedLiquidation").count()
    spoiled = db.query(CargoBatch).filter(CargoBatch.status == "Spoiled").count()
    rescued = db.query(CargoBatch).filter(CargoBatch.status == "Cleared").count()
    delivered = db.query(CargoBatch).filter(CargoBatch.status == "Delivered").count()
    active_auctions = db.query(FlashAuction).filter(FlashAuction.status == "Open").count()
    salvaged = db.query(func.coalesce(func.sum(Settlement.farmer_total_payout_inr),0.0)).scalar() or 0.0
    penalties = db.query(func.coalesce(func.sum(Settlement.logistics_penalty_inr),0.0)).scalar() or 0.0
    avg_saving = db.query(func.coalesce(func.avg(Settlement.buyer_savings_pct),0.0)).scalar() or 0.0
    return schemas.DashboardSummary(
        active_trucks=db.query(Truck).count(), active_batches=active,
        distressed=distressed, spoiled_total=spoiled, rescued_total=rescued,
        delivered=delivered, spoof_rejections=db.query(CargoEvent).filter(CargoEvent.kind=="spoof_rejected").count(),
        total_farmer_value_salvaged_inr=round(salvaged,2),
        total_logistics_penalties_inr=round(penalties,2),
        avg_buyer_savings_pct=round(avg_saving,2),
        active_auctions=active_auctions,
    )


@app.get("/api/route")
def route_graph(db: OrmSession = Depends(get_db)):
    nodes = [{"id":n.id,"name":n.name,"lat":n.lat,"lng":n.lng,"kind":n.node_kind,"cold":n.has_cold_storage}
             for n in db.query(RouteNode).filter(RouteNode.corridor=="NH44").order_by(RouteNode.id).all()]
    edges = [{"from":e.from_node,"to":e.to_node,"km":e.distance_km,"speed":e.base_speed_kmh,"type":e.road_type,"coverage":e.cellular_coverage_pct}
             for e in db.query(RouteEdge).filter(RouteEdge.corridor=="NH44").all()]
    # Dead zones
    from .simulation.seed_data import DEAD_ZONES
    dz = [{"lat":a,"lng":b,"radius_km":c,"name":n} for (a,b,c,n) in DEAD_ZONES]
    return {"nodes":nodes,"edges":edges,"dead_zones":dz,"corridor":"NH44"}


# ===== Admin / simulator bootstrap =====
@app.post("/api/admin/seed-truck-batch")
def seed_truck_batch(payload: schemas.SeedTruckBatchIn, db: OrmSession = Depends(get_db)):
    if payload.commodity not in COMMODITY_PROFILES:
        raise HTTPException(422, "unknown commodity")
    # Create truck if missing
    truck = db.query(Truck).get(payload.truck_id)
    if not truck:
        truck = Truck(
            id=payload.truck_id, carrier_id=payload.carrier_id, hsm_serial=payload.hsm_serial,
            reefer_model="Carrier Supra 850",
            lat=payload.origin_lat, lng=payload.origin_lng,
        )
        db.add(truck); db.flush()
    register_hsm(payload.hsm_serial)
    # Pick a farmer (cycling through sample set)
    farmers = db.query(Farmer).all()
    farmer = random.choice(farmers) if farmers else None
    bid = f"B-{uuid.uuid4().hex[:8].upper()}"
    batch = CargoBatch(
        id=bid, commodity=payload.commodity,
        farmer_id=farmer.id if farmer else None,
        carrier_id=payload.carrier_id, truck_id=payload.truck_id,
        origin_name=payload.origin_name, origin_lat=payload.origin_lat, origin_lng=payload.origin_lng,
        destination_name=payload.destination_name, dest_lat=payload.dest_lat, dest_lng=payload.dest_lng,
        weight_kg=payload.weight_kg, contract_value_inr=payload.contract_value_inr,
        farmer_payout_inr=payload.farmer_payout_inr,
        current_lat=payload.origin_lat, current_lng=payload.origin_lng,
        planned_route_km=haversine_km(payload.origin_lat, payload.origin_lng, payload.dest_lat, payload.dest_lng),
        status="InTransit",
    )
    db.add(batch); db.flush()
    # Insurance policy auto-issued
    policy = InsurancePolicy(
        id=f"P-{uuid.uuid4().hex[:8].upper()}", batch_id=bid,
        policy_no=f"AGIC-{random.randint(100000,999999)}",
        sum_assured_inr=payload.contract_value_inr*0.6,
        premium_paid_inr=payload.contract_value_inr*0.008,
        deductible_pct=settings.INSURANCE_DEDUCTIBLE_PCT,
        cover_pct=settings.INSURANCE_COVER_PCT,
    )
    db.add(policy)
    bio_timers[bid] = BioTimer(payload.commodity)
    db.commit()
    return {"batch_id": bid, "truck_id": payload.truck_id}


# ===== Telemetry ingestion =====
def _process_telemetry(db: OrmSession, p: dict) -> dict:
    """Core ingest path — runs for every packet."""
    global spoof_rejections
    lock_writer(db)
    db.expire_all()
    batch = db.query(CargoBatch).get(p["batch_id"])
    if not batch:
        db.rollback()
        return {"error":"batch_not_found","batch_id":p["batch_id"]}
    try:
        p = schemas.TelemetryIn.model_validate(p).model_dump()
    except Exception:
        db.rollback()
        return {"error":"invalid_telemetry_values"}
    # Zero-trust attestation
    truck = db.query(Truck).get(p["truck_id"])
    if not truck or batch.truck_id != truck.id or truck.hsm_serial != p["hsm_serial"]:
        db.rollback()
        return {"error":"telemetry_identity_mismatch"}
    cursor = db.get(ReceiverCursor, p["truck_id"])
    if settings.ENV=="production" and p["signature_version"]!=2:
        db.rollback()
        return {"error":"version_2_signature_required"}
    if p["signature_version"]==2:
        att=verify_packet_v2(p,cursor.sequence if cursor else -1)
    else:
        att = verify_packet(
            last_sequence=cursor.sequence if cursor else -1, advance_memory=False,
            hsm_serial=p["hsm_serial"], signature=p["hsm_signature"].replace("+MESH",""),
            batch_id=p["batch_id"], truck_id=p["truck_id"],
            seq=p["seq"], ts=p["ts"], lat=p["lat"], lng=p["lng"],
            temp_c=p["temp_c"], humidity_pct=p["humidity_pct"], ethylene_ppm=p["ethylene_ppm"],
        )
    if not att.ok or ("+MESH" not in p["hsm_signature"] and not p.get("hsm_signature","").startswith(("HSM-", "AG2-"))):
        spoof_rejections += 1
        db.add(CargoEvent(batch_id=batch.id, kind="spoof_rejected", severity="critical",
                          description=f"Attestation failure: {att.reason}",
                          metadata_json={"reason":att.reason,"seq":p["seq"]}))
        db.commit()
        return {"error":"attestation_failed","reason":att.reason}
    if not att.ok:
        spoof_rejections += 1
        db.add(CargoEvent(batch_id=batch.id, kind="spoof_rejected", severity="critical",
                          description=f"Attestation failure: {att.reason}", metadata_json=p))
        db.commit()
        return {"error":"attestation_failed","reason":att.reason}

    baseline = db.get(TelemetryBaseline, batch.id)
    if settings.ENV == "production":
        if not baseline or not db.get(TelemetryCheckpoint, batch.id):
            db.rollback(); return {"error":"reviewed_baseline_required"}
        prior_ts = max(baseline.reference_timestamp, cursor.timestamp if cursor else baseline.reference_timestamp)
        if p["ts"] < prior_ts:
            db.rollback(); return {"error":"timestamp_regression"}
        if p["ts"] - prior_ts > settings.ATTESTATION_TOLERANCE_SEC:
            db.rollback(); return {"error":"telemetry_gap_requires_review"}
        interval_hours = (p["ts"] - prior_ts)/3600.0
    else:
        interval_hours = settings.SIM_BIO_HOURS_PER_PACKET
    # Persist sample
    sample = TelemetrySample(
        batch_id=batch.id, truck_id=batch.truck_id, ts=dt.datetime.utcfromtimestamp(p["ts"]),
        lat=p["lat"], lng=p["lng"], temp_c=p["temp_c"], humidity_pct=p["humidity_pct"],
        ethylene_ppm=p["ethylene_ppm"], speed_kmh=p["speed_kmh"],
        reefer_setpoint_c=p.get("reefer_setpoint_c"), door_open=p.get("door_open",False),
        fuel_level_pct=p.get("fuel_level_pct"), cellular_rssi=p.get("cellular_rssi"),
        in_dead_zone=p.get("in_dead_zone",False), hsm_signature=p["hsm_signature"],
        attestation_ok=True, seq_number=p["seq"],
    )
    db.add(sample)

    # Update truck
    if truck:
        truck.lat = p["lat"]; truck.lng = p["lng"]; truck.temp_c = p["temp_c"]
        truck.humidity_pct = p["humidity_pct"]; truck.ethylene_ppm = p["ethylene_ppm"]
        truck.last_heartbeat = dt.datetime.utcnow()
        # Detect reefer failure if temp > 8°C above setpoint
        if p.get("reefer_setpoint_c") is not None:
            truck.reefer_healthy = p["temp_c"] < p["reefer_setpoint_c"] + 6.0

    # Bio-timer integration (30 seconds of bio-time per tick, at 0.5s tick = ~1 bio-minute/real-second)
    checkpoint = db.get(TelemetryCheckpoint, batch.id)
    bt = BioTimer(batch.commodity)
    if checkpoint:
        for key in ("life_consumed", "max_temp_c", "max_ethylene_ppm", "hours_out_of_range"):
            setattr(bt, key, getattr(checkpoint, key))
    elif db.query(TelemetrySample).filter(TelemetrySample.batch_id==batch.id).count():
        # Includes pending sample only with autoflush sessions; exclude it by seq.
        old_count = db.query(TelemetrySample).filter(TelemetrySample.batch_id==batch.id,
            TelemetrySample.id != sample.id).count()
        if old_count:
            db.rollback()
            return {"error":"legacy_checkpoint_missing", "requires":"reviewed state migration; no silent reset"}
    bt.apply_interval(p["temp_c"], p["humidity_pct"], p["ethylene_ppm"], hours=interval_hours,
                      door_open=p.get("door_open",False))
    if checkpoint is None:
        checkpoint = TelemetryCheckpoint(batch_id=batch.id)
        db.add(checkpoint)
    for key in ("life_consumed", "max_temp_c", "max_ethylene_ppm", "hours_out_of_range"):
        setattr(checkpoint, key, getattr(bt, key))
    if cursor is None:
        cursor = ReceiverCursor(truck_id=p["truck_id"])
        db.add(cursor)
    cursor.sequence=p["seq"]; cursor.timestamp=p["ts"]
    km_remaining = haversine_km(p["lat"], p["lng"], batch.dest_lat, batch.dest_lng)
    ett = km_remaining / settings.AVG_TRUCK_SPEED_KMH
    snap = bt.snapshot(p["temp_c"], p["humidity_pct"], p["ethylene_ppm"], ett, settings.RVH_PANIC_MULTIPLIER)

    # Update batch fields
    batch.current_lat = p["lat"]; batch.current_lng = p["lng"]
    batch.rvh_hours = snap.rvh_hours_at_optimal_temp
    batch.ett_hours = round(ett,2)
    batch.ett_to_original_dest_hours = round(ett,2)
    batch.life_consumed_pct = snap.life_consumed_pct
    batch.health = snap.health
    batch.current_temp_c = p["temp_c"]
    batch.max_temp_experienced_c = max(batch.max_temp_experienced_c or 0, p["temp_c"])
    batch.eth_exposure_peak_ppm = max(batch.eth_exposure_peak_ppm or 0, p["ethylene_ppm"])
    if p.get("in_dead_zone"): batch.deadzone_minutes = (batch.deadzone_minutes or 0) + 1/60
    batch.traveled_km = haversine_km(batch.origin_lat,batch.origin_lng,p["lat"],p["lng"])

    event_payload = None
    # Reefer failure / restore events
    if truck and not truck.reefer_healthy and not p.get("door_open"):
        existing = db.query(CargoEvent).filter(CargoEvent.batch_id==batch.id,
                                               CargoEvent.kind=="reefer_failure").order_by(CargoEvent.ts.desc()).first()
        if not existing or (dt.datetime.utcnow() - existing.ts).total_seconds() > 120:
            db.add(CargoEvent(batch_id=batch.id,kind="reefer_failure",severity="warn",
                              description=f"Reefer unit failed at {p['temp_c']:.1}°C, {km_remaining:.0f} km from destination"))
    # Delivery
    if km_remaining < 2.0 and snap.health != "spoiled" and batch.status not in ("Delivered", "Cleared", "Spoiled", "RescueDeliveryReported"):
        batch.status = "Delivered"; batch.delivered_at = dt.datetime.utcnow()
        db.add(CargoEvent(batch_id=batch.id,kind="delivered",severity="ok",
                          description=f"Delivered to {batch.destination_name} with {snap.life_consumed_pct:.0f}% life used"))
    # Spoilage
    if snap.health == "spoiled" and batch.status not in ("Spoiled","Cleared","Delivered","RescueDeliveryReported"):
        batch.status = "Spoiled"
        db.add(CargoEvent(batch_id=batch.id,kind="spoiled",severity="critical",
                          description=f"Cargo spoiled at ({p['lat']:.2f},{p['lng']:.2f}) before rescue"))
    # Distressed liquidation trigger: must have reefer trouble OR temp excursion, AND RVH < threshold*ETT
    reefer_trouble = (truck and not truck.reefer_healthy) or p["temp_c"] > (COMMODITY_PROFILES[batch.commodity]["max_safe_temp_c"] - 2) or snap.health in ("critical","aging")
    if batch.status == "InTransit" and reefer_trouble and snap.rvh_hours_at_optimal_temp < settings.RVH_PANIC_MULTIPLIER * ett:
        batch.status = "DistressedLiquidation"
        # Find nearby buyers within radius
        nearby=[]
        for b in db.query(RegisteredBuyer).all():
            d = haversine_km(p["lat"],p["lng"],b.lat,b.lng)
            if d <= settings.DISTRESSED_RADIUS_KM:
                nearby.append((b,d))
        nearby.sort(key=lambda x:x[1])
        if nearby:
            auction_id = f"F-{uuid.uuid4().hex[:8].upper()}"
            closes = dt.datetime.utcnow() + dt.timedelta(minutes=settings.AUCTION_WINDOW_MIN)
            auc = FlashAuction(
                id=auction_id, batch_id=batch.id, status="Open",
                trigger_lat=p["lat"], trigger_lng=p["lng"],
                trigger_rvh_hours=snap.rvh_hours_at_optimal_temp,
                trigger_temp_c=p["temp_c"], trigger_life_pct=snap.life_consumed_pct,
                opened_at=dt.datetime.utcnow(), closes_at=closes,
            )
            db.add(auc)
            db.add(CargoEvent(batch_id=batch.id,kind="auction_opened",severity="critical",
                              description=f"Flash auction opened for {len(nearby)} buyers within {settings.DISTRESSED_RADIUS_KM:.0f} km (RVH {snap.rvh_hours_at_optimal_temp:.1f}h < {settings.RVH_PANIC_MULTIPLIER}×ETT {ett:.1f}h)"))
            buyer_summaries = [{"id":b.id,"name":b.name,"kind":b.kind,"lat":b.lat,"lng":b.lng,
                                "distance_km":round(d,2),"capacity_kg":b.capacity_kg} for b,d in nearby[:10]]
            event_payload = {"type":"distressed","auction_id":auction_id,
                "batch_id":batch.id,"commodity":batch.commodity,"truck_id":batch.truck_id,
                "lat":p["lat"],"lng":p["lng"],"rvh_hours":round(snap.rvh_hours_at_optimal_temp,2),
                "ett_hours":round(ett,2),"life_consumed_pct":round(snap.life_consumed_pct,2),
                "temp_c":p["temp_c"],"closes_at":closes.isoformat(),
                "nearby_buyers":buyer_summaries}
        else:
            # No buyers nearby; check cold-storage recharge
            db.add(CargoEvent(batch_id=batch.id,kind="no_rescue",severity="critical",
                              description="No buyers in rescue radius; cargo likely to spoil"))

    # Run routing plan every ~20 ticks (handled via bus emission; simplified here)
    db.commit()

    bio_timers[batch.id] = bt  # cache only; persisted checkpoint is authoritative
    # Emit telemetry event
    return {"ok":True,"snapshot":snap.as_dict(),"event":event_payload,
            "batch_status":batch.status}


@app.post("/api/telemetry")
async def ingest_rest(p: schemas.TelemetryIn, db: OrmSession = Depends(get_db)):
    result = _process_telemetry(db, p.model_dump())
    if result.get("event"): await get_bus().emit("distressed", result["event"])
    return result


@app.websocket("/telemetry/stream")
async def telemetry_stream(ws: WebSocket):
    await ws.accept()
    db = SessionLocal()
    try:
        while True:
            raw = await ws.receive_text()
            try: data = json.loads(raw)
            except Exception:
                await ws.send_json({"ok":False,"error":"bad_json"}); continue
            points = data if isinstance(data, list) else [data]
            results=[]; accepted=0; rejected=0; failures=[]; events=[]
            for p in points:
                try:
                    r = _process_telemetry(db, p)
                    if r.get("ok"):
                        accepted+=1
                        if r.get("event"): events.append(r["event"])
                        await get_bus().emit("telemetry",{
                            "batch_id":p["batch_id"],"truck_id":p["truck_id"],
                            "lat":p["lat"],"lng":p["lng"],"temp_c":p["temp_c"],
                            "humidity_pct":p["humidity_pct"],"ethylene_ppm":p["ethylene_ppm"],
                            "speed_kmh":p["speed_kmh"],"door_open":p.get("door_open",False),
                            "in_dead_zone":p.get("in_dead_zone",False),
                            "rvh_hours":r["snapshot"]["rvh_hours"],
                            "spoil_eta_hours":r["snapshot"]["spoil_eta_hours"],
                            "life_consumed_pct":r["snapshot"]["life_consumed_pct"],
                            "decay_rate_mult":r["snapshot"]["decay_rate_mult"],
                            "health":r["snapshot"]["health"],
                            "time_to_distress_hours":r["snapshot"]["time_to_distress_hours"],
                            "status":r["batch_status"],
                        })
                    else:
                        rejected+=1; failures.append(r)
                    results.append(r)
                except Exception as e:
                    db.rollback()
                    rejected+=1; failures.append({"error":str(e)})
            for ev in events:
                await get_bus().emit("distressed", ev)
            await ws.send_json({"ok":True,"accepted":accepted,"rejected":rejected,"failures":failures[:5]})
    except WebSocketDisconnect:
        pass
    finally:
        db.close()


# ===== Auction endpoints =====
@app.post("/api/auctions/{auction_id}/bid")
async def place_bid(auction_id: str, payload: schemas.BidIn, db: OrmSession = Depends(get_db)):
    lock_writer(db)
    auc: FlashAuction = db.get(FlashAuction, auction_id)
    if not auc: raise HTTPException(404,"auction not found")
    if auc.status != "Open": raise HTTPException(400,"auction closed")
    buyer: RegisteredBuyer = db.query(RegisteredBuyer).get(payload.buyer_id)
    if not buyer: raise HTTPException(404,"buyer not found")
    batch = db.get(CargoBatch, auc.batch_id)
    auth = db.get(BuyerAuthorization, buyer.id)
    if not batch or batch.status != "DistressedLiquidation":
        raise HTTPException(409, "batch is not available for rescue")
    if not auth or auth.mode != "simulated":
        raise HTTPException(403, "missing demo pre-authorization; real escrow is not integrated")
    d = haversine_km(auc.trigger_lat, auc.trigger_lng, buyer.lat, buyer.lng)
    reasons = rejection_reasons(commodity=batch.commodity, lot_kg=batch.weight_kg,
        requested_kg=payload.kg_requested, price=payload.price_inr_per_kg,
        capacity_kg=buyer.capacity_kg, accepted_commodities=auth.accepted_commodities,
        escrow_inr=auth.simulated_escrow_inr, distance_km=d,
        service_radius_km=buyer.service_radius_km, rescue_radius_km=settings.DISTRESSED_RADIUS_KM,
        rvh_hours=max(0, min(auc.trigger_rvh_hours, batch.rvh_hours or 0) -
            (dt.datetime.utcnow() - auc.opened_at).total_seconds()/3600),
        approved=auth.pre_authorized, expired=dt.datetime.utcnow() >= auc.closes_at)
    if reasons:
        raise HTTPException(422, {"reasons": reasons, "mode": "simulated"})
    # Conditional writes guard against double awards and competing capacity/fund use.
    claimed = db.query(FlashAuction).filter(FlashAuction.id == auc.id,
        FlashAuction.status == "Open").update({"status": "Awarded"}, synchronize_session=False)
    reserved = db.query(RegisteredBuyer).filter(RegisteredBuyer.id == buyer.id,
        RegisteredBuyer.capacity_kg >= batch.weight_kg).update(
        {"capacity_kg": RegisteredBuyer.capacity_kg - batch.weight_kg}, synchronize_session=False)
    cost = payload.price_inr_per_kg * batch.weight_kg
    funded = db.query(BuyerAuthorization).filter(BuyerAuthorization.buyer_id == buyer.id,
        BuyerAuthorization.simulated_escrow_inr >= cost).update(
        {"simulated_escrow_inr": BuyerAuthorization.simulated_escrow_inr - cost}, synchronize_session=False)
    if not (claimed and reserved and funded):
        db.rollback()
        raise HTTPException(409, "auction/capacity/escrow changed; try another eligible buyer")
    bid = AuctionBid(
        id=f"BID-{uuid.uuid4().hex[:8].upper()}", auction_id=auc.id, buyer_id=buyer.id,
        price_inr_per_kg=payload.price_inr_per_kg, kg_requested=payload.kg_requested,
        distance_km=round(d,2), eta_minutes=int((d/30 + 0.25)*60), auto_generated=payload.auto_generated,
        placed_at=dt.datetime.utcnow(),
    )
    db.add(bid); db.flush()
    auc.winning_bid_id = bid.id; auc.status = "Awarded"
    auc.status = "AwaitingConfirmation"
    control = control_for(db, auc)
    control.confirmation_deadline = dt.datetime.utcnow() + dt.timedelta(seconds=settings.CONFIRMATION_WINDOW_SEC)
    db.add(CargoEvent(batch_id=batch.id,kind="awaiting_confirmation",severity="warn",
        description=f"Simulated funds/capacity reserved for {buyer.name}; operator confirmation required. No payout yet."))
    db.commit()
    await get_bus().emit("auction_pending", {"auction_id": auc.id, "batch_id": batch.id})
    return {"status":"awaiting_confirmation", "mode":"simulated",
        "confirmation_deadline":control.confirmation_deadline.isoformat()+"Z"}


@app.post("/api/auctions/{auction_id}/confirm")
async def confirm_auction(auction_id: str, decision: schemas.ConfirmationIn,
                          operator_token: str = Header(default="", alias="X-Operator-Token"),
                          db: OrmSession = Depends(get_db)):
    if not settings.OPERATOR_TOKEN or not secrets.compare_digest(operator_token, settings.OPERATOR_TOKEN):
        raise HTTPException(403, "operator confirmation requires configured X-Operator-Token")
    if not decision.simulated_escrow_acknowledged:
        raise HTTPException(422, "acknowledge this uses simulated escrow, not actual funds")
    lock_writer(db)
    auc = db.get(FlashAuction, auction_id)
    if not auc: raise HTTPException(404, "auction not found")
    if auc.status != "AwaitingConfirmation": raise HTTPException(409, "auction not awaiting confirmation")
    batch = db.get(CargoBatch, auc.batch_id)
    control = control_for(db, auc)
    now = dt.datetime.utcnow()
    unavailable = not batch or batch.status != "DistressedLiquidation" or (batch.life_consumed_pct or 0) >= 100
    if decision.action == "reject" or unavailable or not control.confirmation_deadline or now >= control.confirmation_deadline:
        child = fail_and_retry(db, auc, now, "Operator rejection or unavailable/expired lot")
        db.commit()
        return {"status":"released", "mode":"simulated", "reauction_id":child.id if child else None}
    # Serialized state read + write prevents two confirmations from settling twice.
    control.confirmed_by = decision.operator_name
    control.confirmed_at = now
    payload = db.get(AuctionBid, auc.winning_bid_id)
    if not payload: raise HTTPException(409, "reserved bid missing")
    bid = payload
    buyer = db.get(RegisteredBuyer, bid.buyer_id)
    batch: CargoBatch = db.query(CargoBatch).get(auc.batch_id)
    carrier = db.query(LogisticsCarrier).get(batch.carrier_id) if batch.carrier_id else None
    # Demo-only settlement after simulated escrow reservation; no real money movement
    checkpoint = db.get(TelemetryCheckpoint, batch.id)
    hours_oor = checkpoint.hours_out_of_range if checkpoint else 0
    policy = db.query(InsurancePolicy).filter(InsurancePolicy.batch_id == batch.id).first()
    door_events = db.query(func.count(TelemetrySample.id)).filter(TelemetrySample.batch_id==batch.id, TelemetrySample.door_open==True).scalar() or 0
    carrier_sla = 96.0
    cr = db.get(LogisticsCarrier, batch.carrier_id) if batch.carrier_id else None
    if cr: carrier_sla = cr.sla_compliance_pct
    nums = compute_settlement(
        commodity=batch.commodity, weight_kg=min(batch.weight_kg, payload.kg_requested),
        contract_value_inr=batch.contract_value_inr,
        sum_assured_inr=policy.sum_assured_inr if policy else None,
        cover_pct=policy.cover_pct if policy else settings.INSURANCE_COVER_PCT,
        deductible_pct=policy.deductible_pct if policy else settings.INSURANCE_DEDUCTIBLE_PCT,
        winning_bid_price_inr_per_kg=payload.price_inr_per_kg, kg_cleared=payload.kg_requested,
        life_consumed_pct=batch.life_consumed_pct or 0, hours_out_of_range=hours_oor,
        door_open_events=door_events, carrier_sla_compliance_pct=carrier_sla,
    )
    auc.status = "Settled"
    setl = Settlement(
        id=f"S-{uuid.uuid4().hex[:8].upper()}", batch_id=batch.id, auction_id=auc.id,
        winning_bid_id=bid.id, buyer_id=buyer.id,
        kg_cleared=payload.kg_requested, price_inr_per_kg=payload.price_inr_per_kg,
        salvage_revenue_inr=nums.salvage_revenue_inr, insurance_payout_inr=nums.insurance_payout_inr,
        logistics_penalty_inr=nums.logistics_penalty_inr,
        farmer_total_payout_inr=nums.farmer_total_payout_inr,
        farmer_recovery_pct=nums.farmer_recovery_pct,
        buyer_savings_pct=nums.buyer_savings_pct,
        txn_reference=new_txn_reference(),
    )
    db.add(setl)
    batch.status = "Cleared"; batch.farmer_payout_inr = nums.farmer_total_payout_inr
    # Update policy
    if policy: policy.oracle_verified = True; policy.oracle_payload = nums.oracle_payload
    db.add(CargoEvent(batch_id=batch.id,kind="settled",severity="ok",
                      description=f"DEMO ledger: {payload.kg_requested:.0f}kg awarded to {buyer.name} at ₹{payload.price_inr_per_kg:.0f}/kg — simulated farmer credit ₹{nums.farmer_total_payout_inr:,.0f}; no physical delivery or real payment confirmed"))
    db.commit()
    await get_bus().emit("auction_settled", {
        "auction_id": auc.id, "batch_id": batch.id, "commodity": batch.commodity,
        "buyer_id": buyer.id, "buyer_name": buyer.name,
        "kg_cleared": payload.kg_requested, "price_per_kg": payload.price_inr_per_kg,
        "farmer_payout_rs": nums.farmer_total_payout_inr,
        "salvage_revenue_rs": nums.salvage_revenue_inr,
        "insurance_payout_rs": nums.insurance_payout_inr,
        "logistics_penalty_rs": nums.logistics_penalty_inr,
        "buyer_savings_pct": nums.buyer_savings_pct,
        "txn_reference": setl.txn_reference,
    })
    return {"status":"won","mode":"simulated", "settlement":nums.oracle_payload}


from .api.operations import router as operations_router
app.include_router(operations_router)

# ===== Serve production React frontend =====
FRONTEND_DIST = settings.FRONTEND_DIST
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST/"assets"), name="assets")
    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_catchall(full_path: str):
        # Never let SPA catchall intercept socket.io engine.io paths
        if full_path.startswith("socket.io") or full_path.startswith("engine.io"):
            return JSONResponse({"detail":"not found"}, status_code=404)
        index = FRONTEND_DIST / "index.html"
        if not index.exists():
            return JSONResponse({"error":"frontend not built — run `cd frontend && npm run build`"}, status_code=503)
        return FileResponse(index)
else:
    @app.get("/", include_in_schema=False)
    def not_built():
        return JSONResponse({
            "name":"AetherGrid",
            "message":"Frontend not built yet. Run `cd frontend && npm install && npm run build`.",
            "docs":"/docs",
            "author":"Praveen Sudireddy",
        })


# ===== Socket.IO client-facing events =====
@sio.event
async def connect(sid, environ):
    await sio.emit("hello", {"service":"AetherGrid","author":"Praveen Sudireddy"}, to=sid)


def serve():
    uvicorn.run(asgi_app, host=settings.API_HOST, port=settings.API_PORT, log_level="info")


if __name__ == "__main__":
    serve()
