"""Shared fail-closed MVP gates. Escrow is a simulated ledger, NOT bank funds.
Full-lot sales only. Travel time is a straight-line heuristic, not road routing.
"""
import math


def rejection_reasons(*, commodity, lot_kg, requested_kg, price, capacity_kg,
                      accepted_commodities, escrow_inr, distance_km,
                      service_radius_km, rescue_radius_km, rvh_hours,
                      approved, expired=False):
    reasons = []
    numbers = (lot_kg, requested_kg, price, capacity_kg, escrow_inr,
               distance_km, service_radius_km, rescue_radius_km, rvh_hours)
    if not all(isinstance(x, (int, float)) and math.isfinite(x) for x in numbers):
        return ['non_finite_or_missing_input']
    if expired: reasons.append('auction_expired')
    if not approved: reasons.append('policy_not_pre_authorized')
    if commodity not in accepted_commodities: reasons.append('commodity_mismatch')
    if lot_kg <= 0 or abs(requested_kg - lot_kg) > 0.001:
        reasons.append('full_lot_required')
    if requested_kg > capacity_kg: reasons.append('insufficient_capacity')
    if price <= 0 or escrow_inr < price * requested_kg:
        reasons.append('insufficient_simulated_escrow')
    if distance_km < 0 or distance_km > min(service_radius_km, rescue_radius_km):
        reasons.append('outside_radius')
    # 30 km/h conservative heuristic + 15 min loading; RVH is itself uncalibrated.
    if rvh_hours <= 0 or distance_km / 30 + 0.25 >= rvh_hours:
        reasons.append('unreachable_before_rvh')
    return reasons


def demo_commodities(kind, all_commodities):
    if kind == 'juice_processor': return ['Alphonso Mango', 'Banana (Yelakki)']
    return list(all_commodities)
