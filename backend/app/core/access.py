"""Production-mode API-key/RBAC foundation, not a complete IdP or tenant system.
Only digests in configuration. Demo mode intentionally remains open and labelled.
WebSocket APIs are operator-only in production to avoid broadcasting buyer data.
"""
import hashlib, hmac, json, time, math
from .config import settings


def validate_deployment():
    if settings.ENV != 'production': return
    if not settings.MTLS_REQUIRED: raise RuntimeError('Telemetry verification cannot be disabled')
    if len(settings.HSM_SECRET)<32 or 'aethergrid-hsm-root-secret' in settings.HSM_SECRET:
        raise RuntimeError('Configure a non-default telemetry root secret')
    if len(settings.OPERATOR_TOKEN)<32: raise RuntimeError('Configure a strong confirmation token')
    if not settings.AUTH_PRINCIPALS: raise RuntimeError('No production principals configured')
    if "*" in settings.CORS_ORIGINS: raise RuntimeError('Explicit production origins required')
    seen=set()
    for p in settings.AUTH_PRINCIPALS:
        if len(p.get('sha256',''))!=64 or not p.get('subject') or p.get('role') not in ('operator','auditor','buyer','device'):
            raise RuntimeError('Invalid principal record')
        try:
            int(p['sha256'],16)
            if p['sha256'] in seen or not math.isfinite(float(p['expires_at'])) or float(p['expires_at'])<=time.time():raise ValueError()
            seen.add(p['sha256'])
        except (ValueError,KeyError,TypeError):raise RuntimeError('Duplicate/invalid/expired credential')


class AccessBoundary:
    def __init__(self, app): self.app=app
    async def __call__(self, scope, receive, send):
        if scope['type']=='lifespan' or settings.ENV!='production':
            return await self.app(scope,receive,send)
        path=scope.get('path','');headers=dict(scope.get('headers',[]))
        async def reject(status,detail):
            if scope['type']=='websocket':
                await send({'type':'websocket.close','code':4401 if status==401 else 4403});return
            body=json.dumps({'detail':detail}).encode()
            await send({'type':'http.response.start','status':status,'headers':[(b'content-type',b'application/json'),(b'cache-control',b'no-store')]})
            await send({'type':'http.response.body','body':body})
        # Only the unprivileged liveness route bypasses auth. No dataset in it.
        if path=='/healthz':
            if scope['type']!='http':return await reject(403,'HTTP only')
            await send({'type':'http.response.start','status':200,'headers':[(b'content-type',b'application/json')]})
            await send({'type':'http.response.body','body':b'{"alive":true}'});return
        if path=='/api/integrations/sandbox/webhook':
            return await self.app(scope,receive,send)  # independently HMAC-authenticated callback
        raw=headers.get(b'authorization',b'').decode('utf-8','ignore')
        digest=hashlib.sha256(raw[7:].encode()).hexdigest() if raw.startswith('Bearer ') else ''
        principal=next((p for p in settings.AUTH_PRINCIPALS if hmac.compare_digest(p.get('sha256',''),digest)),None)
        if principal is None:return await reject(401,'Bearer credential required')
        try:
            if principal.get('disabled') or not math.isfinite(float(principal['expires_at'])) or float(principal['expires_at'])<=time.time():raise ValueError()
        except (ValueError,TypeError,KeyError):return await reject(401,'Credential expired/disabled')
        scope.setdefault('state',{})['principal']=principal
        role=principal['role'];method=scope.get('method','GET')
        if path.startswith('/api/admin'):return await reject(403,'Demo provisioning disabled in production')
        if scope['type']=='websocket' or path.startswith('/socket.io'):
            if role!='operator':return await reject(403,'Operator-only live stream')
        elif method in ('GET','HEAD'):
            if role not in ('operator','auditor'):return await reject(403,'Read scope requires operator/auditor')
        elif role=='operator':pass
        elif role=='buyer' and path.startswith('/api/auctions/') and path.endswith('/bid'):pass
        elif role=='device' and path=='/api/telemetry':pass
        else:return await reject(403,'Role cannot perform action')
        # Bind buyer/device identity, and cap request bodies before JSON parsing.
        if scope['type']=='http' and method not in ('GET','HEAD'):
            body=b''
            while True:
                message=await receive()
                if message['type']=='http.disconnect':return
                body+=message.get('body',b'')
                if len(body)>1_000_000:return await reject(413,'Payload too large')
                if not message.get('more_body',False):break
            if role in ('buyer','device'):
                try:data=json.loads(body)
                except Exception:return await reject(400,'JSON required')
                key='buyer_id' if role=='buyer' else 'truck_id'
                if not isinstance(data,dict) or not principal.get(key) or data.get(key)!=principal[key]:
                    return await reject(403,'Identity does not match credential')
            delivered=False
            async def replay():
                nonlocal delivered
                if not delivered:delivered=True;return {'type':'http.request','body':body,'more_body':False}
                return await receive()
            return await self.app(scope,replay,send)
        return await self.app(scope,receive,send)
