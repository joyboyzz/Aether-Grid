import json
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1];f=json.loads((ROOT/'verification/v2/parity_fixtures.json').read_text())
headers={'Authorization':'Bearer local-algorithm-test-token-at-least-32-chars'};checks={}
with httpx.Client(base_url='http://127.0.0.1:8001') as c:
    r=c.get('/healthz');assert r.status_code==200;checks['liveness']=r.json()
    r=c.post('/api/algorithm/settlement',json=f['settlements'][0]['input']);assert r.status_code==401;checks['unauthenticated']=401
    case=f['settlements'][0];r=c.post('/api/algorithm/settlement',headers=headers,json=case['input']);assert r.status_code==200,r.text
    assert abs(round(r.json()['farmer'],2)-case['expected']['farmer'])<.01;checks['settlement_matches_python']=True
    case=f['eligibility'][0];r=c.post('/api/algorithm/eligibility',headers=headers,json=case['input']);assert r.status_code==200,r.text
    assert r.json()['reasons']==case['expected'];checks['eligibility_matches_python']=True
    case=f['bio'][0];p=case['profile'];q=case['query']
    def interval(row):return dict(temp=row[0],humidity=row[1],ethylene=row[2],hours=row[3],door=row[4] if len(row)>4 else False)
    body=dict(profile=dict(shelfHoursRef=p['shelf_hours_ref'],q10=p['q10'],optimalTemp=p['opt_temp_c'],maxSafeTemp=p['max_safe_temp_c'],ethSensitivity=p['eth_sensitivity'],wholesale=p['wholesale_price_inr_per_kg']),intervals=[interval(row) for row in case['intervals']],query=interval([*q[:3],0,False]),ett=q[3])
    r=c.post('/api/algorithm/bio',headers=headers,json=body);assert r.status_code==200,r.text
    assert abs(r.json()['lifeConsumed']-case['expected']['life'])<1e-9;checks['bio_matches_python']=True
    r=c.post('/api/algorithm/bio',headers=headers,json={});assert r.status_code==400,r.text;checks['missing_profile_rejected']=400
(ROOT/'verification/v2/dotnet_http.json').write_text(json.dumps(checks,indent=2)+'\n');print(json.dumps(checks,indent=2))
