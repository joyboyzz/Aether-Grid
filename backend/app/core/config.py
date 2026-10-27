"""
AetherGrid Configuration
========================
All constants, calibration values, and production tunables live here.
Biological parameters are prototype heuristics; exact provenance and field
calibration remain unverified. See the evidence-led technical report.

Author: Praveen Sudireddy
"""
from __future__ import annotations
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "AetherGrid"
    APP_VERSION: str = "1.0.0"
    ENV: str = "demo"

    # Paths
    ROOT: Path = Path(__file__).resolve().parent.parent.parent
    DATA_DIR: Path = ROOT / "data"
    FRONTEND_DIST: Path = ROOT.parent / "frontend" / "dist"
    STATIC_DIR: Path = ROOT.parent / "frontend" / "public"
    DB_PATH: Path = DATA_DIR / "aethergrid.db"

    # Network
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    CORS_ORIGINS: list[str] = ["*"]

    # Security (HSM/mTLS simulation; rotate per crate in production)
    HSM_SECRET: str = "aethergrid-hsm-root-secret-praveen-sudireddy-2026"
    AUTH_PRINCIPALS: list[dict] = []  # sha256, subject, role; optional buyer_id/truck_id
    MTLS_REQUIRED: bool = True
    ATTESTATION_TOLERANCE_SEC: int = 120  # reject packets older than 2 min (anti-replay)

    # Geo-liquidation
    DISTRESSED_RADIUS_KM: float = 80.0
    RVH_PANIC_MULTIPLIER: float = 3.0   # trigger when RVH < multiplier * ETT and reefer trouble detected
    AUCTION_WINDOW_MIN: int = 15
    MIN_BIDDERS_FOR_COMPETITION: int = 1
    CONFIRMATION_WINDOW_SEC: int = 120
    REAUCTION_WINDOW_SEC: int = 120
    MAX_REAUCTIONS: int = 2
    # Required for manual confirmation; empty = confirmation disabled, fail closed.
    OPERATOR_TOKEN: str = ""
    SANDBOX_WEBHOOK_SECRET: str = ""

    # Insurance oracle (productized parameters; loaded live from an oracle in prod)
    INSURANCE_COVER_PCT: float = 0.45
    INSURANCE_DEDUCTIBLE_PCT: float = 0.05
    REEFER_MAINT_SLA_VIOLATION_PENALTY_MULT: float = 2.0
    FARMER_MIN_RECOVERY_PCT: float = 0.70  # target only; top-up is limited to available simulated penalty

    # Routing
    AVG_TRUCK_SPEED_KMH: float = 42.0
    TRAFFIC_PENALTY_MULT: float = 1.35
    REROUTE_PLAN_HORIZON_KM: float = 100.0

    # Simulation defaults
    SIM_BIO_HOURS_PER_PACKET: float = 0.5 / 60.0  # explicit accelerated demo clock, not device elapsed time
    SIM_TRUCKS: int = 36
    SIM_TICK_SEC: float = 0.5
    SIM_KM_PER_TICK: float = 0.7

    class Config:
        env_prefix = "AG_"
        env_file = ".env"


settings = Settings()
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# Commodity kinetic profiles (Q10 + shelf life at reference)
# Source: Taoukis et al. (1999); USDA ARS Cold Chain Handbook;
#         Nanda et al. (2012) "Postharvest profile of Alphonso mango".
# ============================================================
COMMODITY_PROFILES: dict[str, dict] = {
    "Alphonso Mango": {
        "shelf_hours_ref": 264,      # shelf at 5°C
        "q10": 2.8,
        "opt_temp_c": 12.0,
        "max_safe_temp_c": 18.0,
        "eth_sensitivity": 1.4,      # ethylene strongly accelerates ripening
        "wholesale_price_inr_per_kg": 120,
        "unit": "crate",
        "crate_kg": 20,
    },
    "Tomato": {
        "shelf_hours_ref": 360,
        "q10": 2.5,
        "opt_temp_c": 10.0,
        "max_safe_temp_c": 21.0,
        "eth_sensitivity": 1.2,
        "wholesale_price_inr_per_kg": 25,
        "unit": "crate",
        "crate_kg": 25,
    },
    "Dairy (Peda)": {
        "shelf_hours_ref": 48,
        "q10": 3.5,
        "opt_temp_c": 4.0,
        "max_safe_temp_c": 10.0,
        "eth_sensitivity": 1.0,
        "wholesale_price_inr_per_kg": 180,
        "unit": "box",
        "crate_kg": 10,
    },
    "Seafood (Pomfret)": {
        "shelf_hours_ref": 84,
        "q10": 3.2,
        "opt_temp_c": 0.0,
        "max_safe_temp_c": 4.4,
        "eth_sensitivity": 1.0,
        "wholesale_price_inr_per_kg": 420,
        "unit": "tote",
        "crate_kg": 30,
    },
    "Leafy Greens (Palak)": {
        "shelf_hours_ref": 108,
        "q10": 3.0,
        "opt_temp_c": 2.0,
        "max_safe_temp_c": 12.0,
        "eth_sensitivity": 1.3,
        "wholesale_price_inr_per_kg": 32,
        "unit": "crate",
        "crate_kg": 15,
    },
    "Banana (Yelakki)": {
        "shelf_hours_ref": 288,
        "q10": 2.6,
        "opt_temp_c": 13.0,
        "max_safe_temp_c": 20.0,
        "eth_sensitivity": 1.8,   # very ethylene-sensitive
        "wholesale_price_inr_per_kg": 45,
        "unit": "crate",
        "crate_kg": 20,
    },
    "Poultry (Chicken)": {
        "shelf_hours_ref": 96,
        "q10": 3.4,
        "opt_temp_c": 0.0,
        "max_safe_temp_c": 4.4,
        "eth_sensitivity": 1.0,
        "wholesale_price_inr_per_kg": 190,
        "unit": "tote",
        "crate_kg": 25,
    },
}
