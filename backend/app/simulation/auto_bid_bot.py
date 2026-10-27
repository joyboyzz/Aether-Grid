"""AetherGrid auto-bid bot (v2) — listens on Socket.IO and bids instantly."""
from __future__ import annotations
import asyncio, random, os
import socketio, httpx

API = os.environ.get("AETHER_HTTP","http://127.0.0.1:8000")
WHOLESALE = {"Alphonso Mango":120,"Tomato":25,"Dairy (Peda)":180,"Seafood (Pomfret)":420,"Leafy Greens (Palak)":32,"Banana (Yelakki)":45,"Poultry (Chicken)":190}
AGG = {"juice_processor":0.62,"wholesaler":0.72,"cold_storage":0.78,"supermarket":0.75,"restaurant":0.70,"distributor":0.73}
sio = socketio.AsyncClient()

async def place_bid(ev):
    await asyncio.sleep(random.uniform(0.3,2.0))
    buyers = ev.get("nearby_buyers") or []
    if not buyers: return
    async with httpx.AsyncClient() as c:
        batch = (await c.get(f"{API}/api/batches/{ev['batch_id']}")).json()
        kg = batch["kg"]
        bmap = {b["id"]: b for b in (await c.get(f"{API}/api/buyers")).json()}
        # Fallback: rejection never closes the auction; try the next candidate.
        for w in buyers:
            b = bmap.get(w["id"], {})
            base = WHOLESALE.get(ev["commodity"], 60)
            price = round(base * AGG.get(b.get("kind"), 0.7) * random.uniform(0.9, 1.1))
            try:
                r = await c.post(f"{API}/api/auctions/{ev['auction_id']}/bid",
                    json={"buyer_id":w["id"], "price_inr_per_kg":price,
                          "kg_requested":kg, "auto_generated":True}, timeout=5)
                print(f"[bot] {w['id']} full lot {kg}kg → {r.status_code}")
                if r.is_success or r.status_code in (400, 409): return
            except httpx.HTTPError as exc:
                print(f"[bot] transport failure: {exc}; stop to avoid ambiguous retry")
                return
        print("[bot] all candidates rejected; auction remains open until its deadline (no forced award)")

@sio.event
async def connect():
    print("[bot] connected, listening for distress…")
@sio.on("distressed")
def on_distress(ev):
    print(f"[bot] ⚡ {ev['commodity']} RVH={ev['rvh_hours']:.1f}h ETT={ev['ett_hours']:.1f}h bidders={len(ev.get('nearby_buyers') or [])}")
    asyncio.create_task(place_bid(ev))
@sio.on("auction_settled")
def on_settled(a):
    print(f"[bot]   ✓ {a.get('buyer_name','')[:30]:30s} saved {a.get('buyer_savings_pct',0):.0f}%  farmer=₹{a.get('farmer_payout_rs',0):,.0f}  penalty=₹{a.get('logistics_penalty_rs',0):,.0f}")

async def main():
    await sio.connect(API)
    await sio.wait()

if __name__=="__main__":
    asyncio.run(main())
