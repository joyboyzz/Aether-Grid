"""
AetherGrid Dynamic Router (Modified-Dijkstra / A*)
==================================================
Given a cargo's current biological state and the road graph,
the router finds the minimum-spoilage path to either:

  1. The ORIGINAL destination (if RVH allows), or
  2. The nearest viable BUYER within rescue radius (flash liquidation), or
  3. The nearest COLD-STORAGE hub for emergency recharging.

Edge weight = (time_hours) * temperature_sensitivity(commodity, current_T)
            + penalty if cellular dead zone, if poor road, if reefer broken.

Because edge weights change with the crate's live temperature (unlike
classic Dijkstra where weights are static), we call this a *thermal
shortest-path* problem and recompute whenever the bio-state changes
materially (ΔT > 1°C or ΔRVH > 1h).

Author: Praveen Sudireddy
"""
from __future__ import annotations
import heapq
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from ..core.config import COMMODITY_PROFILES
import math as _m


EARTH_R_KM = 6371.0


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    phi1, phi2 = _m.radians(lat1), _m.radians(lat2)
    dphi = _m.radians(lat2 - lat1); dlmb = _m.radians(lng2 - lng1)
    a = _m.sin(dphi/2)**2 + _m.cos(phi1)*_m.cos(phi2)*_m.sin(dlmb/2)**2
    return 2 * EARTH_R_KM * _m.asin(_m.sqrt(a))


@dataclass
class RoutePlan:
    plan_type: str                 # "deliver" | "liquidate" | "cold_recharge"
    target_node_id: str
    target_name: str
    target_lat: float
    target_lng: float
    distance_km: float
    ett_hours: float
    expected_spoilage_pct: float
    edge_path: List[str]
    node_path: List[str]
    score: float                   # lower is better
    reason: str

    def as_dict(self) -> dict:
        return {
            "plan_type": self.plan_type,
            "target_id": self.target_node_id,
            "target_name": self.target_name,
            "target_lat": self.target_lat,
            "target_lng": self.target_lng,
            "distance_km": round(self.distance_km, 2),
            "ett_hours": round(self.ett_hours, 2),
            "expected_spoilage_pct": round(self.expected_spoilage_pct, 2),
            "node_path": self.node_path,
            "edge_count": len(self.edge_path),
            "score": round(self.score, 4),
            "reason": self.reason,
        }


