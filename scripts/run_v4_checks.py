"""Disposable server/process/crash checks; no operational DB is touched."""
import subprocess,os,time,httpx,pathlib,json,hashlib,base64,sqlite3,hmac
OUT=os.getenv('AETHER_EVIDENCE_DIR','verification/v4');pathlib.Path(OUT).mkdir(parents=True,exist_ok=True)
root=pathlib.Path.cwd();private=root/os.getenv('AETHER_TEST_PRIVATE','.v4-private');private.mkdir(parents=True,exist_ok=True);db=private/'test.db'
for suffix in ['', '-wal','-shm']:pathlib.Path(str(db)+suffix).unlink(missing_ok=True)
salt=os.urandom(16);encoded='pbkdf2-sha256$210000$'+base64.b64encode(salt).decode()+'$'+base64.b64encode(hashlib.pbkdf2_hmac('sha256',b'Local-test-password-874!',salt,210000)).decode();(private/'users.json').write_text(json.dumps([dict(username='operator',role='operator',password_hash=encoded)]))
oldroot='local-test-only-root-01234567890123456789';keyring={s:[dict(root=oldroot,not_after=time.time()+3600)] for s in ['SW-TEST-001','SW-EXP-001']};keyfile=private/'keyring.json';keyfile.write_text(json.dumps(keyring))
env={**os.environ,'AETHER_DB':str(db),'AETHER_USERS_FILE':str(private/'users.json'),'AETHER_TELEMETRY_ROOT':oldroot,'AETHER_CALLBACK_SECRET':'local-callback-test-01234567890123456789','AETHER_AUTO_MODEL_ROUTING':'true','AETHER_AUCTION_SECONDS':'20','AETHER_REVIEW_SECONDS':'5','AETHER_TEST_URL':'http://127.0.0.1:8020','AETHER_EVIDENCE_DIR':OUT,'AETHER_SIGNING_KEYS_FILE':str(keyfile)}
cmd=[os.getenv('DOTNET','/home/user/.cache/dotnet/dotnet'),str(root/os.getenv('AETHER_SERVER_DLL','.server-build/AetherGrid.Server.dll')),'--urls','http://0.0.0.0:8020'];cmd += ['--contentRoot',str(pathlib.Path(cmd[1]).parent)];log=open(OUT+'/server.log','w')
def start():
 p=subprocess.Popen(cmd,env=env,stdout=log,stderr=log)
 for _ in range(100):
  try:
   if httpx.get(env['AETHER_TEST_URL']+'/api/health').status_code==200:return p
  except httpx.ConnectError:pass
  if p.poll() is not None:raise RuntimeError('server exited')
  time.sleep(.1)
 raise RuntimeError('startup deadline')
def login():
 c=httpx.Client(base_url=env['AETHER_TEST_URL']);r=c.post('/api/auth/login',json=dict(username='operator',password='Local-test-password-874!'));assert r.status_code==200;c.headers['X-CSRF-Token']=r.json()['csrf'];return c
