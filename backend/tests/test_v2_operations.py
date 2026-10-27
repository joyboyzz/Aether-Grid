import datetime as dt,hashlib,hmac,json,time,unittest
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.core.database import Base,CargoBatch,RegisteredBuyer,FlashAuction,AuctionBid,ExternalIntent
from app.api.operations import router,get_db
from app.core.config import settings

class OperationsTests(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine('sqlite:///:memory:',connect_args={'check_same_thread':False},poolclass=StaticPool)
        Base.metadata.create_all(self.engine);self.Session=sessionmaker(bind=self.engine)
        with self.Session() as db:
            db.add(RegisteredBuyer(id='buyer',name='Demo',kind='wholesaler',lat=12,lng=77,capacity_kg=0))
            db.add(CargoBatch(id='lot',commodity='Alphonso Mango',origin_name='A',origin_lat=12,origin_lng=77,destination_name='B',dest_lat=13,dest_lng=78,weight_kg=1000,contract_value_inr=120000,status='Cleared'))
            db.add(FlashAuction(id='a',batch_id='lot',status='Settled',winning_bid_id='bid',closes_at=dt.datetime.utcnow(),trigger_lat=12,trigger_lng=77))
            db.add(AuctionBid(id='bid',auction_id='a',buyer_id='buyer',kg_requested=1000,price_inr_per_kg=78));db.commit()
        app=FastAPI();app.include_router(router)
        def session():
            with self.Session() as db:yield db
        app.dependency_overrides[get_db]=session;self.client=TestClient(app)
        self.token=patch.object(settings,'OPERATOR_TOKEN','test');self.token.start()
        self.secret=patch.object(settings,'SANDBOX_WEBHOOK_SECRET','callback-secret');self.secret.start()
    def tearDown(self):self.client.close();self.secret.stop();self.token.stop();self.engine.dispose()
    def delivery(self,**kw):
        data=dict(received_kg=1000,external_reference='receipt-0001',evidence_note='Synthetic test receipt, no physical shipment.',operator_name='Test operator');data.update(kw)
        return self.client.post('/api/deliveries/lot/report',json=data,headers={'X-Operator-Token':'test'})
    def intent(self,**kw):
        data=dict(idempotency_key='intent-0001',batch_id='lot',kind='escrow_reserve',amount_paise=7800000,mode='sandbox');data.update(kw)
        return self.client.post('/api/integrations/intents',json=data,headers={'X-Operator-Token':'test'})
    def callback(self,**kw):
        data=dict(event_id='event-0001',idempotency_key='intent-0001',amount_paise=7800000,currency='INR',status='sandbox_confirmed',timestamp=int(time.time()));data.update(kw)
        body=json.dumps(data).encode();sig=hmac.new(b'callback-secret',body,hashlib.sha256).hexdigest()
        return self.client.post('/api/integrations/sandbox/webhook',content=body,headers={'X-Sandbox-Signature':sig})
    def test_baseline_cannot_reset_or_reuse_history(self):
        with self.Session() as db:
            db.get(CargoBatch,'lot').status='InTransit';db.commit()
        body=dict(reference_timestamp=int(time.time())-30,initial_life_consumed=.1,hours_out_of_range=2,reference='baseline-0001',asserted_by='Test reviewer',evidence_note='Synthetic baseline, not a field measurement.')
        r=self.client.post('/api/telemetry/baselines/lot',json=body,headers={'X-Operator-Token':'test'})
        self.assertEqual(r.status_code,200,r.text)
        r=self.client.post('/api/telemetry/baselines/lot',json=body,headers={'X-Operator-Token':'test'})
        self.assertEqual(r.status_code,409)

    def test_delivery_release_once(self):
        self.assertEqual(self.delivery().status_code,200);self.assertEqual(self.delivery().status_code,200)
        with self.Session() as db:self.assertEqual(db.get(RegisteredBuyer,'buyer').capacity_kg,1000)
    def test_conflicting_delivery_rejected(self):
        self.delivery();self.assertEqual(self.delivery(external_reference='receipt-0002').status_code,409)
    def test_partial_receipt_is_dispute(self):self.assertEqual(self.delivery(received_kg=500).status_code,422)
    def test_intent_idempotency(self):
        self.assertFalse(self.intent().json()['actual_money_moved']);self.assertEqual(self.intent().status_code,200)
        self.assertEqual(self.intent(amount_paise=12).status_code,409)
        with self.Session() as db:self.assertEqual(db.query(ExternalIntent).count(),1)
    def test_live_mode_blocked(self):self.assertEqual(self.intent(mode='live').status_code,422)
    def test_signed_callback_duplicate(self):
        self.intent();self.assertEqual(self.callback().json()['status'],'sandbox_confirmed')
        self.assertEqual(self.callback().json()['status'],'duplicate')
    def test_callback_amount_and_freshness(self):
        self.intent();self.assertEqual(self.callback(amount_paise=1).status_code,409)
        self.assertEqual(self.callback(timestamp=1).status_code,422)
    def test_unsigned_callback_denied(self):
        self.assertEqual(self.client.post('/api/integrations/sandbox/webhook',json={}).status_code,403)
