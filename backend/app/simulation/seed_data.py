"""
Synthetic demonstration seed data for the AetherGrid Indian demo corridor.

Corridor: NH-44 (formerly NH-7 / North-South Corridor)
          Delhi → Agra → Gwalior → Jhansi → Lalitpur → Nagpur →
          Adilabad → Nizamabad → Hyderabad → Kurnool → Anantapur →
          Doddaballapur → Bengaluru

Also includes:
  - 36 registered B2B buyers (mandis, cold storages, juice processors,
    supermarkets, restaurant collectives, distributors)
  - Illustrative cellular dead zones (coverage not verified)
  - Known cold-storage hubs (emergency recharge candidates)
  - Placeholder commodity prices (not verified market observations)

Author: Praveen Sudireddy
"""
from __future__ import annotations
import uuid
from typing import List, Tuple, Dict


# ------------------------------------------------------------
# NH-44 route nodes (major waypoints)
# ------------------------------------------------------------
ROUTE_NODES: List[Dict] = [
    {"id": "N-DEL", "name": "Delhi (Azadpur Mandi)",   "lat": 28.7076, "lng": 77.1689, "kind": "origin", "pop": 32_000_000},
    {"id": "N-FBD", "name": "Faridabad Toll",          "lat": 28.4089, "lng": 77.3178, "kind": "checkpoint"},
    {"id": "N-AGR", "name": "Agra",                    "lat": 27.1767, "lng": 78.0081, "kind": "city", "pop": 1_600_000},
    {"id": "N-GWL", "name": "Gwalior",                 "lat": 26.2183, "lng": 78.1828, "kind": "city", "pop": 1_100_000, "cold": True},
    {"id": "N-JHS", "name": "Jhansi",                  "lat": 25.4484, "lng": 78.5685, "kind": "city", "pop": 500_000},
    {"id": "N-LAL", "name": "Lalitpur",                "lat": 23.8314, "lng": 78.7378, "kind": "checkpoint"},
    {"id": "N-SGR", "name": "Sagar",                   "lat": 23.8388, "lng": 78.7367, "kind": "checkpoint"},
    {"id": "N-NGP", "name": "Nagpur (Kalamna)",        "lat": 21.1739, "lng": 79.0663, "kind": "city", "pop": 2_900_000, "cold": True},
    {"id": "N-WRD", "name": "Wardha",                  "lat": 20.7453, "lng": 78.6022, "kind": "checkpoint"},
    {"id": "N-ADB", "name": "Adilabad",                "lat": 19.6640, "lng": 78.5320, "kind": "city", "pop": 120_000},
    {"id": "N-NZB", "name": "Nizamabad",               "lat": 18.6725, "lng": 78.1050, "kind": "city", "pop": 310_000},
    {"id": "N-KMM", "name": "Kamareddy",               "lat": 18.3195, "lng": 78.3386, "kind": "checkpoint"},
    {"id": "N-HYD", "name": "Hyderabad (Bowenpally)",  "lat": 17.4800, "lng": 78.4800, "kind": "city", "pop": 10_500_000, "cold": True},
    {"id": "N-KRN", "name": "Kurnool",                 "lat": 15.8281, "lng": 78.0373, "kind": "city", "pop": 480_000},
    {"id": "N-ATP", "name": "Anantapur",               "lat": 14.6819, "lng": 77.6006, "kind": "city", "pop": 370_000},
    {"id": "N-DBP", "name": "Doddaballapur",           "lat": 13.6288, "lng": 77.5917, "kind": "checkpoint"},
    {"id": "N-BLR", "name": "Bengaluru (Yeshwanthpur)","lat": 13.0296, "lng": 77.5457, "kind": "destination", "pop": 13_600_000, "cold": True},
]


