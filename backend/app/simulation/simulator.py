"""
AetherGrid Live Fleet Simulator (v2)
===================================
Time-lapse simulation of 36 reefer trucks moving on real NH-44.
Produces software HMAC-signed telemetry every tick. Models:

  * Heuristic refrigeration-unit dynamics (compressor cycling,
    ambient-temperature leakage on failure, humidity control)
  * Ethylene (ripening hormone) production spike at climacteric
  * Door-open events at checkpoints (5% probability)
  * Cellular RSSI dropping in illustrative dead zones
  * Driver reefer repair after 6-12 minutes of failure
  * Spoofed packets injected twice per run to demonstrate
    zero-trust rejection (a driver attempting to fake temperature)

Author: Praveen Sudireddy
"""
from __future__ import annotations
import asyncio, hmac, hashlib, json, os, random, time
import dataclasses
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import httpx
import aiohttp

from ..core.config import settings, COMMODITY_PROFILES
from ..core.security import sign_packet, register_hsm
from .seed_data import ROUTE_NODES, DEAD_ZONES, CARRIERS

API_HTTP = os.environ.get("AETHER_HTTP", f"http://127.0.0.1:{settings.API_PORT}")
API_WS = os.environ.get("AETHER_WS", f"ws://127.0.0.1:{settings.API_PORT}/telemetry/stream")


import math as _m
def _haversine(a,b,c,d):
    phi1,phi2=_m.radians(a),_m.radians(c);dp=_m.radians(c-a);dl=_m.radians(d-b)
    return 2*6371*_m.asin(_m.sqrt(_m.sin(dp/2)**2+_m.cos(phi1)*_m.cos(phi2)*_m.sin(dl/2)**2))


def _build_cumulative_route():
    nodes = ROUTE_NODES
    cum=[0.0]; seg=[]
    for i in range(1,len(nodes)):
        d=_haversine(nodes[i-1]["lat"],nodes[i-1]["lng"],nodes[i]["lat"],nodes[i]["lng"])
        cum.append(cum[-1]+d); seg.append(d)
    return nodes,cum,seg


def _position_at(cum, nodes, km):
    total=cum[-1]
    if km>=total: return nodes[-1]["lat"],nodes[-1]["lng"],nodes[-1]["name"],True
    for i in range(1,len(cum)):
        if cum[i]>=km:
            frac=(km-cum[i-1])/(cum[i]-cum[i-1])
            lat=nodes[i-1]["lat"]+frac*(nodes[i]["lat"]-nodes[i-1]["lat"])
            lng=nodes[i-1]["lng"]+frac*(nodes[i]["lng"]-nodes[i-1]["lng"])
            nm=nodes[i-1]["name"] if frac<0.5 else nodes[i]["name"]
            return lat,lng,nm,False
    return nodes[-1]["lat"],nodes[-1]["lng"],nodes[-1]["name"],True


def _in_deadzone(lat,lng):
    for clat,clng,r,_ in DEAD_ZONES:
        if _haversine(lat,lng,clat,clng)<r: return True
    return False


@dataclass
class SimTruck:
    truck_id: str
    carrier_id: str
    hsm_serial: str
    batch_id: str
    commodity: str
    setpoint_c: float
    total_km: float
    pos_km: float = 0.0
    temp_c: float = 0.0
    humidity: float = 88.0
    ethylene: float = 1.5
    speed: float = 45.0
    door_open: bool = False
    fuel_pct: float = 98.0
    reefer_healthy: bool = True
    failure_eta_ticks: int = 0
    repair_ticks: int = 0
    seq: int = 0
    arrived: bool = False
    door_open_count: int = 0
    hours_out_of_range: float = 0.0
    mesh_buffer: List[dict] = field(default_factory=list)
    city: str = ""
    spawned_spoof: bool = False
    spawned_spoof2: bool = False


