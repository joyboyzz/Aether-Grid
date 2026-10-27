import math, time, unittest
from app.services.insurance_oracle import compute_settlement
from app.core.security import register_hsm, sign_packet, verify_packet, _last_seq
from app.algorithms.bio_timer import BioTimer
from app.main import _process_telemetry
from app.core.database import Base, CargoBatch, Truck
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

class OracleAndSecurityTests(unittest.TestCase):
    def settle(self,price=78,life=50):
        return compute_settlement('Alphonso Mango',1000,120000,72000,.45,.05,price,1000,life,0,0,100)
    def test_bootstrap_sum_assured_example(self):
        s=self.settle()
        self.assertEqual(s.insurance_payout_inr,30780)
        self.assertEqual(s.farmer_total_payout_inr,108780)
        self.assertEqual(s.farmer_recovery_pct,90.65)
        self.assertEqual(s.buyer_savings_pct,35)
        self.assertEqual(s.oracle_payload['insurance_cover_cap_inr'],32400)
    def test_floor_is_not_guaranteed(self):
        s=self.settle(price=1,life=0)
        self.assertLess(s.farmer_recovery_pct,70)
        self.assertEqual(s.oracle_payload['farmer_floor_topup_inr'],0)
    def test_topup_bounded_by_penalty(self):
        s=self.settle(price=10,life=95)
        p=s.oracle_payload
        self.assertLessEqual(p['farmer_floor_topup_inr'],p['logistics_penalty_inr'])
        self.assertAlmostEqual(s.farmer_total_payout_inr,s.salvage_revenue_inr+s.insurance_payout_inr+p['farmer_floor_topup_inr'])
    def test_signature_replay_and_tamper(self):
        serial='unit-serial';truck='unit-truck';_last_seq.pop(truck,None);register_hsm(serial)
        p=dict(hsm_serial=serial,batch_id='unit-batch',truck_id=truck,seq=1,ts=int(time.time()),lat=12.,lng=77.,temp_c=30.,humidity_pct=88.,ethylene_ppm=2.)
        sig=sign_packet(**p)
        self.assertFalse(verify_packet(**dict(p,temp_c=10.),signature=sig).ok)
        self.assertTrue(verify_packet(**p,signature=sig).ok)
        self.assertFalse(verify_packet(**p,signature=sig).ok)
    def test_stale_packet_rejected(self):
        p=dict(hsm_serial='stale-serial',batch_id='lot',truck_id='stale-truck',seq=1,ts=int(time.time())-1000,lat=12.,lng=77.,temp_c=30.,humidity_pct=88.,ethylene_ppm=2.)
        sig=sign_packet(**p)
        self.assertFalse(verify_packet(**p,signature=sig).ok)
    def test_snapshot_has_no_infinity(self):
        snap=BioTimer('Alphonso Mango').snapshot(12,88,.1,0,3).as_dict()
        self.assertTrue(all(not isinstance(x,float) or math.isfinite(x) for x in snap.values()))
    def test_identity_binding(self):
        engine=create_engine('sqlite:///:memory:');Base.metadata.create_all(engine)
        with sessionmaker(bind=engine)() as db:
            db.add(Truck(id='bound',carrier_id='c',hsm_serial='bound-serial'))
            db.add(CargoBatch(id='bound-lot',truck_id='bound',commodity='Alphonso Mango',origin_name='A',origin_lat=12,origin_lng=77,
                destination_name='B',dest_lat=13,dest_lng=78,weight_kg=1000,contract_value_inr=120000))
            db.commit()
            self.assertEqual(_process_telemetry(db,dict(batch_id='bound-lot',truck_id='bound',hsm_serial='other',seq=1,ts=int(time.time()),lat=12,lng=77,temp_c=20,humidity_pct=88,ethylene_ppm=1,hsm_signature='HSM-invalid'))['error'],'telemetry_identity_mismatch')
        engine.dispose()