def _edges_from_nodes() -> List[Dict]:
    """Create edges between consecutive nodes with realistic metadata."""
    import math as _m
    edges = []
    # per-stretch attributes: (speed_kmh, road_type, coverage_pct, risk, note)
    stretch_meta = [
        (70, "nh", 92, 0.01, "Delhi-Agra expressway section"),
        (65, "nh", 88, 0.02, "Agra bypass"),
        (55, "nh", 80, 0.03, "Agra-Gwalior 2-lane"),
        (50, "nh", 72, 0.04, "Gwalior-Jhansi"),
        (45, "rural", 55, 0.05, "Jhansi-Lalitpur ghats [DEAD ZONE]"),
        (50, "nh", 62, 0.04, "Lalitpur-Sagar"),
        (65, "nh", 88, 0.02, "Sagar-Nagpur"),
        (55, "sh", 75, 0.03, "Wardha road"),
        (45, "rural", 50, 0.05, "Adilabad ghats [DEAD ZONE]"),
        (50, "nh", 70, 0.03, "Adilabad-Nizamabad"),
        (60, "nh", 82, 0.02, "Nizamabad-Kamareddy"),
        (70, "nh", 95, 0.02, "ORR Hyderabad approach"),
        (60, "nh", 85, 0.03, "Hyderabad-Kurnool"),
        (55, "rural", 60, 0.04, "Kurnool-Anantapur rural [DEAD ZONE]"),
        (55, "nh", 72, 0.03, "Anantapur-Doddaballapur"),
        (75, "nh", 95, 0.02, "Doddaballapur-Bengaluru"),
    ]
    for i in range(len(ROUTE_NODES) - 1):
        a = ROUTE_NODES[i]; b = ROUTE_NODES[i+1]
        R = 6371.0
        lat1, lat2 = _m.radians(a["lat"]), _m.radians(b["lat"])
        dphi = _m.radians(b["lat"] - a["lat"]); dlmb = _m.radians(b["lng"] - a["lng"])
        d = 2*R*_m.asin(_m.sqrt(_m.sin(dphi/2)**2 + _m.cos(lat1)*_m.cos(lat2)*_m.sin(dlmb/2)**2))
        speed, rtype, cov, risk, note = stretch_meta[i] if i < len(stretch_meta) else (50, "nh", 80, 0.02, "")
        edges.append({
            "id": f"E-{i:03d}",
            "corridor": "NH44",
            "from_node": a["id"], "to_node": b["id"],
            "distance_km": round(d, 2), "base_speed_kmh": speed,
            "road_type": rtype, "cellular_coverage_pct": cov,
            "accident_risk": risk, "notes": note,
        })
    return edges


ROUTE_EDGES = _edges_from_nodes()


# ------------------------------------------------------------
# Dead zones (lat, lng, radius_km, description)
# ------------------------------------------------------------
DEAD_ZONES: List[Tuple[float,float,float,str]] = [
    (24.70, 78.60, 35.0, "Jhansi-Lalitpur jungle stretch"),
    (20.20, 79.10, 45.0, "Adilabad ghats"),
    (16.40, 77.90, 40.0, "Kurnool-Anantapur rural"),
    (14.00, 77.65, 35.0, "Anantapur-Doddaballapur scrubland"),
]


# ------------------------------------------------------------
# Realistic buyers along/around the corridor
# ------------------------------------------------------------
def _buyer(uid: str, name: str, kind: str, lat: float, lng: float,
           capacity_kg: float, auto_bid_pct: float = 72) -> Dict:
    return {
        "id": uid, "name": name, "kind": kind, "lat": lat, "lng": lng,
        "service_radius_km": 55.0, "capacity_kg": capacity_kg,
        "gstn": f"29{uid[2:]}Z{hash(name)%1000:03d}",
        "auto_bid_ceiling_pct": auto_bid_pct,
    }


