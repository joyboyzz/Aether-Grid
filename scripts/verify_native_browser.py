from playwright.sync_api import sync_playwright
import json,os
BASE=os.getenv("AETHER_TEST_URL","http://127.0.0.1:8010")
OUT=os.getenv("AETHER_EVIDENCE_DIR","verification/v3")
with sync_playwright() as p:
 b=p.chromium.launch(headless=True,args=['--no-sandbox']);page=b.new_page(viewport={'width':1440,'height':1000});errors=[];failed=[];page.on('pageerror',lambda e:errors.append(str(e)));page.on('response',lambda r:failed.append({'url':r.url,'status':r.status}) if '/api/' in r.url and r.status>=400 else None);page.goto(BASE);page.get_by_label('Username',exact=True).fill('operator');page.get_by_label('Password',exact=True).fill('Local-test-password-874!');page.get_by_role('button',name='Sign in',exact=True).click();page.get_by_role('button',name='Sign out',exact=True).wait_for();failed.clear();results=[]
 for route in ['/','/buyer','/analytics','/carrier','/insurance']:
  response=page.goto(BASE+route);page.wait_for_timeout(1400);assert 'NaN' not in page.locator('body').inner_text(),route;results.append(dict(route=route,status=response.status,body_chars=len(page.locator('body').inner_text()),errors=errors.copy()));page.screenshot(path=OUT+'/portal-'+(route.strip('/') or 'operator')+'.png',full_page=True)
 result=dict(portals=results,page_errors=errors,failed_api=failed,passed=not errors and not failed)
 print(json.dumps(result,indent=2));json.dump(result,open(OUT+'/browser-smoke.json','w'),indent=2);b.close();assert result['passed']
