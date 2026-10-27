"""Three-minute captioned recording of the ACTUAL browser + HTTP prototype.
No voiceover; no fabricated UI. Run against the isolated demo DB/environment.
"""
import asyncio, json, sys, time
from pathlib import Path
import httpx
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
from app.core.security import sign_packet
BASE='http://127.0.0.1:8000';OUT=ROOT/'verification';VIDEO=OUT/'recording';VIDEO.mkdir(exist_ok=True)

async def main():
    evidence={'clock':'1 simulated biological hour per accepted packet; no real travel/delivery', 'steps':[]}
    async with httpx.AsyncClient(base_url=BASE,timeout=15) as client, async_playwright() as p:
        buyers=(await client.get('/api/buyers')).json()
        buyer=next(b for b in buyers if b['lat']<13.5 and b['kind']=='wholesaler' and b['capacity_kg']>=1000)
        browser=await p.chromium.launch(headless=True,args=['--no-sandbox'])
        context=await browser.new_context(viewport={'width':1440,'height':960},record_video_dir=str(VIDEO),record_video_size={'width':1440,'height':960})
        page=await context.new_page(); errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        start=time.monotonic()
        async def until(second): await asyncio.sleep(max(0,second-(time.monotonic()-start)))
        async def caption(text):
            await page.evaluate('''text=>{ let e=document.getElementById('walkthrough-caption'); if(!e){ e=document.createElement('div');e.id='walkthrough-caption';document.body.appendChild(e);}
            Object.assign(e.style,{position:'fixed',bottom:'20px',left:'5%',right:'5%',zIndex:99999,background:'#0f172a',color:'#f8fafc',border:'2px solid #14b8a6',padding:'16px',borderRadius:'12px',font:'16px sans-serif',boxShadow:'0 8px 40px #000'});e.textContent=text;}''',text)
        async def go(path,text):
            await page.goto(BASE+path,wait_until='networkidle');await caption(text)
        await go('/','AetherGrid | 3-minute software demonstration. Synthetic telemetry, simulated money, manual operator review. This is not a physical rescue.')
        await until(12)
        stamp=int(time.time());truck=f'VERIFY-{stamp}';serial=f'VERIFY-HMAC-{stamp}'
        payload=dict(truck_id=truck,carrier_id='CR-01',hsm_serial=serial,commodity='Alphonso Mango',weight_kg=1000,
            contract_value_inr=120000,farmer_payout_inr=0,origin_name='Bengaluru synthetic load',origin_lat=buyer['lat'],origin_lng=buyer['lng'],
            destination_name='Hyderabad',dest_lat=17.385,dest_lng=78.4867)
        r=await client.post('/api/admin/seed-truck-batch',json=payload);r.raise_for_status();lot=r.json()['batch_id']
        evidence.update(batch_id=lot,buyer_id=buyer['id'],bootstrap=payload)
        await page.reload(wait_until='networkidle');await caption('A 1,000 kg mango lot is seeded near Bengaluru. Wholesale baseline ₹120/kg; demo policy sum assured = 60% of contract.')
        await until(25)
        telemetry=[];auction=None
        for seq in range(1,30):
            packet=dict(hsm_serial=serial,batch_id=lot,truck_id=truck,seq=seq,ts=int(time.time()),lat=buyer['lat'],lng=buyer['lng'],
                temp_c=32.,humidity_pct=88.,ethylene_ppm=5.,speed_kmh=0.,reefer_setpoint_c=12.)
            packet['hsm_signature']=sign_packet(**{k:packet[k] for k in ('hsm_serial','batch_id','truck_id','seq','ts','lat','lng','temp_c','humidity_pct','ethylene_ppm')})
            response=await client.post('/api/telemetry',json=packet);response.raise_for_status();result=response.json()
            assert result.get('ok'),result
            telemetry.append({'seq':seq,'snapshot':result['snapshot'],'batch_status':result['batch_status']})
            if result.get('event'): auction=result['event']['auction_id'];break
        assert auction,'No distress auction was actually triggered'
        evidence.update(telemetry=telemetry,auction_id=auction)
        await page.get_by_role('button',name='Flash Auctions').click();await page.wait_for_timeout(1500)
        await caption(f'Signed warm-telemetry replay triggered distress after {len(telemetry)} packets. The clock is accelerated: one biological hour per packet. No time-to-rescue benchmark is claimed.')
        await page.screenshot(path=str(OUT/'screenshots/e2e_distress.png'))
        # Replayed signed packet must fail; no physical-tamper claim.
        replay=(await client.post('/api/telemetry',json=packet)).json()
        assert replay.get('error')=='attestation_failed',replay
        tampered=dict(packet,seq=packet['seq']+1,hsm_signature='HSM-'+'0'*24)
        invalid=(await client.post('/api/telemetry',json=tampered)).json()
        assert invalid.get('error')=='attestation_failed',invalid
        evidence['negative_telemetry']={'replay':replay,'bad_signature':invalid}
        await until(50)
        await go('/buyer?buyer='+buyer['id'],'Buyer view: this is a full-lot offer. Commodity, capacity, simulated funds, radius and heuristic reachability are checked by the backend.')
        await page.locator('input[type=number]').first.fill('78')
        await until(65)
        async with page.expect_response(lambda r: r.url.endswith(f'/api/auctions/{auction}/bid') and r.request.method=='POST') as response_info:
            await page.get_by_role('button',name='RESERVE FULL LOT').click()
        response=await response_info.value;reservation=await response.json();assert response.status==200,reservation
        assert reservation['status']=='awaiting_confirmation';evidence['reservation']=reservation
        settlements=(await client.get('/api/settlements')).json();assert not any(s['batch_id']==lot for s in settlements)
        await caption('Bid accepted for reservation only. Simulated funds and capacity are reserved. There is still NO settlement until an operator confirms.')
        await page.screenshot(path=str(OUT/'screenshots/e2e_reserved.png'))
        await until(83)
        await go('/','Operator view: manual review is required. An operator token protects confirmation, but the broader demo API is not production-authenticated.')
        await page.get_by_role('button',name='Flash Auctions').click();await page.get_by_label('Operator token').fill('local-demo-review')
        await caption('Review the lot and reserved buyer. Confirm explicitly acknowledges simulated escrow. Rejection or timeout releases the reservation and permits bounded retries.')
        await until(105)
        async with page.expect_response(lambda r:r.url.endswith(f'/api/auctions/{auction}/confirm') and r.request.method=='POST') as response_info:
            await page.get_by_role('button',name='Confirm simulated settlement').click()
        response=await response_info.value;confirmation=await response.json();assert response.status==200,confirmation
        assert confirmation['status']=='won';evidence['confirmation']=confirmation
        # A repeated confirm must not pay twice.
        duplicate=await client.post(f'/api/auctions/{auction}/confirm',headers={'X-Operator-Token':'local-demo-review'},
            json={'operator_name':'Verification reviewer','action':'confirm','simulated_escrow_acknowledged':True})
        assert duplicate.status_code==409;evidence['duplicate_confirmation_status']=duplicate.status_code
        await until(116)
        await page.get_by_role('button',name='Settlements',exact=True).click();await page.wait_for_timeout(4500)
        await caption('Ledger reconciliation: ₹78,000 salvage + ₹30,780 simulated insurance = ₹1,08,780 farmer credit (90.65%). Buyer savings 35%. No real payment or rescue delivery occurred.')
        data=(await client.get('/api/settlements')).json();settlement=next(s for s in data if s['batch_id']==lot)
        assert settlement['farmer_total_payout_inr']==108780,settlement
        assert len([s for s in data if s['batch_id']==lot])==1
        evidence['settlement']=settlement
        await page.screenshot(path=str(OUT/'screenshots/e2e_settled.png'))
        await until(135)
        await go('/insurance','Insurance portal: deterministic claim calculations are visible. No insurer has approved or paid these demo claims.')
        await until(148)
        await go('/carrier','Carrier portal: SLA-style scoring and penalty calculations are software outputs. Carrier names and registrations in the seed data are demo labels, not partnerships.')
        await until(161)
        await go('/analytics','Analytics portal: synthetic telemetry, not field measurements. Q10 and travel-time estimates require calibration. Hardware, real escrow and payments remain out of scope.')
        await until(180)
        evidence.update(page_errors=errors,duration_seconds=time.monotonic()-start)
        video=page.video;await context.close();await video.save_as(str(OUT/'AetherGrid_3min_walkthrough.webm'));await browser.close()
    (OUT/'e2e_evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
    assert not errors, errors
    print(json.dumps({'passed':True,'batch_id':lot,'auction_id':auction,'seconds':evidence['duration_seconds']},indent=2))
asyncio.run(main())