BUYERS: List[Dict] = [
    # Delhi NCR
    _buyer("B-AZM", "Azadpur Fruit Mandi", "wholesaler", 28.7076, 77.1689, 15000, 70),
    _buyer("B-OKH", "Okhla Cold Storage Ltd", "cold_storage", 28.5625, 77.2806, 8000, 80),
    _buyer("B-DLJ", "Delhi Juice Processors Co-op", "juice_processor", 28.6304, 77.2171, 5000, 65),
    _buyer("B-DLR", "NCR Restaurant Collective", "restaurant", 28.6200, 77.2200, 1500, 72),
    _buyer("B-DLS", "BigBasket Delhi Hub", "supermarket", 28.5200, 77.2500, 4000, 75),
    # Agra
    _buyer("B-AGR", "Agra Wholesale Sabzi Mandi", "wholesaler", 27.1767, 78.0081, 6000, 70),
    _buyer("B-AGC", "Agra Cold Chain Hub", "cold_storage", 27.2200, 77.9500, 5000, 78),
    _buyer("B-AGJ", "Taj Juice & Preserves", "juice_processor", 27.1900, 78.0200, 3000, 62),
    # Gwalior
    _buyer("B-GWL", "Gwalior Fruit Market", "wholesaler", 26.2183, 78.1828, 5000, 70),
    _buyer("B-GWL-J","Gwalior Juice & Preserves", "juice_processor",26.2050, 78.1600, 3500, 62),
    _buyer("B-GWL-R","Gwalior Restaurant Assoc.", "restaurant",26.2100, 78.1800, 1000, 72),
    # Jhansi
    _buyer("B-JHS", "Jhansi Mandi Samiti", "wholesaler", 25.4484, 78.5685, 3500, 70),
    _buyer("B-JHS-C","Jhansi Cold Storage", "cold_storage", 25.4600, 78.5500, 2500, 76),
    # Lalitpur
    _buyer("B-LAL", "Lalitpur Fruit Depot", "wholesaler", 23.8314, 78.7378, 2000, 68),
    # Nagpur
    _buyer("B-NAG", "Kalamna APMC Nagpur", "wholesaler", 21.1739, 79.0663, 9000, 70),
    _buyer("B-NAG-J","Nagpur Orange Juice Co.", "juice_processor", 21.1200, 79.0000, 6000, 60),
    _buyer("B-NAG-S","Nagpur Supermarket Chain", "supermarket",21.1458, 79.0882, 2500, 75),
    _buyer("B-NAG-C","Nagpur Cold Storage Hub", "cold_storage",21.1800, 79.0500, 5000, 78),
    # Adilabad
    _buyer("B-ADB", "Adilabad Rythu Bazaar", "wholesaler", 19.6640, 78.5320, 2500, 68),
    _buyer("B-ADJ", "Adilabad Juice Makers", "juice_processor",19.6000, 78.5500, 1800, 60),
    # Nizamabad
    _buyer("B-NZB", "Nizamabad Grain & Fruit Mandi", "wholesaler", 18.6725, 78.1050, 3000, 68),
    # Hyderabad
    _buyer("B-HYD", "Bowenpally Mundi (Hyd)", "wholesaler", 17.4800, 78.4800, 12000, 70),
    _buyer("B-HYD-J","Charminar Juice Processors", "juice_processor",17.3616, 78.4747, 5000, 60),
    _buyer("B-HYD-R","HITEC City Restaurant Assoc.", "restaurant",17.4200, 78.4500, 2000, 72),
    _buyer("B-HYD-S","Hyderabad Supermarket Alliance", "supermarket",17.4000, 78.4600, 3500, 75),
    _buyer("B-HYD-C","Shamshabad Perishable Hub", "cold_storage",17.2600, 78.4000, 7000, 80),
    # Kurnool
    _buyer("B-KRN", "Kurnool Rythu Bazaar", "wholesaler", 15.8281, 78.0373, 4500, 68),
    _buyer("B-KRN-J","Kurnool Mango Pulp Unit", "juice_processor",15.8000,78.0200,3000,58),
    # Anantapur
    _buyer("B-ATP", "Anantapur Fruit Mandi", "wholesaler", 14.6819, 77.6006, 3500, 68),
    _buyer("B-ATP-C","Anantapur Cold Point", "cold_storage",14.6500,77.5800,2500,76),
    # Doddaballapur
    _buyer("B-DBP", "Doddaballapur Market", "wholesaler", 13.6288, 77.5917, 3000, 70),
    # Bengaluru
    _buyer("B-BLR", "Yeshwanthpur APMC (BLR)", "wholesaler", 13.0296, 77.5457, 15000, 70),
    _buyer("B-BLR-J","BLR Juice Processing Unit", "juice_processor",12.9716, 77.5946, 7000, 60),
    _buyer("B-BLR-R","Indiranagar Rest. Assoc.", "restaurant",12.9784, 77.6408, 2000, 72),
    _buyer("B-BLR-S","Namma Supermarket Chain", "supermarket",12.9352, 77.6245, 3500, 75),
    _buyer("B-BLR-C","BIAL Perishable Cold Hub", "cold_storage",13.1986, 77.7066, 9000, 80),
]


