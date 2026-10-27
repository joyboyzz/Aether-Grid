import json,random,sys,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
from app.core.config import COMMODITY_PROFILES
from app.algorithms.bio_timer import BioTimer
from app.services.insurance_oracle import compute_settlement
from app.services.buyer_eligibility import rejection_reasons
rng=random.Random(20261023);bio=[];settlements=[];eligibility=[]
for commodity,profile in COMMODITY_PROFILES.items():
    for case in range(30):
        timer=BioTimer(commodity);intervals=[]
        for i in range(10):
            t=rng.uniform(-5,45);h=rng.uniform(40,100);e=rng.uniform(0,50);hours=rng.uniform(0,5);door=rng.random()<.1
            intervals.append([t,h,e,hours,door]);timer.apply_interval(t,h,e,hours,door)
        q=[rng.uniform(0,40),rng.uniform(50,100),rng.uniform(0,30),rng.uniform(0,20)];snap=timer.snapshot(*q,3)
        bio.append(dict(commodity=commodity,profile=profile,intervals=intervals,query=q,expected=dict(life=timer.life_consumed,rvh=snap.rvh_hours_at_optimal_temp,eta=snap.spoilage_eta_hours_at_current_temp,rate=snap.current_decay_rate_mult,health=snap.health,oor=timer.hours_out_of_range,ttd=snap.time_to_distress_hours if math.isfinite(snap.time_to_distress_hours) else None)))
    for case in range(20):
        kg=rng.uniform(100,2000);contract=kg*profile['wholesale_price_inr_per_kg'];price=profile['wholesale_price_inr_per_kg']*rng.uniform(.1,.95);life=rng.uniform(0,100);hours=rng.uniform(0,24);doors=rng.randint(0,5);sla=rng.uniform(60,100)
        s=compute_settlement(commodity,kg,contract,contract*.6,.45,.05,price,kg,life,hours,doors,sla)
        inp=dict(Wholesale=profile['wholesale_price_inr_per_kg'],WeightKg=kg,ContractValue=contract,SumAssured=contract*.6,Cover=.45,Deductible=.05,BidPrice=price,ClearedKg=kg,LifePct=life,HoursOutOfRange=hours,DoorEvents=doors,Sla=sla)
        settlements.append(dict(input=inp,expected=dict(farmer=s.farmer_total_payout_inr,insurance=s.insurance_payout_inr,penalty=s.logistics_penalty_inr,recovery=s.farmer_recovery_pct)))
for case in range(200):
    p=dict(commodity='Alphonso Mango',lot_kg=1000,requested_kg=1000 if case%5 else 500,price=rng.uniform(20,100),capacity_kg=rng.uniform(100,2000),accepted_commodities=['Alphonso Mango'] if rng.random()<.8 else [],escrow_inr=rng.uniform(10000,200000),distance_km=rng.uniform(0,100),service_radius_km=50,rescue_radius_km=80,rvh_hours=rng.uniform(0,5),approved=rng.random()<.8,expired=rng.random()<.1)
    names=['Commodity','LotKg','RequestedKg','Price','CapacityKg','AcceptedCommodities','EscrowInr','DistanceKm','ServiceRadiusKm','RescueRadiusKm','RvhHours','Approved','Expired']
    eligibility.append(dict(input=dict(zip(names,p.values())),expected=rejection_reasons(**p)))
(ROOT/'verification/v2/parity_fixtures.json').write_text(json.dumps(dict(bio=bio,settlements=settlements,eligibility=eligibility),indent=2))
