"""
AetherGrid Bio-Timer Engine v2
==============================
Biologically grounded real-time Remaining Viable Hours (RVH) calculator.

Model
-----
The engine accumulates *life consumed* as a path integral of the
instantaneous spoilage rate r(T,h,E), where:

    r(T,h,E) = q10^((T - T_ref)/10)  *  f_hum(h)  *  f_eth(E)

- T_ref = 5°C, per standard cold-chain reference.
- q10 = 2.5–3.5 depending on commodity (Taoukis et al. 1999).
- Humidity stress f_hum(h):
    - h in [85,93] % → 1.0 (optimal)
    - h < 70%  → 1 + (70 - h)/70     (wilting / weight loss)
    - h > 95%  → 1 + (h - 95)/30     (mould / bacterial rot)
- Ethylene acceleration f_eth(E) = 1 + k_eth * log10(1 + E/10)
    where k_eth is commodity-specific. Models the autocatalytic
    climacteric ripening burst.

At every telemetry tick we integrate r·Δt / L_ref to get total life
consumed fraction (0 = fresh, 1 = spoiled).

Author: Praveen Sudireddy
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..core.config import COMMODITY_PROFILES


@dataclass
class BioSnapshot:
    commodity: str
    rvh_hours_at_optimal_temp: float   # remaining hours IF moved to optimal temp immediately
    spoilage_eta_hours_at_current_temp: float
    life_consumed_fraction: float       # 0..1.5
    life_consumed_pct: float
    current_temp_c: float
    current_humidity_pct: float
    current_ethylene_ppm: float
    current_decay_rate_mult: float
    health: str                         # fresh | aging | critical | spoiled
    time_to_distress_hours: float       # when we cross threshold *if rates stay*

    def as_dict(self) -> dict:
        return {
            "commodity": self.commodity,
            "rvh_hours": round(self.rvh_hours_at_optimal_temp, 2),
            "spoil_eta_hours": round(self.spoilage_eta_hours_at_current_temp, 2),
            "life_consumed_pct": round(self.life_consumed_pct, 2),
            "temp_c": round(self.current_temp_c, 2),
            "humidity_pct": round(self.current_humidity_pct, 1),
            "ethylene_ppm": round(self.current_ethylene_ppm, 2),
            "decay_rate_mult": round(self.current_decay_rate_mult, 2),
            "health": self.health,
            "time_to_distress_hours": round(self.time_to_distress_hours, 2) if math.isfinite(self.time_to_distress_hours) else None,
        }


class BioTimer:
    """Per-batch stateful integrator."""

    def __init__(self, commodity: str):
        if commodity not in COMMODITY_PROFILES:
            raise ValueError(f"Unknown commodity: {commodity}")
        self.commodity = commodity
        p = COMMODITY_PROFILES[commodity]
        self.shelf_hours_ref: float = p["shelf_hours_ref"]
        self.q10: float = p["q10"]
        self.opt_temp_c: float = p["opt_temp_c"]
        self.eth_sensitivity: float = p["eth_sensitivity"]
        self.t_ref_c: float = 5.0
        # life_consumed ∈ [0, 1+], 1.0 = end of usable life
        self.life_consumed: float = 0.0
        # Running maxima (used for insurance forensics)
        self.max_temp_c: float = 0.0
        self.max_ethylene_ppm: float = 0.0
        self.hours_out_of_range: float = 0.0

    # ------------- decay kinetics -------------
    def _temp_mult(self, temp_c: float) -> float:
        return self.q10 ** ((temp_c - self.t_ref_c) / 10.0)

    @staticmethod
    def _humidity_mult(h: float) -> float:
        if 85.0 <= h <= 93.0:
            return 1.0
        if h < 70.0:
            return 1.0 + (70.0 - h) / 70.0
        if h > 95.0:
            return 1.0 + (h - 95.0) / 30.0
        # 70-85: slight suboptimal
        if h < 85.0:
            return 1.0 + (85.0 - h) / 200.0
        # 93-95: near-mould
        return 1.0 + (h - 93.0) / 60.0

    def _ethylene_mult(self, eth_ppm: float) -> float:
        # Ethylene acts on a log scale; 1ppm ≈ baseline, 100ppm ≈ ~2-3x acceleration
        return 1.0 + self.eth_sensitivity * math.log10(1.0 + eth_ppm / 10.0)

    def decay_rate(self, temp_c: float, h: float, eth_ppm: float) -> float:
        return self._temp_mult(temp_c) * self._humidity_mult(h) * self._ethylene_mult(eth_ppm)

    # ------------- integration -------------
    def apply_interval(self, temp_c: float, humidity_pct: float, eth_ppm: float,
                       hours: float, door_open: bool = False) -> float:
        """Accrue `hours` hours of exposure. Returns rate multiplier used."""
        rate = self.decay_rate(temp_c, humidity_pct, eth_ppm)
        # Door open events: instantaneous thermal shock (5x rate for the duration)
        if door_open:
            rate *= 5.0
        self.life_consumed += (rate * hours) / self.shelf_hours_ref
        self.life_consumed = min(self.life_consumed, 1.5)
        self.max_temp_c = max(self.max_temp_c, temp_c)
        self.max_ethylene_ppm = max(self.max_ethylene_ppm, eth_ppm)
        if temp_c > COMMODITY_PROFILES[self.commodity]["max_safe_temp_c"]:
            self.hours_out_of_range += hours
        return rate

    # ------------- forecasts -------------
    def remaining_hours_at(self, temp_c: float, h: float, eth_ppm: float) -> float:
        remaining = max(0.0, 1.0 - self.life_consumed)
        if remaining <= 0.0:
            return 0.0
        rate = self.decay_rate(temp_c, h, eth_ppm)
        if rate <= 0:
            return float("inf")
        return (remaining * self.shelf_hours_ref) / rate

    def rvh_optimistic(self) -> float:
        """Best-case RVH if cargo is moved to optimal conditions now."""
        remaining = max(0.0, 1.0 - self.life_consumed)
        if remaining <= 0:
            return 0.0
        rate_opt = self._temp_mult(self.opt_temp_c) * 1.0 * self._ethylene_mult(0.1)
        return (remaining * self.shelf_hours_ref) / rate_opt

    def classify_health(self) -> str:
        p = self.life_consumed
        if p < 0.35:
            return "fresh"
        if p < 0.65:
            return "aging"
        if p < 0.95:
            return "critical"
        return "spoiled"

    def time_until_distress(self, current_temp_c, h, eth_ppm, ett_primary_hours: float,
                            panic_mult: float) -> float:
        """
        Predicts hours until RVH(t) drops below panic_mult * ETT.
        ETT shrinks as the truck moves, so for the next planning window
        we approximate ETT decreasing linearly at truck speed.
        Solve the ODE numerically (simple Euler) with Δt=5min steps.
        """
        dt = 5.0 / 60.0
        sim_life = self.life_consumed
        sim_ett = ett_primary_hours
        rate = self.decay_rate(current_temp_c, h, eth_ppm)
        for i in range(1, int(24 * 12) + 1):  # up to 24h out
            sim_life += (rate * dt) / self.shelf_hours_ref
            sim_ett = max(0.0, sim_ett - dt)
            remaining = max(0.0, 1.0 - sim_life)
            rvh_now = (remaining * self.shelf_hours_ref) / rate if remaining > 0 else 0.0
            if rvh_now < panic_mult * sim_ett or sim_life >= 1.0:
                return i * dt
        return float("inf")

    def snapshot(self, temp_c: float, humidity_pct: float, eth_ppm: float,
                 ett_hours: float, panic_mult: float) -> BioSnapshot:
        rate = self.decay_rate(temp_c, humidity_pct, eth_ppm)
        remaining = max(0.0, 1.0 - self.life_consumed)
        eta_spoil = (remaining * self.shelf_hours_ref) / rate if rate > 0 and remaining > 0 else 0.0
        rvh_opt = self.rvh_optimistic()
        health = self.classify_health()
        ttd = self.time_until_distress(temp_c, humidity_pct, eth_ppm, ett_hours, panic_mult)
        return BioSnapshot(
            commodity=self.commodity,
            rvh_hours_at_optimal_temp=rvh_opt,
            spoilage_eta_hours_at_current_temp=eta_spoil,
            life_consumed_fraction=self.life_consumed,
            life_consumed_pct=self.life_consumed * 100.0,
            current_temp_c=temp_c,
            current_humidity_pct=humidity_pct,
            current_ethylene_ppm=eth_ppm,
            current_decay_rate_mult=rate,
            health=health,
            time_to_distress_hours=ttd,
        )
