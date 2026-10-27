"""
AetherGrid Insurance Oracle
===========================
Deterministic, auditable computation of insurance payouts for a
distressed/rescued batch. Replaces the fixed 40% fallback from the
prototype with an actuarial model:

  salvage_revenue        = winning_bid_price × kg_cleared
  expected_revenue       = wholesale_price × weight_kg
  gross_shortfall        = max(0, expected_revenue − salvage_revenue)
  insurance_payout       = min(gross_shortfall, cover_pct × sum_assured)
                           × (1 − deductible_pct)
  logistics_penalty      = contract_value × sla_penalty_mult × abuse_factor
     where abuse_factor = life_consumed_pct × (1 + hours_out_of_range / 24)
                          × (1 if door_open_count==0 else 1.2)
  farmer_shortfall       = expected_revenue − salvage − insurance
  farmer_floor_payout    = farmer_min_recovery_pct × expected_revenue
  final_farmer_payout = salvage + insurance + min(required_floor_topup, penalty)

The 70% floor is a target, NOT guaranteed. No funded market-maker account exists.
`oracle_payload` is mutable database JSON, not a separately signed or immutable
record, and contains no complete binding to all original telemetry signatures.
All payment and insurance outputs here are simulated ledger calculations.

Author: Praveen Sudireddy
"""
from __future__ import annotations
import datetime as dt
import uuid
from dataclasses import dataclass
from typing import Optional

from ..core.config import COMMODITY_PROFILES, settings


@dataclass
class SettlementNumbers:
    salvage_revenue_inr: float
    insurance_payout_inr: float
    logistics_penalty_inr: float
    farmer_total_payout_inr: float
    farmer_recovery_pct: float
    buyer_savings_pct: float
    oracle_payload: dict


def compute_settlement(
    commodity: str,
    weight_kg: float,
    contract_value_inr: float,
    sum_assured_inr: Optional[float],
    cover_pct: float,
    deductible_pct: float,
    winning_bid_price_inr_per_kg: float,
    kg_cleared: float,
    life_consumed_pct: float,
    hours_out_of_range: float,
    door_open_events: int,
    carrier_sla_compliance_pct: float,
) -> SettlementNumbers:
    p = COMMODITY_PROFILES[commodity]
    wholesale = p["wholesale_price_inr_per_kg"]
    expected_revenue = wholesale * weight_kg

    salvage = winning_bid_price_inr_per_kg * kg_cleared
    shortfall = max(0.0, expected_revenue - salvage)

    cover_cap = (sum_assured_inr or contract_value_inr * 0.5) * cover_pct
    insurance_before_deductible = min(shortfall, cover_cap)
    insurance = insurance_before_deductible * (1.0 - deductible_pct)

    # Logistics penalty scales with severity of thermal abuse and carrier SLA history
    sla_factor = max(0.2, (100.0 - carrier_sla_compliance_pct) / 20.0 + 1.0)
    abuse_factor = (life_consumed_pct / 100.0) * (1.0 + hours_out_of_range / 24.0) * \
                   (1.0 if door_open_events == 0 else 1.2)
    penalty = contract_value_inr * 0.05 * abuse_factor * sla_factor * settings.REEFER_MAINT_SLA_VIOLATION_PENALTY_MULT
    penalty = min(penalty, contract_value_inr * 0.30)  # cap at 30% of contract

    # Farmer payout: salvage + insurance, topped up to FARMER_MIN_RECOVERY_PCT if short
    farmer_payout = salvage + insurance
    floor_payout = settings.FARMER_MIN_RECOVERY_PCT * expected_revenue
    # In a live network, the top-up comes from a sector-wide stabilization fund financed by penalties.
    topup = max(0.0, floor_payout - farmer_payout)
    farmer_payout = farmer_payout + min(topup, penalty)

    farmer_recovery_pct = farmer_payout / max(1.0, expected_revenue) * 100.0
    buyer_savings_pct = max(0.0, (wholesale - winning_bid_price_inr_per_kg) / wholesale * 100.0)

    payload = {
        "commodity": commodity,
        "weight_kg": weight_kg,
        "contract_value_inr": contract_value_inr,
        "wholesale_baseline_inr_per_kg": wholesale,
        "expected_revenue_inr": round(expected_revenue, 2),
        "salvage_revenue_inr": round(salvage, 2),
        "shortfall_inr": round(shortfall, 2),
        "insurance_cover_cap_inr": round(cover_cap, 2),
        "insurance_payout_inr": round(insurance, 2),
        "logistics_penalty_inr": round(penalty, 2),
        "farmer_floor_topup_inr": round(min(topup, penalty), 2),
        "farmer_total_payout_inr": round(farmer_payout, 2),
        "farmer_recovery_pct": round(farmer_recovery_pct, 2),
        "buyer_paid_inr_per_kg": round(winning_bid_price_inr_per_kg, 2),
        "buyer_savings_pct": round(buyer_savings_pct, 2),
        "abuse_factor": round(abuse_factor, 3),
        "computed_at": dt.datetime.utcnow().isoformat(),
        "oracle_version": "1.0.0",
        "author": "Praveen Sudireddy",
    }

    return SettlementNumbers(
        salvage_revenue_inr=round(salvage, 2),
        insurance_payout_inr=round(insurance, 2),
        logistics_penalty_inr=round(penalty, 2),
        farmer_total_payout_inr=round(farmer_payout, 2),
        farmer_recovery_pct=round(farmer_recovery_pct, 2),
        buyer_savings_pct=round(buyer_savings_pct, 2),
        oracle_payload=payload,
    )


def new_txn_reference() -> str:
    return "AG-TXN-" + uuid.uuid4().hex[:10].upper()