def spawn_trucks(n: int) -> List[SimTruck]:
    nodes, cum, _ = _build_cumulative_route()
    total = cum[-1]
    commodity_set = list(COMMODITY_PROFILES.keys())
    trucks: List[SimTruck] = []
    for i in range(n):
        c = random.choice(commodity_set)
        sp = COMMODITY_PROFILES[c]["opt_temp_c"] + random.uniform(-0.5, 0.5)
        carrier = random.choice(CARRIERS)
        hsm = f"{carrier['hsm_prefix']}-HSM-{1000+i:05d}"
        register_hsm(hsm)
        # 40% start at Delhi, others spread along route
        if i < n*0.4:
            pos = random.uniform(0, total*0.05)
        else:
            pos = random.uniform(total*0.25, total*0.85)
        # Failures within 30–180 ticks (time-lapse)
        failure = random.choice([0,0,60,100,150,200,260])
        trucks.append(SimTruck(
            truck_id=f"TRK-{1000+i}", carrier_id=carrier["id"], hsm_serial=hsm,
            batch_id=f"PENDING-{i}", commodity=c, setpoint_c=sp,
            total_km=total, pos_km=pos,
            temp_c=sp + random.uniform(-1,1),
            humidity=random.uniform(82,92),
            ethylene=random.uniform(1,4),
            reefer_healthy=True, failure_eta_ticks=failure, repair_ticks=0,
        ))
    return trucks, nodes, cum


def _step(t: SimTruck, nodes, cum) -> Optional[dict]:
    if t.arrived: return None
    # Drive
    t.pos_km += settings.SIM_KM_PER_TICK + random.uniform(-0.05,0.1)
    lat,lng,city,done = _position_at(cum, nodes, t.pos_km)
    t.city = city
    if done: t.arrived = True

    # Reefer failure logic
    if t.reefer_healthy and t.failure_eta_ticks>0:
        t.failure_eta_ticks -= 1
        if t.failure_eta_ticks<=0:
            t.reefer_healthy=False
            t.repair_ticks=random.randint(180,420)
    elif not t.reefer_healthy:
        t.repair_ticks-=1
        if t.repair_ticks<=0:
            t.reefer_healthy=True
            t.failure_eta_ticks=random.randint(400,1200)

    # Temperature physics
    ambient = random.uniform(31,43)
    target = t.setpoint_c if t.reefer_healthy else ambient
    tau = 0.018 if t.reefer_healthy else 0.07
    t.temp_c += (target-t.temp_c)*tau + random.uniform(-0.15,0.15)

    # Humidity
    ht = 88 if t.reefer_healthy else random.uniform(40,60)
    t.humidity += (ht-t.humidity)*0.05 + random.uniform(-0.5,0.5)
    t.humidity = max(30,min(100,t.humidity))

    # Ethylene production: rises faster at higher T, spikes at climacteric (~life_consumed 40-60% handled server-side)
    t.ethylene += (0.02 + max(0,(t.temp_c-t.setpoint_c))*0.04) + random.uniform(-0.05,0.08)
    t.ethylene = max(0.5, t.ethylene)

    # Speed
    t.speed = settings.AVG_TRUCK_SPEED_KMH + random.uniform(-10,15)
    # Fuel
    t.fuel_pct -= 0.02
    if t.fuel_pct < 15: t.fuel_pct = 99  # refuel

    # Door open events (5% chance at checkpoint-like random ticks)
    t.door_open = random.random() < 0.02
    if t.door_open: t.door_open_count += 1

    # Cellular RSSI (very low in dead zones)
    rssi = -75 - random.uniform(0,20)
    in_dz = _in_deadzone(lat,lng)
    if in_dz: rssi = -110 - random.uniform(0,10)

    # Temp excursion book-keeping
    p = COMMODITY_PROFILES[t.commodity]
    if t.temp_c > p["max_safe_temp_c"]:
        t.hours_out_of_range += 1.0/60.0

    t.seq += 1
    ts = int(time.time())
    pkt = {
        "hsm_serial": t.hsm_serial,
        "batch_id": t.batch_id, "truck_id": t.truck_id,
        "seq": t.seq, "ts": ts,
        "lat": round(lat,5), "lng": round(lng,5),
        "temp_c": round(t.temp_c,2),
        "humidity_pct": round(t.humidity,1),
        "ethylene_ppm": round(t.ethylene,2),
        "speed_kmh": round(t.speed,1),
        "reefer_setpoint_c": round(t.setpoint_c,2),
        "door_open": t.door_open,
        "fuel_level_pct": round(t.fuel_pct,1),
        "cellular_rssi": round(rssi,0),
        "in_dead_zone": in_dz,
    }
    pkt["hsm_signature"] = sign_packet(t.hsm_serial, pkt["batch_id"], pkt["truck_id"],
                                       pkt["seq"], pkt["ts"], pkt["lat"], pkt["lng"],
                                       pkt["temp_c"], pkt["humidity_pct"], pkt["ethylene_ppm"])
    return pkt


