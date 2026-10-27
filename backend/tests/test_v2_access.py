import hashlib,json,unittest,time
from unittest.mock import patch
from fastapi import FastAPI,Request
from fastapi.testclient import TestClient
from app.core.access import AccessBoundary,validate_deployment
from app.core.config import settings

def principal(token,role,**kw):return dict(subject=role,role=role,expires_at=int(time.time())+3600,sha256=hashlib.sha256(token.encode()).hexdigest(),**kw)

class AccessTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.object(settings,'ENV','production');self.env.start()
        self.principals=patch.object(settings,'AUTH_PRINCIPALS',[principal('op','operator'),principal('aud','auditor'),principal('buy','buyer',buyer_id='buyer1'),principal('dev','device',truck_id='truck1')]);self.principals.start()
        app=FastAPI()
        @app.get('/api/data')
        def data():return {'ok':True}
        @app.post('/api/auctions/a/bid')
        async def bid(r:Request):return await r.json()
        @app.post('/api/admin/seed')
        def admin():return {}
        @app.post('/api/telemetry')
        async def telemetry(r:Request):return await r.json()
        self.client=TestClient(AccessBoundary(app))
    def tearDown(self):self.client.close();self.principals.stop();self.env.stop()
    def test_anonymous_and_wrong_token_denied(self):
        self.assertEqual(self.client.get('/api/data').status_code,401)
        self.assertEqual(self.client.get('/api/data',headers={'Authorization':'Bearer wrong'}).status_code,401)
    def test_expired_credential_denied(self):
        with patch.object(settings,'AUTH_PRINCIPALS',[dict(principal('old','operator'),expires_at=1)]):
            self.assertEqual(self.client.get('/api/data',headers={'Authorization':'Bearer old'}).status_code,401)

    def test_auditor_read_only(self):
        headers={'Authorization':'Bearer aud'}
        self.assertEqual(self.client.get('/api/data',headers=headers).status_code,200)
        self.assertEqual(self.client.post('/api/auctions/a/bid',json={},headers=headers).status_code,403)
    def test_buyer_binding(self):
        headers={'Authorization':'Bearer buy'}
        self.assertEqual(self.client.post('/api/auctions/a/bid',json={'buyer_id':'buyer1'},headers=headers).status_code,200)
        self.assertEqual(self.client.post('/api/auctions/a/bid',json={'buyer_id':'someone'},headers=headers).status_code,403)
    def test_device_binding(self):
        headers={'Authorization':'Bearer dev'}
        self.assertEqual(self.client.post('/api/telemetry',json={'truck_id':'truck1'},headers=headers).status_code,200)
        self.assertEqual(self.client.post('/api/telemetry',json={'truck_id':'truck2'},headers=headers).status_code,403)
    def test_demo_admin_disabled_even_operator(self):
        self.assertEqual(self.client.post('/api/admin/seed',headers={'Authorization':'Bearer op'}).status_code,403)
    def test_websocket_requires_operator(self):
        with self.assertRaises(Exception):
            with self.client.websocket_connect('/telemetry/stream',headers={'Authorization':'Bearer buy'}):pass
    def test_default_deployment_secrets_fail_closed(self):
        with self.assertRaises(RuntimeError):validate_deployment()
    def test_oversized_body_rejected(self):
        r=self.client.post('/api/auctions/a/bid',content=b'a'*1000001,headers={'Authorization':'Bearer buy'})
        self.assertEqual(r.status_code,413)
