import json,os,subprocess,sys,tempfile,time,unittest
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base,CargoBatch,Truck,TelemetryCheckpoint,ReceiverCursor,TelemetrySample,TelemetryBaseline
from app.core.security import register_hsm,sign_packet,_last_seq
from app.main import _process_telemetry,bio_timers

class RestartTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'restart.db'
        self.engine=create_engine('sqlite:///'+str(self.path));Base.metadata.create_all(self.engine);self.Session=sessionmaker(bind=self.engine)
        with self.Session() as db:
            db.add(Truck(id='truck',carrier_id='carrier',hsm_serial='restart-serial'))
            db.add(CargoBatch(id='lot',truck_id='truck',commodity='Alphonso Mango',origin_name='A',origin_lat=12,origin_lng=77,destination_name='B',dest_lat=13,dest_lng=78,weight_kg=1000,contract_value_inr=120000))
            db.commit()
        register_hsm('restart-serial')
    def tearDown(self):self.engine.dispose();self.tmp.cleanup()
    def packet(self,seq):
        p=dict(hsm_serial='restart-serial',batch_id='lot',truck_id='truck',seq=seq,ts=int(time.time()),lat=12.,lng=77.,temp_c=25.,humidity_pct=88.,ethylene_ppm=2.,speed_kmh=40.)
        p['hsm_signature']=sign_packet(**{k:p[k] for k in ('hsm_serial','batch_id','truck_id','seq','ts','lat','lng','temp_c','humidity_pct','ethylene_ppm')});return p
    def test_fresh_process_retains_clock_and_replay_cursor(self):
        packet=self.packet(1)
        with self.Session() as db:
            first=_process_telemetry(db,packet);life=db.get(TelemetryCheckpoint,'lot').life_consumed
        # A genuinely new Python process, not just clearing a dictionary.
        code='''import json,sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.security import register_hsm
from app.main import _process_telemetry
from app.core.database import TelemetryCheckpoint
engine=create_engine('sqlite:///'+sys.argv[1]);Session=sessionmaker(bind=engine)
register_hsm('restart-serial')
with Session() as db:r=_process_telemetry(db,json.loads(sys.argv[2]));assert r['error']=='attestation_failed',r
with Session() as db:r=_process_telemetry(db,json.loads(sys.argv[3]));assert r['ok'],r;print(db.get(TelemetryCheckpoint,'lot').life_consumed)
'''
        env=dict(os.environ,PYTHONPATH=str(Path(__file__).resolve().parents[1]),PYTHONWARNINGS='ignore')
        result=subprocess.run([sys.executable,'-c',code,str(self.path),json.dumps(packet),json.dumps(self.packet(2))],env=env,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertAlmostEqual(float(result.stdout.strip()),2*life)
        with self.Session() as db:
            self.assertEqual(db.get(ReceiverCursor,'truck').sequence,2)
            self.assertEqual(db.query(TelemetrySample).count(),2)
    def test_failed_transaction_cannot_advance_checkpoint(self):
        from unittest.mock import patch
        with self.Session() as db,patch('app.algorithms.bio_timer.BioTimer.snapshot',side_effect=RuntimeError('crash before commit')):
            with self.assertRaises(RuntimeError):_process_telemetry(db,self.packet(1))
            db.rollback()
        with self.Session() as db:
            self.assertIsNone(db.get(ReceiverCursor,'truck'))
            self.assertIsNone(db.get(TelemetryCheckpoint,'lot'))
            self.assertTrue(_process_telemetry(db,self.packet(1))['ok'])

class EnvelopeTests(unittest.TestCase):
    def packet(self):return dict(signature_version=2,hsm_serial='envelope',batch_id='lot',truck_id='truck',seq=1,ts=int(time.time()),lat=12,lng=77,temp_c=25,humidity_pct=88,ethylene_ppm=2,speed_kmh=40,door_open=False,reefer_setpoint_c=12)
    def test_v2_mac_binds_auxiliary_fields(self):
        from app.core.security import sign_packet_v2,verify_packet_v2
        p=self.packet();p['hsm_signature']=sign_packet_v2(p)
        self.assertTrue(verify_packet_v2(p,-1).ok)
        for key,value in [('door_open',True),('speed_kmh',90),('reefer_setpoint_c',5),('temp_c',10)]:
            with self.subTest(field=key):self.assertFalse(verify_packet_v2(dict(p,**{key:value}),-1).ok)
    def test_v2_replay_rejected(self):
        from app.core.security import sign_packet_v2,verify_packet_v2
        p=self.packet();p['hsm_signature']=sign_packet_v2(p)
        self.assertFalse(verify_packet_v2(p,1).ok)

class ProductionEnvelopeTests(unittest.TestCase):
    setUp = RestartTests.setUp
    tearDown = RestartTests.tearDown
    packet = RestartTests.packet
    def test_production_requires_reviewed_baseline(self):
        from unittest.mock import patch
        from app.core.config import settings
        from app.core.security import sign_packet_v2
        p=dict(self.packet(1),signature_version=2);p['hsm_signature']=sign_packet_v2(p)
        with patch.object(settings,'ENV','production'),self.Session() as db:
            self.assertEqual(_process_telemetry(db,p)['error'],'reviewed_baseline_required')

    def test_production_rejects_legacy_and_accepts_bound_v2(self):
        from unittest.mock import patch
        from app.core.config import settings
        from app.core.security import sign_packet_v2
        with self.Session() as db:
            db.add(TelemetryBaseline(batch_id='lot',reference_timestamp=int(time.time())-30,reference='test-baseline',asserted_by='Test reviewer',evidence_note='Synthetic baseline used only for automated tests'))
            db.add(TelemetryCheckpoint(batch_id='lot',life_consumed=0,hours_out_of_range=0,max_temp_c=0,max_ethylene_ppm=0));db.commit()
        with patch.object(settings,'ENV','production'):
            with self.Session() as db:self.assertEqual(_process_telemetry(db,self.packet(1))['error'],'version_2_signature_required')
            p=dict(self.packet(1),signature_version=2);p['hsm_signature']=sign_packet_v2(p)
            with self.Session() as db:
                self.assertTrue(_process_telemetry(db,p)['ok'])
                baseline=db.get(TelemetryBaseline,'lot')
                from app.algorithms.bio_timer import BioTimer
                expected=BioTimer('Alphonso Mango');expected.apply_interval(25,88,2,(p['ts']-baseline.reference_timestamp)/3600)
                self.assertAlmostEqual(db.get(TelemetryCheckpoint,'lot').life_consumed,expected.life_consumed)
