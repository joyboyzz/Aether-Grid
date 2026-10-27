"""No-access lab: local-only provider emulator and synthetic calibration pipeline QA."""
import os,sys,json,threading,time,http.server,httpx,hashlib,pathlib,random,csv,math
sys.path.insert(0,'backend')
from app.calibration.fit_q10 import fit
from app.core.config import COMMODITY_PROFILES
OUT=pathlib.Path(os.getenv('AETHER_EVIDENCE_DIR','verification/v4'))/'offline-lab';OUT.mkdir(parents=True,exist_ok=True)
records={};lock=threading.Lock()
class Emulator(http.server.BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def send(self,status,obj):
  payload=json.dumps(obj).encode()
  try:self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
  except BrokenPipeError:pass
 def do_GET(self):
  key=self.path.removeprefix('/lookup/');self.send(200 if key in records else 404,records.get(key,dict(state='absent')))
 def do_POST(self):
  if self.path!='/obligations':return self.send(404,{})
  p=json.loads(self.rfile.read(int(self.headers['Content-Length'])));key=self.headers.get('Idempotency-Key','')
  if not key:return self.send(422,dict(error='idempotency key required'))
  with lock:
   if key in records:
    if records[key]['amount_paise']!=p['amount_paise']:return self.send(409,dict(error='idempotency conflict'))
    return self.send(200,records[key])
   records[key]=dict(reference='LOCAL-'+hashlib.sha256(key.encode()).hexdigest()[:12],amount_paise=p['amount_paise'],state='pending',financial_execution=False)
  scenario=p.get('scenario')
  if scenario=='timeout_after_commit':time.sleep(.25)
  if scenario=='error_after_commit':return self.send(502,dict(error='ambiguous response; reconcile before any retry'))
  self.send(201,records[key])
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Emulator);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();base=f'http://127.0.0.1:{server.server_port}';checks=[]
try:
 c=httpx.Client(base_url=base,timeout=2);body=dict(amount_paise=7800000);headers={'Idempotency-Key':'LOCAL-001'}
 assert c.post('/obligations',json=body,headers=headers).status_code==201
 assert c.post('/obligations',json=body,headers=headers).status_code==200
 assert c.post('/obligations',json=dict(amount_paise=1),headers=headers).status_code==409;checks.append('idempotency duplicates stable, changed obligation rejected')
 assert c.post('/obligations',json=dict(**body,scenario='error_after_commit'),headers={'Idempotency-Key':'LOCAL-002'}).status_code==502
 assert c.get('/lookup/LOCAL-002').json()['state']=='pending';checks.append('ambiguous 502 reconciled by lookup, not an automatic POST retry')
 try:c.post('/obligations',json=dict(**body,scenario='timeout_after_commit'),headers={'Idempotency-Key':'LOCAL-003'},timeout=.05);raise AssertionError('timeout expected')
 except httpx.ReadTimeout:pass
 assert c.get('/lookup/LOCAL-003').json()['state']=='pending';checks.append('actual HTTP read timeout after commit reconciled without second submission')
 assert c.get('/lookup/NO-SUCH-KEY').status_code==404
finally:server.shutdown();server.server_close()
results=[];rng=random.Random(20261024)
for commodity,p in COMMODITY_PROFILES.items():
 rows=[]
 for i in range(15):
  t=[5,12,20,28,35][i%5];rows.append(dict(lot_id=f'SYNTHETIC-{commodity}-{i}',source='synthetic',split='train' if i<10 else 'holdout',temperature_c=t,observed_shelf_hours=p['shelf_hours_ref']*p['q10']**(-(t-5)/10)*(1+rng.uniform(-.03,.03)),shelf_reference_hours=p['shelf_hours_ref']))
 try:fit(rows);raise AssertionError('synthetic opt-in mandatory')
 except ValueError:pass
 result=fit(rows,allow_synthetic=True);assert result['configuration_changed'] is False and result['synthetic'];results.append(dict(commodity=commodity,**result))
 slug=commodity.split(' ')[0].lower()
 with (OUT/(slug+'-synthetic.csv')).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
 bad=[dict(r) for r in rows];bad[-1]['lot_id']=bad[0]['lot_id']
 try:fit(bad,True);raise AssertionError('train/holdout leakage not rejected')
 except ValueError:pass
checks+=['all 7 commodity synthetic pipelines require opt-in','all 7 reject repeated-lot leakage','candidate fits never modify runtime coefficients']
report=dict(passed=True,checks=checks,provider='our local invented HTTP contract, NOT a provider sandbox',field_validation=False,real_financial_execution=False,calibration_results=results)
(OUT/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(dict(passed=True,checks=checks,commodities=len(results),field_validation=False),indent=2))