async def register_batches(http: httpx.AsyncClient, trucks: List[SimTruck]):
    nodes, cum, _ = _build_cumulative_route()
    origin = nodes[0]; dest = nodes[-1]
    for t in trucks:
        p = COMMODITY_PROFILES[t.commodity]
        # Random weight
        crates = random.randint(120, 400)
        kg = crates * p["crate_kg"]
        contract = round(kg * p["wholesale_price_inr_per_kg"] * 1.0, 0)
        farmer_payout = round(contract * 0.58, 0)
        # Pick random farmer and carrier
        r = await http.post(f"{API_HTTP}/api/admin/seed-truck-batch", json={
            "truck_id": t.truck_id,
            "carrier_id": t.carrier_id,
            "hsm_serial": t.hsm_serial,
            "commodity": t.commodity,
            "weight_kg": kg,
            "contract_value_inr": contract,
            "farmer_payout_inr": farmer_payout,
            "origin_name": origin["name"], "origin_lat": origin["lat"], "origin_lng": origin["lng"],
            "destination_name": dest["name"], "dest_lat": dest["lat"], "dest_lng": dest["lng"],
        })
        d = r.json()
        t.batch_id = d["batch_id"]
    print(f"[sim] registered {len(trucks)} trucks+batches on server")


async def run():
    trucks, nodes, cum = spawn_trucks(settings.SIM_TRUCKS)
    total = cum[-1]
    print(f"[sim] spawned {len(trucks)} trucks along {total:.0f} km NH-44 Delhi→Bengaluru")
    async with httpx.AsyncClient(timeout=10) as http:
        # Wait for backend
        for _ in range(20):
            try:
                r = await http.get(f"{API_HTTP}/api/health");
                if r.status_code == 200: break
            except Exception: pass
            await asyncio.sleep(0.5)
        await register_batches(http, trucks)
        await asyncio.sleep(1.0)
        async with aiohttp.ClientSession() as wsess:
            async with wsess.ws_connect(API_WS) as ws:
                tick=0
                while True:
                    tick += 1
                    packets=[]
                    for t in trucks:
                        pkt = _step(t, nodes, cum)
                        if pkt is None: continue
                        # Dead zone: buffer in mesh
                        if pkt["in_dead_zone"]:
                            t.mesh_buffer.append(pkt); continue
                        if t.mesh_buffer:
                            flushed = t.mesh_buffer; t.mesh_buffer=[]
                            for bp in flushed:
                                bp["hsm_signature"] += "+MESH"
                            packets.extend(flushed)
                        packets.append(pkt)
                        # Inject a spoofed packet once per run
                        if not t.spawned_spoof and tick==250 and t.truck_id == trucks[0].truck_id:
                            bad = dict(pkt)
                            bad["temp_c"]=5.0  # driver tries to claim safe temp during failure
                            bad["hsm_signature"]="FAKED-BY-DRIVER"
                            bad["signed_by_hsm"]=False
                            packets.append(bad)
                            t.spawned_spoof=True
                            print("[zerotrust] injected spoofed packet from "+t.truck_id)
                        # Second spoof: replayed seq
                        if not t.spawned_spoof2 and tick==500 and t.truck_id == trucks[1].truck_id:
                            bad=dict(pkt); bad["seq"]=1; bad["ts"]=int(time.time())-3600
                            bad["hsm_signature"]=sign_packet(t.hsm_serial,bad["batch_id"],bad["truck_id"],bad["seq"],bad["ts"],bad["lat"],bad["lng"],bad["temp_c"],bad["humidity_pct"],bad["ethylene_ppm"])
                            packets.append(bad)
                            t.spawned_spoof2=True
                            print("[zerotrust] injected replayed-seq packet from "+t.truck_id)
                    if packets:
                        await ws.send_str(json.dumps(packets))
                    try:
                        resp = await ws.receive_json(timeout=2)
                    except asyncio.TimeoutError:
                        resp=None
                    if tick % 100 == 0:
                        failed = sum(1 for t in trucks if not t.reefer_healthy and not t.arrived)
                        active = sum(1 for t in trucks if not t.arrived)
                        in_dz = sum(1 for t in trucks if not t.arrived and _in_deadzone(*_position_at(cum,nodes,t.pos_km)[:2]))
                        print(f"[tick {tick:04d}] active={active} reefer_failed={failed} in_deadzone={in_dz} sent={len(packets)}")
                    await asyncio.sleep(settings.SIM_TICK_SEC)


if __name__ == "__main__":
    asyncio.run(run())
