"""Candidate Q10 fit for controlled constant-temperature shelf-life experiments.
Not a general fit for varying truck telemetry, humidity/ethylene or food safety.
Never changes production coefficients automatically. No field data bundled.
"""
import argparse,csv,json,math
from pathlib import Path

def fit(rows,allow_synthetic=False):
    if not rows:raise ValueError('No observations')
    if any(r['source'] not in ('field','synthetic') for r in rows):raise ValueError('Unknown provenance label')
    if not allow_synthetic and any(r['source']!='field' for r in rows):raise ValueError('Synthetic data requires explicit opt-in')
    if any(r['split'] not in ('train','holdout') for r in rows):raise ValueError('Invalid split')
    train=[r for r in rows if r['split']=='train'];hold=[r for r in rows if r['split']=='holdout']
    if len(train)<3 or len(hold)<2:raise ValueError('Need at least 3 training and 2 holdout observations')
    if len({r['lot_id'] for r in rows})!=len(rows):raise ValueError('Repeated lot: cannot establish independent holdout')
    points=[]
    for r in rows:
        t=float(r['temperature_c']);life=float(r['observed_shelf_hours']);ref=float(r['shelf_reference_hours'])
        if not all(map(math.isfinite,(t,life,ref))) or life<=0 or ref<=0 or not -5<=t<=45:raise ValueError('Invalid experiment')
        points.append((r,t-5,math.log(ref/life)))
    tp=[(x,y) for r,x,y in points if r['split']=='train']
    if len({x for x,y in tp})<3:raise ValueError('At least three distinct training temperatures required')
    denominator=sum(x*x for x,y in tp)
    slope=sum(x*y for x,y in tp)/denominator;q10=math.exp(10*slope)
    if not 1<q10<=10:raise ValueError('Fit outside candidate plausibility range; investigate data')
    errors=[]
    for r,x,y in points:
        if r['split']=='holdout':
            predicted=float(r['shelf_reference_hours'])*q10**(-x/10)
            errors.append(abs(predicted-float(r['observed_shelf_hours']))/float(r['observed_shelf_hours'])*100)
    return dict(status='candidate_fit_only_not_validated',q10=q10,train_n=len(train),holdout_n=len(hold),holdout_mape_pct=sum(errors)/len(errors),synthetic=any(r['source']=='synthetic' for r in rows),configuration_changed=False,
        limitations=['Constant-temperature controlled experiments only; fixed 5C reference.', 'Provenance labels are user assertions, not independent verification.', 'No food-safety approval, external validation, humidity/ethylene fitting or deployment authorization.'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('csv');p.add_argument('--allow-synthetic',action='store_true');p.add_argument('--output',required=True);a=p.parse_args()
    with open(a.csv) as f:result=fit(list(csv.DictReader(f)),a.allow_synthetic)
    Path(a.output).write_text(json.dumps(result,indent=2)+'\n')
