"""Operator-reported delivery and sandbox intent APIs; no physical proof or live rails."""
import hashlib,hmac,json,math,datetime as dt
from fastapi import APIRouter,Depends,Header,HTTPException,Request
from pydantic import BaseModel,Field
from sqlalchemy.orm import Session
from ..core.database import (SessionLocal,DeliveryConfirmation,CargoBatch,FlashAuction,
    AuctionBid,RegisteredBuyer,CargoEvent,ExternalIntent,ProviderEvent,TelemetryBaseline,TelemetryCheckpoint,TelemetrySample)
from ..core.config import settings
from ..services.auction_lifecycle import lock_writer
from ..services.external_rails import DryRunProvider,RailRequest
router=APIRouter(prefix='/api')
def get_db():
    with SessionLocal() as db:yield db

def operator(token:str):
    if not settings.OPERATOR_TOKEN or not hmac.compare_digest(token,settings.OPERATOR_TOKEN):
        raise HTTPException(403,'Operator token required')

class BaselineIn(BaseModel):
    reference_timestamp:int=Field(gt=0)
    initial_life_consumed:float=Field(ge=0,le=1.5,allow_inf_nan=False)
    hours_out_of_range:float=Field(ge=0,allow_inf_nan=False)
    reference:str=Field(min_length=8,max_length=120)
    asserted_by:str=Field(min_length=2,max_length=80)
    evidence_note:str=Field(min_length=20,max_length=2000)

@router.post('/telemetry/baselines/{batch_id}')
def record_baseline(batch_id:str,payload:BaselineIn,token:str=Header('',alias='X-Operator-Token'),db:Session=Depends(get_db)):
    operator(token);lock_writer(db)
    batch=db.get(CargoBatch,batch_id)
    if not batch:raise HTTPException(404,'Lot missing')
    if batch.status!='InTransit':raise HTTPException(409,'Baseline must precede active exposure/intervention')
    if db.get(TelemetryCheckpoint,batch_id) or db.get(TelemetryBaseline,batch_id) or db.query(TelemetrySample).filter_by(batch_id=batch_id).first():
        raise HTTPException(409,'Cannot reset existing model history; reviewed migration required')
    if db.query(TelemetryBaseline).filter_by(reference=payload.reference).first():raise HTTPException(409,'Baseline reference reused')
    if payload.reference_timestamp>dt.datetime.now(dt.timezone.utc).timestamp():raise HTTPException(422,'Future baseline')
    db.add(TelemetryBaseline(batch_id=batch_id,**payload.model_dump(exclude={'initial_life_consumed','hours_out_of_range'})))
    db.add(TelemetryCheckpoint(batch_id=batch_id,life_consumed=payload.initial_life_consumed,hours_out_of_range=payload.hours_out_of_range,max_temp_c=0,max_ethylene_ppm=0))
    db.commit();return {'status':'operator_baseline_recorded','independently_verified':False}

class DeliveryIn(BaseModel):
    received_kg:float=Field(gt=0,allow_inf_nan=False)
    external_reference:str=Field(min_length=8,max_length=120)
    evidence_note:str=Field(min_length=20,max_length=2000)
    operator_name:str=Field(min_length=2,max_length=80)

