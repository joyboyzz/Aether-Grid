"""Requires isolated local server populated by verify_native_server.py; no live rails."""
import os,sys,json,random,time,math,hashlib,base64,concurrent.futures,httpx
sys.path.insert(0,'backend')
from app.algorithms.router import DynamicRouter
from app.core.config import COMMODITY_PROFILES
BASE=os.getenv('AETHER_TEST_URL','http://127.0.0.1:8020');c=httpx.Client(base_url=BASE,timeout=30);s=c.post('/api/auth/login',json=dict(username='operator',password='Local-test-password-874!'));assert s.status_code==200;c.headers['X-CSRF-Token']=s.json()['csrf'];checks=[]
def req(method,path,body=None,status=200,client=None):
 r=(client or c).request(method,path,json=body);assert r.status_code==status,(path,r.status_code,r.text);return r.json()
def check(name,value):assert value,name;checks.append(name)
x=json.load(open('dotnet/AetherGrid.Server/catalog.json'));router=DynamicRouter({n['id']:n for n in x['nodes']},x['edges']);rng=random.Random(20261024);comparisons=0
for i in range(70):
 a,b=rng.sample(x['nodes'],2);buyers=[dict(id='PB-'+str(j),name=n['name'],kind='processor',lat=n['lat'],lng=n['lng']) for j,n in enumerate(rng.sample(x['nodes'],3))];cold=[n for n in x['nodes'] if n.get('cold')];commodity=list(COMMODITY_PROFILES)[i%7];t=rng.uniform(0,38);life=rng.uniform(0,1.2);broken=i%2==0
 expected=[p.as_dict() for p in router.plan(a['lat'],a['lng'],commodity,t,broken,life,b['lat'],b['lng'],buyers,cold)]
 body=dict(lat=a['lat'],lng=a['lng'],dest_lat=b['lat'],dest_lng=b['lng'],commodity=commodity,temp_c=t,reefer_broken=broken,life_consumed_pct=life*100,buyers=buyers,cold_storages=cold)
 actual=req('POST','/api/routing/evaluate',body);assert len(actual)==len(expected)
 for got,want in zip(actual,expected):
  for k,v in want.items():
   assert abs(got[k]-v)<1e-7 if isinstance(v,(float,int)) else got[k]==v,(i,k,got[k],v)
   comparisons+=1
check('70 routing cases / 7 commodities match Python ranked plans',True)
# Empty candidates, same-node, invalid coordinates.
body.update(buyers=[],cold_storages=[],dest_lat=body['lat'],dest_lng=body['lng']);check('same-node empty candidates returns delivery only',len(req('POST','/api/routing/evaluate',body))==1)
req('POST','/api/routing/evaluate',{**body,'lat':91},422)
# Real operational filtering, model route selection, no biological reset.
before=req('GET','/api/batches/BA-EXP');plans=req('GET','/api/batches/BA-EXP/route-options');p=plans[0]
req('POST','/api/batches/BA-EXP/route-decision',dict(target_id=p['target_id'],plan_type=p['plan_type'],evidence_note='Synthetic model routing decision, not dispatch.',advisory_acknowledged=True));after=req('GET','/api/batches/BA-EXP');check('model route selection preserves biological life and original destination',before['life_consumed_pct']==after['life_consumed_pct'] and before['dest_lat']==after['dest_lat'])
# Dedicated account: recovery token one-time, no plaintext persisted, revoked sessions.
pw='Synthetic-auditor-before-123';salt=os.urandom(16);encoded='pbkdf2-sha256$210000$'+base64.b64encode(salt).decode()+'$'+base64.b64encode(hashlib.pbkdf2_hmac('sha256',pw.encode(),salt,210000)).decode()
req('POST','/api/admin/provision',dict(kind='user',record=dict(id='recover-test',role='auditor',password_hash=encoded)))
a=httpx.Client(base_url=BASE);req('POST','/api/auth/login',dict(username='recover-test',password=pw),client=a)
r=req('POST','/api/admin/password-recovery/recover-test');new='Synthetic-auditor-after-123';req('POST','/api/auth/recover',dict(token=r['token'],password=new),client=httpx.Client(base_url=BASE));req('GET','/api/auth/session',client=a,status=401);req('POST','/api/auth/recover',dict(token=r['token'],password=new),status=401);req('POST','/api/auth/login',dict(username='recover-test',password=new),client=a);check('recovery token is one-time and revokes old sessions',True)
sa=req('GET','/api/auth/session',client=a);a.headers['X-CSRF-Token']=sa['csrf']
req('POST','/api/auth/change-password',dict(old_password='wrong-password',new_password='Synthetic-final-password-123'),403,client=a)
req('POST','/api/auth/change-password',dict(old_password=new,new_password='Synthetic-final-password-123'),client=a)
req('GET','/api/auth/session',client=a,status=401)
req('POST','/api/auth/login',dict(username='recover-test',password='Synthetic-final-password-123'),client=a)
check('auditor can change own password; incorrect old password rejected and old session revoked',True)

