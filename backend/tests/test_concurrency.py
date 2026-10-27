"""Actual competing threads, separate SQLite connections, temporary file DB."""
import asyncio, datetime as dt, tempfile, threading, unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException
from app.core.database import (Base, CargoBatch, FlashAuction, RegisteredBuyer, BuyerAuthorization, Settlement)
from app.main import place_bid, confirm_auction
from app.api.schemas import BidIn, ConfirmationIn
from app.core.config import settings

class ConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.engine=create_engine('sqlite:///'+str(Path(self.temp.name)/'test.db'),connect_args={'check_same_thread':False,'timeout':10})
        Base.metadata.create_all(self.engine);self.Session=sessionmaker(bind=self.engine)
        with self.Session() as db:
            for i in range(2):
                db.add(CargoBatch(id=f'lot{i}',commodity='Alphonso Mango',origin_name='A',origin_lat=12,origin_lng=77,
                    destination_name='B',dest_lat=13,dest_lng=78,weight_kg=1000,contract_value_inr=120000,
                    rvh_hours=3,status='DistressedLiquidation',life_consumed_pct=50))
                db.add(FlashAuction(id=f'auc{i}',batch_id=f'lot{i}',trigger_lat=12,trigger_lng=77,
                    trigger_rvh_hours=3,opened_at=dt.datetime.utcnow(),closes_at=dt.datetime.utcnow()+dt.timedelta(minutes=15)))
                db.add(RegisteredBuyer(id=f'b{i}',name=f'b{i}',kind='wholesaler',lat=12,lng=77,capacity_kg=1000,service_radius_km=50))
                db.add(BuyerAuthorization(buyer_id=f'b{i}',accepted_commodities=['Alphonso Mango'],
                    simulated_escrow_inr=100000,pre_authorized=True,mode='simulated'))
            db.commit()
    def tearDown(self): self.engine.dispose();self.temp.cleanup()
    def race(self, calls):
        barrier=threading.Barrier(len(calls))
        def go(call):
            with self.Session() as db:
                barrier.wait()
                try: return asyncio.run(call(db))
                except HTTPException as exc: db.rollback();return {'error':exc.status_code}
        with ThreadPoolExecutor(max_workers=len(calls)) as pool: return list(pool.map(go,calls))
    def bid(self,a,b,db): return place_bid(a,BidIn(buyer_id=b,price_inr_per_kg=78,kg_requested=1000),db)
    def test_same_auction_one_reservation(self):
        results=self.race([lambda db:self.bid('auc0','b0',db),lambda db:self.bid('auc0','b1',db)])
        self.assertEqual(sum(r.get('status')=='awaiting_confirmation' for r in results),1)
        with self.Session() as db:
            self.assertEqual(sum(x.capacity_kg for x in db.query(RegisteredBuyer)),1000)
            self.assertEqual(sum(x.simulated_escrow_inr for x in db.query(BuyerAuthorization)),122000)
            self.assertEqual(db.query(Settlement).count(),0)
    def test_shared_buyer_no_double_spend(self):
        results=self.race([lambda db:self.bid('auc0','b0',db),lambda db:self.bid('auc1','b0',db)])
        self.assertEqual(sum(r.get('status')=='awaiting_confirmation' for r in results),1)
        with self.Session() as db:
            self.assertEqual(db.get(RegisteredBuyer,'b0').capacity_kg,0)
            self.assertEqual(db.get(BuyerAuthorization,'b0').simulated_escrow_inr,22000)
    def test_competing_confirmations_one_settlement(self):
        with self.Session() as db: asyncio.run(self.bid('auc0','b0',db))
        payload=ConfirmationIn(operator_name='Concurrency test',action='confirm',simulated_escrow_acknowledged=True)
        with patch.object(settings,'OPERATOR_TOKEN','test-token'):
            results=self.race([lambda db:confirm_auction('auc0',payload,'test-token',db)]*2)
        self.assertEqual(sum(r.get('status')=='won' for r in results),1)
        with self.Session() as db:
            self.assertEqual(db.query(Settlement).count(),1)
            self.assertEqual(db.get(BuyerAuthorization,'b0').simulated_escrow_inr,22000)
    def test_failed_computation_rolls_back_confirmation(self):
        with self.Session() as db: asyncio.run(self.bid('auc0','b0',db))
        payload=ConfirmationIn(operator_name='Failure test',action='confirm',simulated_escrow_acknowledged=True)
        with self.Session() as db, patch.object(settings,'OPERATOR_TOKEN','test-token'), patch('app.main.compute_settlement',side_effect=RuntimeError('injected')):
            with self.assertRaises(RuntimeError): asyncio.run(confirm_auction('auc0',payload,'test-token',db))
            db.rollback()
        with self.Session() as db:
            self.assertEqual(db.query(Settlement).count(),0)
            self.assertEqual(db.get(FlashAuction,'auc0').status,'AwaitingConfirmation')
