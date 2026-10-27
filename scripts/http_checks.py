import asyncio,json,sys,time
from pathlib import Path
import httpx,socketio
from websockets.asyncio.client import connect
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
from app.core.security import sign_packet
BASE='http://127.0.0.1:8000'
async def main():
    checks={}
    async with httpx.AsyncClient(base_url=BASE) as client:
        for path in ['/api/health','/api/buyers','/api/batches','/api/auctions','/api/settlements','/api/events','/api/summary','/api/commodities','/api/route','/api/carrier/sla','/api/insurance/claims','/api/settlements.csv']:
            r=await client.get(path);checks[path]=r.status_code;assert r.status_code==200,(path,r.text)
        stamp=int(time.time());serial=f'wscheck-{stamp}';truck=f'WSCHECK-{stamp}'
        seed=dict(truck_id=truck,carrier_id='CR-01',hsm_serial=serial,commodity='Alphonso Mango',weight_kg=1000,contract_value_inr=120000,
            farmer_payout_inr=0,origin_name='Synthetic Bengaluru',origin_lat=12.97,origin_lng=77.59,destination_name='Hyderabad',dest_lat=17.38,dest_lng=78.49)
        invalid=await client.post('/api/admin/seed-truck-batch',json=dict(seed,commodity='unknown'))
        assert invalid.status_code==422;checks['unknown_commodity']=422
        r=await client.post('/api/admin/seed-truck-batch',json=seed);r.raise_for_status();lot=r.json()['batch_id']
        packet=dict(hsm_serial=serial,batch_id=lot,truck_id=truck,seq=1,ts=int(time.time()),lat=12.97,lng=77.59,temp_c=12.,humidity_pct=88.,ethylene_ppm=.1,speed_kmh=40.)
        packet['hsm_signature']=sign_packet(**{k:packet[k] for k in ('hsm_serial','batch_id','truck_id','seq','ts','lat','lng','temp_c','humidity_pct','ethylene_ppm')})
        async with connect('ws://127.0.0.1:8000/telemetry/stream') as ws:
            await ws.send(json.dumps(packet));ack=json.loads(await ws.recv());assert ack['accepted']==1 and ack['rejected']==0,ack
            checks['websocket_accept']=ack
            await ws.send(json.dumps(packet));ack=json.loads(await ws.recv());assert ack['accepted']==0 and ack['rejected']==1,ack
            checks['websocket_replay_reject']=ack
        r=await client.post('/api/telemetry',json=dict(packet,lat=200));assert r.status_code==422;checks['invalid_coordinate']=422
        e=json.loads((ROOT/'verification/e2e_evidence.json').read_text())
        r=await client.post('/api/auctions/'+e['auction_id']+'/confirm',json={'operator_name':'Test reviewer','action':'confirm','simulated_escrow_acknowledged':True})
        assert r.status_code==403;checks['missing_operator_token']=403
    sio=socketio.AsyncClient();await sio.connect(BASE,transports=['polling']);checks['socketio_polling_connected']=sio.connected;await sio.disconnect()
    (ROOT/'verification/http_checks.json').write_text(json.dumps(checks,indent=2)+'\n');print(json.dumps(checks,indent=2))
asyncio.run(main())