@router.post('/deliveries/{batch_id}/report')
def report_delivery(batch_id:str,payload:DeliveryIn,token:str=Header('',alias='X-Operator-Token'),db:Session=Depends(get_db)):
    operator(token);lock_writer(db)
    old=db.get(DeliveryConfirmation,batch_id)
    if old:
        if (old.external_reference,old.received_kg,old.evidence_note)!=(payload.external_reference,payload.received_kg,payload.evidence_note):
            raise HTTPException(409,'Conflicting delivery assertion')
        return {'status':'already_reported','independently_verified':False}
    if db.query(DeliveryConfirmation).filter_by(external_reference=payload.external_reference).first():
        raise HTTPException(409,'Reference belongs to another lot')
    batch=db.get(CargoBatch,batch_id)
    if not batch or batch.status!='Cleared':raise HTTPException(409,'Requires a settled demo award')
    auction=db.query(FlashAuction).filter_by(batch_id=batch_id,status='Settled').one_or_none()
    bid=db.get(AuctionBid,auction.winning_bid_id) if auction else None
    if not bid or abs(payload.received_kg-bid.kg_requested)>.001:
        raise HTTPException(422,'Full-lot receipt required; discrepancy needs manual dispute review')
    buyer=db.get(RegisteredBuyer,bid.buyer_id)
    buyer.capacity_kg+=bid.kg_requested
    db.add(DeliveryConfirmation(batch_id=batch_id,buyer_id=buyer.id,**payload.model_dump(exclude={'operator_name'}),recorded_by=payload.operator_name))
    batch.status='RescueDeliveryReported'
    db.add(CargoEvent(batch_id=batch_id,kind='delivery_reported',severity='ok',description='Operator-reported receipt; capacity released once. Not independent physical verification.'))
    db.commit()
    return {'status':'reported','capacity_released_kg':bid.kg_requested,'independently_verified':False}

class IntentIn(BaseModel):
    idempotency_key:str=Field(min_length=8,max_length=120)
    batch_id:str
    kind:str=Field(pattern='^(escrow_reserve|insurance_claim)$')
    amount_paise:int=Field(gt=0,le=100000000)
    mode:str=Field(pattern='^sandbox$')

@router.post('/integrations/intents')
def record_intent(payload:IntentIn,token:str=Header('',alias='X-Operator-Token'),db:Session=Depends(get_db)):
    operator(token);lock_writer(db)
    if not db.get(CargoBatch,payload.batch_id):raise HTTPException(404,'Lot missing')
    old=db.get(ExternalIntent,payload.idempotency_key)
    if old and (old.batch_id,old.kind,old.amount_paise)!=(payload.batch_id,payload.kind,payload.amount_paise):
        raise HTTPException(409,'Idempotency conflict')
    if not old:db.add(ExternalIntent(**payload.model_dump(),status='dry_run_only'))
    result=DryRunProvider().reserve(RailRequest(payload.idempotency_key,payload.kind,payload.amount_paise))
    if old:result["status"]=old.status
    db.commit();return result

@router.post('/integrations/sandbox/webhook')
async def sandbox_webhook(request:Request,signature:str=Header('',alias='X-Sandbox-Signature'),db:Session=Depends(get_db)):
    body=b''
    async for chunk in request.stream():
        body+=chunk
        if len(body)>10000:raise HTTPException(413,'Callback too large')
    secret=settings.SANDBOX_WEBHOOK_SECRET
    expected=hmac.new(secret.encode(),body,hashlib.sha256).hexdigest()
    if not secret or not hmac.compare_digest(signature,expected):raise HTTPException(403,'Invalid callback signature')
    try:
        event=json.loads(body)
        event_id=event['event_id'];key=event['idempotency_key'];amount=event['amount_paise'];timestamp=event['timestamp']
        if not isinstance(event_id,str) or not 8<=len(event_id)<=120 or not math.isfinite(float(timestamp)) or abs(dt.datetime.now(dt.timezone.utc).timestamp()-float(timestamp))>300:raise ValueError()
    except Exception:raise HTTPException(422,'Invalid/stale sandbox event')
    lock_writer(db);digest=hashlib.sha256(body).hexdigest();old=db.get(ProviderEvent,event_id)
    if old:
        if old.payload_sha256!=digest:raise HTTPException(409,'Conflicting event replay')
        return {'status':'duplicate','actual_money_moved':False}
    intent=db.get(ExternalIntent,key)
    if not intent or intent.mode!='sandbox' or intent.amount_paise!=amount or event.get('currency')!='INR':
        raise HTTPException(409,'Intent/amount/currency mismatch')
    if event.get('status')!='sandbox_confirmed':raise HTTPException(422,'Only sandbox confirmation supported')
    intent.status='sandbox_confirmed'
    db.add(ProviderEvent(event_id=event_id,payload_sha256=digest,idempotency_key=key));db.commit()
    return {'status':'sandbox_confirmed','actual_money_moved':False,'independently_verified':False}
