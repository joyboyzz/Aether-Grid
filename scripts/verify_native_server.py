#!/usr/bin/env python3
"""Actual HTTP integration test; isolated synthetic fixtures, no live providers."""
import httpx,time,json,hashlib,hmac,concurrent.futures,os
BASE=os.getenv('AETHER_TEST_URL','http://127.0.0.1:8010');ROOT='local-test-only-root-01234567890123456789';CB='local-callback-test-01234567890123456789'
c=httpx.Client(base_url=BASE,timeout=10);checks=[]
def check(name,condition):
 assert condition,name
 checks.append(name)
def req(method,path,data=None,status=200,client=None,headers=None):
 r=(client or c).request(method,path,json=data,headers=headers)
 assert r.status_code==status,(method,path,r.status_code,r.text)
 return r.json() if r.content else None
check('health explicitly software-only',req('GET','/api/health')['financial_execution'] is False)
req('GET','/api/batches',status=401)
req('POST','/api/auth/login',{'username':'operator','password':'wrong'},401)
s=req('POST','/api/auth/login',{'username':'operator','password':'Local-test-password-874!'})
check('opaque HttpOnly cookie', 'httponly' in {k.lower() for k in c.cookies.jar._cookies['127.0.0.1']['/']['ag_session']._rest})
c.headers['X-CSRF-Token']=s['csrf']
req('POST','/api/admin/provision',{'kind':'carrier','record':{'id':'CA-TEST','name':'Synthetic carrier','sla_compliance_pct':96}},headers={'X-CSRF-Token':'wrong'},status=403)
req('POST','/api/admin/provision',{'kind':'carrier','record':{'id':'CA-TEST','name':'Synthetic carrier','sla_compliance_pct':96}},headers={'Origin':'https://attacker.invalid'},status=403)
def provision(entity_kind,**record):return req('POST','/api/admin/provision',{'kind':entity_kind,'record':record})
provision('carrier',id='CA-TEST',name='Synthetic carrier',sla_compliance_pct=96)
provision('truck',id='TR-TEST',carrier_id='CA-TEST',hsm_serial='SW-TEST-001')
provision('buyer',id='BY-TEST',name='Synthetic buyer',kind='processor',lat=13.0,lng=77.5,capacity_kg=2000,service_radius_km=80,simulated_escrow_inr=500000,accepted_commodities=['Alphonso Mango'],pre_authorized=True)
provision('batch',id='BA-TEST',truck_id='TR-TEST',commodity='Alphonso Mango',weight_kg=1000,contract_value_inr=120000,origin_lat=13.0,origin_lng=77.5,dest_lat=17.38,dest_lng=78.48,origin_name='Bengaluru',destination_name='Hyderabad')
ts=int(time.time());req('POST','/api/batches/BA-TEST/baseline',dict(reference_timestamp=ts-10,initial_life_consumed=.8,hours_out_of_range=0,reference='SYNTHETIC-BASELINE-TEST',evidence_note='Synthetic fixture; not a physical measurement.'))
p=dict(hsm_serial='SW-TEST-001',batch_id='BA-TEST',truck_id='TR-TEST',seq=1,ts=ts,signature_version=2,lat=13.,lng=77.5,temp_c=32.,humidity_pct=90.,ethylene_ppm=.1,speed_kmh=0.,reefer_setpoint_c=None,fuel_level_pct=None,cellular_rssi=None,door_open=False,in_dead_zone=False)
def sign(packet):return {**packet,'hsm_signature':'AG2-'+hmac.new((ROOT+'|'+packet['hsm_serial']).encode(),json.dumps(packet,sort_keys=True,separators=(',',':')).encode(),hashlib.sha256).hexdigest()}
req('POST','/api/telemetry',{**sign(p),'hsm_signature':'AG2-bad'},403)
t=req('POST','/api/telemetry',sign(p));check('Python-signed v2 packet accepted by C#',t['ok']);check('distress opens auction',t['batch_status']=='DistressedLiquidation')
req('POST','/api/telemetry',sign(p),409)
req('POST','/api/batches/BA-TEST/baseline',dict(reference_timestamp=ts,initial_life_consumed=0,reference='RESET-ATTEMPT',evidence_note='Must not permit model history reset.'),409)
a=req('GET','/api/auctions')[0];bid=dict(buyer_id='BY-TEST',price_inr_per_kg=78,kg_requested=1000)
req('POST',f"/api/auctions/{a['id']}/bid",{**bid,'kg_requested':100},422)
# Two independent concurrent requests must never reserve twice.
def race(_):return c.post(f"/api/auctions/{a['id']}/bid",json=bid).status_code
with concurrent.futures.ThreadPoolExecutor(2) as pool: codes=list(pool.map(race,range(2)))
check('concurrent bid single winner',sorted(codes)==[200,409]);check('single capacity reservation',req('GET','/api/buyers')[0]['capacity_kg']==1000)
s=req('POST',f"/api/auctions/{a['id']}/confirm",dict(action='confirm',simulated_escrow_acknowledged=True));check('manual confirm settles once',s['status']=='won');req('POST',f"/api/auctions/{a['id']}/confirm",dict(action='confirm',simulated_escrow_acknowledged=True),409)
check('explicit payout baseline',s['settlement']['farmer_total_payout_inr']==108780 and s['settlement']['farmer_recovery_pct']==90.65)
receipt=dict(received_kg=1000,external_reference='SYNTHETIC-RECEIPT-001',evidence_note='Synthetic full lot receipt only; no delivery independently verified.')
req('POST','/api/batches/BA-TEST/delivery',receipt);req('POST','/api/batches/BA-TEST/delivery',receipt);check('receipt capacity released once',req('GET','/api/buyers')[0]['capacity_kg']==2000)
req('POST','/api/batches/BA-TEST/delivery',{**receipt,'received_kg':900},409)
intent=req('POST','/api/integrations/intents',dict(idempotency_key='SYNTHETIC-INTENT-001',batch_id='BA-TEST',kind='payment',simulated_escrow_acknowledged=True));check('integer paise obligation',intent['amount_paise']==10878000)
intent=req('POST','/api/integrations/intents/SYNTHETIC-INTENT-001/dispatch',dict(simulated_escrow_acknowledged=True));callback=dict(event_id='SYNTHETIC-EVENT-001',provider_reference=intent['provider_reference'],state='succeeded',amount_paise=10878000,currency='INR',timestamp=int(time.time()))
message='|'.join(str(x) for x in ['SYNTHETIC-INTENT-001',callback['event_id'],callback['provider_reference'],callback['state'],callback['amount_paise'],callback['currency'],callback['timestamp']]);signature=hmac.new(CB.encode(),message.encode(),hashlib.sha256).hexdigest()
req('POST','/api/integrations/intents/SYNTHETIC-INTENT-001/callback',callback,403)
for _ in range(2):req('POST','/api/integrations/intents/SYNTHETIC-INTENT-001/callback',callback,headers={'X-Callback-Signature':signature})
check('callback reconciled and duplicate idempotent',req('GET','/api/integrations/intents')[0]['state']=='succeeded')
for endpoint in ['summary','batches','buyers','auctions','settlements','events','carriers','trucks','route','commodities','batches/BA-TEST/telemetry','admin/integrity','carrier/sla','insurance/claims','batches/BA-TEST/route-plan']:req('GET','/api/'+endpoint)
check('five-portal read contracts respond',True)
# Scoped opaque API keys do not expose operator data.
key='SYNTHETIC-DEVICE-KEY-NOT-FOR-DEPLOYMENT';provision('api_key',id=hashlib.sha256(key.encode()).hexdigest(),subject='TR-TEST',role='device',truck_id='TR-TEST',expires_at=time.time()+3600)
d=httpx.Client(base_url=BASE,headers={'Authorization':'Bearer '+key});req('GET','/api/batches',client=d,status=403)
check('device read scope blocked',True)
# Audit role and immediate browser-session revocation.
import base64
salt=os.urandom(16);password='Test-auditor-password';encoded='pbkdf2-sha256$210000$'+base64.b64encode(salt).decode()+'$'+base64.b64encode(hashlib.pbkdf2_hmac('sha256',password.encode(),salt,210000)).decode()
provision('user',id='auditor-test',role='auditor',password_hash=encoded)
aud=httpx.Client(base_url=BASE);auds=req('POST','/api/auth/login',dict(username='auditor-test',password=password),client=aud);aud.headers['X-CSRF-Token']=auds['csrf'];req('GET','/api/settlements',client=aud);req('POST','/api/admin/provision',{},403,client=aud);req('POST','/api/admin/revoke-user/auditor-test',{});req('GET','/api/auth/session',client=aud,status=401);check('auditor read-only and revocation immediate',True)
# Durable SSE replay from an explicit cursor.
with c.stream('GET','/api/stream',headers={'Last-Event-ID':'1'}) as stream:
 check('SSE authorized stream opens',stream.status_code==200)
 for line in stream.iter_lines():
  if line.startswith('id: '):
   check('SSE durable replay advances cursor',int(line[4:])>1);break
