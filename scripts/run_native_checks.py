#!/usr/bin/env python3
"""Finite disposable-process verification harness. Run from repository root."""
import subprocess,os,time,httpx,pathlib,sqlite3,json,hashlib,base64
root=pathlib.Path.cwd();private=root/'.v3-private';private.mkdir(exist_ok=True);db=private/'test.db'
for suffix in ['', '-wal','-shm']:
 pathlib.Path(str(db)+suffix).unlink(missing_ok=True)
salt=os.urandom(16);encoded='pbkdf2-sha256$210000$'+base64.b64encode(salt).decode()+'$'+base64.b64encode(hashlib.pbkdf2_hmac('sha256',b'Local-test-password-874!',salt,210000)).decode();(private/'users.json').write_text(json.dumps([dict(username='operator',role='operator',password_hash=encoded)]))
env={**os.environ,'AETHER_DB':str(db),'AETHER_USERS_FILE':str(private/'users.json'),'AETHER_TELEMETRY_ROOT':'local-test-only-root-01234567890123456789','AETHER_CALLBACK_SECRET':'local-callback-test-01234567890123456789','AETHER_AUCTION_SECONDS':'20','AETHER_REVIEW_SECONDS':'5'}
cmd=[os.getenv('DOTNET','/home/user/.cache/dotnet/dotnet'),str(root/'.server-build/AetherGrid.Server.dll'),'--urls','http://0.0.0.0:8010']
log=open('verification/v3/server-test.log','w')
def start():
 p=subprocess.Popen(cmd,env=env,stdout=log,stderr=log)
 for _ in range(100):
  try:
   if httpx.get('http://127.0.0.1:8010/api/health').status_code==200:return p
  except httpx.ConnectError:pass
  if p.poll() is not None:raise RuntimeError('Server failed to start; see log')
  time.sleep(.1)
 raise RuntimeError('Server startup deadline')
p=start()
try:subprocess.run(['python','scripts/verify_native_server.py'],check=True)
finally:p.terminate();p.wait(timeout=10)
# Real process restart on the SAME durable store, then consistent backup and independent restore.
p=start()
try:
 c=httpx.Client(base_url='http://127.0.0.1:8010');s=c.post('/api/auth/login',json=dict(username='operator',password='Local-test-password-874!')).json();c.headers['X-CSRF-Token']=s['csrf']
 assert len(c.get('/api/settlements').json())==1
 assert c.get('/api/buyers').json()[0]['capacity_kg']==2000
 assert c.get('/api/integrations/intents').json()[0]['state']=='succeeded'
 # Replay a valid MAC from the pre-restart cursor; verify persisted replay defense.
 import hmac
 with sqlite3.connect(db) as con:cursor=json.loads(con.execute("select json from documents where kind='cursor' and id='TR-EXP'").fetchone()[0])
 packet=dict(hsm_serial='SW-EXP-001',batch_id='BA-EXP',truck_id='TR-EXP',seq=1,ts=int(cursor['ts']),signature_version=2,lat=13.,lng=77.5,temp_c=32.,humidity_pct=90.,ethylene_ppm=.1,speed_kmh=0.,reefer_setpoint_c=None,fuel_level_pct=None,cellular_rssi=None,door_open=False,in_dead_zone=False)
 packet['hsm_signature']='AG2-'+hmac.new((env['AETHER_TELEMETRY_ROOT']+'|SW-EXP-001').encode(),json.dumps(packet,sort_keys=True,separators=(',',':')).encode(),hashlib.sha256).hexdigest()
 assert c.post('/api/telemetry',json=packet).status_code==409
 assert c.post('/api/auctions/'+c.get('/api/auctions').json()[0]['id']+'/confirm',json=dict(action='confirm',simulated_escrow_acknowledged=True)).status_code==409
 backup=private/'backup.db';backup.unlink(missing_ok=True)
 with sqlite3.connect(db) as source,sqlite3.connect(backup) as target:source.backup(target)
 with sqlite3.connect(backup) as con:
  assert con.execute('pragma integrity_check').fetchone()[0]=='ok';assert con.execute("select count(*) from documents where kind='settlement'").fetchone()[0]==1
 subprocess.run(['python','scripts/verify_native_browser.py'],check=True)
 json.dump(dict(passed=True,checks=['fresh process preserves settlement','valid-MAC replay rejected after restart','capacity retained without double release','callback terminal state retained','duplicate confirmation blocked after restart','online SQLite backup integrity and settlement retained']),open('verification/v3/recovery.json','w'),indent=2)
finally:p.terminate();p.wait(timeout=10)
# Independently open backup in a THIRD server process, not just SQLite integrity.
env['AETHER_DB']=str(backup);p=start()
try:
 r=httpx.Client(base_url='http://127.0.0.1:8010');r.post('/api/auth/login',json=dict(username='operator',password='Local-test-password-874!'))
 assert len(r.get('/api/settlements').json())==1
 result=json.load(open('verification/v3/recovery.json'));result['checks'].append('independent application process boots restored backup and serves settlement');json.dump(result,open('verification/v3/recovery.json','w'),indent=2)
finally:p.terminate();p.wait(timeout=10)
print('PASS: native integration, fresh-process replay defense, and independent backup restore')
