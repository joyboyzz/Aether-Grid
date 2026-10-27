"""Seeded software-path replay: actual HMAC ingest, bio-clock, auction + confirmation.
Five synthetic mango trucks/run, shared buyer balances/capacity, accelerated clock.
No road traffic, hardware, physical rescue or real funds are modelled.
"""
import asyncio, csv, datetime as dt, json, random, time
from collections import Counter
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException
from .. import main
from ..api.schemas import BidIn, ConfirmationIn
from ..core.config import settings
from ..core.database import (Base, CargoBatch, Truck, RegisteredBuyer, BuyerAuthorization,
    FlashAuction, Settlement, InsurancePolicy, LogisticsCarrier)
from ..core.security import register_hsm, sign_packet, _last_seq
from .monte_carlo import percentile

async def run(runs=1000, seed=20261023):
    engine=create_engine('sqlite:///:memory:');Base.metadata.create_all(engine)
    Session=sessionmaker(bind=engine,autoflush=False)
    rows=[]; counts=Counter();old_hours=settings.SIM_BIO_HOURS_PER_PACKET;old_token=settings.OPERATOR_TOKEN
    settings.SIM_BIO_HOURS_PER_PACKET=1.0;settings.OPERATOR_TOKEN='internal-replay-only'
    try:
        for scenario in range(runs):
            rng=random.Random(seed+scenario)
            with engine.begin() as connection:
                for table in Base.metadata.tables.values(): connection.execute(table.delete())
            main.bio_timers.clear();_last_seq.clear()
            distressed_seen=set()
            paths={};seqs=Counter();buyer_ids=[f'b{i}' for i in range(rng.randint(2,8))]
            with Session() as db:
                db.add(LogisticsCarrier(id="c",name="Synthetic carrier",hsm_serial_prefix="replay",sla_compliance_pct=96))
                for b in buyer_ids:
                    position=rng.random()
                    db.add(RegisteredBuyer(id=b,name=b,kind='wholesaler',lat=12.97+4.41*position+rng.uniform(-.15,.15),
                        lng=77.59+.90*position+rng.uniform(-.15,.15),service_radius_km=rng.uniform(25,80),capacity_kg=rng.uniform(700,4000)))
                    db.add(BuyerAuthorization(buyer_id=b,accepted_commodities=['Alphonso Mango'] if rng.random()<.8 else [],
                        pre_authorized=rng.random()<.9,mode='simulated',simulated_escrow_inr=rng.uniform(30000,300000)))
                for i in range(5):
                    tid=f't{i}';lot=f'lot{i}';serial=f'replay-{i}';register_hsm(serial)
                    origin=(12.97+rng.uniform(-.1,.1),77.59+rng.uniform(-.1,.1));dest=(17.38,78.49)
                    kg=rng.uniform(500,1500)
                    paths[lot]={'tid':tid,'serial':serial,'origin':origin,'dest':dest,
                        'temp':rng.uniform(24,38) if rng.random()<.75 else 12.0,'eth':rng.uniform(.1,15),'kg':kg}
                    db.add(Truck(id=tid,carrier_id='c',hsm_serial=serial,lat=origin[0],lng=origin[1]))
                    db.add(CargoBatch(id=lot,truck_id=tid,carrier_id='c',commodity='Alphonso Mango',origin_name='Bengaluru (synthetic)',
                        origin_lat=origin[0],origin_lng=origin[1],destination_name='Hyderabad (synthetic)',dest_lat=dest[0],dest_lng=dest[1],
                        weight_kg=kg,contract_value_inr=kg*120,current_lat=origin[0],current_lng=origin[1],status='InTransit'))
                    db.add(InsurancePolicy(id=f'p{i}',batch_id=lot,policy_no=f'replay-{i}',sum_assured_inr=.6*kg*120,
                        cover_pct=.45,deductible_pct=.05))
                db.commit()
            for tick in range(1,15):
                for lot, p in paths.items():
                    with Session() as db:
                        b=db.get(CargoBatch,lot)
                        if b.status in ('Cleared','Spoiled','Delivered'):continue
                        # 12 one-hour steps along a straight GPS interpolation, not a road route.
                        f=min(1,tick/12);lat=p['origin'][0]+f*(p['dest'][0]-p['origin'][0]);lng=p['origin'][1]+f*(p['dest'][1]-p['origin'][1])
                        seqs[lot]+=1;ts=int(time.time())
                        packet=dict(hsm_serial=p['serial'],batch_id=lot,truck_id=p['tid'],seq=seqs[lot],ts=ts,
                            lat=lat,lng=lng,temp_c=p['temp'],humidity_pct=88.,ethylene_ppm=p['eth'],speed_kmh=42.,reefer_setpoint_c=12.)
                        packet['hsm_signature']=sign_packet(**{k:packet[k] for k in ('hsm_serial','batch_id','truck_id','seq','ts','lat','lng','temp_c','humidity_pct','ethylene_ppm')})
                        result=main._process_telemetry(db,packet)
                        assert result.get('ok'), result
                        if result['batch_status']=='DistressedLiquidation': distressed_seen.add(lot)
                    with Session() as db:
                        auction=db.query(FlashAuction).filter_by(batch_id=lot,status='Open').first()
                        aid=auction.id if auction else None
                    if aid:
                        for buyer in buyer_ids:
                            with Session() as db:
                                try:
                                    await main.place_bid(aid,BidIn(buyer_id=buyer,price_inr_per_kg=120*rng.uniform(.5,.85),
                                        kg_requested=p['kg'],auto_generated=True),db)
                                except HTTPException:
                                    db.rollback();continue
                            # Explicit policy simulation: 85% approve, 15% reject.
                            decision='confirm' if rng.random()<.85 else 'reject'
                            with Session() as db:
                                await main.confirm_auction(aid,ConfirmationIn(operator_name='Simulated reviewer',action=decision,
                                    simulated_escrow_acknowledged=True),'internal-replay-only',db)
                            break
            with Session() as db:
                statuses=Counter(b.status for b in db.query(CargoBatch))
                settlements=db.query(Settlement).all()
                distressed=db.query(CargoBatch).filter(CargoBatch.id.in_(
                    [a.batch_id for a in db.query(FlashAuction)])).count()
                for s in settlements:
                    assert s.kg_cleared>0
                    counts['settlements']+=1
                row={'scenario':scenario,'seed':seed+scenario,'lots':5,'distressed_lots':len(distressed_seen),'auctioned_lots':distressed,
                    'ledger_awards':statuses['Cleared'],'delivered_original':statuses['Delivered'],'spoiled_model':statuses['Spoiled'],
                    'unresolved':5-sum(statuses[x] for x in ('Cleared','Delivered','Spoiled')),
                    'recovery_sum_pct':sum(s.farmer_recovery_pct for s in settlements),
                    'savings_sum_pct':sum(s.buyer_savings_pct for s in settlements)}
                assert sum(row[x] for x in ('ledger_awards','delivered_original','spoiled_model','unresolved'))==5
                rows.append(row)
            if (scenario+1)%100==0: print(f'{scenario+1}/{runs}',flush=True)
    finally:
        settings.SIM_BIO_HOURS_PER_PACKET=old_hours;settings.OPERATOR_TOKEN=old_token;engine.dispose()
    totals={k:sum(r[k] for r in rows) for k in rows[0] if k not in ('scenario','seed')}
    rates=[100*r['ledger_awards']/r['distressed_lots'] for r in rows if r['distressed_lots']]
    summary={'runs':runs,'root_seed':seed,'trucks_per_run':5,'totals':totals,
        'award_fraction_of_distressed_pct':100*totals['ledger_awards']/totals['distressed_lots'] if totals['distressed_lots'] else None,
        'run_award_fraction_p2_5_p97_5':[percentile(rates,.025),percentile(rates,.975)],
        'conditional_mean_recovery_pct':totals['recovery_sum_pct']/totals['ledger_awards'] if totals['ledger_awards'] else None,
        'conditional_mean_savings_pct':totals['savings_sum_pct']/totals['ledger_awards'] if totals['ledger_awards'] else None,
        'limitations':['Synthetic five-truck replay, not the historical 36-truck demo or field validation.',
            'Actual HMAC, BioTimer, telemetry state transitions, buyer gates and settlement handlers exercised.',
            'One hour per packet, straight-line GPS interpolation; not realistic traffic/food-safety calibration.',
            'Reviewer approve probability 85% is an assumption, not observed behaviour.',
            'Ledger award is not physical rescue or confirmed delivery. Monetary metrics exclude non-awarded lots.',
            'Percentiles are run spread, not confidence bounds; deadlines use wall time, not accelerated bio-time.',
            'No packet loss/dead zones or physical tamper simulated here; cryptographic rejection covered separately.']}
    return rows,summary

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--runs',type=int,default=1000);p.add_argument('--seed',type=int,default=20261023)
    p.add_argument('--output',default='../verification/fleet_replay');a=p.parse_args()
    if a.runs<1:p.error('--runs must be positive')
    rows,summary=asyncio.run(run(a.runs,a.seed));dest=Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.with_suffix('.json').write_text(json.dumps(summary,indent=2)+'\n')
    with dest.with_suffix('.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
    print(json.dumps(summary,indent=2))