# Second lot exercises actual timed reservation release and bounded fallback.
provision('truck',id='TR-EXP',carrier_id='CA-TEST',hsm_serial='SW-EXP-001')
provision('batch',id='BA-EXP',truck_id='TR-EXP',commodity='Alphonso Mango',weight_kg=1000,contract_value_inr=120000,origin_lat=13.,origin_lng=77.5,dest_lat=17.38,dest_lng=78.48)
now=int(time.time());req('POST','/api/batches/BA-EXP/baseline',dict(reference_timestamp=now-1,initial_life_consumed=.8,hours_out_of_range=0,reference='SYNTHETIC-EXP-BASELINE',evidence_note='Synthetic expiry test fixture, not field evidence.'))
req('POST','/api/telemetry',sign({**p,'batch_id':'BA-EXP','truck_id':'TR-EXP','hsm_serial':'SW-EXP-001','ts':now}))
exp=next(x for x in req('GET','/api/auctions') if x['batch_id']=='BA-EXP');req('POST',f"/api/auctions/{exp['id']}/bid",bid)
check('expiry fixture reserved capacity',req('GET','/api/buyers')[0]['capacity_kg']==1000)
time.sleep(6.2)
check('expired confirmation releases reservation',req('GET','/api/buyers')[0]['capacity_kg']==2000)
check('fallback auction persisted',any(x['batch_id']=='BA-EXP' and x['attempt']==1 for x in req('GET','/api/auctions')))
req('POST','/api/auth/logout',{});req('GET','/api/batches',status=401);check('logout invalidates server-side session',True)
result=dict(scope='synthetic native .NET HTTP integration; no hardware, physical results or real money',checks=checks,count=len(checks),passed=True)
open(os.getenv('AETHER_EVIDENCE_DIR','verification/v3')+'/http-integration.json','w').write(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
