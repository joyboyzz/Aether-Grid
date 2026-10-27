"""Fresh real-browser buyer/operator journey. Synthetic accounts, data and ledger only."""
import os,pathlib,json,time,subprocess,hashlib,base64,hmac,httpx
from playwright.sync_api import sync_playwright
ROOT=pathlib.Path(__file__).resolve().parents[1];os.chdir(ROOT);OUT=ROOT/'verification/final';OUT.mkdir(parents=True,exist_ok=True);P=ROOT/'.acceptance-private/ui';P.mkdir(parents=True,exist_ok=True);os.chmod(P,0o700)
for f in P.glob('ui.db*'):f.unlink()
def hashed(pw):
 salt=os.urandom(16);return 'pbkdf2-sha256$210000$'+base64.b64encode(salt).decode()+'$'+base64.b64encode(hashlib.pbkdf2_hmac('sha256',pw.encode(),salt,210000)).decode()
pw='Synthetic-UI-operator-12345!';bp='Synthetic-UI-buyer-12345!';(P/'users.json').write_text(json.dumps([dict(username='ui-operator',role='operator',password_hash=hashed(pw))]));root='SYNTHETIC-UI-signing-root-0123456789012345';BASE='http://127.0.0.1:8030'
env={**os.environ,'AETHER_DB':str(P/'ui.db'),'AETHER_USERS_FILE':str(P/'users.json'),'AETHER_TELEMETRY_ROOT':root,'AETHER_AUCTION_SECONDS':'180','AETHER_REVIEW_SECONDS':'180','AETHER_PRODUCTION':'false'};env.pop('AETHER_SIGNING_KEYS_FILE',None)
log=open(OUT/'ui-server.log','w');runtime=ROOT/'.runtime';proc=subprocess.Popen([os.getenv('DOTNET','dotnet'),str(runtime/'AetherGrid.Server.dll'),'--contentRoot',str(runtime),'--urls','http://0.0.0.0:8030'],env=env,stdout=log,stderr=log)
checks=[];errors=[];failed=[]
try:
 for _ in range(100):
  try:
   if httpx.get(BASE+'/api/health').status_code==200:break
  except httpx.ConnectError:pass
  if proc.poll() is not None:raise RuntimeError('UI test server exited')
  time.sleep(.1)
 c=httpx.Client(base_url=BASE,timeout=15);r=c.post('/api/auth/login',json=dict(username='ui-operator',password=pw));r.raise_for_status();c.headers['X-CSRF-Token']=r.json()['csrf']
 def post(path,data):
  r=c.post(path,json=data);r.raise_for_status();return r.json()
 def provision(entity,**record):return post('/api/admin/provision',dict(kind=entity,record=record))
 provision('carrier',id='UI-CARRIER',name='Synthetic UI carrier',sla_compliance_pct=96)
 provision('truck',id='UI-TRUCK',carrier_id='UI-CARRIER',hsm_serial='UI-SOFTWARE-SERIAL')
 for ident in ['UI-BUYER-A','UI-BUYER-B']:
  provision('buyer',id=ident,name=ident,kind='processor',lat=13.,lng=77.5,capacity_kg=2000,service_radius_km=80,simulated_escrow_inr=500000,accepted_commodities=['Alphonso Mango'],pre_authorized=True)
 for username,buyer in [('ui-buyer-a','UI-BUYER-A'),('ui-buyer-b','UI-BUYER-B')]:provision('user',id=username,role='buyer',buyer_id=buyer,password_hash=hashed(bp))
 provision('batch',id='UI-LOT',truck_id='UI-TRUCK',commodity='Alphonso Mango',weight_kg=1000,contract_value_inr=120000,origin_lat=13.,origin_lng=77.5,dest_lat=17.38,dest_lng=78.48,origin_name='Bengaluru',destination_name='Hyderabad')
 ts=int(time.time());post('/api/batches/UI-LOT/baseline',dict(reference_timestamp=ts-1,initial_life_consumed=.8,hours_out_of_range=0,reference='SYNTHETIC-UI-BASELINE',evidence_note='Synthetic UI acceptance only, not physical quality evidence.'))
 packet=dict(hsm_serial='UI-SOFTWARE-SERIAL',batch_id='UI-LOT',truck_id='UI-TRUCK',seq=1,ts=ts,signature_version=2,lat=13.,lng=77.5,temp_c=32.,humidity_pct=90.,ethylene_ppm=.1,speed_kmh=0.,reefer_setpoint_c=None,fuel_level_pct=None,cellular_rssi=None,door_open=False,in_dead_zone=False);packet['hsm_signature']='AG2-'+hmac.new((root+'|UI-SOFTWARE-SERIAL').encode(),json.dumps(packet,sort_keys=True,separators=(',',':')).encode(),hashlib.sha256).hexdigest();post('/api/telemetry',packet);checks+=['fresh DB provisioned via authorized API','Python-signed telemetry opened distress auction']
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True,args=['--no-sandbox']);bc=browser.new_context(viewport=dict(width=1440,height=1000));oc=browser.new_context(viewport=dict(width=1440,height=1000));buyer=bc.new_page();operator=oc.new_page()
  for page in [buyer,operator]:
   page.on('pageerror',lambda e:errors.append(str(e)))
   page.on('response',lambda r:failed.append(dict(url=r.url,status=r.status)) if '/api/' in r.url and r.status>=400 and not r.url.endswith('/auth/session') else None)
  def login(page,username,password):
   page.goto(BASE);page.get_by_label('Username',exact=True).fill(username);page.get_by_label('Password',exact=True).fill(password);page.get_by_role('button',name='Sign in',exact=True).click();page.get_by_role('button',name='Sign out',exact=True).wait_for()
  login(buyer,'ui-buyer-a',bp);buyer.wait_for_url('**/buyer');buyer.get_by_role('button',name='RESERVE FULL LOT').wait_for();assert buyer.locator('select').first.input_value()=='UI-BUYER-A';checks.append('real buyer login redirects and auto-selects bound identity')
  buyer.locator('input[type=number]:not([readonly])').fill('78')
  with buyer.expect_response(lambda r:'/bid' in r.url and r.request.method=='POST') as response:buyer.get_by_role('button',name='RESERVE FULL LOT').click()
  assert response.value.status==200;buyer.screenshot(path=str(OUT/'journey-buyer-reserved.png'),full_page=True);checks.append('buyer browser reserves complete lot with CSRF')
  assert c.get('/api/settlements').json()==[];checks.append('reservation alone cannot create settlement')
  login(operator,'ui-operator',pw);operator.get_by_role('button',name='Confirm simulated settlement',exact=True).first.wait_for()
  with operator.expect_response(lambda r:'/confirm' in r.url and r.request.method=='POST') as response:operator.get_by_role('button',name='Confirm simulated settlement',exact=True).first.click()
  assert response.value.status==200;assert response.value.json()['status']=='won';operator.get_by_text('₹1,08,780',exact=True).first.wait_for();operator.screenshot(path=str(OUT/'journey-operator-settled.png'),full_page=True);checks.append('separate operator browser confirms; UI shows expected simulated credit')
  rows=c.get('/api/settlements').json();assert len(rows)==1 and rows[0]['farmer_total_payout_inr']==108780 and rows[0]['farmer_recovery_pct']==90.65
  auction=c.get('/api/auctions').json()[0];assert c.post('/api/auctions/'+auction['id']+'/confirm',json=dict(action='confirm',simulated_escrow_acknowledged=True)).status_code==409
  receipt=dict(received_kg=1000,external_reference='SYNTHETIC-UI-RECEIPT',evidence_note='Operator-reported synthetic receipt, not independently verified delivery.')
  post('/api/batches/UI-LOT/delivery',receipt);post('/api/batches/UI-LOT/delivery',receipt);assert c.get('/api/buyers').json()[0]['capacity_kg']==2000;checks.append('receipt API and duplicate guard release capacity once')
  b=httpx.Client(base_url=BASE);b.post('/api/auth/login',json=dict(username='ui-buyer-b',password=bp)).raise_for_status();assert b.get('/api/settlements').json()==[] and b.get('/api/summary').json()['total_farmer_payout_inr']==0;assert b.get('/api/batches').status_code==403;assert b.get('/api/auctions').json()==[];checks.append('different buyer cannot read another buyer award or financial totals')
  a=httpx.Client(base_url=BASE);a.post('/api/auth/login',json=dict(username='ui-buyer-a',password=bp)).raise_for_status();assert len(a.get('/api/settlements').json())==1 and len(a.get('/api/buyers').json())==1;checks.append('winning buyer sees own scoped settlement')
  csv=c.get('/api/settlements/export.csv');assert csv.status_code==200 and '108780' in csv.text;checks.append('CSV reporting includes confirmed simulation')
  operator.get_by_role('button',name='Sign out',exact=True).click();operator.get_by_role('button',name='Sign in',exact=True).wait_for();checks.append('browser logout returns to login')
  browser.close()
 assert not errors and not failed,(errors,failed)
 report=dict(passed=True,checks=checks,browser_page_errors=errors,failed_ui_requests=failed,financial_execution=False,physical_delivery_verified=False,scope='Fresh native published-build acceptance; two actual browser roles, simulated telemetry and ledger; receipt via API')
 (OUT/'ui-journey.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
finally:
 if proc.poll() is None:proc.terminate();proc.wait(timeout=10)
 log.close()