# Actual rotating device API keys, preserving scope and atomic revocation.
old='SYNTHETIC-DEVICE-KEY-NOT-FOR-DEPLOYMENT';newkey='SYNTHETIC-ROTATED-DEVICE-ONLY-123';oldhash=hashlib.sha256(old.encode()).hexdigest();newhash=hashlib.sha256(newkey.encode()).hexdigest()
req('POST',f'/api/admin/api-keys/{oldhash}/rotate',dict(new_digest=newhash,expires_at=time.time()+3600));d=httpx.Client(base_url=BASE,headers={'Authorization':'Bearer '+old});req('POST','/api/telemetry',{},401,client=d);d.headers['Authorization']='Bearer '+newkey
# Device is authenticated but cannot read operator data.
req('GET','/api/batches',client=d,status=403);req('POST',f'/api/admin/api-keys/{newhash}/revoke',{});req('POST','/api/telemetry',{},401,client=d);check('atomic key rotation and explicit revocation',True)
check('readiness exposes alert list and disclaims certification',isinstance(req('GET','/api/admin/readiness')['alerts'],list) and req('GET','/api/admin/readiness')['production_certified'] is False)
req('GET','/api/admin/retention/preview');req('POST','/api/admin/retention/apply',dict(acknowledged=False),422);req('POST','/api/admin/retention/apply',dict(acknowledged=True));check('retention preserves ledger, samples and replay cursor',len(req('GET','/api/settlements'))==1 and len(req('GET','/api/batches/BA-TEST/telemetry'))==1)
# Measured limited concurrency; not a capacity/SLA claim.
def load(_):
 start=time.monotonic();r=c.get('/api/summary');return r.status_code,(time.monotonic()-start)*1000
with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:out=list(pool.map(load,range(80)))
lat=sorted(t for code,t in out);check('80 requests at concurrency 12 have no 5xx',all(code<500 for code,t in out));check('bounded load all 80 successful',all(code==200 for code,t in out))
# Offline callback-contract adversity, with no financial HTTP request.
id='SYNTHETIC-INSURANCE-002';intent=req('POST','/api/integrations/intents',dict(idempotency_key=id,batch_id='BA-TEST',kind='insurance',simulated_escrow_acknowledged=True));req('POST','/api/integrations/intents',dict(idempotency_key=id,batch_id='BA-TEST',kind='payment',simulated_escrow_acknowledged=True),409)
req('POST',f'/api/integrations/intents/{id}/dispatch',dict(simulated_escrow_acknowledged=True));ref=req('GET','/api/integrations/intents');it=next(x for x in ref if x['id']==id)
import hmac
def callback(event,state,amount,ts=None):
 p=dict(event_id=event,provider_reference=it['provider_reference'],state=state,amount_paise=amount,currency='INR',timestamp=ts or int(time.time()));message='|'.join(str(x) for x in [id,p['event_id'],p['provider_reference'],state,amount,'INR',p['timestamp']]);sig=hmac.new(b'local-callback-test-01234567890123456789',message.encode(),hashlib.sha256).hexdigest();return c.post(f'/api/integrations/intents/{id}/callback',json=p,headers={'X-Callback-Signature':sig})
assert callback('WRONG-AMOUNT-001','succeeded',1).status_code==409
assert callback('EXPIRED-EVENT-001','succeeded',it['amount_paise'],int(time.time())-600).status_code==422
assert callback('FAILURE-EVENT-001','failed',it['amount_paise']).status_code==200
assert callback('TERMINAL-CHANGE-001','succeeded',it['amount_paise']).status_code==409
check('offline provider contract rejects mismatch, stale event, terminal reversal',True)
result=dict(passed=True,checks=checks,routing_cases=70,routing_field_assertions=comparisons,load=dict(requests=80,concurrency=12,status_counts={str(code):sum(1 for x,t in out if x==code) for code,t in out},p50_ms=lat[40],p95_ms=lat[75],max_ms=max(lat)),scope='local synthetic tests only; no provider certification or field evidence')
json.dump(result,open(os.getenv('AETHER_EVIDENCE_DIR','verification/v4')+'/native-v4.json','w'),indent=2);print(json.dumps(result,indent=2))
