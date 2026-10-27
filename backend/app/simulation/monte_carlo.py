"""Synthetic mango full-lot sensitivity study, NOT an end-to-end fleet replay.
Run: python -m app.simulation.monte_carlo --runs 1000 --seed 20261023
"""
import argparse, csv, json, math, random
from pathlib import Path
from collections import Counter
from app.services.buyer_eligibility import rejection_reasons
from app.services.insurance_oracle import compute_settlement


def percentile(xs, p):
    if not xs: return None
    xs = sorted(xs); i = (len(xs)-1)*p; lo=int(i); hi=math.ceil(i)
    return xs[lo] + (xs[hi]-xs[lo])*(i-lo)


def run(n=1000, seed=20261023):
    rng=random.Random(seed); rows=[]; rejections=Counter()
    for i in range(n):
        kg=rng.uniform(500,2000); rvh=rng.uniform(.5,4); winner=None
        # Explicit assumed local buyer density, NOT measured demand.
        candidates=rng.randint(0,10)
        for j in range(candidates):
            price=120*rng.uniform(.50,.85)
            distance=60*math.sqrt(rng.random())
            reasons=rejection_reasons(commodity='Alphonso Mango',lot_kg=kg,requested_kg=kg,
                price=price,capacity_kg=rng.uniform(500,4000),
                accepted_commodities=['Alphonso Mango'] if rng.random()<.8 else [],
                escrow_inr=rng.uniform(20000,300000),distance_km=distance,
                service_radius_km=rng.uniform(20,60),rescue_radius_km=50,
                rvh_hours=rvh,approved=rng.random()<.9)
            rejections.update(reasons)
            if not reasons:
                winner=price; break
        row=dict(scenario=i,seed=seed,lot_kg=round(kg,3),rvh_hours=round(rvh,3),
            candidate_count=candidates,rescued=winner is not None,
            farmer_recovery_pct='',buyer_savings_pct='')
        if winner is not None:
            s=compute_settlement('Alphonso Mango',kg,120*kg,.6*120*kg,.45,.05,winner,kg,
                rng.uniform(40,95),rng.uniform(0,12),rng.randint(0,3),rng.uniform(80,99))
            row.update(farmer_recovery_pct=s.farmer_recovery_pct,buyer_savings_pct=s.buyer_savings_pct)
        rows.append(row)
    k=sum(r['rescued'] for r in rows); p=k/n; z=1.96; den=1+z*z/n
    mid=(p+z*z/(2*n))/den; half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    metrics={}
    for key in ('farmer_recovery_pct','buyer_savings_pct'):
        xs=[r[key] for r in rows if r['rescued']]
        metrics[key]={'n':len(xs),'mean':sum(xs)/len(xs) if xs else None,
            'p2_5':percentile(xs,.025),'p97_5':percentile(xs,.975)}
    summary=dict(runs=n,seed=seed,rescued=k,rescue_rate_pct=p*100,
        rescue_rate_wilson_95_pct=[100*(mid-half),100*(mid+half)],
        conditional_on_rescue=metrics,rejection_counts=dict(rejections),
        caveats=['Synthetic independent scenarios; not measured fleet performance.',
            'Rescue means an eligible funded simulated bid, not successful physical delivery.',
            'Recovery and savings exclude unrescued lots; no claim about all-farmer recovery.',
            'Percentile intervals describe scenario spread, NOT confidence intervals on means.',
            'Wilson interval measures simulation sampling error only, not model uncertainty.',
            'RVH, demand, travel speed and insurance availability are unvalidated assumptions.',
            'Each scenario resets funds/capacity; no multi-auction competition or telemetry replay.',
            'Insurance sum assured = 60% of contract, matching demo bootstrap; prior full-contract-assurance results superseded.'])
    return rows,summary

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--runs',type=int,default=1000);ap.add_argument('--seed',type=int,default=20261023)
    ap.add_argument('--output',default='../DAY1_LOGS/day4_monte_carlo');a=ap.parse_args()
    if a.runs<1: ap.error('--runs must be positive')
    rows,summary=run(a.runs,a.seed);path=Path(a.output);path.parent.mkdir(parents=True,exist_ok=True)
    path.with_suffix('.json').write_text(json.dumps(summary,indent=2)+'\n')
    with path.with_suffix('.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
    print(json.dumps(summary,indent=2))
