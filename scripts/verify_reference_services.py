"""Finite supplementary smoke: Python demo transport and protected .NET calculation API."""
import os,sys,pathlib,subprocess,time,json,asyncio,httpx,socketio
ROOT=pathlib.Path(__file__).resolve().parents[1];os.chdir(ROOT);sys.path.insert(0,str(ROOT/'backend'));OUT=ROOT/'verification/final';P=ROOT/'.acceptance-private/reference';P.mkdir(parents=True,exist_ok=True)
from app.core.security import sign_packet_v2
from websockets.asyncio.client import connect
checks={}
def launch(cmd,env,port,health,log):
 p=subprocess.Popen(cmd,env=env,stdout=log,stderr=log)
 for _ in range(100):
  try:
   if httpx.get(f'http://127.0.0.1:{port}'+health).status_code==200:return p
  except httpx.ConnectError:pass
  if p.poll() is not None:raise RuntimeError('service exited before health')
  time.sleep(.1)
 raise RuntimeError('startup deadline')
for f in P.glob('python.db*'):f.unlink()
log=open(OUT/'reference-services.log','w');env={**os.environ,'AG_ENV':'demo','AG_DB_PATH':str(P/'python.db'),'AG_OPERATOR_TOKEN':'SYNTHETIC-REFERENCE-REVIEW-TOKEN-123'};p=launch([sys.executable,'-m','uvicorn','app.main:asgi_app','--app-dir','backend','--host','0.0.0.0','--port','8040'],env,8040,'/api/health',log)
try:
 c=httpx.Client(base_url='http://127.0.0.1:8040')
 for route in ['/','/buyer','/analytics','/carrier','/insurance','/api/batches','/api/buyers','/api/settlements','/api/summary','/api/carrier/sla','/api/insurance/claims']:
  r=c.get(route);assert r.status_code==200,(route,r.status_code);checks['python '+route]=r.status_code
 r=c.post('/api/admin/seed-truck-batch',json=dict(truck_id='REF-TRUCK',carrier_id='CR-01',hsm_serial='REF-SERIAL',commodity='Alphonso Mango',weight_kg=1000,contract_value_inr=120000,farmer_payout_inr=0,origin_name='Synthetic Bengaluru',origin_lat=12.97,origin_lng=77.59,destination_name='Hyderabad',dest_lat=17.38,dest_lng=78.49));r.raise_for_status();lot=r.json()['batch_id']
 packet=dict(hsm_serial='REF-SERIAL',batch_id=lot,truck_id='REF-TRUCK',seq=1,ts=int(time.time()),signature_version=2,lat=12.97,lng=77.59,temp_c=12.,humidity_pct=88.,ethylene_ppm=.1,speed_kmh=40.);packet['hsm_signature']=sign_packet_v2(packet)
 async def transports():
  async with connect('ws://127.0.0.1:8040/telemetry/stream') as ws:
   await ws.send(json.dumps(packet));ack=json.loads(await ws.recv());assert ack['accepted']==1,ack
   await ws.send(json.dumps(packet));ack=json.loads(await ws.recv());assert ack['rejected']==1,ack
  client=socketio.AsyncClient();await client.connect('http://127.0.0.1:8040',transports=['polling']);assert client.connected;await client.disconnect()
 asyncio.run(transports());checks['python v2 WebSocket accept/replay and Socket.IO polling']=True
finally:p.terminate();p.wait(timeout=40)
# Publish/run the optional protected calculation API independently.
dotnet=os.getenv('DOTNET','dotnet');target=ROOT/'.acceptance-private/algorithm'
subprocess.run([dotnet,'publish','dotnet/AetherGrid.Api','-c','Release','-o',str(target)],stdout=log,stderr=log,check=True)
env={**os.environ,'AETHER_DOTNET_TOKEN':'local-algorithm-test-token-at-least-32-chars'};p=launch([dotnet,str(target/'AetherGrid.Api.dll'),'--urls','http://0.0.0.0:8041'],env,8041,'/healthz',log)
try:
 f=json.loads((ROOT/'verification/v2/parity_fixtures.json').read_text());c=httpx.Client(base_url='http://127.0.0.1:8041');assert c.post('/api/algorithm/settlement',json=f['settlements'][0]['input']).status_code==401;c.headers['Authorization']='Bearer '+env['AETHER_DOTNET_TOKEN'];r=c.post('/api/algorithm/settlement',json=f['settlements'][0]['input']);r.raise_for_status();assert abs(round(r.json()['farmer'],2)-f['settlements'][0]['expected']['farmer'])<.01;checks['calculation service unauthorized blocked / authorized parity']=True
finally:p.terminate();p.wait(timeout=40);log.close()
(OUT/'reference-services.json').write_text(json.dumps(dict(passed=True,checks=checks,scope='Supplementary reference-service smoke, not whole-server equivalence'),indent=2));print(json.dumps(checks,indent=2))