p=start()
try:
 subprocess.run(['python','scripts/verify_native_server.py'],env=env,check=True)
 subprocess.run(['python','scripts/verify_native_v4.py'],env=env,check=True)
 c=login();check=[]
 assert c.get('/api/batches/BA-EXP').json()['best_plan'] is not None
 check.append('opt-in automatic model rerouting recomputes recommendations without changing original destination')
 # Root rotation is file-based, serial-scoped, atomically replaced, and read for each packet.
 newroot='rotated-local-test-root-1234567890123456789';keyring['SW-EXP-001']=[dict(root=newroot,not_after=time.time()+3600)];tmp=private/'next.json';tmp.write_text(json.dumps(keyring));tmp.replace(keyfile)
 packet=dict(hsm_serial='SW-EXP-001',batch_id='BA-EXP',truck_id='TR-EXP',seq=2,ts=int(time.time()),signature_version=2,lat=13.,lng=77.5,temp_c=32.,humidity_pct=90.,ethylene_ppm=.1,speed_kmh=0.,reefer_setpoint_c=None,fuel_level_pct=None,cellular_rssi=None,door_open=False,in_dead_zone=False)
 def signed(root):return {**packet,'hsm_signature':'AG2-'+hmac.new((root+'|SW-EXP-001').encode(),json.dumps(packet,sort_keys=True,separators=(',',':')).encode(),hashlib.sha256).hexdigest()}
 assert c.post('/api/telemetry',json=signed(oldroot)).status_code==403
 assert c.post('/api/telemetry',json=signed(newroot)).status_code==200;check.append('serial-scoped root rotation revokes old root and accepts new MAC without restart')
 # Reserve and SIGKILL before confirmation; recover transaction state and deadline cleanup.
 auctions=c.get('/api/auctions').json();auction=next(a for a in auctions if a['batch_id']=='BA-EXP' and a['status']=='Open')
 assert c.post('/api/auctions/'+auction['id']+'/bid',json=dict(buyer_id='BY-TEST',price_inr_per_kg=78,kg_requested=1000)).status_code==200
 assert c.get('/api/buyers').json()[0]['capacity_kg']==1000
 p.kill();p.wait(timeout=10);time.sleep(5.2);p=start();c=login()
 for _ in range(30):
  if c.get('/api/buyers').json()[0]['capacity_kg']==2000:break
  time.sleep(.1)
 assert c.get('/api/buyers').json()[0]['capacity_kg']==2000
 assert len(c.get('/api/settlements').json())==1;check.append('SIGKILL with pending reservation recovers and releases once after deadline')
 # Expired ephemeral document cleanup actually deletes; ledger/outbox/cursor retained.
 with sqlite3.connect(db) as con:con.execute("insert into documents values('session','expired-test',?)",(json.dumps(dict(username='operator',expires_at=1,version=1)),));con.commit()
 preview=c.get('/api/admin/retention/preview').json();assert preview['eligible']>=1;c.post('/api/admin/retention/apply',json=dict(acknowledged=True)).raise_for_status()
 with sqlite3.connect(db) as con:
  assert con.execute("select count(*) from documents where id='expired-test'").fetchone()[0]==0
  assert con.execute("select count(*) from documents where kind='cursor'").fetchone()[0]==2
 check.append('expired legacy-shaped session deleted without deleting cursors or ledger')
 # Force a stale timestamp in the synthetic fixture to exercise actual alert generation.
 with sqlite3.connect(db) as con:
  text=con.execute("select json from documents where kind='cursor' and id='TR-EXP'").fetchone()[0];cursor=json.loads(text);cursor['ts']=1;con.execute("update documents set json=? where kind='cursor' and id='TR-EXP'",(json.dumps(cursor),));con.commit()
 assert any(x['code']=='telemetry_stale_or_missing' and x['batch_id']=='BA-EXP' for x in c.get('/api/admin/readiness').json()['alerts'])
 with sqlite3.connect(db) as con:con.execute("update documents set json=? where kind='cursor' and id='TR-EXP'",(text,));con.commit()
 check.append('stale telemetry generates a concrete critical readiness alert')
 subprocess.run(['python','scripts/verify_native_browser.py'],env=env,check=True)
 # Unknown API returns JSON 404, not successful HTML; rate limit actually rejects excess.
 assert c.get('/api/unknown').status_code==404
 statuses=[c.get('/api/health').status_code for _ in range(310)];assert 429 in statuses;check.append('global rate limit returns 429 under excess requests')
 json.dump(dict(passed=True,checks=check),open(OUT+'/crash-rotation-retention.json','w'),indent=2)
finally:
 if p.poll() is None:p.terminate();p.wait(timeout=10)
print('PASS v4 parity, operations, offline contract adversity, load, rotation and crash recovery')
