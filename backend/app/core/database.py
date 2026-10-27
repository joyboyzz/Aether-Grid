"""
Database layer — SQLAlchemy ORM with SQLite (prototype) /
SQL Server (production). Spatial queries use portable helpers
that map to GEOGRAPHY.STDistance/STBuffer on SQL Server.

Author: Praveen Sudireddy
"""
from __future__ import annotations
import datetime as dt
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import (
    create_engine, Column, Integer, String, Float, DateTime, Boolean,
    ForeignKey, Text, UniqueConstraint, Index, JSON, event
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, Session

from .config import settings

Base = declarative_base()


# ============================================================
# Domain Models
# ============================================================
class Farmer(Base):
    __tablename__ = "farmers"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    phone = Column(String)
    village = Column(String)
    district = Column(String)
    state = Column(String)
    upi = Column(String)
    created_at = Column(DateTime, default=dt.datetime.utcnow)


class LogisticsCarrier(Base):
    __tablename__ = "logistics_carriers"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    iata_gstn = Column(String)
    hsm_serial_prefix = Column(String, nullable=False)
    sla_compliance_pct = Column(Float, default=98.0)
    created_at = Column(DateTime, default=dt.datetime.utcnow)


class Truck(Base):
    __tablename__ = "trucks"
    id = Column(String, primary_key=True)      # TRK-####
    carrier_id = Column(String, ForeignKey("logistics_carriers.id"), nullable=False)
    driver_name = Column(String)
    driver_phone = Column(String)
    reefer_model = Column(String)
    hsm_serial = Column(String, unique=True, nullable=False)
    last_heartbeat = Column(DateTime)
    # current live state (denormalized for dashboard)
    lat = Column(Float)
    lng = Column(Float)
    temp_c = Column(Float)
    humidity_pct = Column(Float)
    ethylene_ppm = Column(Float)
    reefer_healthy = Column(Boolean, default=True)
    created_at = Column(DateTime, default=dt.datetime.utcnow)


class RegisteredBuyer(Base):
    __tablename__ = "registered_buyers"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    kind = Column(String, nullable=False)  # wholesaler | restaurant | juice_processor | cold_storage | supermarket | distributor
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    service_radius_km = Column(Float, default=50.0)
    capacity_kg = Column(Float, default=5000.0)
    gstn = Column(String)
    contact_phone = Column(String)
    upi = Column(String)
    auto_bid_ceiling_pct = Column(Float, default=75.0)  # max % of wholesale this buyer will auto-bid
    created_at = Column(DateTime, default=dt.datetime.utcnow)


class BuyerAuthorization(Base):
    """Demo pre-authorization and escrow balances. Never actual funds."""
    __tablename__ = "buyer_authorizations"
    buyer_id = Column(String, ForeignKey("registered_buyers.id"), primary_key=True)
    accepted_commodities = Column(JSON, nullable=False)
    simulated_escrow_inr = Column(Float, default=0.0, nullable=False)
    pre_authorized = Column(Boolean, default=False, nullable=False)
    mode = Column(String, default="simulated", nullable=False)


class TelemetryCheckpoint(Base):
    __tablename__ = "telemetry_checkpoints"
    batch_id = Column(String, primary_key=True)
    life_consumed = Column(Float, nullable=False)
    max_temp_c = Column(Float, nullable=False)
    max_ethylene_ppm = Column(Float, nullable=False)
    hours_out_of_range = Column(Float, nullable=False)


class TelemetryBaseline(Base):
    __tablename__ = "telemetry_baselines"
    batch_id = Column(String, primary_key=True)
    reference_timestamp = Column(Integer, nullable=False)
    reference = Column(String, nullable=False, unique=True)
    asserted_by = Column(String, nullable=False)
    evidence_note = Column(Text, nullable=False)


class ReceiverCursor(Base):
    __tablename__ = "receiver_cursors"
    truck_id = Column(String, primary_key=True)
    sequence = Column(Integer, nullable=False)
    timestamp = Column(Integer, nullable=False)


class DeliveryConfirmation(Base):
    __tablename__ = "delivery_confirmations"
    batch_id = Column(String, primary_key=True)
    buyer_id = Column(String, nullable=False)
    received_kg = Column(Float, nullable=False)
    external_reference = Column(String, nullable=False, unique=True)
    recorded_by = Column(String, nullable=False)
    confirmed_at = Column(DateTime, default=dt.datetime.utcnow)
    # This is an operator-entered assertion, not independent physical verification.
    evidence_note = Column(Text, nullable=False)


class ExternalIntent(Base):
    __tablename__ = "external_intents"
    idempotency_key = Column(String, primary_key=True)
    batch_id = Column(String, nullable=False)
    kind = Column(String, nullable=False)
    amount_paise = Column(Integer, nullable=False)
    mode = Column(String, nullable=False, default="sandbox")
    status = Column(String, nullable=False, default="dry_run_only")
    created_at = Column(DateTime, default=dt.datetime.utcnow)


class ProviderEvent(Base):
    __tablename__ = "provider_events"
    event_id = Column(String, primary_key=True)
    payload_sha256 = Column(String, nullable=False)
    idempotency_key = Column(String, nullable=False)


class CargoBatch(Base):
    __tablename__ = "cargo_batches"
    id = Column(String, primary_key=True)
    commodity = Column(String, nullable=False)
    farmer_id = Column(String, ForeignKey("farmers.id"))
    carrier_id = Column(String, ForeignKey("logistics_carriers.id"))
    truck_id = Column(String, ForeignKey("trucks.id"))

    origin_name = Column(String, nullable=False)
    origin_lat = Column(Float, nullable=False)
    origin_lng = Column(Float, nullable=False)
    destination_name = Column(String, nullable=False)
    dest_lat = Column(Float, nullable=False)
    dest_lng = Column(Float, nullable=False)

    weight_kg = Column(Float, nullable=False)
    contract_value_inr = Column(Float, nullable=False)
    farmer_payout_inr = Column(Float, default=0.0)

    status = Column(String, default="InTransit", nullable=False, index=True)
    # InTransit | DistressedLiquidation | Delivered | Spoiled | Cleared | Rerouted

    current_lat = Column(Float)
    current_lng = Column(Float)
    current_route_node_id = Column(String)
    rvh_hours = Column(Float)
    ett_hours = Column(Float)
    ett_to_original_dest_hours = Column(Float)
    life_consumed_pct = Column(Float, default=0.0)
    health = Column(String, default="fresh")
    current_temp_c = Column(Float)
    max_temp_experienced_c = Column(Float, default=0.0)
    eth_exposure_peak_ppm = Column(Float, default=0.0)
    deadzone_minutes = Column(Float, default=0.0)
    reroute_count = Column(Integer, default=0)

    planned_route_km = Column(Float, default=0.0)
    traveled_km = Column(Float, default=0.0)

    created_at = Column(DateTime, default=dt.datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)
    delivered_at = Column(DateTime)

    telemetry = relationship("TelemetrySample", back_populates="batch",
                             cascade="all,delete-orphan", lazy="dynamic")
    auctions = relationship("FlashAuction", back_populates="batch",
                            cascade="all,delete-orphan")
    events = relationship("CargoEvent", back_populates="batch",
                          cascade="all,delete-orphan")


class TelemetrySample(Base):
    __tablename__ = "telemetry_samples"
    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(String, ForeignKey("cargo_batches.id"), nullable=False, index=True)
    truck_id = Column(String, ForeignKey("trucks.id"), nullable=False, index=True)
    ts = Column(DateTime, default=dt.datetime.utcnow, index=True)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    temp_c = Column(Float, nullable=False)
    humidity_pct = Column(Float, nullable=False)
    ethylene_ppm = Column(Float, nullable=False)
    speed_kmh = Column(Float, default=0.0)
    reefer_setpoint_c = Column(Float)
    door_open = Column(Boolean, default=False)
    fuel_level_pct = Column(Float)
    cellular_rssi = Column(Float)
    in_dead_zone = Column(Boolean, default=False)
    # Zero-trust attestation block
    hsm_signature = Column(String, nullable=False)
    attestation_ok = Column(Boolean, default=True)
    attestation_failure_reason = Column(String)
    seq_number = Column(Integer, default=0)  # per-truck monotonic counter
    batch = relationship("CargoBatch", back_populates="telemetry")


class CargoEvent(Base):
    __tablename__ = "cargo_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(String, ForeignKey("cargo_batches.id"), nullable=False, index=True)
    ts = Column(DateTime, default=dt.datetime.utcnow, index=True)
    kind = Column(String, nullable=False)  # reefer_failure | reefer_restored | distressed | auction_opened | bid_received | settled | delivered | spoiled | rerouted | spoof_rejected
    severity = Column(String, default="info")  # info | warn | critical | ok
    description = Column(Text)
    metadata_json = Column(JSON)
    batch = relationship("CargoBatch", back_populates="events")


class FlashAuction(Base):
    __tablename__ = "flash_auctions"
    id = Column(String, primary_key=True)
    batch_id = Column(String, ForeignKey("cargo_batches.id"), nullable=False)
    opened_at = Column(DateTime, default=dt.datetime.utcnow)
    closes_at = Column(DateTime, nullable=False)
    status = Column(String, default="Open", index=True)  # Open | Awarded | Settled | Expired
    trigger_lat = Column(Float, nullable=False)
    trigger_lng = Column(Float, nullable=False)
    trigger_rvh_hours = Column(Float)
    trigger_temp_c = Column(Float)
    trigger_life_pct = Column(Float)
    winning_bid_id = Column(String, ForeignKey("auction_bids.id"))
    batch = relationship("CargoBatch", back_populates="auctions")
    bids = relationship("AuctionBid", back_populates="auction",
                        cascade="all,delete-orphan", foreign_keys="AuctionBid.auction_id")


class AuctionControl(Base):
    """Additive lifecycle state; avoids ALTER TABLE of historical auctions."""
    __tablename__ = "auction_controls"
    auction_id = Column(String, ForeignKey("flash_auctions.id"), primary_key=True)
    attempt = Column(Integer, nullable=False, default=0)
    parent_auction_id = Column(String)
    confirmation_deadline = Column(DateTime)
    confirmed_by = Column(String)
    confirmed_at = Column(DateTime)


class AuctionBid(Base):
    __tablename__ = "auction_bids"
    id = Column(String, primary_key=True)
    auction_id = Column(String, ForeignKey("flash_auctions.id"), nullable=False, index=True)
    buyer_id = Column(String, ForeignKey("registered_buyers.id"), nullable=False)
    placed_at = Column(DateTime, default=dt.datetime.utcnow)
    price_inr_per_kg = Column(Float, nullable=False)
    kg_requested = Column(Float, nullable=False)
    distance_km = Column(Float)
    eta_minutes = Column(Integer)
    buyer_rating = Column(Float, default=4.5)
    auto_generated = Column(Boolean, default=False)
    auction = relationship("FlashAuction", back_populates="bids", foreign_keys=[auction_id])
    buyer = relationship("RegisteredBuyer")


class Settlement(Base):
    __tablename__ = "settlements"
    id = Column(String, primary_key=True)
    batch_id = Column(String, ForeignKey("cargo_batches.id"), nullable=False, index=True)
    auction_id = Column(String, ForeignKey("flash_auctions.id"), nullable=False)
    winning_bid_id = Column(String, ForeignKey("auction_bids.id"))
    buyer_id = Column(String, ForeignKey("registered_buyers.id"))
    kg_cleared = Column(Float)
    price_inr_per_kg = Column(Float)
    salvage_revenue_inr = Column(Float)
    insurance_payout_inr = Column(Float)
    logistics_penalty_inr = Column(Float)
    farmer_total_payout_inr = Column(Float)
    farmer_recovery_pct = Column(Float)
    buyer_savings_pct = Column(Float)
    settled_at = Column(DateTime, default=dt.datetime.utcnow)
    txn_reference = Column(String)


class RouteNode(Base):
    __tablename__ = "route_nodes"
    id = Column(String, primary_key=True)
    corridor = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    node_kind = Column(String, default="waypoint")  # origin | city | checkpoint | warehouse | destination
    has_cold_storage = Column(Boolean, default=False)
    population_2023 = Column(Integer)


class RouteEdge(Base):
    __tablename__ = "route_edges"
    id = Column(String, primary_key=True)
    corridor = Column(String, nullable=False, index=True)
    from_node = Column(String, ForeignKey("route_nodes.id"), nullable=False)
    to_node = Column(String, ForeignKey("route_nodes.id"), nullable=False)
    distance_km = Column(Float, nullable=False)
    base_speed_kmh = Column(Float, default=50.0)
    road_type = Column(String, default="nh")  # nh | sh | rural | urban
    cellular_coverage_pct = Column(Float, default=85.0)
    accident_risk = Column(Float, default=0.02)
    notes = Column(Text)
    UniqueConstraint("from_node", "to_node")


class InsurancePolicy(Base):
    __tablename__ = "insurance_policies"
    id = Column(String, primary_key=True)
    batch_id = Column(String, ForeignKey("cargo_batches.id"), nullable=False, unique=True)
    policy_no = Column(String)
    sum_assured_inr = Column(Float)
    premium_paid_inr = Column(Float)
    deductible_pct = Column(Float, default=0.05)
    cover_pct = Column(Float, default=0.45)
    oracle_verified = Column(Boolean, default=False)
    oracle_payload = Column(JSON)
    created_at = Column(DateTime, default=dt.datetime.utcnow)


# Indexes
Index("ix_telemetry_batch_ts", TelemetrySample.batch_id, TelemetrySample.ts.desc())
Index("ix_batches_status", CargoBatch.status)


# ============================================================
# Engine / Session
# ============================================================
def make_engine():
    settings.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{settings.DB_PATH}",
        echo=False,
        connect_args={"check_same_thread": False, "timeout": 30},
        future=True,
        pool_pre_ping=True,
    )
    return engine


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@contextmanager
def session_scope() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db():
    # Enable WAL mode for concurrent reads during live simulation
    with engine.begin() as conn:
        conn.exec_driver_sql("PRAGMA journal_mode=WAL;")
        conn.exec_driver_sql("PRAGMA synchronous=FULL;" if settings.ENV=="production" else "PRAGMA synchronous=NORMAL;")
    Base.metadata.create_all(engine)


# -------- Load spatial extension on platforms that support it (best-effort) --------
@event.listens_for(engine, "connect")
def _load_spatialite(dbapi_conn, connection_record):
    try:
        dbapi_conn.enable_load_extension(True)
        dbapi_conn.load_extension("mod_spatialite")
        dbapi_conn.execute("SELECT InitSpatialMetaData(1);")
    except Exception:
        # Spatialite not present — pure-Python Haversine fallback is used.
        pass