# ------------------------------------------------------------
# Carriers & drivers (demo)
# ------------------------------------------------------------
CARRIERS: List[Dict] = [
    {"id": "CR-01", "name": "Agarwal Reefers Pvt Ltd", "iata_gstn": "29AAAAA0000A1Z5", "hsm_prefix": "AGW", "sla": 96.2},
    {"id": "CR-02", "name": "VRL Cold Logistics",      "iata_gstn": "29AAACV0000E1Z2", "hsm_prefix": "VRL", "sla": 98.1},
    {"id": "CR-03", "name": "Gati Kausar Cold Chain",  "iata_gstn": "29AAACH0000G1Z8", "hsm_prefix": "GTI", "sla": 94.5},
    {"id": "CR-04", "name": "ColdEx Express",          "iata_gstn": "29AAACC0000C1Z6", "hsm_prefix": "CLX", "sla": 97.4},
]


# Sample farmers (Indian names, villages)
FARMERS_SAMPLE: List[Dict] = [
    {"id": "F-001", "name": "Ramesh Patil",       "village": "Sangareddy", "district": "Medak",      "state": "Telangana", "upi": "ramesh@ybl",   "phone": "+919848012345"},
    {"id": "F-002", "name": "Lakshmi Reddy",      "village": "Zaheerabad", "district": "Sangareddy", "state": "Telangana", "upi": "lreddy@ybl",   "phone": "+919948023456"},
    {"id": "F-003", "name": "Arjun Deshmukh",     "village": "Nanded",     "district": "Nanded",     "state": "Maharashtra","upi":"arjun@ybl",    "phone": "+919823011122"},
    {"id": "F-004", "name": "Sunita Devi",        "village": "Guntur",     "district": "Guntur",     "state": "Andhra Pradesh","upi":"sunita@ybl", "phone": "+919866022233"},
    {"id": "F-005", "name": "Mohammed Iqbal",     "village": "Ratnagiri",  "district": "Ratnagiri",  "state": "Maharashtra","upi":"iqbal@ybl",    "phone": "+919822033344"},
    {"id": "F-006", "name": "Kavita Sharma",      "village": "Ratlam",     "district": "Ratlam",     "state": "Madhya Pradesh","upi":"kavita@ybl","phone": "+919755044455"},
    {"id": "F-007", "name": "Venkatesh Rao",      "village": "Kolar",      "district": "Kolar",      "state": "Karnataka", "upi": "venky@ybl",    "phone": "+919845055566"},
    {"id": "F-008", "name": "Farhan Sheikh",      "village": "Anantapur",  "district": "Anantapur",  "state": "Andhra Pradesh","upi":"farhan@ybl", "phone": "+919912066677"},
]