class DynamicRouter:
    """Runs on the road graph loaded from route_nodes / route_edges."""

    def __init__(self, nodes: Dict[str, dict], edges: List[dict]):
        self.nodes = nodes
        self.adj: Dict[str, List[dict]] = {}
        for e in edges:
            self.adj.setdefault(e["from_node"], []).append(e)
            # reverse direction for bidirectional edges
            rev = dict(e)
            rev["from_node"], rev["to_node"] = e["to_node"], e["from_node"]
            self.adj.setdefault(rev["from_node"], []).append(rev)

    # ----- edge weighting -----
    def thermal_edge_weight(self, edge: dict, commodity: str, temp_c: float,
                            reefer_broken: bool, life_consumed_frac: float) -> float:
        """
        Returns an edge 'cost' in equivalent biological minutes.
        A stretch that causes faster spoilage gets higher weight.
        """
        hours = edge["distance_km"] / max(5.0, edge["base_speed_kmh"])
        q10 = COMMODITY_PROFILES[commodity]["q10"]
        # Estimate in-transit temp on this edge: if reefer is broken,
        # temp drifts toward ambient along the edge duration
        ambient = 35.0 if edge.get("road_type", "nh") != "urban" else 38.0
        if reefer_broken:
            # asymptotic warm-up with tau ~45 minutes
            tau = 45.0 / 60.0
            proj_temp = ambient - (ambient - temp_c) * math.exp(-hours / tau)
        else:
            proj_temp = temp_c
        avg_temp = (temp_c + proj_temp) / 2.0
        rate_mult = q10 ** ((avg_temp - 5.0) / 10.0)
        # Penalties
        dead_penalty = 1.0 + max(0.0, (100.0 - edge.get("cellular_coverage_pct", 90.0)) / 100.0)  # dead zones add cost
        road_penalty = {"nh": 1.0, "sh": 1.15, "rural": 1.3, "urban": 1.2}.get(edge.get("road_type", "nh"), 1.0)
        risk_penalty = 1.0 + edge.get("accident_risk", 0.0) * 5.0
        # As cargo nears end of life, we penalize high-rate edges harder
        urgency_mult = 1.0 + max(0.0, life_consumed_frac - 0.5) * 2.0
        return hours * rate_mult * dead_penalty * road_penalty * risk_penalty * urgency_mult

    def _nearest_node(self, lat: float, lng: float) -> Tuple[str, float]:
        best, best_d = None, float("inf")
        for nid, n in self.nodes.items():
            d = haversine_km(lat, lng, n["lat"], n["lng"])
            if d < best_d:
                best, best_d = nid, d
        return best, best_d

    def _dijkstra(self, start_id: str, commodity: str, temp_c: float,
                  reefer_broken: bool, life_consumed_frac: float,
                  target_predicate=None) -> Tuple[Dict[str, float], Dict[str, str]]:
        dist = {start_id: 0.0}
        prev = {}
        pq = [(0.0, start_id)]
        visited = set()
        while pq:
            d, u = heapq.heappop(pq)
            if u in visited:
                continue
            visited.add(u)
            if target_predicate and target_predicate(u):
                break
            for e in self.adj.get(u, []):
                v = e["to_node"]
                if v in visited:
                    continue
                w = self.thermal_edge_weight(e, commodity, temp_c, reefer_broken, life_consumed_frac)
                nd = d + w
                if nd < dist.get(v, float("inf")):
                    dist[v] = nd
                    prev[v] = u
                    heapq.heappush(pq, (nd, v))
        return dist, prev

    def _reconstruct(self, prev: Dict[str, str], target: str) -> List[str]:
        path = []
        cur = target
        while cur in prev:
            path.append(cur)
            cur = prev[cur]
        path.append(cur)
        path.reverse()
        return path

    def plan(self, current_lat: float, current_lng: float, commodity: str, temp_c: float,
             reefer_broken: bool, life_consumed_frac: float,
             destination_lat: float, destination_lng: float,
             buyers: List[dict], cold_storages: List[dict]) -> List[RoutePlan]:
        """Return ranked plans (deliver / liquidate / recharge)."""
        start_id, _ = self._nearest_node(current_lat, current_lng)
        target_id, _ = self._nearest_node(destination_lat, destination_lng)

        # Compute shortest thermal-cost paths to ALL nodes
        dist, prev = self._dijkstra(start_id, commodity, temp_c, reefer_broken, life_consumed_frac)

        plans: List[RoutePlan] = []

        # Plan A: deliver to original destination
        if target_id in dist:
            node_path = self._reconstruct(prev, target_id)
            # Geometric distance for ETT display
            km_remaining = haversine_km(current_lat, current_lng, destination_lat, destination_lng)
            ett = km_remaining / 45.0
            expected_spoilage_pct = min(100.0, life_consumed_frac * 100 + (dist[target_id] / COMMODITY_PROFILES[commodity]["shelf_hours_ref"]) * 100)
            plans.append(RoutePlan(
                plan_type="deliver", target_node_id=target_id,
                target_name=self.nodes[target_id]["name"],
                target_lat=destination_lat, target_lng=destination_lng,
                distance_km=km_remaining, ett_hours=ett,
                expected_spoilage_pct=expected_spoilage_pct,
                edge_path=[], node_path=node_path, score=dist[target_id],
                reason="Original destination reachable within biological budget"
                     if expected_spoilage_pct < 100 else "Will spoil before arrival",
            ))

        # Plan B: liquidate to best nearby buyer (lowest thermal cost)
        best_buyer = None
        for b in buyers:
            nid, _ = self._nearest_node(b["lat"], b["lng"])
            if nid not in dist:
                continue
            # Buyer rank weighted by offered price premium (we pick fastest-to-reach buyer with sufficient capacity)
            score = dist[nid] - 2.0  # buyers are preferred (discount to encourage rescue)
            if best_buyer is None or score < best_buyer["score"]:
                best_buyer = {"buyer": b, "nid": nid, "score": score}
        if best_buyer:
            b = best_buyer["buyer"]
            km = haversine_km(current_lat, current_lng, b["lat"], b["lng"])
            ett = km / 50.0
            node_path = self._reconstruct(prev, best_buyer["nid"])
            plans.append(RoutePlan(
                plan_type="liquidate", target_node_id=b["id"],
                target_name=b["name"],
                target_lat=b["lat"], target_lng=b["lng"],
                distance_km=km, ett_hours=ett,
                expected_spoilage_pct=life_consumed_frac*100 + ett*1.2,  # minimal extra spoilage
                edge_path=[], node_path=node_path, score=best_buyer["score"],
                reason=f"Geo-liquidate to {b['kind']} within 45 km",
            ))

        # Plan C: emergency cold-storage recharge
        best_cs = None
        for cs in cold_storages:
            nid, _ = self._nearest_node(cs["lat"], cs["lng"])
            if nid not in dist:
                continue
            score = dist[nid] - 1.0
            if best_cs is None or score < best_cs["score"]:
                best_cs = {"cs": cs, "nid": nid, "score": score}
        if best_cs and reefer_broken:
            c = best_cs["cs"]
            km = haversine_km(current_lat, current_lng, c["lat"], c["lng"])
            ett = km / 50.0
            node_path = self._reconstruct(prev, best_cs["nid"])
            plans.append(RoutePlan(
                plan_type="cold_recharge", target_node_id=c["id"],
                target_name=c["name"],
                target_lat=c["lat"], target_lng=c["lng"],
                distance_km=km, ett_hours=ett,
                expected_spoilage_pct=life_consumed_frac*100,
                edge_path=[], node_path=node_path, score=best_cs["score"],
                reason="Emergency cold-storage: reefer failure, recharge to rescue cargo",
            ))

        # Sort by score (lowest cost first)
        plans.sort(key=lambda p: p.score)
        return plans
