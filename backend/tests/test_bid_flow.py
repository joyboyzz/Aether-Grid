import asyncio, datetime as dt, unittest
from unittest.mock import patch, AsyncMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException
from app.core.database import Base, CargoBatch, FlashAuction, RegisteredBuyer, BuyerAuthorization, Settlement
from app.main import place_bid, confirm_auction
from app.core.config import settings
from app.services.auction_lifecycle import expire_due
from app.core.database import AuctionControl
from app.api.schemas import BidIn

class BidFlowTests(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.db=sessionmaker(bind=self.engine)()
        self.db.add(CargoBatch(id='lot',commodity='Alphonso Mango',origin_name='A',origin_lat=12,origin_lng=77,
            destination_name='B',dest_lat=13,dest_lng=78,weight_kg=1000,contract_value_inr=120000,
            rvh_hours=3,status='DistressedLiquidation',life_consumed_pct=50))
        self.db.add(FlashAuction(id='auc',batch_id='lot',trigger_lat=12,trigger_lng=77,
            trigger_rvh_hours=3,opened_at=dt.datetime.utcnow(),closes_at=dt.datetime.utcnow()+dt.timedelta(minutes=15)))
        for bid,commodities in [('bad',[]),('good',['Alphonso Mango'])]:
            self.db.add(RegisteredBuyer(id=bid,name=bid,kind='wholesaler',lat=12,lng=77,capacity_kg=2000,service_radius_km=50))
            self.db.add(BuyerAuthorization(buyer_id=bid,accepted_commodities=commodities,
                simulated_escrow_inr=100000,pre_authorized=True,mode='simulated'))
        self.db.commit()
    def tearDown(self): self.db.close();self.engine.dispose()
    def bid(self,buyer='good',kg=1000):
        self.db.rollback()
        with patch('app.main.get_bus') as bus:
            bus.return_value.emit=AsyncMock()
            try:
                return asyncio.run(place_bid('auc',BidIn(buyer_id=buyer,price_inr_per_kg=78,kg_requested=kg),self.db))
            except Exception:
                self.db.rollback(); raise
    def confirm(self, action='confirm', token='test-token'):
        self.db.rollback()
        from app.api.schemas import ConfirmationIn
        with patch.object(settings,'OPERATOR_TOKEN','test-token'), patch('app.main.get_bus') as bus:
            bus.return_value.emit=AsyncMock()
            try:
                return asyncio.run(confirm_auction('auc', ConfirmationIn(operator_name='Tester',action=action,
                    simulated_escrow_acknowledged=True),token,self.db))
            except Exception:
                self.db.rollback();raise
    def test_reject_then_fallback_and_no_double_spend(self):
        with self.assertRaises(HTTPException) as err: self.bid('bad')
        self.assertEqual(err.exception.status_code,422)
        self.assertEqual(self.db.get(FlashAuction,'auc').status,'Open')
        self.assertEqual(self.bid()['status'],'awaiting_confirmation')
        self.assertEqual(self.db.query(Settlement).count(),0)
        self.assertEqual(self.confirm()['mode'],'simulated')
        self.db.expire_all()
        self.assertEqual(self.db.get(RegisteredBuyer,'good').capacity_kg,1000)
        self.assertEqual(self.db.get(BuyerAuthorization,'good').simulated_escrow_inr,22000)
        self.assertEqual(self.db.get(CargoBatch,'lot').status,'Cleared')
        self.assertEqual(self.db.query(Settlement).count(),1)
        with self.assertRaises(HTTPException): self.bid()
        self.assertEqual(self.db.query(Settlement).count(),1)
    def test_unauthorized_confirmation_rejected(self):
        self.bid()
        with self.assertRaises(HTTPException) as err: self.confirm(token='wrong')
        self.assertEqual(err.exception.status_code,403)
        self.assertEqual(self.db.query(Settlement).count(),0)

    def test_rejection_releases_reservations_and_reopens(self):
        self.bid()
        result=self.confirm(action='reject')
        self.assertTrue(result['reauction_id'])
        self.db.expire_all()
        self.assertEqual(self.db.get(RegisteredBuyer,'good').capacity_kg,2000)
        self.assertEqual(self.db.get(BuyerAuthorization,'good').simulated_escrow_inr,100000)
        self.assertEqual(self.db.query(Settlement).count(),0)

    def test_timeout_sweep_idempotent(self):
        self.bid()
        deadline=self.db.get(AuctionControl,'auc').confirmation_deadline
        self.db.rollback()
        changes=expire_due(self.db,deadline+dt.timedelta(seconds=1))
        self.assertEqual(len(changes),1)
        self.assertEqual(len(expire_due(self.db,deadline+dt.timedelta(seconds=2))),0)
        self.assertEqual(self.db.get(RegisteredBuyer,'good').capacity_kg,2000)
        self.assertEqual(self.db.get(BuyerAuthorization,'good').simulated_escrow_inr,100000)
        self.assertEqual(self.db.query(FlashAuction).filter_by(status='Open').count(),1)

    def test_expired_confirmation_cannot_pay(self):
        self.bid()
        self.db.get(AuctionControl,'auc').confirmation_deadline=dt.datetime.utcnow()-dt.timedelta(seconds=1)
        self.db.commit()
        self.assertEqual(self.confirm()['status'],'released')
        self.assertEqual(self.db.query(Settlement).count(),0)

    def test_retry_budget_is_bounded(self):
        now=dt.datetime.utcnow()
        for i in range(3):
            current=self.db.query(FlashAuction).filter_by(status='Open').one()
            current.closes_at=now-dt.timedelta(seconds=1)
            self.db.commit()
            expire_due(self.db,now)
            now+=dt.timedelta(seconds=1)
        self.assertEqual(self.db.query(FlashAuction).filter_by(status='Open').count(),0)
        self.assertEqual(self.db.query(FlashAuction).count(),3)
        self.assertEqual(self.db.query(Settlement).count(),0)

    def test_partial_bid_does_not_clear_lot(self):
        with self.assertRaises(HTTPException): self.bid(kg=500)
        self.assertEqual(self.db.query(Settlement).count(),0)
        self.assertEqual(self.db.get(CargoBatch,'lot').status,'DistressedLiquidation')
    def test_expired_rejected(self):
        self.db.get(FlashAuction,'auc').closes_at=dt.datetime.utcnow()-dt.timedelta(seconds=1)
        self.db.commit()
        with self.assertRaises(HTTPException) as err: self.bid()
        self.assertIn('auction_expired',err.exception.detail['reasons'])

if __name__=='__main__': unittest.main()
